import json
import time
from langchain_core.messages import HumanMessage
from core.state import AgentState
from utils.tools import TOOL_MAP
from utils.helpers import log


def researcher_agent(state: AgentState) -> AgentState:
    """
    Researcher agent for BigQuery workflow using state parameters.
    
    Flow:
    1. Generate SQL from user question using generate_sql tool
    2. Execute SQL using execute_bigquery tool
    3. Store SQL in state.SQLQuery and results in state.SQLData
    """
    log.info("━━━ [RESEARCHER] BigQuery SQL generation and execution")
    t0 = time.time()

    user_msg = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
    if not user_msg:
        log.warning("[RESEARCHER] No user message found")
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": ""}

    log.info(f"[RESEARCHER] User question: {user_msg[:100]}...")

    try:
        generate_sql_tool = TOOL_MAP.get("generate_sql")
        execute_bigquery_tool = TOOL_MAP.get("execute_bigquery")
        
        if not generate_sql_tool or not execute_bigquery_tool:
            log.error("[RESEARCHER] BigQuery tools not found in TOOL_MAP")
            return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": ""}

        log.info("[RESEARCHER] Step 1: Generating SQL query...")
        sql_result = generate_sql_tool.invoke({"query": user_msg})
        log.info(f"[RESEARCHER] SQL generated: {sql_result[:200]}...")

        lines = sql_result.strip().split('\n')
        clean_sql = '\n'.join(lines[1:]) if sql_result.startswith("--") else sql_result
        
        log.info("[RESEARCHER] Step 2: Executing BigQuery...")
        execution_result = execute_bigquery_tool.invoke({"sql_query": clean_sql, "limit": 100})
        log.debug(f"[RESEARCHER] Execution result: {execution_result[:300]}...")

        data_rows = []
        try:
            parsed = json.loads(execution_result)
            if isinstance(parsed, list):
                data_rows = parsed
                log.info(f"[RESEARCHER] ✓ Retrieved {len(data_rows)} rows from BigQuery")
            elif isinstance(parsed, dict) and "error" in parsed:
                log.error(f"[RESEARCHER] BigQuery error: {parsed['error']}")
            else:
                log.warning(f"[RESEARCHER] Unexpected result format: {type(parsed)}")
        except json.JSONDecodeError as e:
            log.error(f"[RESEARCHER] Failed to parse BigQuery results: {e}")

        elapsed = time.time() - t0
        log.info(f"[RESEARCHER] ✓ Done in {elapsed:.2f}s | {len(data_rows)} data rows")

        return {
            "messages": [],
            "stream_chunks": [],
            "data_fetched": len(data_rows) > 0,
            "SQLQuery": clean_sql,
            "SQLData": execution_result,
        }

    except Exception as e:
        log.error(f"[RESEARCHER] Failed: {e}", exc_info=True)
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": ""}
