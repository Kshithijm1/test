import asyncio
import json
import re
import time
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from langchain_core.messages import SystemMessage, HumanMessage
from core.graph import agent_graph
from core.state import AgentState
from utils.helpers import LOG_CHUNK_PREVIEW, emit

log = logging.getLogger("agent")
router = APIRouter()

# Agent display names and descriptions for frontend status updates
AGENT_META = {
    "project_manager": {
        "label": "Analysis Agent",
        "start": "Analyzing your query and building execution plan...",
    },
    "researcher_agent": {
        "label": "Research Agent",
        "start": "Generating SQL and fetching data from BigQuery...",
    },
    "response_agent": {
        "label": "Response Agent",
        "start": "Generating your answer...",
    },
    "display_agent": {
        "label": "Display Agent",
        "start": "Building visualization config...",
    },
}

SYSTEM_PROMPT = (
    "You are a helpful data analyst assistant. "
    "You have access to tools and should use them when appropriate. "
    "Be concise and precise in your responses."
)

USER_ROLE = (
    "The primary users of this system are investment professionals at Scotiabank Asset Management. "
    "They are financially sophisticated but not technical users — they do not write SQL or code. "
    "They expect outputs to be precise, visually clean, and immediately presentable to stakeholders. "
    "Default to financial industry conventions in naming, formatting, and time period references. "
    "Avoid technical jargon about the data infrastructure. If the query is ambiguous, apply standard "
    "financial defaults rather than asking the user for clarification."
)

WORKFLOW_GOALS = (
    "This system enables investment professionals to query financial market data using natural language "
    "and receive instant, accurate visualizations — without requiring SQL or coding knowledge. "
    "The goal of every agent in this workflow is to preserve the user's analytical intent at every "
    "transformation step, apply conservative financial defaults when information is missing, and produce "
    "outputs that are immediately usable in investment decision-making contexts. Accuracy and precision "
    "are prioritized over speed. Never hallucinate data, never extrapolate beyond what the data supports, "
    "and never produce a visualization that could mislead a financial professional."
)

MAX_PROMPT_LENGTH = 2000


class ChatRequest(BaseModel):
    prompt: str

    # ── Validation moved into the model — FastAPI returns 422 automatically ──
    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Prompt is required.")
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt too long. Maximum is {MAX_PROMPT_LENGTH} characters.")
        return v


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat")
async def chat(req: ChatRequest):
    async def generate() -> AsyncGenerator[str, None]:
        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=req.prompt),
            ],
            "user_query": req.prompt,
            "UserRole": USER_ROLE,
            "WorkflowGoals": WORKFLOW_GOALS,
            "stream_chunks": [],
            "display_results": [],
            "data_fetched": False,
            "SQLQuery": "",
            "SQLData": "",
            "df50": "",
            "Context": "",
            "pm_plan": "",
            "GraphType": "",
            "VisualizationJSON": "",
            "Schema": "",
            "Reasoning": "",
            "evaluation": "",
            "evaluation_critique": "",
            "retry_count": 0,
            "start_time": time.time(),
        }

        node_chunks: dict[str, list[str]] = {}
        completed_nodes: set[str] = set()

        # Keys that identify the *real* node-level output (vs internal chain outputs)
        NODE_OUTPUT_KEYS = {
            "project_manager": "pm_plan",
            "researcher_agent": "SQLQuery",
            "response_agent": "stream_chunks",
            "display_agent": "display_results",
        }

        # Ordered agent execution sequence (matches graph edges)
        AGENT_ORDER = ["project_manager", "researcher_agent", "response_agent", "display_agent"]

        def _emit_started(node_name: str) -> str:
            """Build a 'started' status event for the given node."""
            meta = AGENT_META[node_name]
            log.info(f"[STREAM] Agent started: {meta['label']}")
            return emit("agent_status", {
                "agent": meta["label"],
                "status": "started",
                "message": meta["start"],
            })

        # ── Immediately emit "started" for the first agent ────────────────
        yield _emit_started(AGENT_ORDER[0])
        await asyncio.sleep(0.3)

        try:
            async for event in agent_graph.astream_events(initial_state, version="v2"):
                kind = event["event"]

                # ── Agent END: emit completion status with summary ────────────
                if kind == "on_chain_end":
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if not node_name:
                        continue

                    node_state = event["data"].get("output", {})
                    if not isinstance(node_state, dict):
                        continue

                    # Only process the real node-level completion (has expected output key)
                    expected_key = NODE_OUTPUT_KEYS.get(node_name)
                    if expected_key and expected_key not in node_state:
                        continue  # internal chain end — skip
                    if node_name in completed_nodes:
                        continue  # already emitted for this node
                    if node_name not in AGENT_META:
                        continue
                    completed_nodes.add(node_name)

                    # Build and emit completion event
                    meta = AGENT_META[node_name]
                    summary = _build_agent_summary(node_name, node_state)
                    detail = _build_agent_detail(node_name, node_state)
                    payload: dict = {
                        "agent": meta["label"],
                        "status": "completed",
                        "message": summary,
                    }
                    if detail:
                        payload["detail"] = detail
                    status_chunk = emit("agent_status", payload)
                    log.info(f"[STREAM] Agent completed: {meta['label']} — {summary}")
                    yield status_chunk
                    await asyncio.sleep(0.3)

                    # ── Proactively emit "started" for the NEXT agent ─────────
                    try:
                        cur_idx = AGENT_ORDER.index(node_name)
                        if cur_idx + 1 < len(AGENT_ORDER):
                            next_node = AGENT_ORDER[cur_idx + 1]
                            yield _emit_started(next_node)
                            await asyncio.sleep(0.3)
                    except ValueError:
                        pass

                    # Collect non-thinking, non-sql_data stream_chunks for ordered flush
                    for chunk in node_state.get("stream_chunks", []):
                        try:
                            chunk_type = json.loads(chunk).get("type", "")
                        except Exception:
                            chunk_type = ""
                        if chunk_type not in ("thinking_content", "sql_data"):
                            node_chunks.setdefault(node_name, []).append(chunk)

                    # Emit sql_data immediately when researcher finishes
                    if node_name == "researcher_agent":
                        sql_query = node_state.get("SQLQuery", "")
                        sql_data = node_state.get("SQLData", "")
                        if sql_query or sql_data:
                            try:
                                data_rows = json.loads(sql_data) if sql_data else []
                            except Exception:
                                data_rows = []
                            sql_chunk = emit("sql_data", {"query": sql_query, "data": data_rows})
                            yield sql_chunk
                            log.info(f"[STREAM] sql_data emitted: {len(data_rows)} rows")

                    # Emit display modules when display_agent finishes
                    if node_name == "display_agent":
                        display_results = node_state.get("display_results", [])
                        if display_results:
                            flat: list = []
                            for r in display_results:
                                flat.extend(r) if isinstance(r, list) else flat.append(r)
                            display_chunk = emit("display_modules", flat)
                            node_chunks.setdefault("display_agent_emit", []).append(display_chunk)
                            log.info(f"[STREAM] display_modules emitted with {len(flat)} item(s)")

                # Tool calls — debug logging
                elif kind == "on_tool_start":
                    log.info(f"[TOOL] Starting: {event.get('name')}")
                elif kind == "on_tool_end":
                    log.info(f"[TOOL] Finished: {event.get('name')}")

        except Exception as e:
            log.error(f"[GRAPH] Error during graph execution: {e}", exc_info=True)
            yield json.dumps(
                {
                    "type": "response_content",
                    "data": "Something went wrong. Please try again.",
                }
            ) + "\n"
            return

        # ── Flush final chunks in type order ─────────────────────────────────
        TYPE_ORDER = {"response_content": 0, "display_modules": 1}
        all_final = [c for chunks in node_chunks.values() for c in chunks]
        all_final.sort(key=lambda c: TYPE_ORDER.get(json.loads(c).get("type", "") if c.strip() else "", 99))
        for chunk in all_final:
            log.info(f"[CONTROLLER] Flushing: {chunk[:LOG_CHUNK_PREVIEW].strip()}")
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


def _build_agent_summary(node_name: str, node_state: dict) -> str:
    """Extract a short human-readable summary from an agent's output state."""
    if node_name == "project_manager":
        plan = node_state.get("pm_plan", "")
        parts = []
        for label in ("USE_CASE", "CHART_TYPE", "OUTPUT_FORMAT"):
            m = re.search(rf"{label}\s*:\s*(.+)", plan)
            if m:
                parts.append(f"{label}: {m.group(1).strip()}")
        return " | ".join(parts) if parts else "Execution plan ready"

    if node_name == "researcher_agent":
        sql_data = node_state.get("SQLData", "")
        try:
            rows = json.loads(sql_data) if sql_data else []
            count = len(rows) if isinstance(rows, list) else 0
        except Exception:
            count = 0
        fetched = node_state.get("data_fetched", False)
        if fetched and count > 0:
            return f"Retrieved {count} rows from BigQuery"
        return "No data returned from BigQuery"

    if node_name == "response_agent":
        return "Response generated"

    if node_name == "display_agent":
        graph_type = node_state.get("GraphType", "")
        return f"Chart configured: {graph_type}" if graph_type else "Visualization ready"

    return "Done"


def _build_agent_detail(node_name: str, node_state: dict) -> dict | None:
    """Build optional rich detail payload for an agent's completion event."""
    if node_name == "project_manager":
        plan = node_state.get("pm_plan", "")
        if plan:
            return {"plan_summary": plan.strip()}
        return None

    if node_name == "researcher_agent":
        detail: dict = {}
        sql_query = node_state.get("SQLQuery", "")
        if sql_query:
            detail["sql"] = sql_query
        sql_data = node_state.get("SQLData", "")
        if sql_data:
            try:
                rows = json.loads(sql_data)
                if isinstance(rows, list) and len(rows) > 0:
                    detail["preview"] = rows[:5]
                    detail["columns"] = list(rows[0].keys())
                    detail["total_rows"] = len(rows)
            except Exception:
                pass
        return detail if detail else None

    if node_name == "display_agent":
        viz_json = node_state.get("VisualizationJSON", "")
        if viz_json:
            try:
                return {"config": json.loads(viz_json)}
            except Exception:
                return {"config_raw": viz_json}
        return None

    return None
