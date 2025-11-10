"""
AI-Powered HRMS Intent & Information Extractor

This module uses LLM (Language Model) to intelligently understand what users want
and extract relevant information from natural language.

Example:
    User: "apply sick leave for 4 nov my health is not good"

    AI extracts:
    - Intent: apply_leave
    - Leave type: Sick Leave
    - Date: 2025-11-04
    - Reason: my health is not good

    → Ready to execute!

Author: Zimyo AI Team
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN AI FUNCTION
# ============================================================================

def detect_intent_and_extract(
    user_message: str,
    user_context: Dict = None,
    available_leave_types: list = None
) -> Dict[str, Any]:
    """
    Use AI to detect user intent and extract structured information.

    This is the MAIN BRAIN of the system. It understands what user wants
    and extracts all relevant information.

    Args:
        user_message: What user typed (e.g., "apply leave for 5 nov")
        user_context: Previous conversation data (optional)
        available_leave_types: List of leave types for this user (optional)

    Returns:
        Dictionary with:
        - intent: What user wants (apply_leave, check_in, leave_balance, etc.)
        - extracted_data: Information found in message
        - missing_fields: What's still needed
        - next_question: What to ask user next (if info missing)
        - ready_to_execute: True if we have all info needed

    Example:
        >>> result = detect_intent_and_extract("apply sick leave for 4 nov")
        >>> result['intent']
        'apply_leave'
        >>> result['extracted_data']
        {'leave_type': 'Sick Leave', 'from_date': '2025-11-04'}
    """
    # Initialize defaults
    user_context = user_context or {}
    available_leave_types = available_leave_types or []

    # ============================================================================
    # PRODUCTION FIX: Keyword-based pre-filter for critical intents
    # This ensures reliability even if AI fails - catches patterns BEFORE AI call
    # ============================================================================
    message_lower = user_message.lower()

    # CRITICAL: Check if we're in an ongoing conversation (context exists)
    # If previous intent was on-duty/regularization, continue with that intent
    previous_intent = user_context.get('intent')
    in_onduty_flow = (previous_intent == 'apply_onduty')
    in_regularization_flow = (previous_intent == 'apply_regularization')

    # Priority 1: On-duty detection (WFH, client site, field work)
    # Trigger if: (1) Keywords found OR (2) Already in on-duty conversation
    if in_onduty_flow or any(keyword in message_lower for keyword in ['on duty', 'onduty', 'on-duty', 'wfh', 'work from home']):
        logger.info("🎯 Pre-filter: Detected ON-DUTY intent")

        # Get previous context
        prev_data = user_context.get('extracted_data', {})

        # Try AI extraction first
        ai_response = _call_ai_model(_build_ai_prompt(user_message, user_context, available_leave_types))

        # Force intent to apply_onduty if AI got it wrong
        if ai_response.get('intent') != 'apply_onduty':
            logger.warning(f"⚠️ AI returned '{ai_response.get('intent')}' for on-duty, forcing to apply_onduty")
            ai_response['intent'] = 'apply_onduty'

        # CRITICAL: Merge previous context with new extracted data
        # This ensures conversation accumulates information
        extracted = ai_response.get('extracted_data', {})

        # FALLBACK: If AI failed to extract time, use regex pattern matching
        if not extracted.get('from_time') or not extracted.get('to_time'):
            import re
            # Pattern: "9am to 6pm", "9:30am to 6:30pm", "09:00 to 18:00", etc.
            time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?\s*(?:to|till|-)\s*(\d{1,2}):?(\d{2})?\s*(am|pm)?'
            match = re.search(time_pattern, message_lower, re.IGNORECASE)

            if match:
                # Extract from_time
                from_hour = int(match.group(1))
                from_min = match.group(2) or "00"
                from_period = (match.group(3) or "").lower()

                # Convert to 24hr
                if from_period == "pm" and from_hour != 12:
                    from_hour += 12
                elif from_period == "am" and from_hour == 12:
                    from_hour = 0

                extracted['from_time'] = f"{from_hour:02d}:{from_min}"

                # Extract to_time
                to_hour = int(match.group(4))
                to_min = match.group(5) or "00"
                to_period = (match.group(6) or "").lower()

                # Convert to 24hr
                if to_period == "pm" and to_hour != 12:
                    to_hour += 12
                elif to_period == "am" and to_hour == 12:
                    to_hour = 0

                extracted['to_time'] = f"{to_hour:02d}:{to_min}"

                logger.info(f"🔧 Fallback regex extracted time: {extracted['from_time']} to {extracted['to_time']}")
                ai_response['extracted_data'] = extracted

        # Merge: previous data + new data (new data overwrites)
        merged_data = {
            **prev_data,  # Old data
            **extracted   # New data (overwrites duplicates)
        }

        # Update AI response with merged data
        ai_response['extracted_data'] = merged_data

        logger.debug(f"🔄 Merged data: prev={list(prev_data.keys())}, new={list(extracted.keys())}, merged={list(merged_data.keys())}")

        # Build conversation - check what's missing
        has_date = merged_data.get('date')
        has_from_time = merged_data.get('from_time')
        has_to_time = merged_data.get('to_time')
        has_reason = merged_data.get('reason')

        # CRITICAL FALLBACK: If only reason is missing and user sent a simple text message
        # Then treat the entire message as the reason!
        if has_date and has_from_time and has_to_time and not has_reason:
            # User sent something and we're waiting for reason
            # Use the entire user message as reason (strip whitespace)
            if user_message and len(user_message.strip()) > 0:
                merged_data['reason'] = user_message.strip()
                has_reason = True
                ai_response['extracted_data'] = merged_data  # Update response!
                logger.info(f"🔧 Fallback: Using entire message as reason: '{merged_data['reason']}'")

        # Override ready_to_execute based on actual field presence
        if has_date and has_from_time and has_to_time and has_reason:
            ai_response['ready_to_execute'] = True
            ai_response['missing_fields'] = []
            ai_response['next_question'] = None
        else:
            ai_response['ready_to_execute'] = False
            # Generate appropriate next question
            if not has_date:
                ai_response['next_question'] = "किस तारीख के लिए on-duty चाहिए? For which date do you need on-duty?"
                ai_response['missing_fields'] = ['date']
            elif not has_from_time or not has_to_time:
                ai_response['next_question'] = "किस समय से किस समय तक? What time range? (e.g., 9am to 6pm)"
                ai_response['missing_fields'] = ['from_time', 'to_time'] if not has_from_time else ['to_time']
            elif not has_reason:
                ai_response['next_question'] = "कारण बताएं? Reason? (e.g., WFH, Client meeting, Field work)"
                ai_response['missing_fields'] = ['reason']

        logger.info(f"✅ On-duty extraction: ready={ai_response['ready_to_execute']}, merged_fields={list(merged_data.keys())}, values={merged_data}")
        return _validate_ai_response(ai_response)

    # Priority 2: Regularization detection
    # Trigger if: (1) Keywords found OR (2) Already in regularization conversation
    if in_regularization_flow or any(keyword in message_lower for keyword in ['regularize', 'regularization', 'forgot to punch', 'missed punch', 'forgot punch']):
        logger.info("🎯 Pre-filter: Detected REGULARIZATION intent")

        # Get previous context
        prev_data = user_context.get('extracted_data', {})

        # Try AI extraction
        ai_response = _call_ai_model(_build_ai_prompt(user_message, user_context, available_leave_types))

        # Force intent if AI missed it
        if ai_response.get('intent') != 'apply_regularization':
            logger.warning(f"⚠️ AI returned '{ai_response.get('intent')}' for regularization, forcing intent")
            ai_response['intent'] = 'apply_regularization'

        # CRITICAL: Merge previous context with new extracted data
        extracted = ai_response.get('extracted_data', {})

        # FALLBACK: If AI failed to extract time, use regex pattern matching
        if not extracted.get('from_time') or not extracted.get('to_time'):
            import re
            time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?\s*(?:to|till|-)\s*(\d{1,2}):?(\d{2})?\s*(am|pm)?'
            match = re.search(time_pattern, message_lower, re.IGNORECASE)

            if match:
                from_hour = int(match.group(1))
                from_min = match.group(2) or "00"
                from_period = (match.group(3) or "").lower()

                if from_period == "pm" and from_hour != 12:
                    from_hour += 12
                elif from_period == "am" and from_hour == 12:
                    from_hour = 0

                extracted['from_time'] = f"{from_hour:02d}:{from_min}"

                to_hour = int(match.group(4))
                to_min = match.group(5) or "00"
                to_period = (match.group(6) or "").lower()

                if to_period == "pm" and to_hour != 12:
                    to_hour += 12
                elif to_period == "am" and to_hour == 12:
                    to_hour = 0

                extracted['to_time'] = f"{to_hour:02d}:{to_min}"

                logger.info(f"🔧 Fallback regex extracted time: {extracted['from_time']} to {extracted['to_time']}")
                ai_response['extracted_data'] = extracted

        # Merge: previous data + new data (new data overwrites)
        merged_data = {
            **prev_data,  # Old data
            **extracted   # New data (overwrites duplicates)
        }

        # Update AI response with merged data
        ai_response['extracted_data'] = merged_data

        logger.debug(f"🔄 Merged data: prev={list(prev_data.keys())}, new={list(extracted.keys())}, merged={list(merged_data.keys())}")

        # Check what's missing
        has_date = merged_data.get('date')
        has_from_time = merged_data.get('from_time')
        has_to_time = merged_data.get('to_time')
        has_reason = merged_data.get('reason')

        # CRITICAL FALLBACK: If only reason is missing, use entire message as reason
        if has_date and has_from_time and has_to_time and not has_reason:
            if user_message and len(user_message.strip()) > 0:
                merged_data['reason'] = user_message.strip()
                has_reason = True
                ai_response['extracted_data'] = merged_data  # Update response!
                logger.info(f"🔧 Fallback: Using entire message as reason: '{merged_data['reason']}'")

        # Set ready_to_execute intelligently
        if has_date and has_from_time and has_to_time and has_reason:
            ai_response['ready_to_execute'] = True
            ai_response['missing_fields'] = []
            ai_response['next_question'] = None
        else:
            ai_response['ready_to_execute'] = False
            # Generate next question
            if not has_date:
                ai_response['next_question'] = "किस तारीख की attendance regularize करनी है? Which date?"
                ai_response['missing_fields'] = ['date']
            elif not has_from_time or not has_to_time:
                ai_response['next_question'] = "आप किस समय से किस समय तक थे? What time range? (e.g., 9am to 6pm)"
                ai_response['missing_fields'] = ['from_time', 'to_time'] if not has_from_time else ['to_time']
            elif not has_reason:
                ai_response['next_question'] = "कारण? Reason? (e.g., Forgot to punch, System issue)"
                ai_response['missing_fields'] = ['reason']

        logger.info(f"✅ Regularization extraction: ready={ai_response['ready_to_execute']}, merged_fields={list(merged_data.keys())}, values={merged_data}")
        return _validate_ai_response(ai_response)

    # Priority 3: Holiday query detection
    if any(keyword in message_lower for keyword in ['holiday', 'holidays', 'upcoming holiday', 'chutti list']):
        logger.info("🎯 Pre-filter: Detected HOLIDAY intent")
        return {
            'intent': 'get_holidays',
            'confidence': 1.0,
            'extracted_data': {},
            'missing_fields': [],
            'next_question': None,
            'ready_to_execute': True
        }

    # Priority 4: Leave balance query (simple, no AI needed)
    if any(keyword in message_lower for keyword in ['leave balance', 'balance', 'remaining leave']):
        logger.info("🎯 Pre-filter: Detected BALANCE query")
        return {
            'intent': 'check_leave_balance',
            'confidence': 1.0,
            'extracted_data': {},
            'missing_fields': [],
            'next_question': None,
            'ready_to_execute': True
        }

    # Priority 5: Salary slip query detection
    if any(keyword in message_lower for keyword in ['salary', 'payslip', 'pay slip', 'salary slip', 'वेतन', 'वेतन पर्ची', 'pay']):
        logger.info("🎯 Pre-filter: Detected SALARY SLIP intent")

        # Try to extract month and year from message using AI
        ai_response = _call_ai_model(_build_ai_prompt(user_message, user_context, available_leave_types))

        # Force intent to get_salary_slip
        extracted_data = ai_response.get('extracted_data', {})
        month = extracted_data.get('month')
        year = extracted_data.get('year')

        # Smart default: Check for "last month" / "previous month" keywords
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # Check if user is asking for last/previous month
        last_month_keywords = ['last month', 'previous month', 'पिछले महीने', 'पिछला महीना',
                               'last mnth', 'prev month', 'previous mnth']
        is_last_month = any(keyword in message_lower for keyword in last_month_keywords)

        if not month and is_last_month:
            # Calculate last month
            last_month_date = datetime.now() - relativedelta(months=1)
            month = last_month_date.month
            year = last_month_date.year
            logger.info(f"📅 Detected 'last month' request - calculated: {month}/{year}")
        elif not month:
            # Default to current month if not specified
            month = datetime.now().month
            year = datetime.now().year if not year else year
            logger.info(f"📅 No month specified - defaulting to current month: {month}/{year}")

        if not year:
            year = datetime.now().year

        return {
            'intent': 'get_salary_slip',
            'confidence': 1.0,
            'extracted_data': {
                'month': month,
                'year': year
            },
            'missing_fields': [],
            'next_question': None,
            'ready_to_execute': True
        }

    # For all other intents, use AI normally
    # Build AI prompt
    prompt = _build_ai_prompt(user_message, user_context, available_leave_types)

    # Get AI response
    ai_response = _call_ai_model(prompt)

    # Validate and return
    return _validate_ai_response(ai_response)


# ============================================================================
# HELPER FUNCTIONS (Internal use only)
# ============================================================================

def _build_ai_prompt(
    user_message: str,
    context: Dict,
    leave_types: list
) -> str:
    """
    Build optimized prompt for AI processing.

    Optimizations:
    - Concise instructions (reduced token usage)
    - Clear structure for faster parsing
    - Essential examples only
    """
    leave_type_names = [lt.get('name', '') for lt in leave_types]
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%Y-%m-%d")  # Today's date for "today" references

    # Build context string if previous data exists
    prev_data = context.get('extracted_data', {})
    context_str = ""
    if prev_data:
        context_str = f"\n\nPrevious conversation data: {json.dumps(prev_data)}"

    # Build leave types list
    leave_types_str = ', '.join(leave_type_names) if leave_type_names else 'None available'

    return f"""HRMS AI: Extract intent+data from message.

MSG: "{user_message}"{context_str}
YEAR: {current_year}
TODAY: {current_date}
TYPES: {leave_types_str}

TASK: Extract ALL fields in ONE pass. Handle typos, Hindi+English, shortcuts (SL/CL/EL), all date formats.

INTENTS (keywords - MATCH THESE FIRST!):
- apply_leave: "apply/aply" + "leave/leav/chutti" (NOT attendance/duty)
- mark_attendance: "punch/pnch", "check in", "attendance" (NOT on duty)
- apply_regularization: "regularize/regularization", "forgot to punch", "missed punch", "attendance correction"
- apply_onduty: "on duty"/"onduty"/"on-duty", "WFH", "work from home", "field work", "client site" ⚠️ PRIORITY!
- check_leave_balance: "balance/balence", "remaining"
- get_holidays: "holiday/hoiday/holidays", "upcoming holiday", "chutti list", "festival", "off days", "छुट्टी", "aane wala", "konsa holiday", "next holiday", "kab hai chutti"
- get_salary_slip: "salary slip", "pay slip", "payslip", "salary", "pay", "वेतन पर्ची", "salary ka slip", "मेरी सैलरी", "salary ka certificate", "salary receipt", "महीने की सैलरी"
- policy_question: "policy", "rule"

⚠️ CRITICAL: If message contains "on duty"/"onduty"/"WFH" → ALWAYS use "apply_onduty" intent!

EXTRACT ALL: If "sick leave for 22 nov" → extract type AND date together!
For regularization: Extract date, from_time (HH:MM), to_time (HH:MM), reason
For on-duty: Extract date, from_time (HH:MM), to_time (HH:MM), reason

OUTPUT (JSON only):
{{
  "intent": "detected_intent",
  "confidence": 0.0-1.0,
  "extracted_data": {{
    "leave_type": "exact_name_from_available_types_or_null (for apply_leave)",
    "from_date": "YYYY-MM-DD_or_null (for apply_leave)",
    "to_date": "YYYY-MM-DD_or_null (for apply_leave)",
    "reason": "text_or_null (for apply_leave, apply_regularization, apply_onduty)",
    "action": "check_in_or_check_out_or_null (for mark_attendance)",
    "location": "text_or_null (for mark_attendance)",
    "date": "YYYY-MM-DD_or_null (for apply_regularization, apply_onduty)",
    "from_time": "HH:MM_24hr_format_or_null (for apply_regularization, apply_onduty)",
    "to_time": "HH:MM_24hr_format_or_null (for apply_regularization, apply_onduty)",
    "month": "1-12_or_null (for get_salary_slip, defaults to current month if not specified)",
    "year": "YYYY_or_null (for get_salary_slip, defaults to current year if not specified)"
  }},
  "missing_fields": ["list_of_missing_required_fields"],
  "next_question": "bilingual_question_in_hindi_and_english_or_null",
  "ready_to_execute": true_or_false
}}

LEARNING EXAMPLES (follow these patterns):

⚠️ ON-DUTY EXAMPLES (PRIORITY - Learn these first!):
"apply my on duty for today" → {{"intent":"apply_onduty","extracted_data":{{"date":"{current_date}"}},"missing_fields":["from_time","to_time","reason"],"next_question":"किस समय से किस समय तक? From what time to what time?","ready_to_execute":false}}
"on duty for today 9am to 6pm" → {{"intent":"apply_onduty","extracted_data":{{"date":"{current_date}","from_time":"09:00","to_time":"18:00"}},"missing_fields":["reason"],"next_question":"कारण? Reason?","ready_to_execute":false}}
"apply on duty today 9:20am to 1pm client meeting" → {{"intent":"apply_onduty","extracted_data":{{"date":"{current_date}","from_time":"09:20","to_time":"13:00","reason":"client meeting"}},"ready_to_execute":true}}

Leave examples:
"apply sick leave 4 nov health issues" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"{current_year}-11-04","to_date":"{current_year}-11-04","reason":"health issues"}},"ready_to_execute":true}}

"apply my leave for 22 nov 2025" → {{"intent":"apply_leave","extracted_data":{{"from_date":"2025-11-22","to_date":"2025-11-22"}},"missing_fields":["leave_type","reason"],"next_question":"किस प्रकार की छुट्टी? What type?","ready_to_execute":false}}

"sick leave chahiye 22 nov ko tabiyat kharab hai" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"{current_year}-11-22","to_date":"{current_year}-11-22","reason":"tabiyat kharab hai"}},"ready_to_execute":true}}

WITH TYPOS (still work perfectly):
"aply sck leav for 22 nv" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"{current_year}-11-22","to_date":"{current_year}-11-22"}},"missing_fields":["reason"],"ready_to_execute":false}}

"casuel leave lena hai 5 nov se" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Casual Leave","from_date":"{current_year}-11-05","to_date":"{current_year}-11-05"}},"missing_fields":["reason"],"ready_to_execute":false}}

"SL for 22 nv helth problm" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"{current_year}-11-22","to_date":"{current_year}-11-22","reason":"health problem"}},"ready_to_execute":true}}

Partial information (extract what's available):
"apply my leave for 22 nov" → {{"intent":"apply_leave","extracted_data":{{"from_date":"{current_year}-11-22","to_date":"{current_year}-11-22"}},"missing_fields":["leave_type","reason"],"next_question":"किस प्रकार की छुट्टी? What type: Sick, Casual, Earned?","ready_to_execute":false}}

"4 nov 2025 and sick leave" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"2025-11-04","to_date":"2025-11-04"}},"missing_fields":["reason"],"next_question":"छुट्टी का कारण? Reason?","ready_to_execute":false}}

"apply leave from 5 to 7 nov" → {{"intent":"apply_leave","extracted_data":{{"from_date":"{current_year}-11-05","to_date":"{current_year}-11-07"}},"missing_fields":["leave_type","reason"],"next_question":"किस प्रकार की छुट्टी? Type?","ready_to_execute":false}}

Continuing conversation (context matters):
Previous: {{"from_date":"2025-11-22"}}
User: "sick" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave"}},"missing_fields":["reason"],"next_question":"छुट्टी का कारण? Reason?","ready_to_execute":false}}

Previous: {{"leave_type":"Sick Leave","from_date":"2025-11-22"}}
User: "family emergency" → {{"intent":"apply_leave","extracted_data":{{"reason":"family emergency"}},"ready_to_execute":true}}

Attendance:
"punch in" → {{"intent":"mark_attendance","extracted_data":{{"action":"check_in"}},"ready_to_execute":true}}
"check out from office" → {{"intent":"mark_attendance","extracted_data":{{"action":"check_out","location":"office"}},"ready_to_execute":true}}

Regularization (forgot to punch):
"regularize attendance for 4 nov 9am to 6pm forgot to punch" → {{"intent":"apply_regularization","extracted_data":{{"date":"{current_year}-11-04","from_time":"09:00","to_time":"18:00","reason":"forgot to punch"}},"ready_to_execute":true}}

Balance query:
"leave balance" → {{"intent":"check_leave_balance","ready_to_execute":true}}

Holidays:
"upcoming holidays" → {{"intent":"get_holidays","ready_to_execute":true}}

Salary Slip:
"salary slip" → {{"intent":"get_salary_slip","ready_to_execute":true}}
"salary slip for october" → {{"intent":"get_salary_slip","extracted_data":{{"month":10}},"ready_to_execute":true}}
"pay slip of october 2024" → {{"intent":"get_salary_slip","extracted_data":{{"month":10,"year":2024}},"ready_to_execute":true}}
"last month salary slip" → {{"intent":"get_salary_slip","ready_to_execute":true}} (leave month/year null, code will calculate)
"previous month salary details" → {{"intent":"get_salary_slip","ready_to_execute":true}} (leave month/year null, code will calculate)
"meri salary ka slip" → {{"intent":"get_salary_slip","ready_to_execute":true}}

CRITICAL RULES - HANDLE TYPOS & NEVER CLASSIFY AS "unknown":
✓ "apply"/"aply"/"apli" + "leave"/"leav"/"leve" → intent = "apply_leave" (ALWAYS!)
✓ "sick"/"sck"/"sik" → leave_type = "Sick Leave"
✓ "casual"/"casuel"/"casul" → leave_type = "Casual Leave"
✓ "earned"/"earn"/"ernd" → leave_type = "Earned Leave"
✓ "22 nov"/"22 nv"/"nov 22"/"22/11" → from_date = "YYYY-11-22"
✓ "punch"/"pnch" or "check in"/"checkin" → intent = "mark_attendance"
✓ "balance"/"balence"/"balnce" → intent = "check_leave_balance"
✓ "on duty"/"onduty"/"on-duty" or "WFH"/"work from home" → intent = "apply_onduty" (ALWAYS!)
✓ "regularize"/"regularization"/"forgot to punch"/"missed punch" → intent = "apply_regularization"
✓ "holiday"/"holidays"/"upcoming holiday"/"chutti list" → intent = "get_holidays"
✓ "salary slip"/"pay slip"/"payslip"/"salary"/"pay"/"वेतन पर्ची" → intent = "get_salary_slip"
✓ Time formats: "9am"/"9:20am"/"09:00" → "09:00" (24hr), "1pm"/"6pm" → "13:00"/"18:00"
✗ NEVER return intent = "unknown" if message has keywords above (even with typos)!

BE SMART: Extract everything you can from the message. Don't ask for information that's already provided. Return ONLY valid JSON."""


def _call_ai_model(prompt: str) -> Dict[str, Any]:
    """
    Call AI model with optimized configuration.

    Optimizations:
    - Lower temperature (0.1) for more consistent extraction
    - Reduced max_tokens (500) since responses are structured
    - Better error handling
    """
    from services.ai.chat import (
        LLM_PROVIDER,
        get_gemini_client,
        get_openai_compatible_client,
        GEMINI_MODEL,
        OPENAI_MODEL,
        DEEPSEEK_MODEL
    )

    try:
        logger.debug(f"🤖 AI: {LLM_PROVIDER}")
        logger.debug(f"📤 Prompt length: {len(prompt)} characters")
        logger.debug(f"📤 Prompt (first 500 chars): {prompt[:500]}")

        # Gemini (Google AI) - Fast and free
        if LLM_PROVIDER == "gemini":
            genai = get_gemini_client()

            # Configure safety settings to allow HRMS content
            import google.generativeai as genai_import
            safety_settings = [
                {"category": genai_import.types.HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": genai_import.types.HarmBlockThreshold.BLOCK_NONE},
                {"category": genai_import.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": genai_import.types.HarmBlockThreshold.BLOCK_NONE},
                {"category": genai_import.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": genai_import.types.HarmBlockThreshold.BLOCK_NONE},
                {"category": genai_import.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": genai_import.types.HarmBlockThreshold.BLOCK_NONE},
            ]

            model = genai.GenerativeModel(
                GEMINI_MODEL,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1,  # Very low for consistent extraction
                    "max_output_tokens": 2000  # Sufficient for complete JSON responses
                },
                safety_settings=safety_settings
            )
            response = model.generate_content(prompt)
            return json.loads(response.text)

        # OpenAI or DeepSeek
        else:
            client = get_openai_compatible_client()
            model_name = OPENAI_MODEL if LLM_PROVIDER == "openai" else DEEPSEEK_MODEL

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Extract HRMS intent and data as JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode failed: {e}")
        raw = getattr(locals().get('response'), 'text', 'N/A')
        logger.error(f"Raw response (first 1000 chars): {raw[:1000]}")
        return _get_fallback_response("Invalid JSON")

    except Exception as e:
        logger.error(f"❌ AI call failed: {e}")
        return _get_fallback_response(str(e))


def _validate_ai_response(ai_response: Dict) -> Dict[str, Any]:
    """
    Validate and enhance AI response.

    No hardcoded validation - trust AI's judgment.
    Only ensure required structure exists.
    """
    if not isinstance(ai_response, dict):
        logger.warning("⚠️ AI returned non-dict, using fallback")
        return _get_fallback_response("Invalid response type")

    # Ensure minimal structure (no business logic validation)
    ai_response.setdefault("intent", "unknown")
    ai_response.setdefault("confidence", 0.0)
    ai_response.setdefault("extracted_data", {})
    ai_response.setdefault("missing_fields", [])
    ai_response.setdefault("ready_to_execute", False)
    ai_response.setdefault("next_question", None)

    # Trust AI's decision - no hardcoded checks
    logger.info(
        f"🤖 Intent: {ai_response['intent']} | "
        f"Ready: {ai_response['ready_to_execute']} | "
        f"Extracted: {list(ai_response['extracted_data'].keys())}"
    )

    return ai_response


def _get_fallback_response(error_msg: str) -> Dict[str, Any]:
    """
    Return fallback response when AI fails.

    This ensures system doesn't crash even if AI has issues.
    """
    logger.warning(f"Using fallback response due to: {error_msg}")

    return {
        "intent": "unknown",
        "confidence": 0.0,
        "extracted_data": {},
        "missing_fields": [],
        "next_question": "मुझे समझ नहीं आया। I didn't understand. Could you rephrase?",
        "ready_to_execute": False,
        "explanation": f"Error: {error_msg}"
    }


# ============================================================================
# USAGE EXAMPLES (for developers)
# ============================================================================

"""
Example 1: Single message with all info
---------------------------------------
>>> result = detect_intent_and_extract(
...     "apply sick leave for 4 nov health issues",
...     available_leave_types=[{"name": "Sick Leave"}]
... )
>>> print(result['ready_to_execute'])
True
>>> print(result['extracted_data'])
{
    'leave_type': 'Sick Leave',
    'from_date': '2025-11-04',
    'to_date': '2025-11-04',
    'reason': 'health issues'
}


Example 2: Conversation flow
----------------------------
# First message
>>> result1 = detect_intent_and_extract("apply leave")
>>> print(result1['next_question'])
"किस प्रकार की छुट्टी? What type of leave?"

# Second message with context
>>> result2 = detect_intent_and_extract(
...     "casual",
...     user_context={'intent': 'apply_leave', 'extracted_data': {}}
... )
>>> print(result2['next_question'])
"कब से? Start date?"

# Third message
>>> result3 = detect_intent_and_extract(
...     "12 nov",
...     user_context={'intent': 'apply_leave', 'extracted_data': {'leave_type': 'Casual Leave'}}
... )
>>> print(result3['next_question'])
"कारण? Reason?"


Example 3: Attendance
--------------------
>>> result = detect_intent_and_extract("punch in")
>>> print(result['intent'])
'mark_attendance'
>>> print(result['ready_to_execute'])
True
"""
