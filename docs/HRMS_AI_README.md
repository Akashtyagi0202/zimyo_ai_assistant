# HRMS Conversational AI Assistant

A comprehensive, production-ready HRMS conversational AI assistant that handles multilingual queries, auto-detects intents, and integrates seamlessly with existing Redis-based policy systems.

## 🚀 Features

### Core Capabilities
- **Multilingual Support**: English, Hindi, Hinglish with automatic language detection
- **Intent Detection**: 6 core HR intents with high accuracy
- **Confidence-Based Clarification**: Asks clarifying questions when confidence is low
- **Redis Integration**: Uses existing policy data stored during login
- **Extensible Architecture**: Modular design for easy customization

### Supported Intents

1. **`leave_policy_query`** - Policy information requests
   - "What's my leave policy?"
   - "If I take Friday and Monday leave, will sandwich apply?"
   - "छुट्टी की नीति क्या है?"

2. **`apply_leave`** - Leave application requests
   - "Apply my leave from Friday to Monday"
   - "I need sick leave for 2 days"
   - "Chutti lagwa do"

3. **`mark_attendance`** - Attendance marking
   - "Mark my attendance"
   - "Punch in"
   - "हाजिरी लगाओ"

4. **`check_leave_balance`** - Leave balance inquiries
   - "Show my available leave balance"
   - "How many leaves do I have left?"
   - "कितनी छुट्टी बची है?"

5. **`create_job_description`** - Job description generation
   - "Create JD for Node.js developer with 5 years' experience"
   - "Generate job description for Python developer"

6. **`general_hr_query`** - General HR questions
   - "Company benefits"
   - "HR policies"
   - "Insurance information"

## 🏗️ Architecture

### System Components

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   User Query        │    │  Language Detector  │    │  Intent Classifier  │
│  (Any Language)     │───▶│  • English          │───▶│  • Pattern Matching │
│                     │    │  • Hindi            │    │  • Entity Extraction│
└─────────────────────┘    │  • Hinglish         │    │  • Confidence Score │
                           └─────────────────────┘    └─────────────────────┘
                                      │                           │
                                      ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Redis Data        │    │  AI Assistant       │    │  Integration Layer  │
│  • User Policies    │◄───│  • Process Query    │───▶│  • Route to Systems │
│  • Embeddings       │    │  • Generate Response│    │  • Format Response  │
│  • User Info        │    │  • Handle Entities  │    │  • Add Metadata     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### Data Flow

1. **Input Processing**
   - User sends query in any language
   - Language detection with confidence scoring
   - Intent classification with entity extraction

2. **Decision Making**
   - Confidence evaluation
   - Clarification generation if needed
   - Route determination

3. **Response Generation**
   - Direct AI response (policy queries, job descriptions)
   - Route to existing systems (leave application, attendance)
   - Use Redis policy data for context

## 📁 File Structure

```
services/
├── hrms_ai_assistant.py     # Core AI assistant logic
├── hrms_integration.py      # Integration layer
└── embeddings.py           # Existing embedding utilities

tests/
└── test_hrms_ai_system.py  # Comprehensive test suite

examples/
├── hrms_app_integration.py # Example FastAPI integration
└── HRMS_AI_README.md       # This documentation
```

## 🚀 Quick Start

### 1. Basic Integration

Replace your existing intent detection with the new AI system:

```python
from services.hrms_integration import process_hrms_query

@app.post("/chat")
async def chat(message: Message):
    result = await process_hrms_query(redis_client, message.userId, message.message, message.sessionId)
    return result
```

### 2. Advanced Integration

Handle different response types:

```python
result = await process_hrms_query(redis_client, user_id, query)

if result.get("requires_clarification"):
    # Show clarification question
    return {"response": result["response"]}

elif result.get("use_existing_leave_system"):
    # Route to existing leave application
    from services.mcp_integration import handle_leave_application
    return await handle_leave_application(user_id, query, None, session_id)

elif result.get("use_policy_search"):
    # Use existing policy search with AI context
    return handle_policy_search_with_ai_context(result)

elif "response" in result:
    # Direct AI response
    return {"response": result["response"]}
```

### 3. Direct AI Assistant Usage

```python
from services.hrms_ai_assistant import HRMSAIAssistant

assistant = HRMSAIAssistant(redis_client)
result = await assistant.process_query(user_id, "What is my leave policy?")
```

## 📋 API Response Format

### Successful Response
```json
{
  "response": "📋 Here's your leave policy information...",
  "intent": "leave_policy_query",
  "confidence": 0.95,
  "language": "english",
  "ai_metadata": {
    "intent": "leave_policy_query",
    "confidence": 0.95,
    "language": "english"
  }
}
```

### Clarification Required
```json
{
  "response": "I understand you want to apply for leave. Could you please specify the dates and type of leave?",
  "intent": "apply_leave",
  "confidence": 0.45,
  "language": "english",
  "requires_clarification": true
}
```

### Route to Existing System
```json
{
  "use_existing_leave_system": true,
  "intent": "apply_leave",
  "confidence": 0.89,
  "language": "english",
  "extracted_entities": {
    "dates": ["2025-03-15", "2025-03-17"],
    "leave_type": "sick"
  }
}
```

## 🔧 Configuration

### Confidence Thresholds

```python
# In IntentClassifier class
self.confidence_threshold = 0.7        # High confidence threshold
self.min_confidence_threshold = 0.4    # Minimum threshold for processing
```

### Language Patterns

Add new language support by extending patterns in `LanguageDetector`:

```python
self.language_patterns = {
    Language.SPANISH: {
        'words': ['licencia', 'política', 'asistencia'],
        'patterns': [r'\b(licencia|política|asistencia)\b']
    }
}
```

### Intent Patterns

Add new intents by extending `IntentClassifier._build_intent_patterns()`:

```python
Intent.NEW_INTENT: {
    'english': [r'\b(pattern1|pattern2)\b'],
    'hindi': [r'हिंदी_पैटर्न'],
    'hinglish': [r'\b(hinglish_pattern)\b']
}
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_hrms_ai_system.py
```

The test suite covers:
- Language detection accuracy
- Intent classification precision
- Policy query handling
- Multilingual support
- Confidence system
- Integration layer

## 🔍 Monitoring & Debugging

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Response Metadata

All responses include AI metadata for monitoring:

```json
{
  "ai_metadata": {
    "intent": "leave_policy_query",
    "confidence": 0.95,
    "language": "english",
    "used_policy_search": true
  }
}
```

## 🚀 Production Deployment

### 1. Dependencies

Ensure these are in your `requirements.txt`:

```
sentence-transformers>=2.0.0
numpy>=1.21.0
redis>=4.0.0
fastapi>=0.68.0
pydantic>=1.8.0
```

### 2. Redis Data Structure

The system expects this Redis structure (created during login):

```json
{
  "userId": "EMP001",
  "role": "employee",
  "user_info": {...},
  "user_policies": {
    "leave_policy.pdf": "Full policy text...",
    "attendance_policy.pdf": "Full policy text..."
  },
  "policy_embeddings": {
    "leave_policy.pdf": [0.1, 0.2, 0.3, ...],
    "attendance_policy.pdf": [0.4, 0.5, 0.6, ...]
  },
  "token": "user_token"
}
```

### 3. Performance Optimization

- **Embedding Model Caching**: Load SentenceTransformer once at startup
- **Redis Connection Pooling**: Use connection pools for high concurrency
- **Response Caching**: Cache frequently asked policy questions

### 4. Error Handling

The system includes comprehensive error handling:
- Graceful fallback to existing systems
- User-friendly error messages
- Detailed logging for debugging

## 🎯 Use Cases

### 1. Employee Self-Service
- **Query**: "What's my leave policy?"
- **Response**: Intelligent policy extraction from Redis data

### 2. Smart Leave Application
- **Query**: "I need sick leave from Friday to Monday"
- **Response**: Routes to existing leave system with extracted entities

### 3. Multilingual Support
- **Query**: "मेरी छुट्टी का बैलेंस दिखाओ"
- **Response**: Detects Hindi, routes to balance system

### 4. Job Description Generation
- **Query**: "Create JD for Node.js developer with 3 years experience"
- **Response**: Generates comprehensive job description

### 5. Clarification Handling
- **Query**: "Something about leave"
- **Response**: "I understand you're asking about leave. Could you be more specific?"

## 🔄 Migration from Existing System

### Step 1: Parallel Deployment
Deploy alongside existing system for testing:

```python
# Try new AI system first, fallback to existing
try:
    result = await process_hrms_query(redis_client, user_id, query)
    if not result.get("error"):
        return result
except Exception:
    pass

# Fallback to existing system
return existing_chat_handler(message)
```

### Step 2: Gradual Migration
Route specific intents to new system:

```python
ai_handled_intents = ["leave_policy_query", "create_job_description"]
if result.get("intent") in ai_handled_intents:
    return result
else:
    return existing_system_handler(message)
```

### Step 3: Full Migration
Replace existing system entirely:

```python
@app.post("/chat")
async def chat(message: Message):
    return await process_hrms_query(redis_client, message.userId, message.message)
```

## 🎉 Benefits

1. **Improved User Experience**
   - Natural language understanding
   - Multilingual support
   - Intelligent clarification

2. **Reduced Development Effort**
   - No hard-coded rules
   - Automatic entity extraction
   - Seamless integration

3. **Better Accuracy**
   - AI-powered intent detection
   - Confidence-based processing
   - Context-aware responses

4. **Scalable Architecture**
   - Modular design
   - Easy to extend
   - Production-ready

## 📞 Support

For issues or questions:
1. Check the test suite for examples
2. Review the integration documentation
3. Enable debug logging for troubleshooting
4. Refer to the confidence scores for intent accuracy

---

**Built with ❤️ for modern HRMS systems**