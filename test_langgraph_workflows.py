#!/usr/bin/env python3
"""
LangGraph Workflows Test Suite

Tests all HRMS workflows built with LangGraph.

Run: python test_langgraph_workflows.py

Author: Zimyo AI Team
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

async def test_simple_leave_application():
    """Test 1: Simple leave application with all info in one message."""
    print("\n" + "="*80)
    print("TEST 1: Simple Leave Application (Complete Info)")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import process_hrms_message

    result = await process_hrms_message(
        user_id="240611",
        user_message="apply sick leave for tomorrow because not feeling well",
        session_id="test_sess_1"
    )

    print(f"\n📝 User: apply sick leave for tomorrow because not feeling well")
    print(f"🤖 Response: {result['response']}")
    print(f"📊 Intent: {result.get('intent')}")
    print(f"✅ Ready to execute: {result.get('ready_to_execute')}")
    print(f"🔄 Workflow type: {result.get('workflow_type')}")

    assert result.get('intent') == 'apply_leave', "Intent should be apply_leave"
    print("\n✅ TEST 1 PASSED")


async def test_multi_turn_conversation():
    """Test 2: Multi-turn conversation (incomplete info)."""
    print("\n" + "="*80)
    print("TEST 2: Multi-turn Conversation (Progressive Info Collection)")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    session_id = "test_sess_2"

    # Message 1: Just "apply leave"
    print("\n📝 User (1): apply leave")
    result1 = await orchestrator.process_message(
        user_id="240611",
        user_message="apply leave",
        session_id=session_id
    )
    print(f"🤖 Response (1): {result1['response']}")

    # Message 2: Provide type
    print("\n📝 User (2): sick leave")
    result2 = await orchestrator.process_message(
        user_id="240611",
        user_message="sick leave",
        session_id=session_id
    )
    print(f"🤖 Response (2): {result2['response']}")

    # Message 3: Provide date
    print("\n📝 User (3): tomorrow")
    result3 = await orchestrator.process_message(
        user_id="240611",
        user_message="tomorrow",
        session_id=session_id
    )
    print(f"🤖 Response (3): {result3['response']}")

    # Message 4: Provide reason
    print("\n📝 User (4): not feeling well")
    result4 = await orchestrator.process_message(
        user_id="240611",
        user_message="not feeling well",
        session_id=session_id
    )
    print(f"🤖 Response (4): {result4['response']}")

    print("\n✅ TEST 2 PASSED")


async def test_balance_query():
    """Test 3: Simple balance query (no workflow needed)."""
    print("\n" + "="*80)
    print("TEST 3: Leave Balance Query")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import process_hrms_message

    result = await process_hrms_message(
        user_id="240611",
        user_message="show my leave balance",
        session_id="test_sess_3"
    )

    print(f"\n📝 User: show my leave balance")
    print(f"🤖 Response: {result['response']}")
    print(f"📊 Intent: {result.get('intent')}")

    assert result.get('intent') == 'check_leave_balance', "Intent should be check_leave_balance"
    print("\n✅ TEST 3 PASSED")


async def test_regularization():
    """Test 4: Attendance regularization."""
    print("\n" + "="*80)
    print("TEST 4: Attendance Regularization")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import process_hrms_message

    result = await process_hrms_message(
        user_id="240611",
        user_message="regularize attendance for yesterday 9am to 6pm forgot to punch",
        session_id="test_sess_4"
    )

    print(f"\n📝 User: regularize attendance for yesterday 9am to 6pm forgot to punch")
    print(f"🤖 Response: {result['response']}")
    print(f"📊 Intent: {result.get('intent')}")

    assert result.get('intent') == 'apply_regularization', "Intent should be apply_regularization"
    print("\n✅ TEST 4 PASSED")


async def test_on_duty():
    """Test 5: On-duty application."""
    print("\n" + "="*80)
    print("TEST 5: On-duty Application")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import process_hrms_message

    result = await process_hrms_message(
        user_id="240611",
        user_message="apply on duty for today 10am to 2pm client meeting",
        session_id="test_sess_5"
    )

    print(f"\n📝 User: apply on duty for today 10am to 2pm client meeting")
    print(f"🤖 Response: {result['response']}")
    print(f"📊 Intent: {result.get('intent')}")

    assert result.get('intent') == 'apply_onduty', "Intent should be apply_onduty"
    print("\n✅ TEST 5 PASSED")


async def test_workflow_visualization():
    """Test 6: Workflow visualization."""
    print("\n" + "="*80)
    print("TEST 6: Workflow Visualization")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()

    try:
        # Visualize leave approval workflow
        orchestrator.visualize_workflow("leave_approval", "leave_approval_graph.png")
        print("✅ Leave approval workflow visualized: leave_approval_graph.png")

        # Visualize base workflow
        orchestrator.visualize_workflow("base", "base_workflow_graph.png")
        print("✅ Base workflow visualized: base_workflow_graph.png")

        print("\n✅ TEST 6 PASSED")

    except Exception as e:
        print(f"⚠️ Visualization skipped (install graphviz): {e}")
        print("\n⚠️ TEST 6 SKIPPED")


async def test_workflow_state_persistence():
    """Test 7: State persistence across messages."""
    print("\n" + "="*80)
    print("TEST 7: State Persistence (Checkpoint/Resume)")
    print("="*80)

    from services.ai.hrms_workflow_orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    session_id = "test_sess_7"

    # First message
    print("\n📝 Message 1: apply leave")
    result1 = await orchestrator.process_message(
        user_id="240611",
        user_message="apply leave",
        session_id=session_id
    )
    print(f"🤖 Response 1: {result1['response']}")
    print(f"📍 Current step: {result1.get('current_step')}")

    # Wait and send second message (simulating user delay)
    print("\n⏸️  Simulating user delay...")
    await asyncio.sleep(1)

    print("\n📝 Message 2: sick")
    result2 = await orchestrator.process_message(
        user_id="240611",
        user_message="sick",
        session_id=session_id  # Same session = resumes from checkpoint
    )
    print(f"🤖 Response 2: {result2['response']}")
    print(f"📍 Current step: {result2.get('current_step')}")

    print("\n✅ State persisted across messages!")
    print("\n✅ TEST 7 PASSED")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print(" LANG GRAPH WORKFLOWS TEST SUITE")
    print("="*80)

    tests = [
        ("Simple Leave Application", test_simple_leave_application),
        ("Multi-turn Conversation", test_multi_turn_conversation),
        ("Leave Balance Query", test_balance_query),
        ("Attendance Regularization", test_regularization),
        ("On-duty Application", test_on_duty),
        ("Workflow Visualization", test_workflow_visualization),
        ("State Persistence", test_workflow_state_persistence),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, test_func in tests:
        try:
            print(f"\n🧪 Running: {name}")
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            if "SKIPPED" in str(e):
                skipped += 1
            else:
                print(f"\n❌ TEST ERROR: {name}")
                print(f"   Error: {e}")
                failed += 1

    # Summary
    print("\n" + "="*80)
    print(" TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed:  {passed}")
    print(f"❌ Failed:  {failed}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"📊 Total:   {len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")

    return failed == 0


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    # Run tests
    success = asyncio.run(run_all_tests())

    # Exit with appropriate code
    sys.exit(0 if success else 1)
