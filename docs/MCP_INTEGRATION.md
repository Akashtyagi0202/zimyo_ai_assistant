# MCP Integration Guide

This document explains how to use the Model Context Protocol (MCP) integration between the Zimyo AI Assistant and the Zimyo API Server.

## Overview

The Zimyo HRMS system uses MCP to provide a standardized interface for AI assistants to interact with HRMS operations like attendance marking and leave management.

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Zimyo AI Assistant │ ◄─────► │  MCP Server      │ ◄─────► │  Zimyo API      │
│  (Python)           │  stdio  │  (Node.js)       │   HTTP  │  (External)     │
└─────────────────────┘         └──────────────────┘         └─────────────────┘
```

## Architecture

### MCP Server (zimyo_api_server/src/mcp/server.js)
- Exposes HRMS operations as MCP tools
- Uses existing controllers (AttendanceController, LeaveController)
- Communicates via stdio transport
- Returns structured JSON responses

### MCP Client (zimyo_ai_assistant/services/mcp_client.py)
- Python client for calling MCP tools
- Manages subprocess communication with MCP server
- Provides async interface for AI assistant

## Available MCP Tools

### 1. mark_attendance
Mark employee attendance (check-in/check-out).

**Usage:**
```python
from services.mcp_client import get_mcp_client

mcp = get_mcp_client()
result = await mcp.mark_attendance(
    user_id="user123",
    location="Office"  # optional
)
```

### 2. apply_leave
Submit a leave application.

**Usage:**
```python
result = await mcp.apply_leave(
    user_id="user123",
    leave_type_name="Casual Leave",
    from_date="2024-01-15",
    to_date="2024-01-16",
    reasons="Personal work",
    is_half_day="0"  # optional
)
```

### 3. get_leave_balance
Get employee's leave balance.

**Usage:**
```python
result = await mcp.get_leave_balance(user_id="user123")
```

### 4. get_leave_types
Get available leave types for an employee.

**Usage:**
```python
result = await mcp.get_leave_types(user_id="user123")
```

### 5. validate_leave_request
Validate a leave request before applying.

**Usage:**
```python
result = await mcp.validate_leave_request(
    user_id="user123",
    leave_type_name="Casual Leave",
    from_date="2024-01-15",
    to_date="2024-01-16"
)
```

## Setup Instructions

### 1. Install MCP SDK in API Server

```bash
cd zimyo_api_server
npm install @modelcontextprotocol/sdk
```

### 2. Start the MCP Server

**Option A: Standalone mode**
```bash
npm run mcp
```

**Option B: From Python (handled automatically by mcp_client.py)**
The Python client will spawn the MCP server process as needed.

### 3. Configure Environment

Make sure both projects have proper environment variables:

**zimyo_api_server/.env:**
```
ZIMYO_BASE_URL=https://api.zimyo.com
REDIS_HOST=localhost
REDIS_PORT=6379
```

**zimyo_ai_assistant/.env:**
```
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Integration with AI Assistant

### Basic Usage Pattern

```python
import asyncio
from services.mcp_client import get_mcp_client

async def handle_attendance_request(user_id: str):
    """Handle attendance marking through MCP"""
    mcp = get_mcp_client()
    result = await mcp.mark_attendance(user_id)

    if result.get('status') == 'success':
        return f"Attendance marked successfully at {result.get('timestamp')}"
    else:
        return f"Error: {result.get('message')}"

# Run async function
result = asyncio.run(handle_attendance_request("user123"))
```

### Integration with HRMS Integration Service

Update `services/hrms_integration.py` to use MCP:

```python
from services.mcp_client import get_mcp_client

async def process_attendance(user_id: str, command: str):
    """Process attendance request via MCP"""
    mcp = get_mcp_client()

    if "mark" in command.lower() or "punch" in command.lower():
        result = await mcp.mark_attendance(user_id)
        return format_attendance_response(result)
```

## Response Format

All MCP tools return consistent JSON responses:

**Success Response:**
```json
{
  "status": "success",
  "message": "Operation completed successfully",
  "data": { ... },
  "timestamp": "2024-01-15 10:30:00"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description",
  "_statusCode": 400
}
```

## Testing

### Test MCP Server Directly

```bash
cd zimyo_api_server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | npm run mcp
```

### Test from Python

```python
import asyncio
from services.mcp_client import get_mcp_client

async def test_mcp():
    mcp = get_mcp_client()

    # Test getting leave types
    result = await mcp.get_leave_types("test_user_id")
    print(result)

asyncio.run(test_mcp())
```

## Troubleshooting

### Issue: MCP server not responding
**Solution:** Check if Node.js is installed and the server path is correct in `mcp_client.py`

### Issue: Authentication errors
**Solution:** Ensure Redis is running and user session data is properly stored

### Issue: Invalid date format
**Solution:** Dates must be in YYYY-MM-DD format

## Benefits of MCP Integration

1. **Standardization**: Unified interface for all HRMS operations
2. **Type Safety**: Schema validation for all tool inputs
3. **Separation of Concerns**: Clear separation between AI logic and API integration
4. **Reusability**: MCP server can be used by multiple clients (CLI, web UI, etc.)
5. **Consistency**: Same business logic for all interfaces

## Future Enhancements

- Add more tools for payroll operations
- Implement resource providers for employee data
- Add prompt templates for common operations
- Support for batch operations
- Real-time notifications via MCP

## References

- [MCP Documentation](https://modelcontextprotocol.io)
- [MCP SDK GitHub](https://github.com/modelcontextprotocol/sdk)
- Zimyo API Documentation
