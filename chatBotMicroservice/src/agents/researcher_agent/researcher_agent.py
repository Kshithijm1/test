import json
import time
from langchain_core.messages import HumanMessage
from core.state import AgentState
from utils.tools import TOOL_MAP
from utils.helpers import log


def researcher_agent(state: AgentState) -> AgentState:
    """
    BQAgent (Researcher Agent) — Generates and executes BigQuery SQL.

    Reads from state:
        user_query, UserRole, WorkflowGoals, Context (pm_plan)

    Writes to state:
        SQLQuery  — the executed SQL statement
        SQLData   — full JSON result from BigQuery
        df50      — top 50 rows as JSON string (for display agent)
        data_fetched — bool indicating if rows were returned
    """
    # Small delay to let frontend render the 'started' event before we begin work
    time.sleep(0.6)
    log.info("━━━ [RESEARCHER] BigQuery SQL generation and execution")
    t0 = time.time()

    # Read all context from state
    user_query = state.get("user_query", "")
    user_role = state.get("UserRole", "")
    workflow_goals = state.get("WorkflowGoals", "")
    context_b = state.get("Context", "") or state.get("pm_plan", "")

    # Fallback to messages if user_query not in state
    if not user_query:
        user_query = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")

    if not user_query:
        log.warning("[RESEARCHER] No user query found in state or messages")
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": "", "df50": ""}

    log.info(f"[RESEARCHER] User query: {user_query[:100]}...")
    log.info(f"[RESEARCHER] Context (B) available: {bool(context_b)}")

    # Enrich query with full state context for SQL generation LLM
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
    log.info("[RESEARCHER] Enriched query with full state context (UserRole, WorkflowGoals, Context)")

    try:
        generate_sql_tool = TOOL_MAP.get("generate_sql")
        execute_bigquery_tool = TOOL_MAP.get("execute_bigquery")

        if not generate_sql_tool or not execute_bigquery_tool:
            log.error("[RESEARCHER] BigQuery tools not found in TOOL_MAP")
            return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": "", "df50": ""}

        log.info("[RESEARCHER] Step 1: Generating SQL query...")
        sql_result = generate_sql_tool.invoke({"query": enriched_query})
        log.info(f"[RESEARCHER] SQL generated: {sql_result[:200]}...")

        # Extract the SQL statement - handle both plain SELECT and CTEs (WITH ...)
        import re
        # Try CTE first (WITH ...), then plain SELECT, skipping dry-run/validation metadata lines
        cte_match = re.search(r'(WITH\s.+)', sql_result, re.DOTALL | re.IGNORECASE)
        select_match = re.search(r'(SELECT\s.+)', sql_result, re.DOTALL | re.IGNORECASE)
        clean_sql = (cte_match or select_match).group(1).strip() if (cte_match or select_match) else sql_result.strip()

        log.info(f"[RESEARCHER] SQL Query to Execute:\n{clean_sql}")
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
        data_fetched_status = len(data_rows) > 0

        # Top 50 rows for display agent (df50)
        df50_rows = data_rows[:50]
        df50_json = json.dumps(df50_rows)

        log.info(f"[RESEARCHER] ✓ Done in {elapsed:.2f}s | {len(data_rows)} rows total | df50={len(df50_rows)} rows | data_fetched={data_fetched_status}")

        # Send full data to frontend for graph reconstruction
        from utils.helpers import emit
        data_chunk = emit("sql_data", {"query": clean_sql, "data": data_rows})

        return {
            "messages": [],
            "stream_chunks": [data_chunk],
            "data_fetched": data_fetched_status,
            "SQLQuery": clean_sql,
            "SQLData": execution_result,
            "df50": df50_json,
        }

    except Exception as e:
        log.error(f"[RESEARCHER] Failed: {e}", exc_info=True)
        return {"messages": [], "stream_chunks": [], "data_fetched": False, "SQLQuery": "", "SQLData": "", "df50": ""}
