# Zimyo AI Assistant - Architecture Documentation

## Overview

The Zimyo AI Assistant has been refactored into a two-tier architecture:

1. **Python FastAPI Application** - Handles validation, session management, AI processing, and conversation handling
2. **Node.js API Server** - Handles all direct Zimyo API communications

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend/Client                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP Requests
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                Python FastAPI Application                    │
│                  (Port 8080)                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ API Endpoints                                       │    │
│  │  - /login                                           │    │
│  │  - /chat                                            │    │
│  │  - /sessions/*                                      │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│  ┌─────────────────────┴────────────────────────────┐      │
│  │ Business Logic Layer                              │      │
│  │  - Intent Detection                               │      │
│  │  - Conversation State Management                  │      │
│  │  - Input Validation                               │      │
│  │  - Policy Search & Embeddings                     │      │
│  │  - Session Management                             │      │
│  └───────────────────┬──────────────────────────────┘      │
│                      │                                       │
│  ┌──────────────────┴───────────────────────────────┐      │
│  │ Node API Client                                   │      │
│  │  (HTTP Client to Node.js Server)                 │      │
│  └──────────────────┬───────────────────────────────┘      │
└───────────────────────┼───────────────────────────────────┘
                       │
                       │ HTTP Requests
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                Node.js API Server                            │
│                  (Port 3000)                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ REST API Endpoints                                  │    │
│  │  - POST /api/leave/apply                           │    │
│  │  - GET  /api/leave/balance                         │    │
│  │  - GET  /api/leave/types                           │    │
│  │  - POST /api/leave/validate                        │    │
│  │  - POST /api/attendance/mark                       │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│  ┌─────────────────────┴────────────────────────────┐      │
│  │ Zimyo Service Layer                               │      │
│  │  - API Call Formatting                            │      │
│  │  - Request/Response Transformation                │      │
│  │  - Error Handling                                 │      │
│  └───────────────────┬──────────────────────────────┘      │
└────────────────────────┼───────────────────────────────────┘
                        │
                        │ HTTPS Requests
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Zimyo HRMS APIs                                 │
│     https://www.zimyo.work/apiv2/auth/hrms                  │
└─────────────────────────────────────────────────────────────┘

                        ┌────────────┐
                        │   Redis    │
                        │  (Port 6379)│
                        │            │
                        │ - Sessions │
                        │ - User Data│
                        │ - Policies │
                        └────────────┘
```

## Component Responsibilities

### Python FastAPI Application (`zimyo_ai_assistant/`)

**Responsibilities:**
- User authentication and session management
- Input validation and sanitization
- Intent detection (AI-powered)
- Conversation state management
- Policy document processing and embeddings
- AI-powered responses and recommendations
- Orchestrating workflow between services

**Key Files:**
- `app.py` - Main FastAPI application, API endpoints
- `services/node_api_client.py` - HTTP client for Node.js API
- `services/mcp_integration.py` - Adapter layer (renamed for compatibility)
- `services/operation_handlers.py` - Business logic orchestration
- `services/conversation_state.py` - Conversation management
- `services/langchain_chat.py` - AI/LLM integration
- `services/embeddings.py` - Document embeddings
- `services/policy_service.py` - Policy processing

**Technology Stack:**
- FastAPI
- Python 3.13
- Redis (session storage)
- SentenceTransformers (embeddings)
- LangChain (AI integration)
- HTTPX (HTTP client)

### Node.js API Server (`zimyo_api_server/`)

**Responsibilities:**
- Direct communication with Zimyo HRMS APIs
- API request formatting (multipart/form-data, JSON)
- Response transformation
- Error handling for external API calls
- Session data retrieval from Redis

**Key Files:**
- `src/index.js` - Express application setup
- `src/routes/` - API route definitions
- `src/controllers/` - Request handling logic
- `src/services/zimyo.service.js` - Zimyo API integration
- `src/config/redis.js` - Redis client
- `src/config/zimyo.js` - Zimyo configuration

**Technology Stack:**
- Node.js
- Express
- Axios (HTTP client)
- Redis client
- Helmet (security)
- Morgan (logging)

## API Flow Examples

### Leave Application Flow

1. **User Request** → Frontend sends chat message to `/chat` endpoint
2. **Python App** →
   - Validates user session
   - Detects intent (apply_leave)
   - Extracts information from message
   - Calls Node.js API: `POST /api/leave/validate`
3. **Node.js Server** →
   - Retrieves session from Redis
   - Validates leave request
   - Returns validation result
4. **Python App** →
   - If valid, calls Node.js API: `POST /api/leave/apply`
5. **Node.js Server** →
   - Formats request for Zimyo API
   - Calls Zimyo HRMS API
   - Returns formatted response
6. **Python App** →
   - Processes response
   - Updates conversation state
   - Returns formatted message to user

### Attendance Marking Flow

1. **User Request** → Frontend sends attendance request
2. **Python App** →
   - Validates user session
   - Detects intent (mark_attendance)
   - Calls Node.js API: `POST /api/attendance/mark`
3. **Node.js Server** →
   - Retrieves session from Redis
   - Formats attendance payload
   - Calls Zimyo clock-in-out API
   - Returns result
4. **Python App** →
   - Returns success/error message to user

## Data Flow

### Session Data
- **Stored in:** Redis
- **Written by:** Python App (during login)
- **Read by:** Both Python App and Node.js Server
- **Contents:**
  - User information
  - Authentication token
  - Leave balance
  - Policy documents
  - Embeddings

### Conversation State
- **Stored in:** Redis
- **Managed by:** Python App
- **Purpose:** Multi-turn conversation handling
- **Contents:**
  - Current action
  - Collected information
  - Context data

## Configuration

### Python App (`.env`)
```env
ZIMYO_PARTNER_ID=your_partner_id
ZIMYO_PARTNER_PASSWORD=your_partner_password
OPENAI_API_KEY=your_openai_key
NODE_API_URL=http://localhost:3000/api
```

### Node.js Server (`.env`)
```env
PORT=3000
ZIMYO_BASE_URL=https://www.zimyo.work/apiv2/auth/hrms
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
NODE_ENV=development
```

## Deployment

### Development
1. Start Redis: `redis-server`
2. Start Node.js Server: `cd zimyo_api_server && npm run dev`
3. Start Python App: `cd zimyo_ai_assistant && uvicorn app:app --reload --port 8080`

### Production
1. Use Docker Compose to orchestrate services
2. Configure environment variables
3. Set up reverse proxy (nginx)
4. Enable SSL/TLS

## Benefits of This Architecture

1. **Separation of Concerns**
   - Python handles AI/ML and business logic
   - Node.js handles external API communications

2. **Scalability**
   - Services can be scaled independently
   - Node.js excels at I/O operations (API calls)
   - Python excels at AI/ML processing

3. **Maintainability**
   - Clear boundaries between components
   - Easier to test and debug
   - Language-specific optimizations

4. **Flexibility**
   - Can add more API integrations to Node.js
   - Can enhance AI capabilities in Python
   - Easy to add new services

## Migration Notes

### What Was Removed
- `mcp_server/` directory - MCP server implementation
- `start_mcp_server.py` - MCP server startup script
- MCP dependency from `requirements.txt`

### What Was Added
- `zimyo_api_server/` - Complete Node.js server
- `services/node_api_client.py` - HTTP client for Node.js API
- Updated `services/mcp_integration.py` - Now uses Node.js API

### Compatibility
- The adapter pattern ensures existing code continues to work
- No changes required to conversation handling logic
- Session management remains unchanged

## Future Enhancements

1. **Add Message Queue** (RabbitMQ/Kafka)
   - Async processing of long-running tasks
   - Better error handling and retries

2. **API Gateway**
   - Centralized authentication
   - Rate limiting
   - Request routing

3. **Monitoring & Logging**
   - ELK Stack for centralized logging
   - Prometheus + Grafana for metrics
   - Distributed tracing

4. **Caching Layer**
   - Redis caching for frequently accessed data
   - Reduce load on external APIs

5. **Testing**
   - Unit tests for both services
   - Integration tests
   - E2E tests
