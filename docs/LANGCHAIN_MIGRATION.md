# LangChain Migration Guide

Complete guide for migrating from manual LLM implementation to LangChain-based HRMS AI Assistant.

## 📋 Table of Contents

1. [Overview](#overview)
2. [What Changed](#what-changed)
3. [Installation](#installation)
4. [Migration Steps](#migration-steps)
5. [Testing](#testing)
6. [Rollback](#rollback)
7. [New Features](#new-features)

---

## 🎯 Overview

This migration replaces manual LLM handling with LangChain for:

- **Better Prompt Management**: Reusable templates instead of hardcoded f-strings
- **Structured Output**: Automatic JSON parsing with validation
- **Memory Integration**: Redis-based chat history compatible with LangChain
- **Observability**: LangSmith tracing for debugging
- **Maintainability**: Standard patterns for LLM applications

---

## 📦 What Changed

### Files Created

```
services/ai/
├── langchain_config.py          # LangChain LLM & memory setup
├── langchain_prompts.py         # All prompt templates
├── hrms_extractor_langchain.py  # New intent extractor (LangChain)
└── chat_langchain.py            # New chat module (LangChain)

migrate_to_langchain.py          # Migration script for Redis data
LANGCHAIN_MIGRATION.md           # This guide
```

### Files Modified

```
requirements.txt                 # Added LangChain packages
```

### Old Files (Still Working)

```
services/ai/
├── hrms_extractor.py            # Old manual implementation
├── chat.py                      # Old manual implementation
└── ...
```

---

## 🚀 Installation

### Step 1: Install New Dependencies

```bash
cd zimyo_ai_assistant

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install new packages
pip install -r requirements.txt
```

**New packages installed:**
- `langchain-google-genai` - Gemini integration
- `langsmith` - Tracing and monitoring

### Step 2: Configure Environment Variables (Optional)

Add to `.env` for LangSmith tracing:

```bash
# Optional: Enable LangSmith for debugging
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=zimyo-hrms-assistant
```

> **Note**: LangSmith is optional. System works without it.

---

## 🔄 Migration Steps

### Option A: Gradual Migration (Recommended)

Test LangChain alongside existing implementation:

#### 1. Test LangChain Components

```python
# Test in Python shell
python

from services.ai.langchain_config import get_llm
from services.ai.langchain_prompts import get_hrms_extraction_prompt
from services.ai.hrms_extractor_langchain import detect_intent_and_extract

# Test intent extraction
result = detect_intent_and_extract(
    user_message="apply sick leave for 4 nov",
    available_leave_types=[{"name": "Sick Leave"}]
)

print(result)
# Should return: {'intent': 'apply_leave', 'ready_to_execute': True, ...}
```

#### 2. Migrate Redis Data

```bash
# Create backup & migrate existing sessions
python migrate_to_langchain.py
```

**What it does:**
- ✅ Creates backup of all Redis data
- ✅ Converts old chat history format to LangChain format
- ✅ Validates migration
- ✅ Preserves all conversation history

**Output:**
```
📦 Step 1: Creating backup...
✅ Backup created: redis_backup_20250110_123456.json (42 keys)

🔍 Step 2: Finding chat history keys...
🔍 Found 15 chat history keys

🔄 Step 3: Migrating 15 keys...
✅ Migrated chat_history:240611:sess123: 8 messages
✅ Migrated chat_history:240611:sess456: 12 messages
...

✅ Step 4: Validating migrations...
✅ Validation passed for all keys

📊 Total keys found: 15
✅ Successfully migrated: 15
❌ Failed migrations: 0
```

#### 3. Switch to LangChain Implementation

Update `services/ai/hrms_extractor.py`:

```python
# OLD (Line 1):
# """
# AI-Powered HRMS Intent & Information Extractor
# ...

# NEW: Replace entire file with:
from services.ai.hrms_extractor_langchain import *
```

Or rename files:

```bash
# Backup old files
mv services/ai/hrms_extractor.py services/ai/hrms_extractor_old.py
mv services/ai/chat.py services/ai/chat_old.py

# Activate new files
mv services/ai/hrms_extractor_langchain.py services/ai/hrms_extractor.py
mv services/ai/chat_langchain.py services/ai/chat.py
```

### Option B: Direct Replacement

Replace everything at once (riskier):

```bash
# Backup
cp services/ai/hrms_extractor.py services/ai/hrms_extractor_backup.py
cp services/ai/chat.py services/ai/chat_backup.py

# Replace
mv services/ai/hrms_extractor_langchain.py services/ai/hrms_extractor.py
mv services/ai/chat_langchain.py services/ai/chat.py

# Migrate data
python migrate_to_langchain.py
```

---

## ✅ Testing

### Test 1: Basic Intent Extraction

```python
from services.ai.hrms_extractor import detect_intent_and_extract

# Test leave application
result = detect_intent_and_extract(
    "apply sick leave for 4 nov health issues",
    available_leave_types=[{"name": "Sick Leave"}, {"name": "Casual Leave"}]
)

assert result['intent'] == 'apply_leave'
assert result['ready_to_execute'] == True
assert 'Sick Leave' in result['extracted_data']['leave_type']
print("✅ Test 1 passed")
```

### Test 2: Conversational Flow

```python
# First message
result1 = detect_intent_and_extract("apply leave")
assert result1['ready_to_execute'] == False
print(f"Question 1: {result1['next_question']}")

# Second message with context
result2 = detect_intent_and_extract(
    "sick",
    user_context={'intent': 'apply_leave', 'extracted_data': {}},
    available_leave_types=[{"name": "Sick Leave"}]
)
assert 'Sick Leave' in str(result2['extracted_data'])
print("✅ Test 2 passed")
```

### Test 3: Chat Response

```python
from services.ai.chat import get_chat_response

response = get_chat_response(
    role="employee",
    prompt="How many leaves do I have?",
    employee_data="Sick Leave: 3.72 days",
    policy_content="Employees get 12 sick leaves per year"
)

assert "3.72" in response or "leave" in response.lower()
print("✅ Test 3 passed")
```

### Test 4: End-to-End API Test

```bash
# Start server
cd zimyo_ai_assistant
source venv/bin/activate
uvicorn app:app --reload --port 8000

# In another terminal, test API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "240611",
    "message": "apply sick leave for today",
    "sessionId": "test123"
  }'
```

Expected response:
```json
{
  "response": "किस कारण से छुट्टी चाहिए? What's the reason?",
  "sessionId": "test123"
}
```

---

## 🔙 Rollback

If something goes wrong, rollback to old implementation:

### Option 1: Restore Files

```bash
# Restore old implementations
mv services/ai/hrms_extractor_backup.py services/ai/hrms_extractor.py
mv services/ai/chat_backup.py services/ai/chat.py

# Restart server
pkill -f uvicorn
uvicorn app:app --reload --port 8000
```

### Option 2: Restore Redis Data

```bash
# Find backup file
ls redis_backup_*.json

# Rollback
python migrate_to_langchain.py rollback redis_backup_20250110_123456.json
```

---

## 🎁 New Features

### 1. LangSmith Tracing

Debug and monitor LLM calls in real-time:

```bash
# Enable in .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=zimyo-hrms

# View traces at https://smith.langchain.com/
```

### 2. Reusable Prompts

```python
from services.ai.langchain_prompts import get_prompt

# Get any prompt by name
hrms_prompt = get_prompt("hrms_extraction")
employee_chat = get_prompt("employee_chat")
hr_content = get_prompt("hr_content")
```

### 3. Structured Output Validation

```python
from services.ai.langchain_config import get_llm, get_json_parser

llm = get_llm()
parser = get_json_parser()  # Auto-validates JSON

chain = prompt | llm | parser
result = chain.invoke({"input": "..."})
# Result is guaranteed to be valid JSON dict
```

### 4. Easy LLM Switching

```python
from services.ai.langchain_config import get_llm

# Change in .env:
# LLM_PROVIDER=gemini  (or openai, deepseek)

llm = get_llm()  # Automatically uses configured provider
```

### 5. Memory Management

```python
from services.ai.langchain_config import get_session_history

# Get chat history for any session
history = get_session_history("240611", "sess123")
history.add_user_message("Hello")
history.add_ai_message("Hi! How can I help?")

# Messages auto-saved to Redis with TTL
```

---

## 📊 Comparison

| Feature | Old (Manual) | New (LangChain) |
|---------|-------------|-----------------|
| Prompt management | ❌ Hardcoded f-strings | ✅ Reusable templates |
| JSON parsing | ❌ Manual try/catch | ✅ Auto-validated |
| Memory | ✅ Custom Redis | ✅ Standard Redis + LangChain |
| Tracing | ❌ Only logs | ✅ LangSmith UI |
| LLM switching | ⚠️ Manual if/else | ✅ Config-based |
| Prompt versioning | ❌ Git only | ✅ Template registry |
| Error handling | ⚠️ Basic | ✅ Structured |
| Testing | ⚠️ Manual | ✅ Chainable components |

---

## 🐛 Troubleshooting

### Issue 1: Import Error

```
ImportError: cannot import name 'ChatGoogleGenerativeAI'
```

**Solution:**
```bash
pip install --upgrade langchain-google-genai
```

### Issue 2: Redis Connection Error

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solution:**
```bash
# Start Redis
redis-server

# Or check Redis config in config.py
```

### Issue 3: LangSmith Traces Not Showing

**Solution:**
- Verify `LANGCHAIN_TRACING_V2=true` in `.env`
- Check API key is valid
- Visit https://smith.langchain.com/

### Issue 4: Different Output Format

**Solution:**
LangChain returns same format as old implementation. If seeing issues:

```python
# Old: direct dict
result = {'intent': 'apply_leave', ...}

# New: also returns dict (no change needed)
result = detect_intent_and_extract("...")  # Same format
```

---

## 📞 Support

**Questions?**
- Check existing logs: `tail -f app.log`
- Test individual components (see Testing section)
- Rollback if needed (see Rollback section)

**Found a bug?**
- Check `COMPREHENSIVE_BUG_SUMMARY.md`
- Add to bug tracker

---

## ✅ Migration Checklist

- [ ] Install new dependencies (`pip install -r requirements.txt`)
- [ ] Test LangChain components in Python shell
- [ ] Run migration script (`python migrate_to_langchain.py`)
- [ ] Verify migration success (check logs)
- [ ] Switch to new implementation (rename files)
- [ ] Run all tests (see Testing section)
- [ ] Test API endpoints (curl/Postman)
- [ ] Monitor logs for errors
- [ ] Enable LangSmith (optional)
- [ ] Create backup plan (rollback instructions)

---

## 🎉 Success!

You've successfully migrated to LangChain! Your HRMS AI Assistant now has:

✅ Professional prompt management
✅ Structured output parsing
✅ Better error handling
✅ Observability with LangSmith
✅ Maintainable codebase
✅ Industry-standard patterns

**Next steps:**
- Monitor performance in production
- Experiment with prompt improvements
- Add new LangChain features (agents, tools)
- Share feedback with team

---

*Migration completed by Zimyo AI Team*
