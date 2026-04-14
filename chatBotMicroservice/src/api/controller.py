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
from langgraph.types import Command
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
    approved_sql: str
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
        AGENT_ORDER = ["project_manager", "researcher_agent", "response_agent", "display_agent"]
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
            log.info(f"[STREAM] Checking for interrupts...")
            log.info(f"[STREAM] State next: {state_snapshot.next}")
            
            # Check if there are pending tasks (indicates interrupt)
            if state_snapshot.next and len(state_snapshot.next) > 0:
                # Graph stopped mid-execution - check for interrupt
                if hasattr(state_snapshot, 'tasks') and state_snapshot.tasks:
                    log.info(f"[STREAM] Found {len(state_snapshot.tasks)} pending tasks")
                    for task in state_snapshot.tasks:
                        log.info(f"[STREAM] Task: {task}")
                        if hasattr(task, 'interrupts') and task.interrupts:
                            log.info(f"[STREAM] Task has {len(task.interrupts)} interrupts")
                            for intr in task.interrupts:
                                log.info(f"[STREAM] Interrupt value: {intr.value if hasattr(intr, 'value') else intr}")
                                sql = intr.value.get("sql", "") if hasattr(intr, 'value') else ""
                                if sql:
                                    log.info(f"[STREAM] ✓ HITL interrupt detected, emitting event")
                                    yield emit("hitl", {"thread_id": thread_id, "sql": sql})
                                    return  # stream ends here
                else:
                    log.info(f"[STREAM] No tasks attribute on state snapshot")
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


@router.post("/chat/resume")
async def chat_resume(req: ResumeRequest):
    """Resume a HITL-paused graph after human SQL review."""
    config = {"configurable": {"thread_id": req.thread_id}}

    async def generate() -> AsyncGenerator[str, None]:
        # Researcher was already shown as "started" before the interrupt.
        # After resume: researcher finishes → response_agent → display_agent.
        # next_agent_idx = 2 means response_agent is the next "started" to emit.
        AGENT_ORDER = ["project_manager", "researcher_agent", "response_agent", "display_agent"]
        next_agent_idx = 2
        node_chunks: dict[str, list[str]] = {}

        try:
            async for chunk in manual_graph.astream(
                Command(resume={"approved_sql": req.approved_sql, "was_edited": req.was_edited}),
                config=config,
            ):
                if "__interrupt__" in chunk:
                    continue  # should not happen after first resume

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

                    if node_name == "researcher_agent":
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
