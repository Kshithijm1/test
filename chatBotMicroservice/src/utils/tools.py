from utils.bigquery_tools import generate_sql, execute_bigquery

TOOLS = [generate_sql, execute_bigquery]

TOOL_MAP = {t.name: t for t in TOOLS}

TOOL_LIST = {t.name: t.description for t in TOOLS}
