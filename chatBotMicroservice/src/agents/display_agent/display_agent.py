import json
import time
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from core.state import AgentState
from utils.helpers import log
from .prompt import CHART_CONFIG_SYSTEM_PROMPT, build_display_context


def display_agent(state: AgentState) -> AgentState:
    """
    PlotlyAgent (Display Agent) — Generates chart configuration JSON.

    Reads from state:
        user_query, UserRole, WorkflowGoals, Context (B), SQLQuery, df50

    Writes to state:
        GraphType, VisualizationJSON, display_results
    """
    # Small delay to let frontend render the 'started' event before we begin work
    time.sleep(0.6)
    log.info("━━━ [DISPLAY AGENT] Generating chart configuration")
    t0 = time.time()

    # Read all context from state
    user_query = state.get("user_query", "")
    user_role = state.get("UserRole", "")
    workflow_goals = state.get("WorkflowGoals", "")
    context_b = state.get("Context", "") or state.get("pm_plan", "")
    sql_query = state.get("SQLQuery", "")
    df50_json = state.get("df50", "")

    # Fallback: use full SQLData if df50 not populated
    if not df50_json:
        df50_json = state.get("SQLData", "")

    if not df50_json:
        log.warning("[DISPLAY] No data available (df50 and SQLData both empty)")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    # Fallback user_query to messages
    if not user_query:
        user_query = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")

    if not user_query:
        log.warning("[DISPLAY] No user query found")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    try:
        samples = json.loads(df50_json) if isinstance(df50_json, str) else df50_json
        if not isinstance(samples, list):
            samples = []
    except json.JSONDecodeError:
        log.error("[DISPLAY] Failed to parse df50")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    log.info(f"[DISPLAY] Processing {len(samples)} rows from df50")
    log.debug(f"[DISPLAY] User query: {user_query[:100]}...")
    log.info(f"[DISPLAY] Context (B) available: {bool(context_b)}")

    # Build runtime context from state values
    runtime_context = build_display_context(
        user_query=user_query,
        user_role=user_role,
        workflow_goals=workflow_goals,
        context_b=context_b,
        sql_query=sql_query,
    )

    try:
        model = ChatVertexAI(
            model_name="gemini-2.0-flash",
            project="cbldt-b016-int-2e05",
            location="us-central1",
            temperature=0.0,
            max_output_tokens=2048,
        )

        # Build system prompt with injected runtime context
        system_prompt_with_context = CHART_CONFIG_SYSTEM_PROMPT.replace(
            "Context:", f"Context:\n{runtime_context}\n"
        )

        # User message with query and df50 samples
        user_message = {
            "user_question": user_query,
            "samples": samples,
        }

        response = model.invoke(
            [
                {"role": "system", "content": system_prompt_with_context},
                {"role": "user", "content": json.dumps(user_message)}
            ],
            response_format={"type": "json_object"}
        )

        # Parse the JSON response (your exact logic: json.loads(response.text))
        log.debug(f"[DISPLAY] Raw response type: {type(response)}")
        log.debug(f"[DISPLAY] Raw response content: {response.content[:500]}")
        
        # Strip markdown code blocks if present
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```
        content = content.strip()
        
        chart_config = json.loads(content)

        if "error" in chart_config:
            log.error(f"[DISPLAY] Chart config error: {chart_config['error']}")
            return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

        if "usecase" not in chart_config:
            log.error("[DISPLAY] Invalid chart config: missing 'usecase' field")
            return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

        # Determine graph type based on use case
        graph_type_map = {
            "1": "LineGraph",
            "2": "ScatterPlot",
            "3": "LineGraph"
        }
        graph_type = graph_type_map.get(chart_config.get("usecase", "1"), "LineGraph")
        visualization_json = json.dumps(chart_config)

        log.info(f"[DISPLAY] ✓ Generated {graph_type} (use case {chart_config.get('usecase')}) in {time.time() - t0:.2f}s")
        log.debug(f"[DISPLAY] Config: {visualization_json}")

        # Send only chart config to frontend (no data)
        display_payload = {
            "type": "chart",
            "graphType": graph_type,
            "config": chart_config
        }

        return {
            "messages": [],
            "display_results": [display_payload],
            "stream_chunks": [],
            "GraphType": graph_type,
            "VisualizationJSON": visualization_json,
        }

    except Exception as e:
        log.error(f"[DISPLAY] Failed to generate chart config: {e}", exc_info=True)
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}
