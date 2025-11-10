# services/mcp_integration.py
"""
MCP Integration service for Zimyo HRMS Operations
Supports both MCP Protocol and HTTP fallback
"""

import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Check which mode to use - MCP or HTTP
USE_MCP = os.getenv('USE_MCP_PROTOCOL', 'true').lower() == 'true'

if USE_MCP:
    # Use new HTTP-based MCP client that supports both local (stdio) and remote (HTTP) modes
    from services.integration.mcp_client import get_http_mcp_client as get_mcp_client
    logger.info("✅ Using MCP Protocol for HRMS operations")
else:
    from services.integration.node_api_client import node_api_client
    logger.info("⚠️ Using HTTP fallback for HRMS operations")


class HRMSAdapter:
    """
    Unified adapter for HRMS operations
    Uses MCP Protocol by default, falls back to HTTP if needed
    """

    def __init__(self):
        self.is_connected = True
        self.use_mcp = USE_MCP

        if self.use_mcp:
            self.client = get_mcp_client()
            logger.info("Initialized MCP client")
        else:
            self.client = node_api_client
            logger.info("Initialized HTTP client (fallback)")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call HRMS tool using MCP protocol or HTTP fallback

        Args:
            tool_name: Name of the tool (apply_leave, mark_attendance, etc.)
            arguments: Tool arguments

        Returns:
            Result from the tool execution
        """
        try:
            if self.use_mcp:
                # MCP Protocol - direct tool call
                logger.debug(f"MCP: Calling tool '{tool_name}' with args: {arguments}")
                result = await self.client.call_tool(tool_name, arguments)
                logger.debug(f"MCP: Tool '{tool_name}' returned: {result}")
                return result
            else:
                # HTTP Fallback - map to specific methods
                return await self._call_http_fallback(tool_name, arguments)

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"status": "error", "message": f"Tool call failed: {str(e)}"}

    async def _call_http_fallback(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP fallback for when MCP is not available"""
        try:
            if tool_name == "apply_leave":
                return await self.client.apply_leave(
                    user_id=arguments["user_id"],
                    leave_type_name=arguments["leave_type_name"],
                    from_date=arguments["from_date"],
                    to_date=arguments["to_date"],
                    reasons=arguments["reasons"],
                    is_half_day=arguments.get("is_half_day", "0"),
                    documents_required=arguments.get("documents_required", "null")
                )

            elif tool_name == "mark_attendance":
                return await self.client.mark_attendance(
                    user_id=arguments["user_id"],
                    location=arguments.get("location", "")
                )

            elif tool_name == "get_leave_balance":
                return await self.client.get_leave_balance(
                    user_id=arguments["user_id"]
                )

            elif tool_name == "get_leave_types":
                return await self.client.get_leave_types(
                    user_id=arguments["user_id"]
                )

            elif tool_name == "collect_leave_details":
                # This is a helper function that doesn't call external API
                # Just returns available leave types
                result = await self.client.get_leave_types(
                    user_id=arguments["user_id"]
                )
                if result.get("status") == "success":
                    collected_info = arguments.get("collected_info", {})
                    required_fields = ["leave_type_name", "from_date", "to_date", "reasons"]
                    missing_fields = [field for field in required_fields if field not in collected_info]

                    return {
                        "status": "success",
                        "user_id": arguments["user_id"],
                        "collected_info": collected_info,
                        "missing_fields": missing_fields,
                        "available_leave_types": result.get("leave_types", []),
                        "leave_balance": result.get("leave_balance", {}),
                        "next_steps": []
                    }
                return result

            elif tool_name == "validate_leave_request":
                return await self.client.validate_leave_request(
                    user_id=arguments["user_id"],
                    leave_type_name=arguments["leave_type_name"],
                    from_date=arguments["from_date"],
                    to_date=arguments["to_date"]
                )

            else:
                return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error in HTTP fallback for tool {tool_name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"status": "error", "message": f"HTTP fallback failed: {str(e)}"}


# Global client instance - now properly uses MCP or HTTP
mcp_client = HRMSAdapter()

# ===================== HR ACTION HANDLERS =====================

async def handle_leave_application(user_id: str, user_message: str, conversation_context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Handle leave application requests"""
    try:
        from services.operations.conversation_state import get_conversation_state, update_conversation_state, clear_conversation_state

        # Get conversation state from Redis or use provided context
        # ALWAYS use Redis if session_id is provided (it's the source of truth)
        if session_id:
            context = get_conversation_state(user_id, session_id) or {}
            logger.info(f"🔑 Using conversation state from Redis for session {session_id}")
        elif conversation_context:
            # Use provided context if no session_id
            context = conversation_context
            logger.info(f"📝 Using provided conversation_context (no session_id)")
        else:
            # Legacy behavior - try to find any active session
            from services.operations.conversation_state import get_conversation_state_legacy
            context = get_conversation_state_legacy(user_id) or {}
            logger.info(f"🔍 Using legacy session lookup")

        # Extract information from user message or context
        collected_info = context.get("leave_info", {}).copy()  # Use copy to preserve original
        logger.info(f"📦 Starting with collected_info from context: {collected_info}")

        # Parse the current user message for leave details
        message_lower = user_message.lower()

        # Get available leave types for parsing
        collect_result = await mcp_client.call_tool("get_leave_types", {
            "user_id": user_id
        })
        logging.info(f"collect_result :{collect_result}")
        available_types = collect_result.get("leave_types", []) if collect_result.get("status") == "success" else []

        # Extract leave type from message using fuzzy matching (handles typos and languages)
        if "leave_type_name" not in collected_info:
            from services.utils.fuzzy_matcher import simple_fuzzy_matcher

            match = simple_fuzzy_matcher.fuzzy_match_leave_type(user_message, available_types)
            if match:
                matched_leave_type, confidence = match
                collected_info["leave_type_name"] = matched_leave_type.get("name")
                logger.info(f"✅ Fuzzy extracted leave type: '{matched_leave_type.get('name')}' from '{user_message}' (confidence: {confidence})")
            else:
                logger.info(f"❌ No leave type extracted from message: '{user_message}'. Available types: {[lt.get('name') for lt in available_types]}")

        # Extract dates from message - always check for new dates in current message
        # This ensures new date requests override any cached dates
        import re
        from datetime import datetime

        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2025-08-22
            r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:\s+\d{4})?',  # 22 aug 2025 or 22 aug or 6 nov
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:\s+\d{4})?',  # aug 22 2025 or aug 22 or nov 6
        ]

        for pattern in date_patterns:
            dates = re.findall(pattern, user_message, re.IGNORECASE)
            if dates:
                converted_dates = []
                for date_str in dates:
                    try:
                        if '-' in date_str:
                            converted_dates.append(date_str)
                        else:
                            # Try with year first
                            try:
                                dt = datetime.strptime(date_str.lower(), '%d %b %Y')
                                converted_dates.append(dt.strftime('%Y-%m-%d'))
                            except ValueError:
                                try:
                                    dt = datetime.strptime(date_str.lower(), '%b %d %Y')
                                    converted_dates.append(dt.strftime('%Y-%m-%d'))
                                except ValueError:
                                    # Try without year - infer the year
                                    try:
                                        # Try "6 nov" format
                                        dt_no_year = datetime.strptime(date_str.lower(), '%d %b')
                                        # Infer year based on current date
                                        current_date = datetime.now()
                                        inferred_date = dt_no_year.replace(year=current_date.year)
                                        # If the inferred date has already passed this year, use next year
                                        if inferred_date < current_date:
                                            inferred_date = inferred_date.replace(year=current_date.year + 1)
                                        converted_dates.append(inferred_date.strftime('%Y-%m-%d'))
                                        logger.info(f"📅 Inferred year for '{date_str}': {inferred_date.strftime('%Y-%m-%d')}")
                                    except ValueError:
                                        # Try "nov 6" format
                                        dt_no_year = datetime.strptime(date_str.lower(), '%b %d')
                                        # Infer year based on current date
                                        current_date = datetime.now()
                                        inferred_date = dt_no_year.replace(year=current_date.year)
                                        # If the inferred date has already passed this year, use next year
                                        if inferred_date < current_date:
                                            inferred_date = inferred_date.replace(year=current_date.year + 1)
                                        converted_dates.append(inferred_date.strftime('%Y-%m-%d'))
                                        logger.info(f"📅 Inferred year for '{date_str}': {inferred_date.strftime('%Y-%m-%d')}")
                    except ValueError:
                        continue

                # Always update dates if found in current message (override cached dates)
                if converted_dates:
                    collected_info["from_date"] = converted_dates[0]
                    logger.info(f"🔄 Updated from_date with new date: {converted_dates[0]}")

                    if len(converted_dates) > 1:
                        collected_info["to_date"] = converted_dates[1]
                        logger.info(f"🔄 Updated to_date: {converted_dates[1]}")
                    else:
                        collected_info["to_date"] = converted_dates[0]
                        logger.info(f"🔄 Updated to_date (same as from): {converted_dates[0]}")
                    break

        # Extract reason from message (avoid extracting dates as reasons)
        if "reasons" not in collected_info:
            import re  # Import re module here

            # Date patterns to avoid extracting as reasons
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',  # 2025-11-06
                r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:\s+\d{4})?',  # 6 nov or 6 nov 2025
                r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:\s+\d{4})?',  # nov 6 or nov 6 2025
            ]

            # First try to extract reason with keywords
            reason_keywords = ["reason", "because", "for", "due to"]
            reason_found = False
            for keyword in reason_keywords:
                if keyword in message_lower:
                    parts = message_lower.split(keyword)
                    if len(parts) > 1:
                        reason = parts[-1].strip()
                        # Clean up the reason
                        reason = reason.replace("is", "").strip()
                        is_date = any(re.search(pattern, reason.lower(), re.IGNORECASE) for pattern in date_patterns)

                        if reason and len(reason) > 2 and not is_date:
                            collected_info["reasons"] = reason
                            logger.info(f"Extracted reason with keyword '{keyword}': {reason}")
                            reason_found = True
                            break

            # If no keyword found and we're in a leave application context with leave_type and dates,
            # treat the entire message as reason (if it's not a date or leave type)
            # IMPORTANT: Only do this if we have both leave_type and dates already (all collected)
            # This prevents extracting dates or leave types as reasons
            if not reason_found and "leave_type_name" in context.get("leave_info", {}) and "from_date" in collected_info and "to_date" in collected_info:
                # Check if message is not a date
                is_date = any(re.search(pattern, user_message.lower(), re.IGNORECASE) for pattern in date_patterns)
                # Check if message is not a leave type
                is_leave_type = any(lt.get("name", "").lower() in user_message.lower() for lt in available_types)
                # Check if message is not asking for more information
                is_question = any(word in message_lower for word in ["what", "when", "which", "how", "why", "?"])

                if not is_date and not is_leave_type and not is_question and len(user_message.strip()) > 3:
                    collected_info["reasons"] = user_message.strip()
                    logger.info(f"Extracted reason from context: {user_message.strip()}")

        # Get leave types and balance info
        leave_types_result = await mcp_client.call_tool("get_leave_types", {
            "user_id": user_id
        })

        if leave_types_result.get("status") != "success":
            return {
                "response": f"Error: {leave_types_result.get('message', 'Failed to process leave request')}",
                "action_needed": False
            }

        # Check which required fields are missing
        required_fields = ["leave_type_name", "from_date", "to_date", "reasons"]
        missing_fields = [field for field in required_fields if field not in collected_info]

        logging.info(f"missing_fields at final {missing_fields}")
        if missing_fields:
            # Need more information from user
            available_types = leave_types_result.get("leave_types", [])
            leave_balance = leave_types_result.get("leave_balance", {})

            # Check if no leave types are available
            if not available_types:
                return {
                    "response": "❌ Cannot process leave application - no leave types are configured for your account. Please contact HR to set up your leave balance.",
                    "action_needed": False
                }

            # Generate multilingual response based on user's language context
            user_language = detect_user_language(user_message)

            # Ask for information one at a time in priority order for better user experience
            if "leave_type_name" in missing_fields:
                type_names = [lt.get("name", "") for lt in available_types if isinstance(lt, dict)]
                if user_language == 'hindi':
                    response_parts = ["🤝 मैं आपकी छुट्टी के लिए आवेदन में मदद करूंगा। "]
                    response_parts.append(f"आपको किस प्रकार की छुट्टी चाहिए? \n📋 उपलब्ध प्रकार: {', '.join(type_names)}")
                else:
                    response_parts = ["🤝 I'll help you apply for leave. "]
                    response_parts.append(f"What type of leave would you like to apply for? \n📋 Available types: {', '.join(type_names)}")
            elif "from_date" in missing_fields:
                if user_language == 'hindi':
                    response_parts = [f"बहुत बढ़िया! अब छुट्टी की शुरुआत की तारीख बताएं। \n📅 (Format: YYYY-MM-DD या '22 Aug 2025')"]
                else:
                    response_parts = [f"Great! Now what's the start date for your leave? \n📅 (Format: YYYY-MM-DD or '22 Aug 2025')"]
            elif "to_date" in missing_fields:
                if user_language == 'hindi':
                    response_parts = [f"अच्छा! अब छुट्टी की अंतिम तारीख बताएं। \n📅 (Format: YYYY-MM-DD या '25 Aug 2025')"]
                else:
                    response_parts = [f"Perfect! What's the end date for your leave? \n📅 (Format: YYYY-MM-DD or '25 Aug 2025')"]
            elif "reasons" in missing_fields:
                if user_language == 'hindi':
                    response_parts = ["बहुत अच्छा! अब छुट्टी का कारण बताएं।"]
                else:
                    response_parts = ["Excellent! What's the reason for your leave?"]
            else:
                # This shouldn't happen if we have missing fields, but just in case
                if user_language == 'hindi':
                    response_parts = ["🤝 मैं आपकी छुट्टी के लिए आवेदन में मदद करूंगा।"]
                else:
                    response_parts = ["🤝 I'll help you apply for leave."]

            # Show leave balance
            if leave_balance:
                balance_info = []
                for key, value in leave_balance.items():
                    if "_balance" in key:
                        leave_type = key.replace("_balance", "").replace("_", " ").title()
                        balance_info.append(f"{leave_type}: {value} days")

                if balance_info:
                    response_parts.append(f"\n💼 आपका वर्तमान छुट्टी शेष। Your current leave balance: {', '.join(balance_info)}")

            # Save conversation state to Redis
            logger.info(f"💾 Saving collected_info to state: {collected_info}")
            conversation_state = {
                "action": "applying_leave",
                "leave_info": collected_info,
                "available_types": available_types,
                "leave_balance": leave_balance
            }

            if session_id:
                update_conversation_state(user_id, session_id, conversation_state)
            else:
                # Legacy behavior - save to any active session
                update_conversation_state(user_id, "legacy", conversation_state)

            return {
                "response": "".join(response_parts),
                "action_needed": True,
                "context": conversation_state
            }

        else:
            # All information collected, validate and apply
            logger.info(f"🔍 Validating leave request with data: {collected_info}")
            validation_result = await mcp_client.call_tool("validate_leave_request", {
                "user_id": user_id,
                "leave_type_name": collected_info["leave_type_name"],
                "from_date": collected_info["from_date"],
                "to_date": collected_info["to_date"]
            })
            logger.info(f"✅ Validation result: {validation_result}")

            if not validation_result.get("is_valid", False):
                errors = validation_result.get("errors", [])
                logger.error(f"❌ Validation failed with errors: {errors}")

                # Save conversation state for validation failures too
                conversation_state = {
                    "action": "applying_leave",
                    "leave_info": collected_info,
                    "available_types": leave_types_result.get("leave_types", []),
                    "leave_balance": leave_types_result.get("leave_balance", {})
                }

                if session_id:
                    update_conversation_state(user_id, session_id, conversation_state)
                else:
                    update_conversation_state(user_id, "legacy", conversation_state)

                return {
                    "response": f"❌ {'; '.join(errors)}",
                    "action_needed": True,
                    "context": conversation_state
                }

            # Apply leave (use leave type as default reason if not provided)
            default_reason = f"{collected_info['leave_type_name']} application"
            apply_result = await mcp_client.call_tool("apply_leave", {
                "user_id": user_id,
                "leave_type_name": collected_info["leave_type_name"],
                "from_date": collected_info["from_date"],
                "to_date": collected_info["to_date"],
                "reasons": collected_info.get("reasons", default_reason)
            })

            if apply_result.get("status") == "success":
                # Clear conversation state on successful completion
                if session_id:
                    clear_conversation_state(user_id, session_id)
                else:
                    clear_conversation_state(user_id, "legacy")
                return {
                    "response": f"✅ बधाई हो! {apply_result.get('message', 'छुट्टी सफलतापूर्वक लागू हो गई')}। Congratulations! Your {collected_info['leave_type_name']} leave from {collected_info['from_date']} to {collected_info['to_date']} has been submitted for approval.",
                    "action_needed": False
                }
            else:
                # DON'T clear conversation state on error - preserve it for retry
                # Save the current state so user can continue
                conversation_state = {
                    "action": "applying_leave",
                    "leave_info": collected_info,
                    "available_types": collect_result.get("available_leave_types", []),
                    "leave_balance": collect_result.get("leave_balance", {})
                }

                if session_id:
                    update_conversation_state(user_id, session_id, conversation_state)
                else:
                    update_conversation_state(user_id, "legacy", conversation_state)

                # Extract the exact API error message
                error_message = apply_result.get('message', 'Unknown error')

                # If there's more detailed error info, use it
                if 'zimyo_response' in apply_result:
                    zimyo_response = apply_result['zimyo_response']
                    if isinstance(zimyo_response, dict):
                        # Try to get more specific error from Zimyo API response
                        api_error = (zimyo_response.get('message') or
                                   zimyo_response.get('error') or
                                   zimyo_response.get('data', {}).get('message') if isinstance(zimyo_response.get('data'), dict) else None)
                        if api_error:
                            error_message = api_error

                return {
                    "response": f"❌ {error_message}",
                    "action_needed": True,
                    "context": conversation_state
                }

    except Exception as e:
        logger.error(f"Error handling leave application: {e}")
        # Don't clear state on exception either - let user retry
        return {
            "response": f"❌ Error processing leave application: {str(e)}. Please try again.",
            "action_needed": True
        }

async def handle_attendance_marking(user_id: str, user_message: str, conversation_context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Handle attendance marking requests"""
    try:
        # Extract location if mentioned in the message
        message_lower = user_message.lower()
        location = ""

        # Simple location extraction (can be enhanced)
        if " at " in message_lower:
            parts = message_lower.split(" at ")
            if len(parts) > 1:
                location = parts[1].strip()
        elif " from " in message_lower:
            parts = message_lower.split(" from ")
            if len(parts) > 1:
                location = parts[1].strip()

        # Mark attendance using Zimyo API (handles both check-in/check-out automatically)
        result = await mcp_client.call_tool("mark_attendance", {
            "user_id": user_id,
            "location": location
        })
        logging.info(f"mark my attendance result : {result}")
        if result.get("status") == "success":
            location_msg = f" from {result.get('location', 'office')}" if result.get('location') else ""
            return {
                "response": f"✅ हाजिरी लग गई! {result.get('message', 'Attendance marked successfully')} at {result.get('timestamp', 'now')}{location_msg}",
                "action_needed": False
            }
        elif result.get("error") and "already marked attendance" in str(result.get("message", "")).lower():
            # Handle duplicate punch attempt gracefully
            return {
                "response": f"ℹ️ {result.get('message', 'You have already marked attendance for this time period')}. No action needed.",
                "action_needed": False
            }
        else:
            return {
                "response": f"❌ Failed to mark attendance: {result.get('message', 'Unknown error')}",
                "action_needed": False
            }

    except Exception as e:
        logger.error(f"Error handling attendance marking: {e}")
        return {
            "response": f"Error marking attendance: {str(e)}",
            "action_needed": False
        }

async def handle_leave_balance_inquiry(user_id: str, user_message: str, conversation_context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Handle leave balance inquiries"""
    try:
        # First, check the leave policy (get leave types with policy information)
        policy_result = await mcp_client.call_tool("get_leave_types", {
            "user_id": user_id
        })

        if policy_result.get("status") != "success":
            return {
                "response": f"❌ Could not retrieve leave policy: {policy_result.get('message', 'Unknown error')}",
                "action_needed": False
            }

        # Then get the leave balance
        result = await mcp_client.call_tool("get_leave_balance", {
            "user_id": user_id
        })

        if result.get("status") == "success":
            leave_balance = result.get("leave_balance", {})

            if leave_balance:
                balance_info = []
                for leave_type, balance_value in leave_balance.items():
                    # Format: "• Leave Type: X days"
                    balance_info.append(f"• {leave_type}: {balance_value} days")

                response = "📊 आपका वर्तमान छुट्टी शेष। Your current leave balance:\n" + "\n".join(balance_info)
            else:
                response = "❌ आपकी प्रोफाइल में कोई छुट्टी बैलेंस जानकारी नहीं मिली। No leave balance information found in your profile."

            return {
                "response": response,
                "action_needed": False
            }
        else:
            return {
                "response": f"❌ Could not retrieve leave balance: {result.get('message', 'Unknown error')}",
                "action_needed": False
            }

    except Exception as e:
        logger.error(f"Error handling leave balance inquiry: {e}")
        return {
            "response": f"Error getting leave balance: {str(e)}",
            "action_needed": False
        }

async def handle_hr_policy_inquiry(user_id: str, user_message: str, conversation_context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Handle employee-specific HR policy questions using Redis policy data"""
    try:
        user_language = detect_user_language(user_message)

        # Get employee's policy information from Redis instead of MCP API
        logger.info(f"Fetching policy information from Redis for user: {user_id}")

        # Return signal to use existing policy search system from Redis
        if user_language == 'hindi':
            response = "📋 मैं आपको आपकी कंपनी की नीतियों के बारे में जानकारी देता हूं। I'll help you with your company policy information based on your profile."
        else:
            response = "📋 I'll help you with your company policy information based on your profile."

        return {
            "response": response,
            "action_needed": False,
            "use_policy_search": True  # Signal to use existing policy search system with Redis data
        }

    except Exception as e:
        logger.error(f"Error handling HR policy inquiry: {e}")
        return {
            "response": f"Error getting policy information: {str(e)}",
            "action_needed": False
        }

# ===================== MAIN INTENT DETECTOR =====================

def detect_user_language(user_message: str) -> str:
    """Detect the primary language of user message"""
    try:
        from langdetect import detect
        detected_lang = detect(user_message)

        # Map language codes to readable names
        lang_map = {
            'hi': 'hindi',
            'en': 'english',
            'es': 'spanish',
            'fr': 'french',
            'de': 'german',
            'pt': 'portuguese',
            'it': 'italian',
            'ja': 'japanese',
            'ko': 'korean',
            'zh': 'chinese',
            'ar': 'arabic',
            'ru': 'russian'
        }

        return lang_map.get(detected_lang, 'english')
    except:
        # Fallback to english if detection fails
        return 'english'

async def detect_hr_intent_with_ai(user_message: str) -> Optional[str]:
    """Use AI model to detect HR-related intents from user message in ANY language"""
    logger.info(f"Starting AI intent detection for: '{user_message}'")

    from services.ai.chat import get_chat_response

    # Detect user's language for better contextual understanding
    user_language = detect_user_language(user_message)
    logger.info(f"Detected language: {user_language}")

    # Create a more comprehensive language-agnostic prompt for intent detection
    intent_prompt = f"""You are an advanced multilingual HR intent classifier. Analyze the employee message and determine their intent, regardless of language, dialect, informal expressions, or typos.

Employee Message: "{user_message}"

Analyze for these HR intents:

🔍 LEAVE APPLICATION (respond: apply_leave):
- Intent: Employee wants to request/apply for time off
- Indicators: "apply", "request", "take", "need", "want", "book" + "leave", "vacation", "time off", "day off", "absent", "holiday", "break"
- Examples: "I want to apply for leave", "Need 2 days off", "Apply chutti", "छुट्टी चाहिए", "Urlaub beantragen", "Solicitar vacaciones"
- Context: Often includes dates, duration, reasons, or urgency

🔍 ATTENDANCE (respond: mark_attendance):
- Intent: Employee wants to record their presence/absence
- Indicators: "mark", "punch", "check", "clock", "record", "log" + "attendance", "present", "in", "out", "time"
- Examples: "Mark my attendance", "Punch in", "Check in office", "हाजिरी लगाओ", "Anwesenheit markieren"
- Context: Often related to being at office, arriving, leaving

🔍 LEAVE BALANCE (respond: leave_balance):
- Intent: Employee wants to check remaining/available leaves
- Indicators: "check", "show", "how many", "balance", "remaining", "left", "available" + "leave", "days", "vacation"
- Examples: "Check leave balance", "How many leaves left", "कितनी छुट्टी बची", "Show my balance", "Verbleibende Urlaubstage"
- Context: Questions about quantities, availability, entitlements

🔍 HR POLICY QUESTIONS (respond: hr_policy):
- Intent: Employee wants information about HR policies, benefits, rules
- Indicators: "policy", "rule", "benefit", "scheme", "guideline", "procedure", "what is", "how does", "explain", "my policy"
- Examples: "What is leave policy", "What my leave policy", "My leave policy", "Company benefits", "HR rules", "नीति क्या है", "Tell me about policy"
- Context: Questions about company policies, procedures, benefits, general HR information
- IMPORTANT: If user asks about "my policy" or "what policy", this is ALWAYS hr_policy, NOT apply_leave

🔍 JOB DESCRIPTION/ROLE QUERIES (respond: hr_policy):
- Intent: Employee asking about job descriptions, role responsibilities, org structure
- Indicators: "job description", "role", "responsibilities", "duties", "position", "designation", "create JD", "write JD"
- Examples: "Create job description", "What are my responsibilities", "Job role details"

🚫 NON-HR (respond: none):
- General conversation, greetings, weather, personal chat, technical issues unrelated to HR

IMPORTANT:
1. Focus on SEMANTIC MEANING and INTENT, not exact word matching
2. Consider context and implied needs
3. Handle informal language, abbreviations, and typos
4. Understand across all languages and cultural contexts

Respond with EXACTLY one of: apply_leave, mark_attendance, leave_balance, hr_policy, none"""

    try:
        logger.info("Calling AI model for intent classification...")
        response = get_chat_response(role="employee", prompt=intent_prompt)
        intent = response.strip().lower()
        logger.info(f"AI model response: '{response}' -> parsed intent: '{intent}'")

        # Clean up the response to extract just the intent - CHECK POLICY FIRST to avoid false positives
        if "hr_policy" in intent:
            logger.info("AI detected: hr_policy")
            return "hr_policy"
        elif "leave_balance" in intent:
            logger.info("AI detected: leave_balance")
            return "leave_balance"
        elif "mark_attendance" in intent:
            logger.info("AI detected: mark_attendance")
            return "mark_attendance"
        elif "apply_leave" in intent:
            logger.info("AI detected: apply_leave")
            return "apply_leave"
        else:
            # Fallback to enhanced simple detection with fuzzy matching
            logger.info(f"AI intent unclear: '{intent}', falling back to enhanced simple detection")
            enhanced_intent = detect_hr_intent_enhanced(user_message)
            if enhanced_intent:
                return enhanced_intent

            # Final fallback: use fuzzy matcher
            from services.utils.fuzzy_matcher import simple_fuzzy_matcher
            fuzzy_intent = simple_fuzzy_matcher.detect_intent_from_text(user_message)
            if fuzzy_intent:
                logger.info(f"Fuzzy matcher detected intent: {fuzzy_intent}")
                return fuzzy_intent

            return None

    except Exception as e:
        logger.error(f"Error in AI intent detection: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Fallback to enhanced simple detection with fuzzy matching
        logger.info("Falling back to enhanced simple detection due to error")
        enhanced_intent = detect_hr_intent_enhanced(user_message)
        if enhanced_intent:
            return enhanced_intent

        # Final fallback: use fuzzy matcher
        from services.simple_fuzzy_matcher import simple_fuzzy_matcher
        fuzzy_intent = simple_fuzzy_matcher.detect_intent_from_text(user_message)
        if fuzzy_intent:
            logger.info(f"Fuzzy matcher detected intent: {fuzzy_intent}")
            return fuzzy_intent

        return None

def detect_hr_intent_enhanced(user_message: str) -> Optional[str]:
    """Enhanced fallback intent detection with fuzzy matching and multilingual support"""
    from fuzzywuzzy import fuzz

    message_lower = user_message.lower().strip()

    # Enhanced leave keywords with Hindi/Hinglish and common typos
    leave_keywords = [
        # English
        "leave", "apply", "take", "request", "book", "vacation", "time off", "absent", "holiday",
        # Hindi/Hinglish
        "chutti", "avkash", "छुट्टी", "अवकाश", "lagwa", "lagao", "karna", "chahiye", "leni",
        # Common typos
        "leav", "aplly", "requist", "tak", "absen", "vaccation"
    ]

    # Enhanced attendance keywords
    attendance_keywords = [
        # English
        "attendance", "check in", "check out", "punch", "clock", "present", "haaziri",
        # Hindi/Hinglish
        "हाजिरी", "उपस्थिति", "mark", "maar", "lagao", "office", "काम",
        # Common typos
        "attendence", "atendance", "puch", "chek", "clok", "attandance"
    ]

    # Enhanced balance keywords
    balance_keywords = [
        # English
        "balance", "remaining", "how many", "left", "available", "kitni", "kitna",
        # Hindi/Hinglish
        "कितना", "कितनी", "बची", "हिसाब", "dekho", "batao", "check",
        # Common typos
        "balanc", "remainig", "avalable", "meny"
    ]

    # HR policy keywords
    policy_keywords = [
        # English
        "policy", "rule", "rules", "guideline", "guidelines", "benefit", "benefits", "scheme",
        # Hindi/Hinglish
        "नीति", "नियम", "guideline", "company", "कंपनी", "फायदे", "लाभ",
        # Common typos
        "polcy", "polisy", "benfit", "benifit", "guidelne"
    ]

    # Use fuzzy matching for better detection
    def fuzzy_match_keywords(text: str, keywords: list, threshold: int = 70) -> bool:
        for keyword in keywords:
            if keyword in text:
                return True
            # Fuzzy match for typos
            for word in text.split():
                if len(word) > 2 and fuzz.ratio(word, keyword) >= threshold:
                    logger.info(f"Fuzzy matched '{word}' to '{keyword}' with score {fuzz.ratio(word, keyword)}")
                    return True
        return False

    # Date pattern detection (enhanced)
    import re
    date_patterns = [
        r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}',  # 22 aug 2025
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\s+\d{4}',  # aug 22 2025
        r'\d{4}-\d{2}-\d{2}',  # 2025-08-22
        r'\d{1,2}/\d{1,2}/\d{4}',  # 22/08/2025
        r'tomorrow|yesterday|today|कल|आज|परसों',  # Natural date expressions
        r'\d+\s*(?:din|day|days)',  # "2 din", "5 days"
    ]
    has_date = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in date_patterns)

    # HR Policy intent detection (enhanced) - CHECK FIRST for more specific patterns
    has_policy_keyword = fuzzy_match_keywords(message_lower, policy_keywords, 70)

    # Special patterns for policy inquiries - more specific patterns
    policy_patterns = [
        r'(?:leave|chutti)\s+(?:policy|polcy|niti)',  # "leave policy"
        r'company\s+(?:policy|rules)',                # "company policy"
        r'(?:what|kya)\s+(?:is|hai|my).*(?:policy|rule)', # "what is policy", "what my policy"
        r'(?:hr|company)\s+(?:benefits|fayde)',       # "HR benefits"
        r'(?:policy|नीति)\s+(?:ke|ka)\s+(?:bare|about)', # "policy ke bare"
        r'my\s+(?:leave\s+)?policy',                  # "my leave policy", "my policy"
        r'what.*(?:leave\s+)?policy',                 # "what leave policy", "what policy"
        r'tell.*(?:about|me).*policy',                # "tell me about policy"
    ]

    has_policy_pattern = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in policy_patterns)

    if has_policy_keyword or has_policy_pattern:
        logger.info(f"Enhanced detection found policy intent in: '{user_message}'")
        return "hr_policy"

    # Balance intent detection (enhanced) - CHECK SECOND for balance-specific patterns
    has_balance_keyword = fuzzy_match_keywords(message_lower, balance_keywords, 70)
    has_leave_context = any(word in message_lower for word in ["leave", "chutti", "छुट्टी"])

    # Special patterns for balance inquiry (enhanced)
    balance_patterns = [
        r'kitni\s+(?:chutti|leave)\s+bachi',   # "kitni chutti bachi"
        r'leaves?\s+check\s+kar+o?',           # "leaves check karo"
        r'balance\s+batao',                    # "balance batao"
        r'kitna\s+leave\s+hai',                # "kitna leave hai"
        r'(?:leave|chutti)\s+ka\s+hisab',      # "leave ka hisab"
        r'(?:leave|chutti)\s+balance\s+dekho', # "leave balance dekho"
        r'कितनी\s+छुट्टी\s+बची\s+है',           # "कितनी छुट्टी बची है"
        r'how\s+(?:many|meny)\s+leaves?',      # "how many leaves"
        r'remainig\s+leaves?',                 # typo: "remainig leaves"
        r'check.*leave.*balance',              # "check leave balance"
        r'show.*balance',                      # "show balance"
    ]

    has_balance_pattern = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in balance_patterns)

    if (has_balance_keyword and has_leave_context) or has_balance_pattern:
        logger.info(f"Enhanced detection found balance intent in: '{user_message}'")
        return "leave_balance"

    # Attendance intent detection (enhanced)
    has_attendance_keyword = fuzzy_match_keywords(message_lower, attendance_keywords, 70)

    # Special patterns for attendance
    attendance_patterns = [
        r'attendance\s+kr+\s+do',           # "attendance kr do"
        r'punch\s+maar\s+do',               # "punch maar do"
        r'office\s+(?:mai|me)\s+hu',        # "office mai hu"
        r'present\s+mark\s+kar+o?',         # "present mark karo"
        r'haaziri\s+lagao',                 # "haaziri lagao"
        r'mark.*attendance',                # "mark attendance"
        r'punch.*in',                       # "punch in"
        r'check.*in',                       # "check in"
    ]

    has_attendance_pattern = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in attendance_patterns)

    if has_attendance_keyword or has_attendance_pattern:
        logger.info(f"Enhanced detection found attendance intent in: '{user_message}'")
        return "mark_attendance"

    # Leave intent detection (enhanced) - CHECK LAST to avoid false positives
    has_leave_keyword = fuzzy_match_keywords(message_lower, leave_keywords, 70)

    # Special patterns for leave requests - make these more specific
    leave_patterns = [
        r'merai?\s+leave\s+apply\s+kr+o?',  # "merai leave apply krro"
        r'chutti\s+kr+\s+do',               # "chutti kr do"
        r'leave\s+lagwa\s+do',              # "leave lagwa do"
        r'absent\s+(?:rahunga|rahuga)',     # "absent rahunga"
        r'time\s+off\s+chahiye',            # "time off chahiye"
        r'apply.*leave',                    # "apply leave"
        r'request.*leave',                  # "request leave"
        r'take.*leave',                     # "take leave"
        r'need.*leave',                     # "need leave"
        r'want.*leave',                     # "want leave"
    ]

    has_leave_pattern = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in leave_patterns)

    # Only match leave application if it has specific action words or dates, not just the word "leave"
    leave_action_words = ["apply", "request", "take", "need", "want", "book", "lagwa", "करना", "chahiye"]
    has_leave_action = any(action in message_lower for action in leave_action_words)

    if (has_leave_pattern or (has_leave_keyword and has_leave_action) or
        (has_date and any(word in message_lower for word in ["leave", "chutti", "absent"]))):
        logger.info(f"Enhanced detection found leave intent in: '{user_message}'")
        return "apply_leave"

    return None

def detect_hr_intent_simple(user_message: str) -> Optional[str]:
    """Simple fallback intent detection - now calls enhanced version"""
    return detect_hr_intent_enhanced(user_message)

# Keep the old function as an alias for backward compatibility
def detect_hr_intent(user_message: str) -> Optional[str]:
    """Simple synchronous intent detection (fallback)"""
    return detect_hr_intent_simple(user_message)

async def process_hr_action(user_id: str, user_message: str, intent: str, conversation_context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Process HR actions based on detected intent"""

    if intent == "apply_leave":
        return await handle_leave_application(user_id, user_message, conversation_context, session_id)

    elif intent == "mark_attendance":
        return await handle_attendance_marking(user_id, user_message, conversation_context, session_id)

    elif intent == "leave_balance":
        return await handle_leave_balance_inquiry(user_id, user_message, conversation_context, session_id)

    elif intent == "hr_policy":
        return await handle_hr_policy_inquiry(user_id, user_message, conversation_context, session_id)

    else:
        return {
            "response": "I'm not sure how to help with that HR request. Please try asking about leave applications, attendance marking, leave balance, or HR policies.",
            "action_needed": False
        }

# ===================== CONTEXT HANDLER FOR ONGOING CONVERSATIONS =====================

async def handle_continuing_conversation(user_id: str, user_message: str, context: Dict = None, session_id: str = None) -> Dict[str, Any]:
    """Handle ongoing conversations based on context"""
    from services.operations.conversation_state import get_conversation_state, update_conversation_state

    # Get conversation state from Redis if not provided
    if context is None:
        if session_id:
            context = get_conversation_state(user_id, session_id) or {}
        else:
            from services.operations.conversation_state import get_conversation_state_legacy
            context = get_conversation_state_legacy(user_id) or {}

    action = context.get("action")

    if action == "applying_leave":
        # Continue collecting leave information
        leave_info = context.get("leave_info", {})

        # Try to extract information from current message
        message_lower = user_message.lower()

        # Extract leave type using fuzzy matching (handles typos and languages)
        if "leave_type_name" not in leave_info:
            available_types = context.get("available_types", [])
            from services.utils.fuzzy_matcher import simple_fuzzy_matcher

            match = simple_fuzzy_matcher.fuzzy_match_leave_type(user_message, available_types)
            if match:
                matched_leave_type, confidence = match
                leave_info["leave_type_name"] = matched_leave_type.get("name")
                logger.info(f"✅ Fuzzy extracted leave type: '{matched_leave_type.get('name')}' from message: '{user_message}' (confidence: {confidence})")
            else:
                logger.info(f"❌ No leave type extracted from message: '{user_message}'. Available types: {[lt.get('name') for lt in available_types]}")

        # Extract dates (multiple formats)
        import re
        from datetime import datetime

        # Try different date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2025-08-22
            r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}',  # 22 aug 2025
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\s+\d{4}',  # aug 22 2025
        ]

        for pattern in date_patterns:
            dates = re.findall(pattern, user_message, re.IGNORECASE)
            if dates:
                # Convert to standard format
                converted_dates = []
                for date_str in dates:
                    try:
                        if '-' in date_str:
                            # Already in YYYY-MM-DD format
                            converted_dates.append(date_str)
                        else:
                            # Parse natural language date
                            dt = datetime.strptime(date_str.lower(), '%d %b %Y')
                            converted_dates.append(dt.strftime('%Y-%m-%d'))
                    except ValueError:
                        try:
                            dt = datetime.strptime(date_str.lower(), '%b %d %Y')
                            converted_dates.append(dt.strftime('%Y-%m-%d'))
                        except ValueError:
                            continue

                # Always assign dates if found in current message (override cached dates)
                if converted_dates:
                    leave_info["from_date"] = converted_dates[0]
                    logger.info(f"🔄 Updated from_date with new date: {converted_dates[0]}")

                    if len(converted_dates) > 1:
                        leave_info["to_date"] = converted_dates[1]
                        logger.info(f"🔄 Updated to_date: {converted_dates[1]}")
                    else:
                        leave_info["to_date"] = converted_dates[0]
                        logger.info(f"🔄 Updated to_date (same as from): {converted_dates[0]}")

                break

        # Extract reason (only if it's not a leave type or date-related)
        available_type_names = [lt.get("name", "").lower() for lt in context.get("available_types", [])]

        # More specific check for leave type keywords to avoid false positives
        is_leave_type = False
        for type_name in available_type_names:
            # Check for specific leave type keywords, not generic "leave"
            leave_keywords = []
            if "earned" in type_name:
                leave_keywords.append("earned")
            elif "sick" in type_name:
                leave_keywords.append("sick")
            elif "casual" in type_name:
                leave_keywords.append("casual")
            elif "emergency" in type_name:
                leave_keywords.append("emergency")
            elif "maternity" in type_name:
                leave_keywords.append("maternity")
            elif "paternity" in type_name:
                leave_keywords.append("paternity")
            elif "comp" in type_name or "compensatory" in type_name:
                leave_keywords.extend(["comp", "compensatory"])
            elif "annual" in type_name:
                leave_keywords.append("annual")

            if any(keyword in message_lower for keyword in leave_keywords):
                is_leave_type = True
                break

        # Only extract reason if we already have both leave_type and dates
        # This prevents dates or leave types from being misidentified as reasons
        if ("reasons" not in leave_info and
            "leave_type_name" in leave_info and
            "from_date" in leave_info and
            "to_date" in leave_info and
            not any(word in message_lower for word in ["type", "date", "when"]) and
            not is_leave_type):
            leave_info["reasons"] = user_message
            logger.info(f"Extracted reason: {user_message}")

        # Update conversation state with extracted info
        if session_id:
            update_conversation_state(user_id, session_id, {"leave_info": leave_info})
        else:
            update_conversation_state(user_id, "legacy", {"leave_info": leave_info})

        # Continue the leave application process
        return await handle_leave_application(user_id, user_message, None, session_id)

    elif action == "marking_attendance":
        # Handle attendance marking (no action needed since Zimyo API handles both)
        return await handle_attendance_marking(user_id, user_message, None, session_id)

    # Default: no context handling
    return {
        "response": "I'm not sure how to proceed. Can you please clarify what you'd like to do?",
        "action_needed": False
    }