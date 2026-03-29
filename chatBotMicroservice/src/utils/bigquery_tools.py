from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from google.cloud import bigquery
import re
import json

PROJECT_ID = "cbldt-b016-int-2e05"
MODEL = "gemini-2.0-flash"

SCHEMA_CONTEXT = """
Project id: cbldt-b016-int-2e05
Dataset id: dw_ext_sgam_1832_sp_ist
Table: financials_dt
Description: Core financial statements table containing detailed financial line items (Revenue, Debt, etc.) from company filings with associated metadata, periods, and company identifiers.
Columns:
  financialCollectionId INT64,
  fiscalYear INT64,
  financialPeriodID INT64,
  periodTypeId INT64,
  calendarYear INT64,
  calendarQuarter INT64,
  fiscalQuarter INT64,
  periodTypeName STRING,
  filingDate DATE,
  periodEndDate DATE,
  documentId INT64,
  dataItemId INT64,
  dataItemValue STRING, <this contains numeric dataitemname like Revenue, Long-Term Debt etc.>
  collectionDataItemValue FLOAT64,
  unitTypeId INT64,
  unitTypeName STRING,
  filingId INT64,
  fileVersionId STRING,
  filing_filingdate DATETIME,
  companyId INT64,
  currencyId INT64,
  currencyName STRING,
  countryId INT64,
  ISOCode STRING,
  _dw_load_ts TIMESTAMP,
  financialInstanceId INT64

Project id: cbldt-b016-int-2e05
Dataset id: stg_ext_sgam_1832_sp_ist
Table: CountryGeo
Description: Country master table containing geographic hierarchy with country codes and region mappings.
Columns:
  countryId INTEGER,
  country STRING,
  isoCountry2 STRING, <This is country a country code that has two Character i.e India -> IN, Canada -> CA, United States -> US. This is going to be used in Query construction.>
  isoCountry3 STRING, <This is country a country code that has three Character i.e India -> IND, Canada -> CAN, United States -> USA>
  regionId INTEGER,
  region STRING,
  _batch_id STRING,
  _ingestion_ts TIMESTAMP,
  _stg_load_ts TIMESTAMP,
  _ingestion_type STRING

Project id: cbldt-b016-int-2e05
Dataset id: dw_ext_sgam_1832_sp_ist
Table: mv_bbg_sp_trade
Description: Company master/reference table with identifiers, GICS classification, and ticker information.
Columns:
  TICKER STRING,
  NAME STRING,
  ID_CUSIP STRING,
  ID_ISIN STRING,
  ID_SEDOL1 STRING,
  EXCH_CODE STRING,
  ID_BB_COMPANY STRING,
  ID_BB_GLOBAL STRING,
  GICS_SECTOR STRING,
  GICS_SECTOR_NAME STRING,
  GICS_INDUSTRY_GROUP STRING,
  GICS_INDUSTRY_GROUP_NAME STRING,
  GICS_INDUSTRY STRING,
  GICS_INDUSTRY_NAME STRING,
  GICS_SUB_INDUSTRY STRING,
  GICS_SUB_INDUSTRY_NAME STRING,
  identifierValue STRING,
  companyId INTEGER,
  companyName STRING,
  companyStatusTypeId INTEGER,
  countryId INTEGER,
  incorporationCountryId INTEGER

CRITICAL - Exact dataItemValue field names (case-sensitive, use these EXACT strings):
  - 'Cost of Revenue' (NOT 'Cost Of Revenues' or 'Cost of Revenues')
  - 'Operating Income (Loss)' (NOT 'Operating Income')
  - 'Total Revenues' (NOT 'Total Revenue')
  - 'Gross Profit'
  - 'Capital Expenditure'
  - 'Cash from Operations'
"""

ROLE = """
You are a highly experienced BigQuery Quantitative Financial Data Analyst, specializing in analyzing large-scale market datasets using Google BigQuery and advanced SQL.
"""

AVAILABLE_TABLES = """
AVAILABLE TABLES (USE ONLY THESE):
- `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` — Financials (Revenue, Capex, etc.)
- `cbldt-b016-int-2e05.stg_ext_sgam_1832_sp_ist.CountryGeo` — Countries
- `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` — Companies
"""

TASK = """
Given the User Question and any relevant context (including schema details, table metadata, and analytical intent), the agent is responsible for generating an accurate and efficient BigQuery SQL query that retrieves the necessary dataset for visualization in Plotly.
"""

CONTEXT = f"""
User Role: "Financial Data Analyst/Portfolio Manager"
User Query: "The natural language analytics request from users about graphical representation of the finance data."
Workflow Goals: "Overall intent of the workflow is to find the data based on user query and create visualization on it."
Schema: {SCHEMA_CONTEXT}
"""

OUTPUT_EXAMPLES = """
Output Examples:
Use case1:
- Example user query: Show me NVIDIA Total Revenues over 10 years.
- Sample SQL output:
    SELECT filingDate, companyName, string_agg(distinct unitTypeName) as Scale,
    AVG(CASE WHEN dataItemValue = 'Total Revenues' THEN collectionDataItemValue END) AS total_revenues
    FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` f
    left join `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` bbg on f.companyId = bbg.companyId
    where filingDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 10 YEAR)
    AND periodTypeName = "Quarterly"
    and companyName = "NVIDIA Corporation"
    GROUP BY filingDate, companyName
    ORDER BY filingDate;

Use case2:
- Example user query: Consumer Discretionary: Cost of Revenues vs Operating Income.
- Sample SQL output:
    SELECT f.companyId, filingDate, string_agg(distinct unitTypeName) as Scale, string_agg(distinct companyName) as Company_Name,
    AVG(CASE WHEN dataItemValue = 'Cost of Revenue' THEN collectionDataItemValue END) AS cost_of_revenue,
    AVG(CASE WHEN dataItemValue = 'Operating Income (Loss)' THEN collectionDataItemValue END) AS operating_income
    FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` f
    left join `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` bbg on f.companyId = bbg.companyId
    left join `cbldt-b016-int-2e05.stg_ext_sgam_1832_sp_ist.CountryGeo` c on f.countryId = c.countryId
    where filingDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
    AND c.isoCountry2 = "US"
    AND periodTypeName = "Quarterly"
    AND bbg.GICS_SECTOR_NAME = "Consumer Discretionary"
    GROUP BY companyId, filingDate
    ORDER BY filingDate DESC
    LIMIT 100;

Use case3:
- Example user query: Tesla: Capital Expenditure vs Cash from Operations over time.
- Sample SQL output:
    SELECT f.companyId, filingDate, string_agg(distinct unitTypeName) as Scale, string_agg(distinct companyName) as Company_Name,
    AVG(CASE WHEN dataItemValue = 'Capital Expenditure' THEN collectionDataItemValue END) AS capital_expenditure,
    AVG(CASE WHEN dataItemValue = 'Cash from Operations' THEN collectionDataItemValue END) AS cash_from_operations
    FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` f
    left join `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` bbg on f.companyId = bbg.companyId
    where filingDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 5 YEAR)
    AND periodTypeName = "Quarterly"
    and companyName = "Tesla, Inc."
    GROUP BY companyId, filingDate
    ORDER BY filingDate;
"""

REASONING = f"""
Follow this reasoning process:
1. Understand user's intent.
2. Identify relevant datasets, tables and fields.
3. Construct a valid bigquery SQL query following the EXACT patterns shown in the Output Examples.
4. Ensure the query is efficient and leverage filters, partitioning, clustering etc. when possible.

{OUTPUT_EXAMPLES}
"""

STOPS = """
Stopping Criteria:
1. Stop when the user question is answered.
2. Return only one final query output with only select statement.
3. CRITICAL: You KNOW all tables. NEVER ask to list tables/datasets.
4. ALWAYS use filingDate (not fiscalYear) for time-series queries.
5. ALWAYS use companyName for company filtering (not TICKER).
6. ALWAYS include periodTypeName = "Quarterly" filter.
7. ALWAYS use LEFT JOIN to mv_bbg_sp_trade on companyId.
8. ALWAYS use AVG(CASE WHEN dataItemValue = '...' THEN collectionDataItemValue END) pattern for metrics.
9. ALWAYS include string_agg(distinct unitTypeName) as Scale in SELECT.
10. ALWAYS GROUP BY and ORDER BY filingDate.
"""

GUARDRAILS = """
1. Never provide DELETE, INSERT, UPDATE, or DROP.
2. Avoid scanning extremely large tables without filters.
3. The statement should only use the data table with schema provided.
4. Follow the EXACT query structure from the Output Examples — same SELECT pattern, same JOIN pattern, same WHERE pattern, same GROUP BY pattern.
5. Do NOT invent new query patterns. Use the patterns demonstrated in the examples.
"""

OUTPUT_FORMAT = """
Return ONLY a SQL query.

Example Structure:
SELECT <columns>
FROM <table>
JOIN <tables>
WHERE <conditions>
GROUP BY <columns>;
"""

NEW_SYSTEM_PROMPT = f"""
Role: {ROLE}
Task: {TASK}
Context: {CONTEXT}
{AVAILABLE_TABLES}
Reasoning: {REASONING}
Stopping Criteria: {STOPS}
Gaurdrails: {GUARDRAILS}
Output: {OUTPUT_FORMAT}
"""


@tool
def generate_sql(query: str) -> str:
    """Generate optimized BigQuery SQL for financial analysis from natural language.
    Use for ALL financial data questions. Returns valid, executable SQL.
    
    Args:
        query: Natural language question about financial data
    
    Returns:
        SQL query string with dry-run validation info
    """
    llm = ChatVertexAI(
        model_name=MODEL,
        project=PROJECT_ID,
        location="us-central1",
        temperature=0.1,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", NEW_SYSTEM_PROMPT), 
        ("human", "User Question: {query}")
    ])

    chain = prompt | llm | StrOutputParser()
    sql_response = chain.invoke({"query": query})

    pattern = r"```sql\s*(.*?)\s*```"
    match = re.search(pattern, sql_response, re.DOTALL)
    sql_query = match.group(1).strip() if match else sql_response.strip()

    client = bigquery.Client(project=PROJECT_ID)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    
    try:
        query_job = client.query(sql_query, job_config=job_config)
        gb = round(query_job.total_bytes_processed / (1024**3), 4)
        result = f"-- DRY-RUN: {gb} GB\n{sql_query}"
    except Exception as e:
        result = f"-- VALIDATION ERROR: {str(e)[:200]}\n{sql_query}"

    return result


@tool
def execute_bigquery(sql_query: str, limit: int = 100) -> str:
    """Execute a BigQuery SQL query and return results as JSON.
    
    Args:
        sql_query: Valid BigQuery SQL SELECT statement
        limit: Maximum number of rows to return (default: 100)
    
    Returns:
        JSON string containing array of result rows
    """
    client = bigquery.Client(project=PROJECT_ID)
    
    # Extract the actual SELECT statement, skipping any DRY-RUN or VALIDATION ERROR metadata
    select_match = re.search(r'(SELECT\s.+)', sql_query, re.DOTALL | re.IGNORECASE)
    clean_sql = select_match.group(1).strip() if select_match else sql_query.strip()
    
    if not clean_sql.upper().strip().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed"})
    
    if "LIMIT" not in clean_sql.upper():
        clean_sql = f"{clean_sql.rstrip(';')} LIMIT {limit}"
    
    try:
        query_job = client.query(clean_sql)
        results = query_job.result()
        
        rows = []
        for row in results:
            row_dict = {}
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row_dict[key] = value.isoformat()
                elif value is None:
                    row_dict[key] = None
                elif isinstance(value, (int, float, str, bool)):
                    row_dict[key] = value
                else:
                    # Convert Decimal and other numeric types to float
                    row_dict[key] = float(value)
            rows.append(row_dict)
        
        return json.dumps(rows, indent=2)
    
    except Exception as e:
        return json.dumps({"error": f"Query execution failed: {str(e)[:300]}"})
