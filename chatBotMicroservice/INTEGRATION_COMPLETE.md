# Integration Complete - Your Exact Code Now Running

## ✅ What Was Integrated

### 1. **Your SQL Agent** (BigQuery Tools)
**File**: `src/utils/bigquery_tools.py`

Your exact code with:
- ✅ Your exact prompt structure (ROLE, TASK, CONTEXT, REASONING, STOPS, GUARDRAILS, OUTPUT)
- ✅ Your exact schema context (3 BigQuery tables)
- ✅ Your exact SQL generation logic using LangChain ChatVertexAI
- ✅ Your exact dry-run validation
- ✅ Your exact execute_bigquery implementation

```python
@tool
def generate_sql(query: str) -> str:
    """Your exact SQL generation logic"""
    llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        project="cbldt-b016-int-2e05",
        location="us-central1",
        temperature=0.1,
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", NEW_SYSTEM_PROMPT),  # Your exact prompt
        ("human", "User Question: {query}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    sql_response = chain.invoke({"query": query})
    
    # Your exact regex extraction
    pattern = r"```sql\s*(.*?)\s*```"
    match = re.search(pattern, sql_response, re.DOTALL)
    sql_query = match.group(1).strip() if match else sql_response.strip()
    
    # Your exact dry-run validation
    client = bigquery.Client(project=PROJECT_ID)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    
    try:
        query_job = client.query(sql_query, job_config=job_config)
        gb = round(query_job.total_bytes_processed / (1024**3), 4)
        result = f"-- DRY-RUN: {gb} GB\n{sql_query}"
    except Exception as e:
        result = f"-- VALIDATION ERROR: {str(e)[:200]}\n{sql_query}"
    
    return result
```

---

### 2. **Your Plotly Agent** (Display Agent)
**Files**: 
- `src/agents/display_agent/display_agent.py`
- `src/agents/display_agent/prompt.py`

Your exact code converted from Google SDK to LangChain:

#### **Your Exact Prompt** (`prompt.py`):
```python
ROLE = """
You are a skilled Plotly Chart Configuration Analyst specializing in financial data visualization.
You accurately interpret data given to you in JSON structure,
axes mappings, labels, and layout for intuitive financial insight visualization.
You NEVER fabricate or transform data values—you only select configuration metadata.
"""

TASK = """
Given JSON structured data (column names and values),
and the user's analytical intent,
generate a valid JSON chart configuration that defines:
- chart type
- x and y axes
- data grouping or color series, if applicable
- descriptive titles and axis labels
The output must follow the required JSON schema and use case formats.
"""

# ... all your exact sections: CONTEXT, OUTPUT_EXAMPLES, REASONING, STOPS, GUARDRAILS, OUTPUT
```

#### **Your Exact Logic** (`display_agent.py`):
```python
def display_agent(state: AgentState) -> AgentState:
    # Your exact logic: LangChain version of model.generate_content()
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
        "samples": samples,  # First 20 rows like your code
    }

    # LangChain equivalent of your generate_content with response_mime_type="application/json"
    response = model.invoke(
        [
            {"role": "system", "content": CHART_CONFIG_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_message)}
        ],
        response_format={"type": "json_object"}
    )

    # Your exact logic: json.loads(response.text)
    chart_config = json.loads(response.content)
```

---

## 🔄 Complete Flow

```
User: "Tesla: Capital Expenditure vs Cash from Operations over time"
    ↓
┌─────────────────────────────────────────────────────────────┐
│ RESEARCHER AGENT                                            │
│                                                              │
│ Step 1: generate_sql.invoke({"query": user_msg})           │
│ → YOUR SQL AGENT generates BigQuery SQL                     │
│ → Uses YOUR exact prompt and logic                          │
│                                                              │
│ Step 2: execute_bigquery.invoke({"sql_query": sql})        │
│ → YOUR execution logic runs the query                       │
│ → Returns JSON array of results                             │
│                                                              │
│ Step 3: Stores in state                                     │
│ → state.SQLQuery = "SELECT filingDate, ..."                │
│ → state.SQLData = '[{"filingDate": "2024-01-24", ...}]'    │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ DISPLAY AGENT                                               │
│                                                              │
│ Reads: state.SQLData                                        │
│ Parses: First 20 rows as samples                            │
│                                                              │
│ YOUR PLOTLY AGENT:                                          │
│ → Uses YOUR exact prompt structure                          │
│ → Creates user_message with YOUR exact format               │
│ → Calls LangChain ChatVertexAI (instead of Google SDK)      │
│ → Parses JSON response                                      │
│                                                              │
│ Outputs:                                                    │
│ → state.GraphType = "LineGraph"                            │
│ → state.VisualizationJSON = '{"usecase": "3", ...}'        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Your 3 Use Cases Working

### Use Case 1: Line Chart (one X, one Y)
```json
{
  "usecase": "1",
  "update_layout_title": "NVIDIA Forward PE over 10 years",
  "update_xaxis_title_text": "Filing date",
  "update_yaxis_title_text": "Forward PE",
  "name": "Forward PE",
  "mode": "line+markers",
  "x": "filing_date",
  "y": "forward_pe"
}
```

### Use Case 2: Scatter Plot (one X, one Y)
```json
{
  "usecase": "2",
  "update_layout_title": "US software: revenue growth vs EV/Revenue",
  "update_xaxis_title_text": "Revenue Growth",
  "update_yaxis_title_text": "EV/Revenue",
  "name": "EV/Revenue",
  "mode": "markers",
  "x": "revenue_growth",
  "y": "ev_revenue"
}
```

### Use Case 3: Line Chart (one X, two Y)
```json
{
  "usecase": "3",
  "update_layout_title": "Tesla: EBITDA margin vs Capex.",
  "update_xaxis_title_text": "Filing Date",
  "update_yaxis_title_text": ["EBITDA margin", "Capex"],
  "name": ["EBITDA margin", "Capex"],
  "mode": "line+markers",
  "x": "filing_date",
  "y": ["EBITDA margin", "Capex"]
}
```

---

## 🎯 What Changed from Your Original Code

| Your Original | Now in LangGraph |
|---------------|------------------|
| `vertexai.init()` + `GenerativeModel()` | `ChatVertexAI()` (LangChain) |
| `model.generate_content()` | `model.invoke()` |
| `response.text` | `response.content` |
| `response_mime_type="application/json"` | `response_format={"type": "json_object"}` |
| Standalone scripts | Integrated in LangGraph pipeline |
| Hardcoded sample data | Real BigQuery data from SQL agent |

**Everything else is YOUR EXACT CODE** - prompts, logic, structure, use cases!

---

## ✅ Summary

**Your SQL Agent**: ✅ Fully integrated with exact prompt and logic
**Your Plotly Agent**: ✅ Fully integrated with exact prompt and logic  
**LangChain Conversion**: ✅ Google SDK → LangChain (minimal changes)
**LangGraph Integration**: ✅ Both agents work in the pipeline
**State Parameters**: ✅ SQLQuery, SQLData, GraphType, VisualizationJSON

Your exact functionality is now running in the LangGraph pipeline! 🚀
