# How to Run Your Project

## Prerequisites

### 1. **Google Cloud Setup**
You need Google Cloud credentials for BigQuery and Vertex AI:

```bash
# Set up Google Cloud authentication
gcloud auth application-default login

# Or set the environment variable
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\service-account-key.json
```

### 2. **Python Environment**
Python 3.10+ required

---

## Installation Steps

### 1. **Navigate to Project Directory**
```bash
cd c:\Users\kshit\Downloads\test\chatBotMicroservice
```

### 2. **Create Virtual Environment**
```bash
python -m venv venv
```

### 3. **Activate Virtual Environment**
```bash
# Windows
venv\Scripts\activate

# You should see (venv) in your terminal
```

### 4. **Install Dependencies**
```bash
pip install -r src\environment\requirements.txt

# Install additional BigQuery dependencies
pip install langchain-google-vertexai google-cloud-bigquery
```

---

## Running the Server

### **Start the FastAPI Server**
```bash
# From the project root directory
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Testing the API

### **1. Health Check**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok"}
```

### **2. Send a Chat Request**

**Using curl:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"Tesla: Capital Expenditure vs Cash from Operations over time\"}"
```

**Using PowerShell:**
```powershell
$body = @{
    prompt = "Tesla: Capital Expenditure vs Cash from Operations over time"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method Post -Body $body -ContentType "application/json"
```

**Using Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={"prompt": "Tesla: Capital Expenditure vs Cash from Operations over time"}
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

---

## Expected Response Format

The API returns a **streaming response** with JSON chunks:

### **1. Thinking Content** (LLM tokens in real-time)
```json
{"type": "thinking_content", "data": "Let"}
{"type": "thinking_content", "data": " me"}
{"type": "thinking_content", "data": " analyze"}
```

### **2. Response Content** (Final answer)
```json
{"type": "response_content", "data": "Here's the analysis of Tesla's financial data..."}
```

### **3. Display Modules** (Chart configuration)
```json
{
  "type": "display_modules",
  "data": [
    {
      "usecase": "3",
      "update_layout_title": "Tesla: Capital Expenditure vs Cash from Operations",
      "update_xaxis_title_text": "Filing Date",
      "update_yaxis_title_text": ["Capital Expenditure", "Cash from Operations"],
      "x": "filingDate",
      "y": ["capital_expenditure", "cash_from_operations"],
      "mode": "lines+markers",
      "name": ["Capital Expenditure", "Cash from Operations"]
    }
  ]
}
```

---

## Project Flow When Running

```
1. User sends POST /chat with prompt
   ↓
2. FastAPI creates initial state
   ↓
3. LangGraph executes agent pipeline:
   
   Project Manager Agent
   → Analyzes intent, creates plan
   
   Researcher Agent
   → Calls generate_sql (LLM creates BigQuery SQL)
   → Calls execute_bigquery (runs SQL, gets data)
   → Stores: state.SQLQuery, state.SQLData
   
   Display Agent
   → Reads state.SQLData
   → LLM generates chart configuration
   → Stores: state.GraphType, state.VisualizationJSON
   
   Response Agent
   → Generates final text response
   → Stores: state.stream_chunks
   ↓
4. FastAPI streams response back to client
   → Thinking tokens (real-time)
   → Response content
   → Display modules (chart config)
```

---

## Troubleshooting

### **Issue: "BigQuery tools not found"**
**Solution**: Make sure `utils/bigquery_tools.py` exists and is imported in `utils/tools.py`

### **Issue: "Authentication error"**
**Solution**: Set up Google Cloud credentials:
```bash
gcloud auth application-default login
```

### **Issue: "Module not found"**
**Solution**: Make sure you're running from the `src` directory:
```bash
cd src
uvicorn main:app --reload
```

### **Issue: "Port already in use"**
**Solution**: Use a different port:
```bash
uvicorn main:app --reload --port 8001
```

### **Issue: "SQL validation failed"**
**Solution**: Check the logs - the LLM may need better schema context or the query may be invalid

---

## Development Mode

### **With Auto-Reload** (recommended for development)
```bash
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Production Mode**
```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
VERTEX_LOCATION=us-central1

# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# CORS (if needed)
ALLOWED_ORIGINS=http://localhost:3000
```

---

## Logs

The application logs to console. You'll see:

```
[RESEARCHER] BigQuery SQL generation and execution
[RESEARCHER] Step 1: Generating SQL query...
[RESEARCHER] SQL generated: SELECT filingDate, capital_expenditure...
[RESEARCHER] Step 2: Executing BigQuery...
[RESEARCHER] ✓ Retrieved 14 rows from BigQuery
[RESEARCHER] ✓ Done in 2.34s | 14 data rows

[DISPLAY] Processing 14 data rows from SQLData
[DISPLAY] ✓ Generated LineGraph (use case 3) in 1.23s

[STREAM] Token: {"type": "thinking_content", "data": "Here"}
[STREAM] display_modules emitted with 1 item(s)
```

---

## Quick Start (Copy-Paste)

```bash
# 1. Navigate to project
cd c:\Users\kshit\Downloads\test\chatBotMicroservice

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r src\environment\requirements.txt
pip install langchain-google-vertexai google-cloud-bigquery

# 4. Set up Google Cloud auth
gcloud auth application-default login

# 5. Run the server
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 6. Test in another terminal
curl http://localhost:8000/health
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/chat` | POST | Send chat request |

### **POST /chat**
**Request Body:**
```json
{
  "prompt": "Your financial data question here"
}
```

**Response:** Server-Sent Events (SSE) stream with JSON chunks

---

Your server is now running and ready to process financial data queries using BigQuery and generate visualizations! 🚀
