import asyncio
import json
import os
import re
import time
import uuid
import logging
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from langchain_core.messages import SystemMessage, HumanMessage
from core.graph import agent_graph, manual_graph
from core.state import AgentState
from utils.helpers import LOG_CHUNK_PREVIEW, emit

TRAINING_LOG_PATH = Path(__file__).parent.parent / "data" / "training_log.jsonl"
TRAINING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("agent")
router = APIRouter()

# Agent display names and descriptions for frontend status updates
AGENT_META = {
    "project_manager": {
        "label": "Analysis Agent",
        "start": "Analyzing your query and building execution plan...",
    },
    "researcher_sql_gen": {
        "label": "SQL Generation",
        "start": "Generating SQL query from analysis plan...",
    },
    "researcher_sql_exec": {
        "label": "SQL Execution",
        "start": "Executing SQL against BigQuery...",
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
    mode: str = "auto"  # "auto" or "manual" (HITL)

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


class ResumeRequest(BaseModel):
    thread_id: str
    checkpoint_type: str  # "plan" or "sql"
    approved_value: str   # the approved plan text or SQL query
    was_edited: bool = False


class TrainingLogRequest(BaseModel):
    query: str
    original_sql: str
    corrected_sql: str
    pm_plan: str = ""


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat")
async def chat(req: ChatRequest):
    is_manual = req.mode == "manual"
    graph = manual_graph if is_manual else agent_graph
    thread_id = str(uuid.uuid4()) if is_manual else None
    config = {"configurable": {"thread_id": thread_id}} if thread_id else {}
    
    log.info(f"[CHAT] ========================================")
    log.info(f"[CHAT] Mode: {req.mode}, is_manual: {is_manual}")
    log.info(f"[CHAT] Using graph: {'manual_graph' if is_manual else 'agent_graph'}")
    log.info(f"[CHAT] Thread ID: {thread_id}")
    log.info(f"[CHAT] ========================================")

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
            "mode": req.mode,
        }

        node_chunks: dict[str, list[str]] = {}
        
        # Ordered agent execution sequence (matches graph edges)
        AGENT_ORDER = ["project_manager", "researcher_sql_gen", "researcher_sql_exec", "response_agent", "display_agent"]
        next_agent_idx = 0

        # ── Emit "started" for the FIRST agent before loop ────────────────
        log.info("=" * 80)
        log.info("[STREAM] NEW STREAMING LOGIC ACTIVE - Using astream() with proactive emission")
        log.info("=" * 80)
        
        if next_agent_idx < len(AGENT_ORDER):
            first_agent = AGENT_ORDER[next_agent_idx]
            meta = AGENT_META[first_agent]
            yield emit("agent_status", {
                "agent": meta["label"],
                "status": "started",
                "message": meta["start"],
            })
            log.info(f"[STREAM] ✓ Emitted STARTED for {meta['label']} (before loop)")
            await asyncio.sleep(0.5)
            log.info(f"[STREAM] ✓ Slept 500ms after {meta['label']} started")
            next_agent_idx += 1

        interrupted = False
        try:
            # Use astream() to get state updates as nodes complete
            async for chunk in graph.astream(initial_state, config=config):
                log.info(f"[STREAM] Chunk keys: {list(chunk.keys())}")
                
                # chunk is a dict: {node_name: state_update}
                for node_name, node_state in chunk.items():
                    if node_name not in AGENT_META:
                        continue
                    
                    node_state = chunk[node_name]
                    
                    # ── The node has finished - emit "completed" ──────────────
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
                    completed_chunk = emit("agent_status", payload)
                    log.info(f"[STREAM] Agent completed: {meta['label']} — {summary}")
                    yield completed_chunk
                    await asyncio.sleep(0.5)
                    
                    # ── Emit "started" for the NEXT agent ─────────────────────
                    if next_agent_idx < len(AGENT_ORDER):
                        next_agent = AGENT_ORDER[next_agent_idx]
                        next_meta = AGENT_META[next_agent]
                        yield emit("agent_status", {
                            "agent": next_meta["label"],
                            "status": "started",
                            "message": next_meta["start"],
                        })
                        log.info(f"[STREAM] Agent started: {next_meta['label']}")
                        await asyncio.sleep(0.5)
                        next_agent_idx += 1

                    # Collect non-thinking, non-sql_data stream_chunks for ordered flush
                    for chunk_item in node_state.get("stream_chunks", []):
                        try:
                            chunk_type = json.loads(chunk_item).get("type", "")
                        except Exception:
                            chunk_type = ""
                        if chunk_type not in ("thinking_content", "sql_data"):
                            node_chunks.setdefault(node_name, []).append(chunk_item)

                    # Emit sql_data immediately when researcher_sql_exec finishes
                    if node_name == "researcher_sql_exec":
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

        except Exception as e:
            log.error(f"[GRAPH] Error during graph execution: {e}", exc_info=True)
            yield json.dumps(
                {
                    "type": "response_content",
                    "data": "Something went wrong. Please try again.",
                }
            ) + "\n"
            return

        # ── Check if graph was interrupted (HITL checkpoint) ──────────────────
        if is_manual and thread_id:
            state_snapshot = graph.get_state(config)
            next_nodes = state_snapshot.next  # tuple of next node names
            log.info(f"[STREAM] Checking for interrupt_after pause...")
            log.info(f"[STREAM] State next: {next_nodes}")

            if next_nodes:
                state_values = state_snapshot.values
                next_node = next_nodes[0]
                log.info(f"[STREAM] Graph paused before: {next_node}")

                if next_node == "researcher_sql_gen":
                    # Checkpoint 1: After PM — let user review the plan
                    pm_plan = state_values.get("pm_plan", "") or state_values.get("Context", "")
                    log.info(f"[HITL] Plan checkpoint, plan length={len(pm_plan)}")
                    yield emit("hitl", {
                        "thread_id": thread_id,
                        "checkpoint_type": "plan",
                        "value": pm_plan,
                    })
                    return

                elif next_node == "researcher_sql_exec":
                    # Checkpoint 2: After SQL gen — let user review the SQL
                    sql_query = state_values.get("SQLQuery", "")
                    log.info(f"[HITL] SQL checkpoint, sql length={len(sql_query)}")
                    yield emit("hitl", {
                        "thread_id": thread_id,
                        "checkpoint_type": "sql",
                        "value": sql_query,
                    })
                    return

                else:
                    log.warning(f"[HITL] Unexpected paused node: {next_node}")
            else:
                log.info(f"[STREAM] No pending next nodes - graph completed normally")

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

    if node_name == "researcher_sql_gen":
        sql = node_state.get("SQLQuery", "")
        if sql:
            return f"SQL query generated ({len(sql)} chars)"
        return "SQL generation completed"

    if node_name == "researcher_sql_exec":
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

    if node_name == "researcher_sql_gen":
        sql_query = node_state.get("SQLQuery", "")
        if sql_query:
            return {"sql": sql_query}
        return None

    if node_name == "researcher_sql_exec":
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


@router.post("/chat/resume")
async def chat_resume(req: ResumeRequest):
    """Resume a HITL-paused graph after human review of plan or SQL."""
    config = {"configurable": {"thread_id": req.thread_id}}

    log.info(f"[RESUME] ========================================")
    log.info(f"[RESUME] Thread: {req.thread_id}")
    log.info(f"[RESUME] Checkpoint type: {req.checkpoint_type}")
    log.info(f"[RESUME] Was edited: {req.was_edited}")
    log.info(f"[RESUME] ========================================")

    # If the user edited the value, update the graph state before resuming
    if req.was_edited:
        if req.checkpoint_type == "plan":
            manual_graph.update_state(config, {"pm_plan": req.approved_value, "Context": req.approved_value})
            log.info("[RESUME] Updated pm_plan + Context in graph state")
        elif req.checkpoint_type == "sql":
            manual_graph.update_state(config, {"SQLQuery": req.approved_value})
            log.info("[RESUME] Updated SQLQuery in graph state")

    async def generate() -> AsyncGenerator[str, None]:
        AGENT_ORDER = ["project_manager", "researcher_sql_gen", "researcher_sql_exec", "response_agent", "display_agent"]

        # Determine where we are in the agent sequence based on checkpoint type
        if req.checkpoint_type == "plan":
            # After plan approval: sql_gen is next to run
            next_agent_idx = 1  # researcher_sql_gen
        else:
            # After SQL approval: sql_exec is next to run
            next_agent_idx = 2  # researcher_sql_exec

        # Emit "started" for the next agent about to run
        if next_agent_idx < len(AGENT_ORDER):
            meta = AGENT_META[AGENT_ORDER[next_agent_idx]]
            yield emit("agent_status", {
                "agent": meta["label"],
                "status": "started",
                "message": meta["start"],
            })
            await asyncio.sleep(0.5)
            next_agent_idx += 1

        node_chunks: dict[str, list[str]] = {}

        try:
            async for chunk in manual_graph.astream(None, config=config):
                log.info(f"[RESUME] Chunk keys: {list(chunk.keys())}")

                for node_name, node_state in chunk.items():
                    if node_name not in AGENT_META:
                        continue

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
                    yield emit("agent_status", payload)
                    log.info(f"[RESUME] Agent completed: {meta['label']} — {summary}")
                    await asyncio.sleep(0.5)

                    if next_agent_idx < len(AGENT_ORDER):
                        next_meta = AGENT_META[AGENT_ORDER[next_agent_idx]]
                        yield emit("agent_status", {
                            "agent": next_meta["label"],
                            "status": "started",
                            "message": next_meta["start"],
                        })
                        await asyncio.sleep(0.5)
                        next_agent_idx += 1

                    for chunk_item in node_state.get("stream_chunks", []):
                        try:
                            chunk_type = json.loads(chunk_item).get("type", "")
                        except Exception:
                            chunk_type = ""
                        if chunk_type not in ("thinking_content", "sql_data"):
                            node_chunks.setdefault(node_name, []).append(chunk_item)

                    if node_name == "researcher_sql_exec":
                        sql_query = node_state.get("SQLQuery", "")
                        sql_data = node_state.get("SQLData", "")
                        if sql_query or sql_data:
                            try:
                                data_rows = json.loads(sql_data) if sql_data else []
                            except Exception:
                                data_rows = []
                            yield emit("sql_data", {"query": sql_query, "data": data_rows})
                            log.info(f"[RESUME] sql_data emitted: {len(data_rows)} rows")

                    if node_name == "display_agent":
                        display_results = node_state.get("display_results", [])
                        if display_results:
                            flat: list = []
                            for r in display_results:
                                flat.extend(r) if isinstance(r, list) else flat.append(r)
                            node_chunks.setdefault("display_agent_emit", []).append(
                                emit("display_modules", flat)
                            )

        except Exception as e:
            log.error(f"[RESUME] Error during graph resume: {e}", exc_info=True)
            yield json.dumps({"type": "response_content", "data": "Something went wrong on resume."}) + "\n"
            return

        # ── Check if another interrupt was hit (plan resume → SQL checkpoint) ──
        state_snapshot = manual_graph.get_state(config)
        next_nodes = state_snapshot.next
        log.info(f"[RESUME] Post-stream next nodes: {next_nodes}")

        if next_nodes:
            state_values = state_snapshot.values
            next_node = next_nodes[0]

            if next_node == "researcher_sql_exec":
                sql_query = state_values.get("SQLQuery", "")
                log.info(f"[RESUME-HITL] SQL checkpoint after plan resume, sql length={len(sql_query)}")
                yield emit("hitl", {
                    "thread_id": req.thread_id,
                    "checkpoint_type": "sql",
                    "value": sql_query,
                })
                return
            else:
                log.warning(f"[RESUME-HITL] Unexpected paused node: {next_node}")

        # ── Flush final chunks in type order ─────────────────────────────────
        TYPE_ORDER = {"response_content": 0, "display_modules": 1}
        all_final = [c for chunks in node_chunks.values() for c in chunks]
        all_final.sort(key=lambda c: TYPE_ORDER.get(json.loads(c).get("type", "") if c.strip() else "", 99))
        for chunk in all_final:
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/training/log")
async def training_log(req: TrainingLogRequest):
    """Persist a human SQL correction for future training."""
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query": req.query,
        "pm_plan": req.pm_plan,
        "original_sql": req.original_sql,
        "corrected_sql": req.corrected_sql,
    }
    try:
        with open(TRAINING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        log.info(f"[TRAINING] Logged SQL correction for query: {req.query[:80]}")
    except Exception as e:
        log.error(f"[TRAINING] Failed to write training log: {e}")
        raise HTTPException(status_code=500, detail="Failed to write training log")
    return {"status": "ok", "logged": True}
