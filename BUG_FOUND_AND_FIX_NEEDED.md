# BUG FOUND - On-Duty Feature

## Test Results

✅ **Fixed:** Gemini JSON truncation (max_output_tokens: 800 → 2000)
❌ **New Bug:** Conversation context not preserved between messages

## Bug Details

### Symptoms
1. Message 1: "apply on duty for today" → ✅ Asks for time correctly
2. Message 2: "9am to 6pm" → ❌ Returns "I didn't understand"

### Root Cause

**Intent is being overwritten to "unknown" in Redis!**

Logs show:
- Message 1: AI detects `intent: "apply_onduty"` ✓
- Message 1: Saves to Redis ✓
- **BUT Redis contains: `intent: "unknown"`** ✗

This causes Message 2 to fail because:
```python
# hrms_extractor.py:76-77
previous_intent = user_context.get('intent')  # Gets 'unknown' instead of 'apply_onduty'
in_onduty_flow = (previous_intent == 'apply_onduty')  # FALSE!
```

Pre-filter doesn't trigger → AI analyzes "9am to 6pm" alone → Returns "unknown"

### Evidence

**After Message 1, Redis shows:**
```json
{
  "intent": "unknown",  ← WRONG! Should be "apply_onduty"
  "extracted_data": {
    "date": "2025-11-05"  ← Correct
  }
}
```

**Server logs show:**
```
07:07:45 - Intent: apply_onduty | Ready: False  ← AI detected correctly
07:07:45 - Saved conversation state  ← Saved
07:12:49 - Analyzing: '9am to 6pm'
07:12:49 - (NO pre-filter log)  ← Pre-filter didn't trigger!
```

## Where to Look

The bug is in the flow between:
1. `services/operations/ai_handler.py` lines 100-104 (saves intent)
2. `services/operations/ai_handler.py` lines 271-274 (overwrites to "unknown"?)

**Hypothesis:** After the correct intent is saved, something triggers the "unknown intent" handler at line 265-279 which overwrites it.

## Fix Needed

Need to trace why the unknown intent handler (lines 265-279) is being called AFTER the correct handler returns. Possibilities:
1. Handler returns None when it shouldn't
2. There's a duplicate update_conversation_state call
3. The routing logic falls through to the unknown handler

## Files to Check

1. `services/operations/ai_handler.py` - Main flow (lines 42-121, 265-279)
2. `services/operations/hrms_handlers/apply_onduty.py` - Handler return value
3. `services/operations/conversation_state.py` - Update logic

## Test Command to Reproduce

```bash
# Clear state
redis-cli DEL "conversation_state:240611:legacy"

# Test 1
curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"userId":"240611","message":"apply on duty for today"}'
# Expected: Asks for time ✓

# Check Redis
redis-cli GET "conversation_state:240611:legacy" | python3 -m json.tool
# BUG: Shows intent="unknown" instead of "apply_onduty"

# Test 2
curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"userId":"240611","message":"9am to 6pm"}'
# Expected: Asks for reason
# Actual: "I didn't understand" ✗
```

## Current Status

- ✅ Server running with fixes on port 8080
- ✅ Gemini JSON truncation fixed
- ✅ Pre-filter logic correct
- ✅ Regex fallbacks correct
- ✅ Data merging logic correct
- ❌ Intent preservation broken

The multiple fallback layers I added ARE working, but they can't help if the intent is lost between messages.
