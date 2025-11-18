"""
Response Generation Node for LangGraph

Generates user-facing responses based on workflow state.

Author: Zimyo AI Team
"""

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


def generate_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate response based on workflow state.

    Args:
        state: Current workflow state

    Returns:
        Updated state with response message
    """
    logger.info(f"💬 Response Node - Action: {state.get('next_action')}")

    next_action = state.get("next_action", "")
    intent = state.get("intent", "")

    # Generate response based on action
    if next_action == "execute":
        response = _generate_success_response(state)

    elif next_action == "wait_approval":
        response = _generate_approval_pending_response(state)

    elif next_action == "ask_user":
        response = _generate_question_response(state)

    elif state.get("execution_result"):
        response = _generate_execution_response(state)

    else:
        response = "मुझे समझ नहीं आया। I didn't understand. Please try again."

    logger.info(f"✅ Generated response (length: {len(response)})")

    # Add AI message to conversation
    messages = state.get("messages", [])
    messages.append(AIMessage(content=response))

    return {
        **state,
        "response": response,
        "messages": messages,
        "current_step": "response_generated"
    }


def _generate_success_response(state: Dict[str, Any]) -> str:
    """Generate response for successful execution."""
    intent = state.get("intent", "")
    extracted_data = state.get("extracted_data", {})

    if intent == "apply_leave":
        return f"""✅ Leave application submitted successfully!

📋 Details:
• Type: {extracted_data.get('leave_type', 'N/A')}
• Dates: {extracted_data.get('from_date', 'N/A')} to {extracted_data.get('to_date', 'N/A')}
• Reason: {extracted_data.get('reason', 'N/A')}

Your leave request has been sent for approval."""

    elif intent == "apply_regularization":
        return f"""✅ Attendance regularization submitted!

📋 Details:
• Date: {extracted_data.get('date', 'N/A')}
• Time: {extracted_data.get('from_time', 'N/A')} to {extracted_data.get('to_time', 'N/A')}
• Reason: {extracted_data.get('reason', 'N/A')}

Your request will be reviewed shortly."""

    elif intent == "apply_onduty":
        return f"""✅ On-duty application submitted!

📋 Details:
• Date: {extracted_data.get('date', 'N/A')}
• Time: {extracted_data.get('from_time', 'N/A')} to {extracted_data.get('to_time', 'N/A')}
• Reason: {extracted_data.get('reason', 'N/A')}

Waiting for manager approval."""

    return "✅ Request submitted successfully!"


def _generate_approval_pending_response(state: Dict[str, Any]) -> str:
    """Generate response when approval is required."""
    intent = state.get("intent", "")

    if intent == "apply_leave":
        return "⏳ Your leave application requires manager approval. Request submitted and pending approval."

    elif intent == "apply_regularization":
        return "⏳ Regularization for dates older than 3 days requires manager approval. Request submitted."

    elif intent == "apply_onduty":
        return "⏳ On-duty application requires manager approval. Your request has been forwarded."

    return "⏳ Your request requires approval and has been submitted."


def _generate_question_response(state: Dict[str, Any]) -> str:
    """Generate question to ask user for missing information."""
    intent = state.get("intent", "")
    extracted_data = state.get("extracted_data", {})
    validation_errors = state.get("validation_errors", [])

    # If there are validation errors, ask for the first missing field
    if validation_errors:
        # Check what's missing
        if not extracted_data.get("leave_type") and intent == "apply_leave":
            return "किस प्रकार की छुट्टी चाहिए? What type of leave? (Sick, Casual, Earned)"

        elif not extracted_data.get("from_date") and intent in ["apply_leave", "apply_regularization", "apply_onduty"]:
            return "किस तारीख के लिए? For which date?"

        elif not extracted_data.get("from_time") and intent in ["apply_regularization", "apply_onduty"]:
            return "किस समय से किस समय तक? What time range? (e.g., 9am to 6pm)"

        elif not extracted_data.get("reason"):
            return "कारण बताएं? What's the reason?"

        # Return first validation error
        return f"⚠️ {validation_errors[0]}"

    return "कृपया अधिक जानकारी दें। Please provide more details."


def _generate_execution_response(state: Dict[str, Any]) -> str:
    """Generate response based on execution result."""
    result = state.get("execution_result", {})

    if result.get("success"):
        return result.get("message", "✅ Request completed successfully!")
    else:
        return f"❌ Error: {result.get('message', 'Unknown error occurred')}"
