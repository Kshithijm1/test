import json
import re
import time
from langchain_core.messages import HumanMessage
from core.state import AgentState
from utils.tools import TOOL_MAP
from utils.helpers import log


def researcher_sql_gen(state: AgentState) -> AgentState:
    """
    Step 1 of Research: Generate SQL query from the user request + PM plan.

    Reads from state:
        user_query, UserRole, WorkflowGoals, Context (pm_plan)

    Writes to state:
        SQLQuery  — the generated (not yet executed) SQL statement
    """
    time.sleep(0.6)
    log.info("━━━ [RESEARCHER-GEN] BigQuery SQL generation")
    t0 = time.time()

    user_query = state.get("user_query", "")
    user_role = state.get("UserRole", "")
    workflow_goals = state.get("WorkflowGoals", "")
    context_b = state.get("Context", "") or state.get("pm_plan", "")

    if not user_query:
        user_query = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")

    if not user_query:
        log.warning("[RESEARCHER-GEN] No user query found in state or messages")
        return {"messages": [], "stream_chunks": [], "SQLQuery": ""}

    log.info(f"[RESEARCHER-GEN] User query: {user_query[:100]}...")
    log.info(f"[RESEARCHER-GEN] Context (B) available: {bool(context_b)}")

    enriched_query_parts = []
    if user_role:
        enriched_query_parts.append(f"User Role: {user_role}")
    if workflow_goals:
        enriched_query_parts.append(f"Workflow Goals: {workflow_goals}")
    enriched_query_parts.append(f"User Query: {user_query}")
    if context_b:
        enriched_query_parts.append(f"""Analysis Agent Output (use this to guide SQL generation):
{context_b}""")
    enriched_query = "\n\n".join(enriched_query_parts)
    log.info("[RESEARCHER-GEN] Enriched query with full state context")

    try:
        generate_sql_tool = TOOL_MAP.get("generate_sql")
        if not generate_sql_tool:
            log.error("[RESEARCHER-GEN] generate_sql tool not found in TOOL_MAP")
            return {"messages": [], "stream_chunks": [], "SQLQuery": ""}

        log.info("[RESEARCHER-GEN] Generating SQL query...")
        sql_result = generate_sql_tool.invoke({"query": enriched_query})
        log.info(f"[RESEARCHER-GEN] SQL generated: {sql_result[:200]}...")

        cte_match = re.search(r'(WITH\s.+)', sql_result, re.DOTALL | re.IGNORECASE)
        select_match = re.search(r'(SELECT\s.+)', sql_result, re.DOTALL | re.IGNORECASE)
        clean_sql = (cte_match or select_match).group(1).strip() if (cte_match or select_match) else sql_result.strip()

        elapsed = time.time() - t0
        log.info(f"[RESEARCHER-GEN] SQL Query:\n{clean_sql}")
        log.info(f"[RESEARCHER-GEN] Done in {elapsed:.2f}s")

        return {
            "messages": [],
            "stream_chunks": [],
            "SQLQuery": clean_sql,
        }

    except Exception as e:
        log.error(f"[RESEARCHER-GEN] Failed: {e}", exc_info=True)
        return {"messages": [], "stream_chunks": [], "SQLQuery": ""}


def researcher_sql_exec(state: AgentState) -> AgentState:
    """
    Step 2 of Research: Execute the SQL query (from state) against BigQuery.

    Reads from state:
        SQLQuery — the SQL to execute (may have been edited by user in HITL mode)

    Writes to state:
        SQLData, df50, data_fetched
    """
    time.sleep(0.3)
    log.info("━━━ [RESEARCHER-EXEC] BigQuery SQL execution")
    t0 = time.time()

    clean_sql = state.get("SQLQuery", "")
    if not clean_sql:
        log.warning("[RESEARCHER-EXEC] No SQL query in state — skipping execution")
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLData": "", "df50": ""}

    log.info(f"[RESEARCHER-EXEC] Executing SQL:\n{clean_sql[:300]}...")

    try:
        execute_bigquery_tool = TOOL_MAP.get("execute_bigquery")
        if not execute_bigquery_tool:
            log.error("[RESEARCHER-EXEC] execute_bigquery tool not found in TOOL_MAP")
            return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLData": "", "df50": ""}

        execution_result = execute_bigquery_tool.invoke({"sql_query": clean_sql, "limit": 100})
        log.debug(f"[RESEARCHER-EXEC] Execution result: {execution_result[:300]}...")

        data_rows = []
        try:
            parsed = json.loads(execution_result)
            if isinstance(parsed, list):
                data_rows = parsed
                log.info(f"[RESEARCHER-EXEC] Retrieved {len(data_rows)} rows from BigQuery")
            elif isinstance(parsed, dict) and "error" in parsed:
                log.error(f"[RESEARCHER-EXEC] BigQuery error: {parsed['error']}")
            else:
                log.warning(f"[RESEARCHER-EXEC] Unexpected result format: {type(parsed)}")
        except json.JSONDecodeError as e:
            log.error(f"[RESEARCHER-EXEC] Failed to parse BigQuery results: {e}")

        elapsed = time.time() - t0
        data_fetched_status = len(data_rows) > 0
        df50_rows = data_rows[:50]
        df50_json = json.dumps(df50_rows)

        log.info(f"[RESEARCHER-EXEC] Done in {elapsed:.2f}s | {len(data_rows)} rows | df50={len(df50_rows)} rows")

        from utils.helpers import emit
        data_chunk = emit("sql_data", {"query": clean_sql, "data": data_rows})

        return {
            "messages": [],
            "stream_chunks": [data_chunk],
            "data_fetched": data_fetched_status,
            "SQLData": execution_result,
            "df50": df50_json,
        }

    except Exception as e:
        log.error(f"[RESEARCHER-EXEC] Failed: {e}", exc_info=True)
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLData": "", "df50": ""}
