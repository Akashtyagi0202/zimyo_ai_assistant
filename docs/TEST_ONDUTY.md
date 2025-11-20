# On-Duty Feature - Test & Debug Guide

## Current Issues:
1. Server not running with latest code (logs from Nov 4)
2. Need fresh restart to load changes
3. Multiple fallback layers may have bugs

## Simple Test After Restart:

### Step 1: Restart Server
```bash
cd "/Users/akashtyagi/Documents/code/zimyo ai/zimyo_ai_assistant"
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

### Step 2: Test Messages
```
User: "apply on duty for today"
Expected: "किस समय से किस समय तक?"

User: "9am to 6pm"
Expected: "कारण बताएं?"

User: "wfh"
Expected: "✅ On-duty applied!"
```

## If Still Failing:

Check server terminal for actual error - look for:
- `🎯 Pre-filter: Detected ON-DUTY intent`
- `🔧 Fallback regex extracted time`
- `🔧 Fallback: Using entire message as reason`

If none appear → Code not loaded
If appear but still error → Share EXACT error from terminal
