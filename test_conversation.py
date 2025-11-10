#!/usr/bin/env python3
"""Test conversation context flow"""
import requests
import json

API_URL = "http://localhost:8080/chat"
USER_ID = "240611"

# Step 1: Start leave application
print("Step 1: Apply sick leave")
response1 = requests.post(API_URL, json={
    "userId": USER_ID,
    "message": "apply sick leave",
    "context": {}
})
data1 = response1.json()
print(f"Response: {data1['response'][:100]}...")
print(f"Has context: {bool(data1.get('context'))}")
print()

# Step 2: Provide date using the context from step 1
print("Step 2: Provide date (with context from step 1)")
response2 = requests.post(API_URL, json={
    "userId": USER_ID,
    "message": "6 nov 2025",
    "context": data1.get("context", {})
})
data2 = response2.json()
print(f"Response: {data2['response'][:150]}...")
print(f"Has context: {bool(data2.get('context'))}")
print()

# Check if it understood the date
if "end date" in data2['response'].lower() or "how many days" in data2['response'].lower() or "reason" in data2['response'].lower():
    print("✅ SUCCESS: Conversation context preserved!")
else:
    print("❌ FAILED: Context not preserved")
    print(f"Full response: {data2['response']}")
