import time
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import AgentState
from core.models import llm_medium
from utils.helpers import log, _sla_exceeded, _truncate, llm_call
from .prompt import PROJECT_MANAGER_PROMPT


def project_manager_agent(state: AgentState) -> AgentState:
    log.info("━━━ [NODE 1 / PROJECT MANAGER] Planning steps")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[PM] Skipping — SLA exceeded")
        return {"messages": [], "pm_plan": "", "stream_chunks": [], "display_results": []}

    user_msg = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
    log.info(f"[PM] User message: {_truncate(user_msg, 100)}")

    plan = llm_call(
        state,
        llm_medium.invoke,
        [
            SystemMessage(content=PROJECT_MANAGER_PROMPT),
            HumanMessage(content=user_msg),
        ],
        status_before="🗂️ Planning your request…",
        status_after="✅ Plan ready",
        label="PM",
    ).strip()

    if not plan:
        log.warning("[PM] llm_call returned empty — using fallback plan")
        plan = "STEPS: 1. Answer the question directly.\n" "DATA_NEEDED: none\nOUTPUT_FORMAT: text\nCHART_TYPE: none"

    log.info(f"[PM] Plan ({len(plan)} chars): {_truncate(plan, 200)}")
    log.info(f"[PM] ✓ Done in {time.time() - t0:.2f}s")

    return {
        "messages": [],
        "pm_plan": plan,
        "stream_chunks": [],
        "display_results": [],
    }
