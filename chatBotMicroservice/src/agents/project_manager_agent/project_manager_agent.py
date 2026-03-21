"""
Analysis Agent (Project Manager Agent)
Translates natural language investment questions into structured analytical briefs.
Follows R+T+C+R+SC+O prompt anatomy: Role, Task, Context, Reasoning, StoppingCriteria, Output
"""
import time
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import AgentState
from core.models import llm_medium
from utils.helpers import log, _truncate, llm_call
from .prompt import build_project_manager_system_prompt, build_project_manager_user_message


def project_manager_agent(state: AgentState) -> AgentState:
    """
    Analysis Agent - Converts user query into structured execution plan.
    
    Input:  User's natural language query (Q)
    Output: Structured context string (B) containing:
            - STEPS: High-level execution plan
            - DATA_NEEDED: Required dataItemValues
            - OUTPUT_FORMAT: text | chart | both
            - CHART_TYPE: ScatterPlot | LineGraph | BarGraph | none
    """
    log.info("━━━ [ANALYSIS AGENT] Translating query into structured plan")
    t0 = time.time()

    # Extract user query (Element A)
    user_msg = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
    log.info(f"[ANALYSIS] User Query (A): {_truncate(user_msg, 100)}")

    # Build Analysis Agent prompt (X = A + AA + F)
    # Split into system (R+T+R+SC+O) and user (Context with query) for Gemini API compatibility
    system_prompt = build_project_manager_system_prompt()
    user_message = build_project_manager_user_message(user_msg)
    
    log.debug(f"[ANALYSIS] System prompt length: {len(system_prompt)} chars")
    log.debug(f"[ANALYSIS] User message length: {len(user_message)} chars")

    # Invoke LLM to generate structured plan (Context output B)
    # Gemini requires: SystemMessage + HumanMessage (not just SystemMessage alone)
    plan = llm_call(
        state,
        llm_medium.invoke,
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ],
        status_before="🗂️ Analyzing query and building execution plan…",
        status_after="✅ Analytical brief ready",
        label="ANALYSIS",
    ).strip()

    # Fallback if LLM returns empty
    if not plan:
        log.warning("[ANALYSIS] LLM returned empty — applying fallback plan")
        plan = "STEPS: 1. Answer the question directly.\nDATA_NEEDED: none\nOUTPUT_FORMAT: text\nCHART_TYPE: none"

    log.info(f"[ANALYSIS] Context Output (B): {_truncate(plan, 200)}")
    log.info(f"[ANALYSIS] ✓ Done in {time.time() - t0:.2f}s")

    # Return structured plan to state (consumed by BQAgent and PlotlyAgent)
    return {
        "messages": [],
        "pm_plan": plan,
        "stream_chunks": [],
        "display_results": [],
    }
