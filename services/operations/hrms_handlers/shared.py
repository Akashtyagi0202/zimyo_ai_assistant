"""
Shared utilities for HRMS handlers

Contains:
- Response templates
- Cache management
- Common helper functions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# CACHING - Avoid repeated MCP calls for leave types
# ============================================================================

_leave_types_cache = {}  # {user_id: {"data": [...], "expires_at": datetime}}
CACHE_DURATION_MINUTES = 30  # Cache for 30 minutes


async def get_leave_types_cached(user_id: str, mcp_client) -> list:
    """
    Get leave types with caching (30 minutes).

    Args:
        user_id: Employee ID
        mcp_client: MCP client instance

    Returns:
        List of leave types or empty list if error
    """
    now = datetime.now()

    # Check cache first
    if user_id in _leave_types_cache:
        cache_entry = _leave_types_cache[user_id]
        if now < cache_entry["expires_at"]:
            logger.debug(f"📦 Using cached leave types for {user_id}")
            return cache_entry["data"]

    # Cache miss - fetch from MCP
    logger.debug(f"🔄 Fetching leave types from MCP for {user_id}")
    result = await mcp_client.call_tool("get_leave_types", {"user_id": user_id})

    if result.get("status") == "success":
        leave_types = result.get("leave_types", [])

        # Update cache
        _leave_types_cache[user_id] = {
            "data": leave_types,
            "expires_at": now + timedelta(minutes=CACHE_DURATION_MINUTES)
        }

        return leave_types

    return []


# ============================================================================
# RESPONSE TEMPLATES - Pre-formatted strings
# ============================================================================

RESPONSE_TEMPLATES = {
    "balance_header": "📊 आपका वर्तमान छुट्टी शेष। Your current leave balance:\n",
    "balance_item": "• {leave_type}: {days} days",
    "balance_empty": "❌ No leave balance information found.",

    "attendance_success": "✅ {action} marked successfully at {time}",
    "attendance_location": " 📍 Location: {location}",

    "leave_success": "✅ छुट्टी सफलतापूर्वक लागू हो गई! Leave applied successfully!\n\n",
    "leave_type": "📋 Type: {leave_type}\n",
    "leave_dates": "📅 Dates: {from_date} to {to_date} ({days} days)\n",
    "leave_reason": "📝 Reason: {reason}",

    "error_api": "❌ {resource} की जानकारी प्राप्त करने में त्रुटि। Error fetching {resource}: {message}",
    "error_invalid_dates": "❌ गलत तारीखें। Invalid dates: {message}",
    "error_missing_info": "❌ अधूरी जानकारी। Missing information: {fields}",
    "error_generic": "❌ {message}",

    "question_leave_type": "किस प्रकार की छुट्टी चाहिए? 📋 What type of leave?\n\nAvailable: {types}",
    "question_dates": "कब से कब तक? 📅 Which dates?",
    "question_reason": "छुट्टी का कारण? 📝 Reason for leave?",
    "question_action": "क्या करना है? What would you like to do? (check-in / check-out)",
}
