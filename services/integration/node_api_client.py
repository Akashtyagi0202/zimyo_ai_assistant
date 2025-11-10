"""
Node.js API Client
Handles communication with the Node.js Zimyo API server
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Node.js API server configuration
NODE_API_BASE_URL = "http://localhost:3000/api"

class NodeAPIClient:
    """Client for calling Node.js API endpoints"""

    def __init__(self, base_url: str = NODE_API_BASE_URL):
        self.base_url = base_url

    async def call_api(self, endpoint: str, method: str = "POST", data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make API call to Node.js server"""
        try:
            url = f"{self.base_url}/{endpoint}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "POST":
                    response = await client.post(url, json=data)
                elif method.upper() == "GET":
                    response = await client.get(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Node API {endpoint}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    return e.response.json()
                except:
                    pass
            return {"status": "error", "message": f"API call failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Error calling Node API {endpoint}: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    # Leave Operations

    async def apply_leave(self, user_id: str, leave_type_name: str, from_date: str,
                         to_date: str, reasons: str, is_half_day: str = "0",
                         documents_required: str = "null") -> Dict[str, Any]:
        """Apply for leave"""
        data = {
            "user_id": user_id,
            "leave_type_name": leave_type_name,
            "from_date": from_date,
            "to_date": to_date,
            "reasons": reasons,
            "is_half_day": is_half_day,
            "documents_required": documents_required
        }
        return await self.call_api("leave/apply", method="POST", data=data)

    async def get_leave_balance(self, user_id: str) -> Dict[str, Any]:
        """Get leave balance"""
        return await self.call_api("leave/balance", method="GET", params={"user_id": user_id})

    async def get_leave_types(self, user_id: str) -> Dict[str, Any]:
        """Get available leave types"""
        return await self.call_api("leave/types", method="GET", params={"user_id": user_id})

    async def validate_leave_request(self, user_id: str, leave_type_name: str,
                                    from_date: str, to_date: str) -> Dict[str, Any]:
        """Validate leave request"""
        data = {
            "user_id": user_id,
            "leave_type_name": leave_type_name,
            "from_date": from_date,
            "to_date": to_date
        }
        return await self.call_api("leave/validate", method="POST", data=data)

    # Attendance Operations

    async def mark_attendance(self, user_id: str, location: str = "") -> Dict[str, Any]:
        """Mark attendance"""
        data = {
            "user_id": user_id,
            "location": location
        }
        return await self.call_api("attendance/mark", method="POST", data=data)

# Global instance
node_api_client = NodeAPIClient()
