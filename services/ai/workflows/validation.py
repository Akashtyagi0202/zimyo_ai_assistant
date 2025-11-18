"""
Validation Node for LangGraph

Validates extracted data and determines next action.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_data_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate extracted data and check if ready to execute.

    Args:
        state: Current workflow state

    Returns:
        Updated state with validation results
    """
    logger.info(f"✅ Validation Node - Intent: {state.get('intent')}")

    intent = state.get("intent", "")
    extracted_data = state.get("extracted_data", {})
    validation_errors = []
    is_valid = False
    requires_approval = False

    # Validate based on intent
    if intent == "apply_leave":
        is_valid, errors, needs_approval = _validate_leave_application(extracted_data)
        validation_errors = errors
        requires_approval = needs_approval

    elif intent == "apply_regularization":
        is_valid, errors, needs_approval = _validate_regularization(extracted_data)
        validation_errors = errors
        requires_approval = needs_approval

    elif intent == "apply_onduty":
        is_valid, errors, needs_approval = _validate_onduty(extracted_data)
        validation_errors = errors
        requires_approval = needs_approval

    elif intent in ["check_leave_balance", "get_holidays", "get_salary_slip", "mark_attendance"]:
        # These are simple queries, no validation needed
        is_valid = True
        validation_errors = []

    else:
        is_valid = False
        validation_errors = ["Unknown intent"]

    logger.info(f"📋 Validation: valid={is_valid}, errors={len(validation_errors)}, needs_approval={requires_approval}")

    # Determine next action
    if is_valid and not requires_approval:
        next_action = "execute"
    elif is_valid and requires_approval:
        next_action = "wait_approval"
    else:
        next_action = "ask_user"

    return {
        **state,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
        "requires_approval": requires_approval,
        "next_action": next_action,
        "current_step": "validated"
    }


def _validate_leave_application(data: Dict[str, Any]) -> tuple[bool, list, bool]:
    """
    Validate leave application data.

    Returns:
        (is_valid, errors, requires_approval)
    """
    errors = []
    requires_approval = False

    # Check required fields
    if not data.get("leave_type"):
        errors.append("Leave type is required")

    if not data.get("from_date"):
        errors.append("Start date is required")

    if not data.get("reason"):
        errors.append("Reason is required")

    # Validate dates
    try:
        from_date = data.get("from_date")
        to_date = data.get("to_date", from_date)

        if from_date:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")

            # Check if dates are in the past
            today = datetime.now()
            if from_dt < today.replace(hour=0, minute=0, second=0, microsecond=0):
                errors.append("Cannot apply leave for past dates")

            # Check if leave duration > 3 days (requires approval)
            duration = (to_dt - from_dt).days + 1
            if duration > 3:
                requires_approval = True

    except ValueError as e:
        errors.append(f"Invalid date format: {e}")

    is_valid = len(errors) == 0
    return is_valid, errors, requires_approval


def _validate_regularization(data: Dict[str, Any]) -> tuple[bool, list, bool]:
    """
    Validate regularization request.

    Returns:
        (is_valid, errors, requires_approval)
    """
    errors = []
    requires_approval = False

    # Check required fields
    if not data.get("date"):
        errors.append("Date is required")

    if not data.get("from_time"):
        errors.append("Start time is required")

    if not data.get("to_time"):
        errors.append("End time is required")

    if not data.get("reason"):
        errors.append("Reason is required")

    # Validate date
    try:
        date_str = data.get("date")
        if date_str:
            reg_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()

            # Check if more than 3 days old (requires manager approval)
            days_diff = (today - reg_date).days
            if days_diff > 3:
                requires_approval = True
                errors.append("Regularization for dates older than 3 days requires manager approval")

            # Check if future date
            if reg_date > today:
                errors.append("Cannot regularize future dates")

    except ValueError as e:
        errors.append(f"Invalid date format: {e}")

    is_valid = len(errors) == 0 or (len(errors) == 1 and requires_approval)
    return is_valid, errors, requires_approval


def _validate_onduty(data: Dict[str, Any]) -> tuple[bool, list, bool]:
    """
    Validate on-duty application.

    Returns:
        (is_valid, errors, requires_approval)
    """
    errors = []
    requires_approval = True  # On-duty always requires approval

    # Check required fields
    if not data.get("date"):
        errors.append("Date is required")

    if not data.get("from_time"):
        errors.append("Start time is required")

    if not data.get("to_time"):
        errors.append("End time is required")

    if not data.get("reason"):
        errors.append("Reason is required")

    # Validate date (must be future or today)
    try:
        date_str = data.get("date")
        if date_str:
            onduty_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if onduty_date < today:
                errors.append("Cannot apply on-duty for past dates")

    except ValueError as e:
        errors.append(f"Invalid date format: {e}")

    is_valid = len(errors) == 0
    return is_valid, errors, requires_approval
