import asyncio
import json
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

        try:
            # ── astream_events replaces threading + queue entirely ────────────
            # version="v2" is required for LangGraph node-level events.
            # LangGraph emits "on_chat_model_stream" per token from every LLM
            # call inside every node — no manual token_queue needed in state.
            async for event in agent_graph.astream_events(initial_state, version="v2"):
                kind = event["event"]

                # Real-time token stream from any LLM call in any node
                if kind == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        chunk = json.dumps({"type": "thinking_content", "data": token}) + "\n"
                        log.info(f"[STREAM] Token: {chunk[:LOG_CHUNK_PREVIEW].strip()}")
                        yield chunk

                # Node finished — capture its state output
                elif kind == "on_chain_end":
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if not node_name:
                        continue

                    node_state = event["data"].get("output", {})
                    if not isinstance(node_state, dict):
                        continue

                    # Collect non-thinking stream_chunks for ordered flush
                    for chunk in node_state.get("stream_chunks", []):
                        try:
                            chunk_type = json.loads(chunk).get("type", "")
                        except Exception:
                            chunk_type = ""
                        if chunk_type != "thinking_content":
                            node_chunks.setdefault(node_name, []).append(chunk)

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

                # Tool calls — useful for debugging / future UI indicators
                elif kind == "on_tool_start":
                    log.info(f"[TOOL] Starting: {event.get('name')} | input: {event['data'].get('input')}")
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
