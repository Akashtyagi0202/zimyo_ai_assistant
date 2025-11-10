#!/usr/bin/env python3
"""
Comprehensive test for salary slip feature
Tests all layers from API to frontend
"""

import asyncio
import json
import sys

async def test_mcp_salary_slip():
    """Test MCP client salary slip call"""
    print("\n" + "="*70)
    print("TEST 1: MCP Client Salary Slip Call")
    print("="*70)

    try:
        from services.integration.mcp_client import get_http_mcp_client

        mcp_client = get_http_mcp_client()

        print("📤 Calling MCP tool: get_salary_slip")
        print("   User: 240611")
        print("   Month: 10")
        print("   Year: 2025")

        result = await mcp_client.call_tool("get_salary_slip", {
            "user_id": "240611",
            "month": 10,
            "year": 2025
        })

        print("\n📥 MCP Response:")
        print(f"   Type: {type(result)}")
        print(f"   Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

        if isinstance(result, dict):
            print(f"   Status: {result.get('status')}")
            print(f"   Has salary_details: {bool(result.get('salary_details'))}")
            print(f"   Has salary_slip: {bool(result.get('salary_slip'))}")
            print(f"   Has salary_slip_buffer: {bool(result.get('salary_slip_buffer'))}")

            if result.get('salary_slip_buffer'):
                buffer_len = len(result['salary_slip_buffer'])
                print(f"   salary_slip_buffer length: {buffer_len} chars")
                print(f"   salary_slip_buffer preview: {result['salary_slip_buffer'][:100]}...")
            else:
                print(f"   ⚠️ salary_slip_buffer is EMPTY or MISSING")

        print("\n✅ MCP test completed")
        return result

    except Exception as e:
        print(f"\n❌ MCP test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_python_handler():
    """Test Python handler"""
    print("\n" + "="*70)
    print("TEST 2: Python Handler (get_salary_slip)")
    print("="*70)

    try:
        from services.operations.hrms_handlers.get_salary_slip import handle_get_salary_slip
        from services.integration.mcp_client import get_http_mcp_client

        mcp_client = get_http_mcp_client()

        print("📤 Calling Python handler")
        print("   User: 240611")
        print("   Month: 10, Year: 2025")

        result = await handle_get_salary_slip(
            user_id="240611",
            mcp_client=mcp_client,
            session_id="test_session",
            ai_response={"values": {"month": 10, "year": 2025}}
        )

        print("\n📥 Handler Response:")
        print(f"   Type: {type(result)}")
        print(f"   Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

        if isinstance(result, dict):
            print(f"   Has response: {bool(result.get('response'))}")
            print(f"   Has sessionId: {bool(result.get('sessionId'))}")
            print(f"   Has salary_slip_buffer: {bool(result.get('salary_slip_buffer'))}")

            if result.get('salary_slip_buffer'):
                buffer_len = len(result['salary_slip_buffer'])
                print(f"   salary_slip_buffer length: {buffer_len} chars")
            else:
                print(f"   ⚠️ salary_slip_buffer is EMPTY or MISSING")

            if result.get('response'):
                response_preview = result['response'][:200].replace('\n', ' ')
                print(f"   Response preview: {response_preview}...")

        print("\n✅ Handler test completed")
        return result

    except Exception as e:
        print(f"\n❌ Handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_ai_handler():
    """Test AI handler with salary slip query"""
    print("\n" + "="*70)
    print("TEST 3: AI Handler (handle_hrms_with_ai)")
    print("="*70)

    try:
        from services.operations.ai_handler import handle_hrms_with_ai

        print("📤 Calling AI handler")
        print("   User: 240611")
        print("   Message: 'salary slip for October 2025'")

        result = await handle_hrms_with_ai(
            user_id="240611",
            user_message="salary slip for October 2025",
            session_id="test_session"
        )

        print("\n📥 AI Handler Response:")
        print(f"   Type: {type(result)}")
        print(f"   Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

        if isinstance(result, dict):
            print(f"   Has response: {bool(result.get('response'))}")
            print(f"   Has sessionId: {bool(result.get('sessionId'))}")
            print(f"   Has salary_slip_buffer: {bool(result.get('salary_slip_buffer'))}")

            if result.get('salary_slip_buffer'):
                buffer_len = len(result['salary_slip_buffer'])
                print(f"   salary_slip_buffer length: {buffer_len} chars")
            else:
                print(f"   ⚠️ salary_slip_buffer is EMPTY or MISSING")

        print("\n✅ AI Handler test completed")
        return result

    except Exception as e:
        print(f"\n❌ AI Handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 SALARY SLIP COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nTesting all layers of salary slip feature...")
    print("This will help identify where the PDF buffer is being lost\n")

    # Test 1: MCP Client
    mcp_result = await test_mcp_salary_slip()

    # Test 2: Python Handler
    handler_result = await test_python_handler()

    # Test 3: AI Handler (full flow)
    ai_result = await test_ai_handler()

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    print("\n1. MCP Client Test:")
    if mcp_result and isinstance(mcp_result, dict):
        has_buffer = bool(mcp_result.get('salary_slip_buffer'))
        print(f"   ✅ Success - Buffer present: {has_buffer}")
    else:
        print(f"   ❌ Failed or no result")

    print("\n2. Python Handler Test:")
    if handler_result and isinstance(handler_result, dict):
        has_buffer = bool(handler_result.get('salary_slip_buffer'))
        print(f"   ✅ Success - Buffer present: {has_buffer}")
    else:
        print(f"   ❌ Failed or no result")

    print("\n3. AI Handler Test:")
    if ai_result and isinstance(ai_result, dict):
        has_buffer = bool(ai_result.get('salary_slip_buffer'))
        print(f"   ✅ Success - Buffer present: {has_buffer}")
    else:
        print(f"   ❌ Failed or no result")

    print("\n" + "="*70)
    print("🏁 ALL TESTS COMPLETED")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
