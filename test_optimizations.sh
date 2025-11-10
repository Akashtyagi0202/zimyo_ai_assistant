#!/bin/bash

# Test script to verify optimizations don't break functionality
# All scenarios from OPTIMIZATIONS_APPLIED.md

API_URL="http://localhost:8080/chat"
USER_ID="240611"

echo "🧪 Testing Optimized HRMS AI Assistant"
echo "========================================"
echo ""

# Function to test API
test_scenario() {
    local description=$1
    local message=$2
    local session_id=$3

    echo "📝 Test: $description"
    echo "   Message: \"$message\""

    if [ -z "$session_id" ]; then
        response=$(curl -s -X POST "$API_URL" \
            -H "Content-Type: application/json" \
            -d "{\"user_id\":\"$USER_ID\",\"message\":\"$message\"}")
    else
        response=$(curl -s -X POST "$API_URL" \
            -H "Content-Type: application/json" \
            -d "{\"user_id\":\"$USER_ID\",\"message\":\"$message\",\"sessionId\":\"$session_id\"}")
    fi

    echo "   Response: $response"
    echo ""

    # Extract sessionId if present
    session=$(echo $response | grep -o '"sessionId":"[^"]*"' | cut -d'"' -f4)
    echo "$session"
}

echo "Test 1: Multi-turn conversation (Context Accumulation)"
echo "-------------------------------------------------------"
SESSION1=$(test_scenario "Step 1: Apply leave" "apply leave")
SESSION1=$(test_scenario "Step 2: Sick" "sick" "$SESSION1")
SESSION1=$(test_scenario "Step 3: 22 nov" "22 nov" "$SESSION1")
test_scenario "Step 4: Medical" "medical" "$SESSION1" > /dev/null
echo ""

sleep 2

echo "Test 2: One-shot complete"
echo "-------------------------"
test_scenario "Complete info" "apply sick leave for 4 nov health issues" > /dev/null
echo ""

sleep 2

echo "Test 3: Multi-field extraction"
echo "-------------------------------"
test_scenario "Both fields" "4 nov 2025 and sick leave" > /dev/null
echo ""

sleep 2

echo "Test 4: Typo tolerance"
echo "---------------------"
test_scenario "With typos" "aply sck leav for 22 nv helth problm" > /dev/null
echo ""

sleep 2

echo "Test 5: Shortcuts"
echo "----------------"
test_scenario "SL shortcut" "SL for 22 nov" > /dev/null
echo ""

sleep 2

echo "Test 6: Mixed language"
echo "---------------------"
test_scenario "Hindi+English" "sick leave chahiye 22 nov ko tabiyat kharab hai" > /dev/null
echo ""

sleep 2

echo "Test 7: Attendance"
echo "-----------------"
test_scenario "Punch in" "punch in" > /dev/null
echo ""

sleep 2

echo "Test 8: Balance query"
echo "--------------------"
test_scenario "Check balance" "leave balance" > /dev/null
echo ""

echo "✅ All tests completed!"
echo "Check the responses above to verify functionality."
echo ""
echo "Expected behaviors:"
echo "- Test 1: Should accumulate context and apply leave at step 4"
echo "- Test 2: Should apply leave directly (all info provided)"
echo "- Test 3: Should extract both date and type"
echo "- Test 4: Should understand despite typos"
echo "- Test 5: Should recognize SL as Sick Leave"
echo "- Test 6: Should understand mixed Hindi-English"
echo "- Test 7: Should mark attendance"
echo "- Test 8: Should show leave balance"
