# On-Duty Feature - Complete Debug Guide

## Files Modified (Summary)

### 1. services/ai/hrms_extractor.py
**Changes:**
- Line 74-78: Added context flow tracking (`previous_intent`)
- Line 82-177: Pre-filter for on-duty (keyword + context detection)
- Line 101-135: Regex fallback for time extraction ("9am to 6pm")
- Line 154-163: Reason fallback (use entire message if only reason missing)

### 2. services/operations/hrms_handlers/apply_onduty.py
**Created - Complete file**
- Handles on-duty application with conversation flow
- Required fields: date, from_time, to_time, reason
- Calculates total_hours automatically
- Calls MCP tool: `apply_onduty`

### 3. Node.js Files (MCP + Controller)
- `src/controllers/onduty.controller.js` - Created
- `src/mcp/handlers/onduty.handler.js` - Created
- `src/mcp/server.js` - Updated (registered OnDutyHandler)

## Debug Steps (DO IN ORDER)

### Step 1: Restart Server
```bash
cd "/Users/akashtyagi/Documents/code/zimyo ai/zimyo_ai_assistant"
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

**Watch for:**
- `INFO: Application startup complete.` ← Server started
- No syntax errors

### Step 2: Test Message 1
**Send:** `apply on duty for today`

**Look for in terminal:**
```
🎯 Pre-filter: Detected ON-DUTY intent
⚠️ AI returned 'XXXX' for on-duty, forcing to apply_onduty
🔄 Merged data: prev=[...], new=[...], merged=[...]
✅ On-duty extraction: ready=False, merged_fields=['date'], values={...}
```

**Expected Response:** `"किस समय से किस समय तक? What time range?"`

### Step 3: Test Message 2
**Send:** `9am to 6pm`

**Look for in terminal:**
```
🎯 Pre-filter: Detected ON-DUTY intent  (← Because previous_intent = 'apply_onduty')
🔧 Fallback regex extracted time: 09:00 to 18:00  (← Regex worked!)
🔄 Merged data: prev=['date'], new=['from_time','to_time'], merged=['date','from_time','to_time']
✅ On-duty extraction: ready=False, merged_fields=['date','from_time','to_time'], values={...}
```

**Expected Response:** `"कारण बताएं? Reason?"`

### Step 4: Test Message 3
**Send:** `wfh`

**Look for in terminal:**
```
🎯 Pre-filter: Detected ON-DUTY intent
🔧 Fallback: Using entire message as reason: 'wfh'  (← Reason fallback!)
✅ On-duty extraction: ready=True, merged_fields=['date','from_time','to_time','reason']
📤 Applying on-duty: 2025-11-05 09:00-18:00 (09:00:00)
```

**Expected Response:** `"✅ On-duty applied successfully!"`

## If It Fails

### Error: "मुझे समझ नहीं आया"
**Cause:** Pre-filter not triggering
**Check:**
1. Is `🎯 Pre-filter: Detected ON-DUTY intent` in logs? NO → Code not loaded
2. Is previous_intent being saved? Check for `💾 Context saved`

### Error: Time loop (keeps asking for time)
**Cause:** Regex not extracting OR data not merging
**Check:**
1. Look for `🔧 Fallback regex extracted time` in logs
2. Look for `🔄 Merged data` - check if 'from_time', 'to_time' in merged list
3. If not there → Regex pattern issue OR merge logic issue

### Error: Reason loop (keeps asking for reason)
**Cause:** Reason fallback not working OR data not merging
**Check:**
1. Look for `🔧 Fallback: Using entire message as reason`
2. Look for merged_fields - check if 'reason' appears
3. If not there → Fallback condition issue

### Error: "❌ कुछ गड़बड़ हो गई"
**Cause:** Handler crashed / MCP call failed
**Check terminal for actual Python exception**
- Likely in `services/operations/hrms_handlers/apply_onduty.py`
- Look for red ERROR/Traceback lines

## Quick Verification Commands

Check if files exist:
```bash
ls -la services/operations/hrms_handlers/apply_onduty.py
ls -la src/controllers/onduty.controller.js
ls -la src/mcp/handlers/onduty.handler.js
```

Check if pre-filter code exists:
```bash
grep -n "🎯 Pre-filter: Detected ON-DUTY" services/ai/hrms_extractor.py
```

## Send Me
If still failing, copy-paste from terminal:
1. The EXACT error/exception (full traceback)
2. All log lines starting with 🎯, 🔧, 🔄, ✅ for your 3 test messages
