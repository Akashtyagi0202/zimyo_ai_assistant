"""
AI-Powered HRMS Intent & Information Extractor (LangChain Version)

This module uses LangChain for LLM interactions to intelligently understand
what users want and extract relevant information from natural language.

Key improvements over manual implementation:
- Reusable prompt templates
- Structured output parsing with validation
- Better error handling
- Memory integration ready
- LangSmith tracing support

Author: Zimyo AI Team
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# LangChain imports
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

# Local imports
from services.ai.langchain_config import get_llm, get_json_parser
from services.ai.langchain_prompts import (
    get_hrms_extraction_prompt,
    format_previous_context,
    format_leave_types
)

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN AI FUNCTION (LangChain Version)
# ============================================================================

def detect_intent_and_extract(
    user_message: str,
    user_context: Dict = None,
    available_leave_types: list = None
) -> Dict[str, Any]:
    """
    Use LangChain LLM to detect user intent and extract structured information.

    This is the MAIN BRAIN of the system using LangChain.

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
    previous_intent = user_context.get('intent')
    in_onduty_flow = (previous_intent == 'apply_onduty')
    in_regularization_flow = (previous_intent == 'apply_regularization')

    # Priority 1: On-duty detection (WFH, client site, field work)
    if in_onduty_flow or any(keyword in message_lower for keyword in ['on duty', 'onduty', 'on-duty', 'wfh', 'work from home']):
        logger.info("🎯 Pre-filter: Detected ON-DUTY intent")
        return _handle_onduty_with_langchain(user_message, user_context, available_leave_types)

    # Priority 2: Regularization detection
    if in_regularization_flow or any(keyword in message_lower for keyword in ['regularize', 'regularization', 'forgot to punch', 'missed punch']):
        logger.info("🎯 Pre-filter: Detected REGULARIZATION intent")
        return _handle_regularization_with_langchain(user_message, user_context, available_leave_types)

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
        return _handle_salary_slip_with_langchain(user_message, user_context, available_leave_types)

    # For all other intents, use LangChain AI
    logger.info("🤖 Using LangChain AI for intent detection")
    return _call_langchain_ai(user_message, user_context, available_leave_types)


# ============================================================================
# LANGCHAIN AI CALL
# ============================================================================

def _call_langchain_ai(
    user_message: str,
    context: Dict,
    leave_types: list
) -> Dict[str, Any]:
    """
    Call LangChain LLM with prompt template for intent extraction.

    Args:
        user_message: User's input message
        context: Previous conversation context
        leave_types: Available leave types

    Returns:
        Extracted intent and data as dictionary
    """
    try:
        # Get LangChain components
        llm = get_llm(temperature=0.1)  # Low temp for consistent extraction
        parser = get_json_parser()
        prompt = get_hrms_extraction_prompt()

        # Build chain: prompt -> llm -> json parser
        chain = prompt | llm | parser

        # Prepare input variables
        current_year = datetime.now().year
        current_date = datetime.now().strftime("%Y-%m-%d")
        leave_types_str = format_leave_types(leave_types)
        previous_context_str = format_previous_context(context)

        logger.info(f"🤖 LangChain: Analyzing message: '{user_message[:50]}...'")

        # Invoke chain
        result = chain.invoke({
            "user_message": user_message,
            "current_date": current_date,
            "current_year": current_year,
            "leave_types": leave_types_str,
            "previous_context": previous_context_str
        })

        logger.info(f"✅ LangChain result: intent={result.get('intent')}, ready={result.get('ready_to_execute')}")

        return _validate_ai_response(result)

    except OutputParserException as e:
        logger.error(f"❌ LangChain JSON parsing failed: {e}")
        return _get_fallback_response(f"JSON parse error: {str(e)}")

    except Exception as e:
        logger.error(f"❌ LangChain call failed: {e}")
        return _get_fallback_response(str(e))


# ============================================================================
# SPECIALIZED HANDLERS (with LangChain)
# ============================================================================

def _handle_onduty_with_langchain(user_message: str, context: Dict, leave_types: list) -> Dict[str, Any]:
    """Handle on-duty requests using LangChain with context merging."""
    prev_data = context.get('extracted_data', {})

    # Call LangChain AI
    ai_response = _call_langchain_ai(user_message, context, leave_types)

    # Force intent if AI missed it
    if ai_response.get('intent') != 'apply_onduty':
        logger.warning(f"⚠️ AI returned '{ai_response.get('intent')}' for on-duty, forcing to apply_onduty")
        ai_response['intent'] = 'apply_onduty'

    # Merge with previous context
    extracted = ai_response.get('extracted_data', {})

    # Regex fallback for time extraction
    if not extracted.get('from_time') or not extracted.get('to_time'):
        import re
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?\s*(?:to|till|-)\s*(\d{1,2}):?(\d{2})?\s*(am|pm)?'
        match = re.search(time_pattern, user_message.lower(), re.IGNORECASE)

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
            logger.info(f"🔧 Regex extracted time: {extracted['from_time']} to {extracted['to_time']}")

    # Merge: previous + new
    merged_data = {**prev_data, **extracted}

    # Fallback: use entire message as reason if only reason is missing
    has_date = merged_data.get('date')
    has_from_time = merged_data.get('from_time')
    has_to_time = merged_data.get('to_time')
    has_reason = merged_data.get('reason')

    if has_date and has_from_time and has_to_time and not has_reason:
        if user_message and len(user_message.strip()) > 0:
            merged_data['reason'] = user_message.strip()
            has_reason = True
            logger.info(f"🔧 Fallback: Using message as reason: '{merged_data['reason']}'")

    # Update response
    ai_response['extracted_data'] = merged_data

    # Set ready_to_execute
    if has_date and has_from_time and has_to_time and has_reason:
        ai_response['ready_to_execute'] = True
        ai_response['missing_fields'] = []
        ai_response['next_question'] = None
    else:
        ai_response['ready_to_execute'] = False
        if not has_date:
            ai_response['next_question'] = "किस तारीख के लिए on-duty चाहिए? For which date do you need on-duty?"
            ai_response['missing_fields'] = ['date']
        elif not has_from_time or not has_to_time:
            ai_response['next_question'] = "किस समय से किस समय तक? What time range? (e.g., 9am to 6pm)"
            ai_response['missing_fields'] = ['from_time', 'to_time']
        elif not has_reason:
            ai_response['next_question'] = "कारण बताएं? Reason? (e.g., WFH, Client meeting, Field work)"
            ai_response['missing_fields'] = ['reason']

    logger.info(f"✅ On-duty: ready={ai_response['ready_to_execute']}, fields={list(merged_data.keys())}")
    return _validate_ai_response(ai_response)


def _handle_regularization_with_langchain(user_message: str, context: Dict, leave_types: list) -> Dict[str, Any]:
    """Handle regularization requests using LangChain with context merging."""
    prev_data = context.get('extracted_data', {})

    # Call LangChain AI
    ai_response = _call_langchain_ai(user_message, context, leave_types)

    # Force intent if AI missed it
    if ai_response.get('intent') != 'apply_regularization':
        logger.warning(f"⚠️ AI returned '{ai_response.get('intent')}' for regularization, forcing intent")
        ai_response['intent'] = 'apply_regularization'

    # Merge with previous context
    extracted = ai_response.get('extracted_data', {})

    # Regex fallback for time extraction (same as on-duty)
    if not extracted.get('from_time') or not extracted.get('to_time'):
        import re
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?\s*(?:to|till|-)\s*(\d{1,2}):?(\d{2})?\s*(am|pm)?'
        match = re.search(time_pattern, user_message.lower(), re.IGNORECASE)

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
            logger.info(f"🔧 Regex extracted time: {extracted['from_time']} to {extracted['to_time']}")

    # Merge
    merged_data = {**prev_data, **extracted}

    # Fallback: use message as reason if only reason missing
    has_date = merged_data.get('date')
    has_from_time = merged_data.get('from_time')
    has_to_time = merged_data.get('to_time')
    has_reason = merged_data.get('reason')

    if has_date and has_from_time and has_to_time and not has_reason:
        if user_message and len(user_message.strip()) > 0:
            merged_data['reason'] = user_message.strip()
            has_reason = True
            logger.info(f"🔧 Fallback: Using message as reason: '{merged_data['reason']}'")

    # Update response
    ai_response['extracted_data'] = merged_data

    # Set ready_to_execute
    if has_date and has_from_time and has_to_time and has_reason:
        ai_response['ready_to_execute'] = True
        ai_response['missing_fields'] = []
        ai_response['next_question'] = None
    else:
        ai_response['ready_to_execute'] = False
        if not has_date:
            ai_response['next_question'] = "किस तारीख की attendance regularize करनी है? Which date?"
            ai_response['missing_fields'] = ['date']
        elif not has_from_time or not has_to_time:
            ai_response['next_question'] = "आप किस समय से किस समय तक थे? What time range? (e.g., 9am to 6pm)"
            ai_response['missing_fields'] = ['from_time', 'to_time']
        elif not has_reason:
            ai_response['next_question'] = "कारण? Reason? (e.g., Forgot to punch, System issue)"
            ai_response['missing_fields'] = ['reason']

    logger.info(f"✅ Regularization: ready={ai_response['ready_to_execute']}, fields={list(merged_data.keys())}")
    return _validate_ai_response(ai_response)


def _handle_salary_slip_with_langchain(user_message: str, context: Dict, leave_types: list) -> Dict[str, Any]:
    """Handle salary slip requests using LangChain."""
    # Call LangChain AI
    ai_response = _call_langchain_ai(user_message, context, leave_types)

    # Force intent
    extracted_data = ai_response.get('extracted_data', {})
    month = extracted_data.get('month')
    year = extracted_data.get('year')

    # Smart default for "last month" keywords
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    last_month_keywords = ['last month', 'previous month', 'पिछले महीने', 'पिछला महीना']
    is_last_month = any(keyword in user_message.lower() for keyword in last_month_keywords)

    if not month and is_last_month:
        last_month_date = datetime.now() - relativedelta(months=1)
        month = last_month_date.month
        year = last_month_date.year
        logger.info(f"📅 Detected 'last month' - calculated: {month}/{year}")
    elif not month:
        month = datetime.now().month
        year = datetime.now().year if not year else year
        logger.info(f"📅 No month specified - defaulting to current: {month}/{year}")

    if not year:
        year = datetime.now().year

    return {
        'intent': 'get_salary_slip',
        'confidence': 1.0,
        'extracted_data': {'month': month, 'year': year},
        'missing_fields': [],
        'next_question': None,
        'ready_to_execute': True
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _validate_ai_response(ai_response: Dict) -> Dict[str, Any]:
    """
    Validate and enhance AI response.

    Ensures required structure exists.
    """
    if not isinstance(ai_response, dict):
        logger.warning("⚠️ AI returned non-dict, using fallback")
        return _get_fallback_response("Invalid response type")

    # Ensure minimal structure
    ai_response.setdefault("intent", "unknown")
    ai_response.setdefault("confidence", 0.0)
    ai_response.setdefault("extracted_data", {})
    ai_response.setdefault("missing_fields", [])
    ai_response.setdefault("ready_to_execute", False)
    ai_response.setdefault("next_question", None)

    return ai_response


def _get_fallback_response(error_msg: str) -> Dict[str, Any]:
    """
    Return fallback response when AI fails.
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
# MIGRATION COMPATIBILITY
# ============================================================================

# Keep the same function signature for backward compatibility
# Existing code can continue to import and use this function
__all__ = ['detect_intent_and_extract']
