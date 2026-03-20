import json
import time
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from core.state import AgentState
from utils.helpers import log, _sla_exceeded
from .prompt import CHART_CONFIG_SYSTEM_PROMPT


def display_agent(state: AgentState) -> AgentState:
    """
    Display agent using your exact Plotly agent logic with LangChain.
    Converts Google SDK model.generate_content() to LangChain ChatVertexAI.
    """
    log.info("━━━ [DISPLAY AGENT] Generating chart configuration")
    t0 = time.time()

    if _sla_exceeded(state):
        log.warning("[DISPLAY] Skipping — SLA exceeded")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    sql_data = state.get("SQLData", "")
    if not sql_data:
        log.warning("[DISPLAY] No SQLData available")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    user_msg = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
    if not user_msg:
        log.warning("[DISPLAY] No user message found")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    try:
        parsed_data = json.loads(sql_data)
        if isinstance(parsed_data, list):
            samples = parsed_data[:50]  # Use first 50 rows for inference
        else:
            samples = []
    except json.JSONDecodeError:
        log.error("[DISPLAY] Failed to parse SQLData")
        return {"messages": [], "display_results": [], "stream_chunks": [], "GraphType": "", "VisualizationJSON": ""}

    log.info(f"[DISPLAY] Processing {len(samples)} sample rows from SQLData")
    log.debug(f"[DISPLAY] User question: {user_msg[:100]}...")

    try:
        # Your exact Plotly agent logic: LangChain version of model.generate_content()
        model = ChatVertexAI(
            model_name="gemini-2.0-flash",
            project="cbldt-b016-int-2e05",
            location="us-central1",
            temperature=0.0,
            max_output_tokens=2048,
        )

        # Your exact user_message structure
        user_message = {
            "user_question": user_msg,
            "samples": samples,
        }

        # LangChain equivalent of your generate_content call with response_mime_type="application/json"
        response = model.invoke(
            [
                {"role": "system", "content": CHART_CONFIG_SYSTEM_PROMPT},
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
