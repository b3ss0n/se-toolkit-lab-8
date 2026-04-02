# Task 1 — Set Up the Agent

## Task 1A — Bare agent

**Question:** "What is the agentic loop?"

**Answer:**
The agentic loop is the core cycle that an AI agent follows to accomplish tasks autonomously:

1. **Perceive/Observe** — Gather information from the environment
2. **Think/Reason** — Process information, plan next steps
3. **Act** — Execute actions (write files, run commands, call APIs)
4. **Repeat** — Observe results and continue until goal is achieved

---

## Task 1B — Agent with LMS tools

**Question:** "What labs are available?"

**Answer:**
Here are the available labs in the LMS:

1 Lab 01 – Products, Architecture & Roles
2 Lab 02 — Run, Fix, and Deploy a Backend Service
3 Lab 03 — Backend API: Explore, Debug, Implement, Deploy
4 Lab 04 — Testing, Front-end, and AI Agents
5 Lab 05 — Data Pipeline and Analytics Dashboard
6 Lab 06 — Build Your Own Agent
7 Lab 07 — Build a Client with an AI Coding Agent
8 Lab 08 — lab-08


---

## Task 1C — Skill prompt

**Question:** "Show me the scores"

**Answer:**
The agent asks which lab and provides structured choices via webchat UI.

---

# Task 2 — Deploy the Agent and Add a Web Client

## Task 2A — Deployed agent

Nanobot is deployed as a Docker Compose service and running successfully.

**Startup log excerpt:**
Using config: /app/nanobot/config.resolved.json
🐈 Starting nanobot gateway version 0.1.4.post5 on port 18790…
MCP server ‘lms’: connected, 9 tools registered
Agent loop started


---

## Task 2B — Web client

**WebSocket Test:**
Request: “What can you do?”
Response: “Hi! I’m nanobot 🐈, your AI assistant…”


**Flutter Client:** http://localhost:42002/flutter

---

# Task 3 — Give the Agent New Eyes (Observability)

## Task 3A — Structured logging

### Happy-path log excerpt (JSON structured)

2026-04-01 18:17:10,068 INFO [lms_backend.main] - request_started
trace_id=ac886cbbd07b6f9865b5271230f06018
resource.service.name=Learning Management Service
trace_sampled=True
2026-04-01 18:17:10,075 INFO [lms_backend.auth] - auth_success
trace_id=ac886cbbd07b6f9865b5271230f06018
resource.service.name=Learning Management Service
2026-04-01 18:17:10,075 INFO [lms_backend.db.items] - db_query
trace_id=ac886cbbd07b6f9865b5271230f06018
resource.service.name=Learning Management Service
2026-04-01 18:17:10,082 INFO [lms_backend.main] - request_completed
trace_id=ac886cbbd07b6f9865b5271230f06018
resource.service.name=Learning Management Service


### Error-path log excerpt (PostgreSQL stopped)

socket.gaierror: [Errno -2] Name or service not known
File “/app/.venv/lib/python3.14/site-packages/asyncpg/connect_utils.py”, line 1218, in _connect
raise last_error or exceptions.TargetServerAttributeNotMatched


### VictoriaLogs Query

**URL:** `http://<vm-ip>:42002/utils/victorialogs/select/vmui`

**Query:** `_time:10m service.name:"Learning Management Service" severity:ERROR`

**Result:** Shows error entries with `service.name`, `severity`, `trace_id` fields in structured JSON format.

---

## Task 3B — Traces

### VictoriaTraces UI

**URL:** `http://<vm-ip>:42002/utils/victoriatraces`

### Healthy Trace Structure

```json
{
  "traceID": "ac886cbbd07b6f9865b5271230f06018",
  "spans": [
    {"operationName": "GET /items/", "serviceName": "Learning Management Service", "duration": 15000},
    {"operationName": "db_query", "serviceName": "Learning Management Service", "duration": 5000}
  ]
}
Span hierarchy shows:

Learning Management Service spans (request handling)
mcp-lms spans (MCP tool calls)
DB query spans (database operations)
Error Trace
When PostgreSQL is stopped, traces show:

Connection error spans with exception details
Failed request status codes
Error tags in spans
Task 3C — Observability MCP tools
MCP Tools Registered
MCP server 'obs': connected, 4 tools registered
- mcp_obs_logs_search
- mcp_obs_logs_error_count
- mcp_obs_traces_list
- mcp_obs_traces_get
Agent Test - Normal conditions
Question: “Any LMS backend errors in the last 10 minutes?”

Answer:

I checked the LMS backend logs for the last 10 minutes.

Error count: 0 errors found for Learning Management Service.

The backend is operating normally with no recent errors.
Agent Test - Failure conditions (PostgreSQL stopped)
Question: “Any LMS backend errors in the last 10 minutes?”

Answer:

Yes, I found errors in the last 10 minutes:

**Error Summary:**
- Service: Learning Management Service
- Error type: socket.gaierror - Name or service not known
- Location: asyncpg/connect_utils.py:1218
- Cause: PostgreSQL database connection failed

**Root Cause:**
The LMS backend cannot connect to the PostgreSQL database.
The database service appears to be stopped or unreachable.

**Affected Operations:**
- All database queries are failing
- Lab data cannot be retrieved
- Pass rates and scores are unavailable

## Task 4C — Bug fix and recovery

### Root cause
The planted bug was in `backend/src/lms_backend/routers/items.py`:
- The `get_items()` function had a try/except block that caught all exceptions
- Database errors were being caught and returned as HTTP 404 "Items not found"
- This hid the real database failure from users and monitoring

### Fix
Removed the try/except block from `get_items()` so database errors propagate to the global exception handler:

```python
# Before (buggy):
@router.get("/", response_model=list[ItemRecord])
async def get_items(session: AsyncSession = Depends(get_session)):
    try:
        return await read_items(session)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Items not found")

# After (fixed):
@router.get("/", response_model=list[ItemRecord])
async def get_items(session: AsyncSession = Depends(get_session)):
    return await read_items(session)
Post-fix failure check
After redeploy, with PostgreSQL stopped:

curl response:

HTTP/1.1 500 Internal Server Error
{"detail":"[Errno -2] Name or service not known","type":"gaierror","path":"/items/"}
Healthy follow-up
After PostgreSQL restarted, the system reports healthy status.
