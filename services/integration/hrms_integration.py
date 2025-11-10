"""
HRMS AI Assistant Integration Layer
Connects the new AI system with existing backend services
"""

import json
import logging
from typing import Dict, Any, Optional
from services.assistants.hrms_assistant import HRMSAIAssistant, Intent

logger = logging.getLogger(__name__)

class HRMSIntegrationLayer:
    """Integration layer for HRMS AI Assistant with existing backend"""

    def __init__(self, redis_client):
        self.ai_assistant = HRMSAIAssistant(redis_client)
        self.redis_client = redis_client

    async def process_user_query(self, user_id: str, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for processing user queries
        Integrates with existing system while using new AI capabilities
        """
        try:
            # Process query using AI assistant
            ai_result = await self.ai_assistant.process_query(user_id, query)

            # Handle different result types
            if ai_result.get("error"):
                return ai_result

            if ai_result.get("requires_clarification"):
                return self._format_clarification_response(ai_result, session_id)

            # Route to existing systems or handle directly
            return await self._handle_ai_result(ai_result, user_id, query, session_id)

        except Exception as e:
            logger.error(f"Error in integration layer: {e}")
            return {
                "response": "I'm sorry, I encountered an error processing your request. Please try again.",
                "status": "error"
            }

    def _format_clarification_response(self, ai_result: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        """Format clarification responses"""
        response_data = {
            "response": ai_result["response"],
            "intent": ai_result["intent"],
            "confidence": ai_result["confidence"],
            "language": ai_result["language"],
            "requires_clarification": True
        }

        if session_id:
            response_data["sessionId"] = session_id

        return response_data

    async def _handle_ai_result(self, ai_result: Dict[str, Any], user_id: str, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Handle AI result and route to appropriate systems"""

        # Direct AI responses (like job descriptions or policy queries)
        if "response" in ai_result and not any(key in ai_result for key in ["use_existing_leave_system", "use_existing_attendance_system", "use_existing_balance_system", "use_policy_search"]):
            response_data = {
                "response": ai_result["response"],
                "intent": ai_result["intent"],
                "confidence": ai_result["confidence"],
                "language": ai_result["language"]
            }

            if session_id:
                response_data["sessionId"] = session_id

            return response_data

        # Route to existing leave application system
        if ai_result.get("use_existing_leave_system"):
            return await self._handle_existing_leave_system(ai_result, user_id, query, session_id)

        # Route to existing attendance system
        if ai_result.get("use_existing_attendance_system"):
            return await self._handle_existing_attendance_system(ai_result, user_id, query, session_id)

        # Route to existing balance system
        if ai_result.get("use_existing_balance_system"):
            return await self._handle_existing_balance_system(ai_result, user_id, query, session_id)

        # Route to existing policy search system
        if ai_result.get("use_policy_search"):
            return await self._handle_existing_policy_search(ai_result, user_id, query, session_id)

        # Default fallback
        return {
            "response": "I processed your request but couldn't determine the appropriate action.",
            "intent": ai_result.get("intent", "unknown"),
            "confidence": ai_result.get("confidence", 0.0),
            "language": ai_result.get("language", "en")
        }

    async def _handle_existing_leave_system(self, ai_result: Dict[str, Any], user_id: str, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Route to existing leave application system"""
        try:
            # Import existing leave handlers
            from services.integration.mcp_integration import handle_leave_application

            # Extract entities if available
            entities = ai_result.get("extracted_entities", {})

            # Create conversation context with extracted entities
            conversation_context = None
            if entities:
                conversation_context = {
                    "action": "applying_leave",
                    "leave_info": {},
                    "ai_extracted_entities": entities
                }

                # Map extracted entities to leave info
                if "dates" in entities:
                    dates = entities["dates"]
                    if dates:
                        conversation_context["leave_info"]["from_date"] = dates[0]
                        if len(dates) > 1:
                            conversation_context["leave_info"]["to_date"] = dates[1]

                if "leave_type" in entities:
                    conversation_context["leave_info"]["leave_type_name"] = entities["leave_type"].title() + " Leave"

            # Call existing leave application handler
            leave_result = await handle_leave_application(user_id, query, conversation_context, session_id)

            # Add AI metadata
            if isinstance(leave_result, dict):
                leave_result["ai_intent"] = ai_result["intent"]
                leave_result["ai_confidence"] = ai_result["confidence"]
                leave_result["ai_language"] = ai_result["language"]

            return leave_result

        except Exception as e:
            logger.error(f"Error routing to existing leave system: {e}")
            return {
                "response": "Error processing leave application. Please try again.",
                "status": "error"
            }

    async def _handle_existing_attendance_system(self, ai_result: Dict[str, Any], user_id: str, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Route to existing attendance system"""
        try:
            # Import existing attendance handlers
            from services.integration.mcp_integration import handle_attendance_marking

            # Call existing attendance handler
            attendance_result = await handle_attendance_marking(user_id, query, None, session_id)

            # Add AI metadata
            if isinstance(attendance_result, dict):
                attendance_result["ai_intent"] = ai_result["intent"]
                attendance_result["ai_confidence"] = ai_result["confidence"]
                attendance_result["ai_language"] = ai_result["language"]

            return attendance_result

        except Exception as e:
            logger.error(f"Error routing to existing attendance system: {e}")
            return {
                "response": "Error processing attendance request. Please try again.",
                "status": "error"
            }

    async def _handle_existing_balance_system(self, ai_result: Dict[str, Any], user_id: str, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Route to existing balance system"""
        try:
            # Import existing balance handlers
            from services.integration.mcp_integration import handle_leave_balance_inquiry

            # Call existing balance handler
            balance_result = await handle_leave_balance_inquiry(user_id, query, None, session_id)

            # Add AI metadata
            if isinstance(balance_result, dict):
                balance_result["ai_intent"] = ai_result["intent"]
                balance_result["ai_confidence"] = ai_result["confidence"]
                balance_result["ai_language"] = ai_result["language"]

            return balance_result

        except Exception as e:
            logger.error(f"Error routing to existing balance system: {e}")
            return {
                "response": "Error checking leave balance. Please try again.",
                "status": "error"
            }

    async def _handle_existing_policy_search(self, ai_result: Dict[str, Any], user_id: str, query: str, session_id: Optional[str]) -> Dict[str, Any]:
        """Route to existing policy search system"""
        try:
            # This signals the main app.py to use the existing policy search system
            response_data = {
                "use_policy_search": True,
                "ai_intent": ai_result["intent"],
                "ai_confidence": ai_result["confidence"],
                "ai_language": ai_result["language"]
            }

            if session_id:
                response_data["sessionId"] = session_id

            return response_data

        except Exception as e:
            logger.error(f"Error routing to existing policy search: {e}")
            return {
                "response": "Error searching policies. Please try again.",
                "status": "error"
            }

# Convenience function for easy integration
async def process_hrms_query(redis_client, user_id: str, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for processing HRMS queries
    Can be used as a drop-in replacement for existing intent detection
    """
    integration_layer = HRMSIntegrationLayer(redis_client)
    return await integration_layer.process_user_query(user_id, query, session_id)