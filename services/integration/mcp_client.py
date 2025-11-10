"""
HTTP-based MCP Client for Zimyo HRMS Operations
Supports both local (stdio subprocess) and remote (HTTP) communication modes
"""

import json
import logging
import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class HTTPMCPClient:
    """
    MCP Client that supports both local and remote server communication

    Modes:
    1. HTTP Mode (Remote): When MCP_SERVER_URL is set
       - Sends HTTP POST requests to remote MCP server
       - Best for production with separate service hosting
       - Supports load balancing and scaling

    2. Stdio Mode (Local): When MCP_SERVER_URL is not set
       - Spawns local Node.js subprocess
       - Best for local development
       - Falls back to this mode if HTTP fails
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        server_path: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize MCP Client

        Args:
            server_url: HTTP URL for remote MCP server (e.g., "http://localhost:3000/mcp")
            server_path: Local file path for stdio mode fallback
            auth_token: Optional authentication token for remote server
            timeout: Request timeout in seconds (default: 30)
        """
        # Try to get server URL from environment
        self.server_url = server_url or os.getenv('MCP_SERVER_URL')

        # Get auth token from environment if not provided
        self.auth_token = auth_token or os.getenv('MCP_AUTH_TOKEN')

        # Set timeout
        self.timeout = timeout

        # Determine mode
        self.mode = 'http' if self.server_url else 'stdio'

        # For stdio mode, set up local server path
        if self.mode == 'stdio':
            if server_path is None:
                server_path = os.getenv('MCP_SERVER_PATH')

            if server_path is None:
                # Calculate path relative to current file
                # __file__ = .../zimyo_ai_assistant/services/integration/mcp_client.py
                # parent.parent.parent = .../zimyo ai/
                current_dir = Path(__file__).parent.parent.parent.parent  # "zimyo ai"/
                server_path = str(current_dir / "zimyo_api_server" / "src" / "mcp" / "server.js")

            self.server_path = server_path
        else:
            self.server_path = None

        logger.info(f"MCP Client initialized in {self.mode.upper()} mode")
        if self.mode == 'http':
            logger.info(f"Remote MCP Server URL: {self.server_url}")
        else:
            logger.info(f"Local MCP Server Path: {self.server_path}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result from the tool execution
        """
        try:
            if self.mode == 'http':
                return await self._call_tool_http(tool_name, arguments)
            else:
                return await self._call_tool_stdio(tool_name, arguments)

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")

            # If HTTP mode failed, try falling back to stdio mode
            if self.mode == 'http' and self.server_path:
                logger.warning("HTTP mode failed, falling back to stdio mode")
                try:
                    return await self._call_tool_stdio(tool_name, arguments)
                except Exception as fallback_error:
                    logger.error(f"Stdio fallback also failed: {fallback_error}")

            return {"status": "error", "message": str(e)}

    async def _call_tool_http(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP tool via HTTP POST request

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result from the tool execution
        """
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }

        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        # Send HTTP POST request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=request,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"HTTP {response.status}: {error_text}")
                    return {
                        "status": "error",
                        "message": f"HTTP {response.status}: {error_text}"
                    }

                response_data = await response.json()

                # Extract result from MCP response
                if 'result' in response_data:
                    content = response_data['result'].get('content', [])
                    if content and len(content) > 0:
                        text = content[0].get('text', '{}')
                        return json.loads(text)

                # If no valid result, check for error
                if 'error' in response_data:
                    error = response_data['error']
                    logger.error(f"MCP Error: {error}")
                    return {
                        "status": "error",
                        "message": error.get('message', 'Unknown error')
                    }

                logger.error("Invalid MCP response format")
                return {
                    "status": "error",
                    "message": "Invalid response format from MCP server"
                }

    async def _call_tool_stdio(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP tool via local subprocess (stdio mode)

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Result from the tool execution
        """
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        # Start the MCP server process
        process = await asyncio.create_subprocess_exec(
            'node',
            self.server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Send request to server
        request_json = json.dumps(request) + '\n'

        try:
            # Write request to stdin
            process.stdin.write(request_json.encode())
            await process.stdin.drain()
            process.stdin.close()

            # Read response with timeout
            stdout_data = b''
            stderr_data = b''

            async def read_output():
                nonlocal stdout_data, stderr_data
                # Read until we get a complete JSON response
                # Increased limit to 10MB to handle large responses (salary slips with PDFs)
                while True:
                    line = await process.stdout.read(10 * 1024 * 1024)  # Read up to 10MB at once
                    if not line:
                        break
                    stdout_data += line
                    # Check if we have a valid JSON-RPC response
                    decoded = stdout_data.decode().strip()
                    for response_line in decoded.split('\n'):
                        if response_line.strip() and '"jsonrpc"' in response_line and '"result"' in response_line:
                            # We got a valid response, we can stop reading
                            return

            await asyncio.wait_for(read_output(), timeout=self.timeout)

            # Get any stderr output
            try:
                stderr_data = await asyncio.wait_for(process.stderr.read(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

            # Kill the process since it won't exit on its own
            process.kill()
            await process.wait()

            stdout = stdout_data
            stderr = stderr_data

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"MCP subprocess timed out after {self.timeout}s")
            return {
                "status": "error",
                "message": f"Request timed out after {self.timeout} seconds"
            }
        except Exception as e:
            process.kill()
            await process.wait()
            logger.error(f"MCP subprocess error: {e}")
            return {
                "status": "error",
                "message": f"Subprocess error: {str(e)}"
            }

        # Parse response
        if stdout:
            # MCP server may send multiple lines, get the last valid JSON
            lines = stdout.decode().strip().split('\n')
            logger.debug(f"MCP stdout lines: {lines}")

            for line in reversed(lines):
                # Skip empty lines and status messages
                if not line.strip() or 'MCP Server running' in line or 'Connected to Redis' in line:
                    continue

                try:
                    response = json.loads(line)
                    if 'result' in response:
                        # Extract text content from MCP response
                        content = response['result'].get('content', [])
                        if content and len(content) > 0:
                            text = content[0].get('text', '{}')
                            logger.debug(f"MCP response text: {text}")
                            return json.loads(text)
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse line as JSON: {line[:100]}... Error: {e}")
                    continue

        # If no valid response found, return error
        stderr_output = stderr.decode() if stderr else ""
        stdout_output = stdout.decode() if stdout else ""
        error_msg = stderr_output or "No valid response from MCP server"
        logger.error(f"MCP Error - stderr: {stderr_output}, stdout: {stdout_output[:200]}")
        return {"status": "error", "message": error_msg}

    async def mark_attendance(self, user_id: str, location: str = "") -> Dict[str, Any]:
        """Mark attendance for a user"""
        return await self.call_tool("mark_attendance", {
            "user_id": user_id,
            "location": location
        })

    async def apply_leave(
        self,
        user_id: str,
        leave_type_name: str,
        from_date: str,
        to_date: str,
        reasons: str,
        is_half_day: str = "0"
    ) -> Dict[str, Any]:
        """Apply for leave"""
        return await self.call_tool("apply_leave", {
            "user_id": user_id,
            "leave_type_name": leave_type_name,
            "from_date": from_date,
            "to_date": to_date,
            "reasons": reasons,
            "is_half_day": is_half_day
        })

    async def get_leave_balance(self, user_id: str) -> Dict[str, Any]:
        """Get leave balance for a user"""
        return await self.call_tool("get_leave_balance", {
            "user_id": user_id
        })

    async def get_leave_types(self, user_id: str) -> Dict[str, Any]:
        """Get available leave types for a user"""
        return await self.call_tool("get_leave_types", {
            "user_id": user_id
        })

    async def validate_leave_request(
        self,
        user_id: str,
        leave_type_name: str,
        from_date: str,
        to_date: str
    ) -> Dict[str, Any]:
        """Validate a leave request"""
        return await self.call_tool("validate_leave_request", {
            "user_id": user_id,
            "leave_type_name": leave_type_name,
            "from_date": from_date,
            "to_date": to_date
        })

    async def collect_leave_details(
        self,
        user_id: str,
        collected_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Collect and validate leave details"""
        return await self.call_tool("collect_leave_details", {
            "user_id": user_id,
            "collected_info": collected_info
        })


# Singleton instance
_http_mcp_client = None


def get_http_mcp_client() -> HTTPMCPClient:
    """
    Get or create the HTTP MCP client singleton

    This factory function automatically detects the mode based on environment:
    - If MCP_SERVER_URL is set: Uses HTTP mode (remote server)
    - If MCP_SERVER_URL is not set: Uses stdio mode (local subprocess)

    Environment Variables:
        MCP_SERVER_URL: URL for remote MCP server (e.g., "http://api.example.com/mcp")
        MCP_AUTH_TOKEN: Optional authentication token for remote server
        MCP_SERVER_PATH: Optional local path for stdio mode fallback
        MCP_TIMEOUT: Optional timeout in seconds (default: 30)

    Returns:
        HTTPMCPClient instance
    """
    global _http_mcp_client
    if _http_mcp_client is None:
        timeout = int(os.getenv('MCP_TIMEOUT', '30'))
        _http_mcp_client = HTTPMCPClient(timeout=timeout)
    return _http_mcp_client


# Backward compatibility alias
get_mcp_client = get_http_mcp_client
