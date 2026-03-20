from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.project_manager_agent.project_manager_agent import project_manager_agent
from agents.researcher_agent.researcher_agent import researcher_agent
from agents.display_agent.display_agent import display_agent
from agents.response_agent.response_agent import response_agent


def after_validator(state: AgentState) -> str:
    if state.get("evaluation") == "fail" and state.get("retry_count", 0) < 2:
        return "retry"
    return END


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("project_manager", project_manager_agent)
    builder.add_node("researcher_agent", researcher_agent)
    builder.add_node("response_agent", response_agent)
    builder.add_node("display_agent", display_agent)

    builder.set_entry_point("project_manager")

    builder.add_edge("project_manager", "researcher")
    builder.add_edge("researcher_agent", "response_agent")
    builder.add_edge("response_agent", "display_agent")
    builder.add_edge("display_agent", END)

    return builder.compile()


agent_graph = build_graph()
