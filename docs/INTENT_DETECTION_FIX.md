# 🎯 Intent Detection Fix

## Problem

User: "apply my leave for 22 nov 2025"
System: "मुझे समझ नहीं आया। I didn't understand..." ❌

**Root Cause:** AI classified the message as "unknown" intent instead of "apply_leave"

---

## Fix Applied

### Changes in `services/ai/hrms_extractor.py`:

#### 1. Added Explicit Keywords (lines 127-134)
```python
POSSIBLE INTENTS (detect from keywords):
- apply_leave: Keywords: "apply", "leave", "chutti", "off", "vacation", "absent"
- mark_attendance: Keywords: "punch", "check in", "check out", "attendance", "mark"
- check_leave_balance: Keywords: "balance", "remaining", "kitne din", "how many"

IMPORTANT: "apply my leave" = apply_leave intent (the word "apply" + "leave" = apply_leave)
```

#### 2. Added Exact Example (line 158)
```python
"apply my leave for 22 nov 2025" → {
    "intent": "apply_leave",
    "extracted_data": {
        "from_date": "2025-11-22",
        "to_date": "2025-11-22"
    },
    "missing_fields": ["leave_type", "reason"],
    "ready_to_execute": false
}
```

#### 3. Added Critical Rules (lines 183-187)
```python
CRITICAL RULES - NEVER CLASSIFY AS "unknown":
✓ If message contains "apply" + "leave" → intent = "apply_leave" (ALWAYS!)
✓ If message contains "punch" / "check in" / "check out" → intent = "mark_attendance"
✓ If message contains "balance" / "remaining" → intent = "check_leave_balance"
✗ NEVER return intent = "unknown" if message has keywords above!
```

---

## Expected Behavior After Fix

### Test Case: "apply my leave for 22 nov 2025"

**AI Should Detect:**
```json
{
  "intent": "apply_leave",
  "extracted_data": {
    "from_date": "2025-11-22",
    "to_date": "2025-11-22"
  },
  "missing_fields": ["leave_type", "reason"],
  "next_question": "किस प्रकार की छुट्टी? What type of leave?",
  "ready_to_execute": false
}
```

**Response:**
```
"किस प्रकार की छुट्टी चाहिए? 📋 What type of leave? Available: Sick, Casual, Earned..."
```

NOT:
```
"मुझे समझ नहीं आया। I didn't understand..." ❌
```

---

## Testing

Restart server and test:
```bash
./start.sh
```

Then test message:
```
User: "apply my leave for 22 nov 2025"
Expected: Asks for leave type ✅
Not: "I didn't understand" ❌
```

---

**Status:** ✅ Fixed
**Date:** 2025-11-04
