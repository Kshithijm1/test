from typing import Annotated, TypedDict, Any
from langgraph.graph.message import add_messages


def merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])


class AgentState(TypedDict):
    messages:            Annotated[list, add_messages]
    user_query:          str
    SQLQuery:            str
    SQLData:             str
    df50:                str
    GraphType:           str
    VisualizationJSON:   str
    Context:             str
    UserRole:            str
    WorkflowGoals:       str
    Schema:              str
    Reasoning:           str
    pm_plan:             str
    stream_chunks:       Annotated[list, merge_lists]
    display_results:     Annotated[list, merge_lists]
    data_fetched:        bool
    evaluation:          str
    evaluation_critique: str
    retry_count:         int
    token_queue:         Any
    start_time:          float
    mode:                str
