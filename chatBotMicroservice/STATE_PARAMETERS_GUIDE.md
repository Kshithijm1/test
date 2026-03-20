# State Parameters Guide

## Updated State Schema

Your project now uses the following state parameters as defined in your schema specification:

```python
class AgentState(TypedDict):
    # Core messaging
    messages:            Annotated[list, add_messages]
    
    # SQL & Data parameters (Researcher Agent)
    SQLQuery:            str    # Generated BigQuery SQL
    SQLData:             str    # JSON string of query results
    
    # Visualization parameters (Display Agent)
    GraphType:           str    # "LineGraph", "ScatterPlot", etc.
    VisualizationJSON:   str    # JSON string of chart configuration
    
    # Context parameters
    Context:             str    # Additional context
    UserRole:            str    # User's role
    WorkflowGoals:       str    # Workflow objectives
    Schema:              str    # Database schema info
    Reasoning:           str    # Agent reasoning
    
    # Legacy parameters (still used)
    pm_plan:             str
    stream_chunks:       Annotated[list, merge_lists]
    display_results:     Annotated[list, merge_lists]
    data_fetched:        bool
    evaluation:          str
    evaluation_critique: str
    retry_count:         int
    token_queue:         Any
    start_time:          float
```

## Parameter Flow Through Agents

### 1. **Researcher Agent** → Populates SQL Parameters

**Input**: 
- `messages` (user query)

**Process**:
```python
# Step 1: Generate SQL
sql = generate_sql.invoke({"query": user_msg})

# Step 2: Execute SQL
results = execute_bigquery.invoke({"sql_query": sql})
```

**Output**:
- `SQLQuery` - The generated BigQuery SQL statement
- `SQLData` - JSON string containing query results
- `data_fetched` - Boolean indicating success

**Example**:
```python
state.SQLQuery = """
SELECT filingDate, capital_expenditure, cash_from_operations
FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt`
WHERE companyName = 'Tesla, Inc.'
"""

state.SQLData = '[{"filingDate": "2024-01-24", "capital_expenditure": -1858, ...}]'
```

---

### 2. **Display Agent** → Populates Visualization Parameters

**Input**:
- `messages` (user query)
- `SQLData` (from researcher agent)

**Process**:
```python
# Parse SQLData
data_rows = json.loads(state.SQLData)

# Generate chart configuration using LLM
chart_config = llm.invoke({
    "user_question": user_msg,
    "samples": data_rows[:20]
})

# Determine graph type
graph_type = "LineGraph" | "ScatterPlot" | "BarGraph"
```

**Output**:
- `GraphType` - Type of visualization ("LineGraph", "ScatterPlot", etc.)
- `VisualizationJSON` - JSON string of complete chart configuration
- `display_results` - List containing chart config dict

**Example**:
```python
state.GraphType = "LineGraph"

state.VisualizationJSON = '''{
  "usecase": "3",
  "update_layout_title": "Tesla: Capital Expenditure vs Cash from Operations",
  "x": "filingDate",
  "y": ["capital_expenditure", "cash_from_operations"],
  "mode": "lines+markers"
}'''

state.display_results = [chart_config_dict]
```

---

### 3. **Response Agent** → Uses All Parameters

**Input**:
- `messages` (user query)
- `SQLQuery` (what data was queried)
- `SQLData` (the actual data)
- `GraphType` (what visualization was chosen)
- `VisualizationJSON` (chart configuration)

**Process**:
```python
# Generate natural language response referencing:
# - The SQL query that was run
# - The data that was retrieved
# - The visualization that was created
```

**Output**:
- `stream_chunks` - Text response to user

---

## Complete State Flow Example

### User Query: "Tesla: Capital Expenditure vs Cash from Operations over time"

**After Researcher Agent**:
```python
{
    "messages": [HumanMessage("Tesla: Capex vs Cash from Ops")],
    "SQLQuery": "SELECT filingDate, capital_expenditure, cash_from_operations FROM ...",
    "SQLData": '[{"filingDate": "2024-01-24", "capital_expenditure": -1858, ...}]',
    "data_fetched": True
}
```

**After Display Agent**:
```python
{
    "messages": [HumanMessage("Tesla: Capex vs Cash from Ops")],
    "SQLQuery": "SELECT filingDate, capital_expenditure, cash_from_operations FROM ...",
    "SQLData": '[{"filingDate": "2024-01-24", "capital_expenditure": -1858, ...}]',
    "GraphType": "LineGraph",
    "VisualizationJSON": '{"usecase": "3", "x": "filingDate", "y": [...]}',
    "display_results": [{"usecase": "3", ...}],
    "data_fetched": True
}
```

**After Response Agent**:
```python
{
    "messages": [HumanMessage("Tesla: Capex vs Cash from Ops")],
    "SQLQuery": "SELECT filingDate, capital_expenditure, cash_from_operations FROM ...",
    "SQLData": '[{"filingDate": "2024-01-24", "capital_expenditure": -1858, ...}]',
    "GraphType": "LineGraph",
    "VisualizationJSON": '{"usecase": "3", "x": "filingDate", "y": [...]}',
    "display_results": [{"usecase": "3", ...}],
    "stream_chunks": ["Here's Tesla's Capital Expenditure vs Cash from Operations..."],
    "data_fetched": True
}
```

---

## Agent Return Patterns

### Researcher Agent Returns:
```python
return {
    "messages": [],
    "stream_chunks": [],
    "data_fetched": True,
    "SQLQuery": clean_sql,
    "SQLData": execution_result,
}
```

### Display Agent Returns:
```python
return {
    "messages": [],
    "display_results": [chart_config],
    "stream_chunks": [],
    "GraphType": graph_type,
    "VisualizationJSON": visualization_json,
}
```

### Response Agent Returns:
```python
return {
    "messages": [],
    "stream_chunks": [response_text],
}
```

---

## Key Changes from Previous Implementation

| Old Parameter | New Parameter | Used By |
|--------------|---------------|---------|
| `bigquery_data` (list) | `SQLData` (str) | Display Agent |
| N/A | `SQLQuery` (str) | Researcher Agent |
| N/A | `GraphType` (str) | Display Agent |
| N/A | `VisualizationJSON` (str) | Display Agent |

---

## Benefits of New State Structure

1. **Explicit SQL Tracking**: `SQLQuery` parameter stores the exact SQL that was executed
2. **Type Consistency**: `SQLData` is a JSON string (not parsed list), consistent with `VisualizationJSON`
3. **Graph Type Clarity**: `GraphType` explicitly states what visualization was chosen
4. **JSON Serialization**: `VisualizationJSON` is ready for frontend consumption
5. **Schema Compliance**: Matches your specified state parameter structure

---

## Frontend Integration

The frontend can now access:

```javascript
// Get the SQL that was executed
const sql = state.SQLQuery;

// Get the raw data
const data = JSON.parse(state.SQLData);

// Get the visualization type
const graphType = state.GraphType; // "LineGraph", "ScatterPlot", etc.

// Get the complete chart configuration
const chartConfig = JSON.parse(state.VisualizationJSON);

// Reconstruct Plotly chart
const plotlyChart = buildChart(graphType, chartConfig, data);
```

---

## Testing with New State Parameters

```python
from core.state import AgentState
from langchain_core.messages import HumanMessage

# Create state with new parameters
state = AgentState(
    messages=[HumanMessage("Tesla: Capex vs Cash from Ops")],
    SQLQuery="",
    SQLData="",
    GraphType="",
    VisualizationJSON="",
    Context="",
    UserRole="Financial Analyst",
    WorkflowGoals="Visualize financial data",
    Schema="",
    Reasoning="",
    pm_plan="",
    stream_chunks=[],
    display_results=[],
    data_fetched=False,
    evaluation="",
    evaluation_critique="",
    retry_count=0,
    token_queue=None,
    start_time=0.0
)

# Run through agents
result = researcher_agent(state)
# result.SQLQuery = "SELECT ..."
# result.SQLData = '[{...}]'

result = display_agent(result)
# result.GraphType = "LineGraph"
# result.VisualizationJSON = '{"usecase": "3", ...}'
```

---

## Summary

Your state now properly tracks:
- ✅ **SQL Generation** via `SQLQuery`
- ✅ **Query Results** via `SQLData`
- ✅ **Visualization Type** via `GraphType`
- ✅ **Chart Configuration** via `VisualizationJSON`
- ✅ **Context & Metadata** via `Context`, `UserRole`, `WorkflowGoals`, etc.

All agents have been updated to use these parameters correctly, ensuring proper data flow through your LangGraph pipeline.
