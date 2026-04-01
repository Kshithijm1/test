import json
import time
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import AgentState
from core.models import llm_respond
from utils.helpers import (
    log,
    _truncate,
    llm_call,
    DATA_NEEDED_EXTRACT,
    RESPOND_TOOL_CONTEXT_WINDOW,
    RESPOND_PM_PLAN_WINDOW,
    _extract_tool_context,
    emit,
)
from .prompt import RESPONSE_AGENT_BASE_PROMPT

def response_agent(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 4 / RESPONSE AGENT] Generating final answer")
    t0 = time.time()

    # Read all state context
    user_query = state.get("user_query", "")
    user_role = state.get("UserRole", "")
    workflow_goals = state.get("WorkflowGoals", "")
    pm_plan = state.get("pm_plan", "")
    sql_data = state.get("SQLData", "")
    data_fetched = state.get("data_fetched", True)
    
    # Fallback to messages if user_query not in state
    if not user_query:
        user_query = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
    
    tool_context = _extract_tool_context(state["messages"])

    log.info(
        f"[RESPOND] Inputs — pm_plan: {bool(pm_plan)}, "
        f"tool_context: {len(tool_context)} chars, "
        f"data_fetched: {data_fetched}, "
        f"SQLData length: {len(sql_data)}"
    )

    # ── Short-circuit if data was required but nothing came back ──────────────
    data_needed_match = DATA_NEEDED_EXTRACT.search(pm_plan)
    data_needed = data_needed_match.group(1).strip() if data_needed_match else ""
    
    # Check if data is actually needed (not "none" or "n/a")
    needs_data = data_needed.lower() not in ("none", "n/a", "") and data_needed.strip() != ""
    
    log.info(f"[RESPOND] DATA_NEEDED regex match: {bool(data_needed_match)}")
    log.info(f"[RESPOND] data_needed extracted: '{data_needed[:100]}...'")
    log.info(f"[RESPOND] needs_data: {needs_data}, data_fetched: {data_fetched}")
    log.info(f"[RESPOND] SQLData length: {len(sql_data)}")
    log.info(f"[RESPOND] pm_plan excerpt: {pm_plan[:400]}...")

    # Short-circuit: regex-based check
    if needs_data and not data_fetched:
        log.warning("[RESPOND] Data was required but not fetched — returning honest failure")
        return {
            "messages": [],
            "stream_chunks": [emit("response_content",
                "I wasn't able to retrieve the data needed to answer this accurately. "
                "This could be due to an API limit or connection issue. Please try again in a moment."
            )],
        }

    # Short-circuit: fallback — SQL ran but returned no rows (catches truncated pm_plan edge case)
    sql_attempted = bool(state.get("SQLQuery", "").strip())
    if sql_attempted and not data_fetched:
        log.warning("[RESPOND] SQL was executed but returned no data — returning honest failure")
        return {
            "messages": [],
            "stream_chunks": [emit("response_content",
                "I wasn't able to retrieve the data for this query. "
                "The database may not have matching records for these filters. Please try a different query."
            )],
        }

    # ── Build system prompt with state context ───────────────────────────────
    is_simple = len(user_query.split()) <= 15

    system_parts = [
        RESPONSE_AGENT_BASE_PROMPT,
        "Do not mention charts or visualizations in your response.",
        (
            "Keep your response short and natural — match the brevity of the user's message."
            if is_simple
            else "Write in natural prose. Be thorough but concise."
        ),
    ]
    
    # Add state context to prompt
    if user_role:
        system_parts.append(f"\nUser Role Context:\n{user_role}")
    
    if workflow_goals:
        system_parts.append(f"\nWorkflow Goals:\n{workflow_goals}")
    
    if tool_context:
        system_parts.append(f"\nResearch context:\n{tool_context[:RESPOND_TOOL_CONTEXT_WINDOW]}")
    
    # Add SQL data to context so LLM can reference actual data
    if sql_data:
        try:
            parsed_data = json.loads(sql_data)
            if isinstance(parsed_data, list) and len(parsed_data) > 0:
                # Provide first few rows as sample
                sample_rows = parsed_data[:3]
                data_context = f"\n\nData Summary:\n- Retrieved {len(parsed_data)} rows of data\n- Sample data (first 3 rows):\n{json.dumps(sample_rows, indent=2)}"
                system_parts.append(data_context)
                log.info(f"[RESPOND] Added {len(parsed_data)} rows of SQL data to context")
        except Exception as e:
            log.warning(f"[RESPOND] Failed to parse SQL data: {e}")

    user_turn = user_query
    if pm_plan:
        user_turn += f"\n\n[Execution plan for context]:\n{pm_plan[:RESPOND_PM_PLAN_WINDOW]}"

    log.info(
        f"[RESPOND] Calling llm_respond — "
        f"{len(chr(10).join(system_parts))} char system, {len(user_turn)} char user turn"
    )

    # ── LLM call via intermediary ─────────────────────────────────────────────
    content = llm_call(
        state,
        llm_respond.invoke,
        [
            SystemMessage(content="\n".join(system_parts)),
            HumanMessage(content=user_turn),
        ],
        status_before="✍️ Generating response…",
        status_after="✅ Response complete",
        label="RESPOND",
    ).strip()

    if not content or content.lower().startswith("no output generated"):
        log.warning(f"[RESPOND] Model returned empty/invalid output: {repr(content)}")
        content = "I wasn't able to generate a response. Please try again."

    stream_chunks = [emit("response_content", content)]
    log.info(f"[RESPOND] ✓ Done in {time.time() - t0:.2f}s | {len(stream_chunks)} chunk(s)")

    return {
        "messages": [],
        "stream_chunks": stream_chunks,
    }
