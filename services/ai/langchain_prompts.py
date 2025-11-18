"""
LangChain Prompt Templates for HRMS AI Assistant

This module contains all prompt templates using LangChain's prompt system:
- HRMS intent detection and extraction
- Few-shot examples for better accuracy
- Policy chat prompts
- HR content generation prompts

Author: Zimyo AI Team
"""

from datetime import datetime
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    MessagesPlaceholder
)
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_core.prompts import PromptTemplate


# ============================================================================
# HRMS INTENT EXTRACTION PROMPT
# ============================================================================

def get_hrms_extraction_prompt() -> ChatPromptTemplate:
    """
    Get LangChain prompt template for HRMS intent detection and data extraction.

    Returns:
        ChatPromptTemplate configured for HRMS operations
    """
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%Y-%m-%d")

    # System prompt with instructions
    system_template = """You are an HRMS AI assistant that extracts intent and structured data from employee messages.

**Your Task:**
Extract ALL fields in ONE pass. Handle typos, Hindi+English mix, shortcuts (SL/CL/EL), and all date formats.

**Current Context:**
- Today's date: {current_date}
- Current year: {current_year}
- Available leave types: {leave_types}

**Supported Intents:**
1. **apply_leave**: "apply/aply" + "leave/leav/chutti" (NOT attendance/duty)
2. **mark_attendance**: "punch/pnch", "check in", "attendance" (NOT on duty)
3. **apply_regularization**: "regularize/regularization", "forgot to punch", "missed punch"
4. **apply_onduty**: "on duty"/"onduty"/"WFH", "work from home", "field work" ⚠️ PRIORITY!
5. **check_leave_balance**: "balance/balence", "remaining leave"
6. **get_holidays**: "holiday/holidays", "upcoming holiday", "chutti list"
7. **get_salary_slip**: "salary slip", "pay slip", "payslip", "salary", "वेतन पर्ची"
8. **policy_question**: "policy", "rule"

**Critical Rules:**
- If message contains "on duty"/"onduty"/"WFH" → ALWAYS use "apply_onduty" intent!
- Extract ALL available fields from message (don't ask for info that's already provided)
- Handle typos gracefully: "aply sck leav" → "apply sick leave"
- Support Hindi + English: "chutti chahiye" → leave request
- Recognize shortcuts: SL=Sick Leave, CL=Casual Leave, EL=Earned Leave

**Output Format (JSON):**
{{
  "intent": "detected_intent",
  "confidence": 0.0-1.0,
  "extracted_data": {{
    "leave_type": "exact_name_from_available_types_or_null",
    "from_date": "YYYY-MM-DD_or_null",
    "to_date": "YYYY-MM-DD_or_null",
    "reason": "text_or_null",
    "action": "check_in_or_check_out_or_null",
    "location": "text_or_null",
    "date": "YYYY-MM-DD_or_null",
    "from_time": "HH:MM_24hr_format_or_null",
    "to_time": "HH:MM_24hr_format_or_null",
    "month": "1-12_or_null",
    "year": "YYYY_or_null"
  }},
  "missing_fields": ["list_of_required_but_missing_fields"],
  "next_question": "bilingual_hindi_english_question_or_null",
  "ready_to_execute": true_or_false
}}

**Examples:**

**Apply Leave:**
- "apply sick leave 4 nov health issues" → {{"intent":"apply_leave","extracted_data":{{"leave_type":"Sick Leave","from_date":"{current_year}-11-04","to_date":"{current_year}-11-04","reason":"health issues"}},"ready_to_execute":true}}
- "apply my leave for 22 nov" → {{"intent":"apply_leave","extracted_data":{{"from_date":"{current_year}-11-22","to_date":"{current_year}-11-22"}},"missing_fields":["leave_type","reason"],"next_question":"किस प्रकार की छुट्टी? What type?","ready_to_execute":false}}

**On-Duty:**
- "apply on duty today 9:20am to 1pm client meeting" → {{"intent":"apply_onduty","extracted_data":{{"date":"{current_date}","from_time":"09:20","to_time":"13:00","reason":"client meeting"}},"ready_to_execute":true}}
- "on duty for today" → {{"intent":"apply_onduty","extracted_data":{{"date":"{current_date}"}},"missing_fields":["from_time","to_time","reason"],"next_question":"किस समय से किस समय तक? Time range?","ready_to_execute":false}}

**Regularization:**
- "regularize attendance for 4 nov 9am to 6pm forgot to punch" → {{"intent":"apply_regularization","extracted_data":{{"date":"{current_year}-11-04","from_time":"09:00","to_time":"18:00","reason":"forgot to punch"}},"ready_to_execute":true}}

**Attendance:**
- "punch in" → {{"intent":"mark_attendance","extracted_data":{{"action":"check_in"}},"ready_to_execute":true}}

**Balance:**
- "leave balance" → {{"intent":"check_leave_balance","ready_to_execute":true}}

**Holidays:**
- "upcoming holidays" → {{"intent":"get_holidays","ready_to_execute":true}}

**Salary Slip:**
- "salary slip for october 2024" → {{"intent":"get_salary_slip","extracted_data":{{"month":10,"year":2024}},"ready_to_execute":true}}

**NEVER return intent="unknown" if keywords match above patterns!**
"""

    # User message template
    user_template = """User message: "{user_message}"

{previous_context}

Extract intent and all available data. Return ONLY valid JSON."""

    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", user_template)
    ])

    return prompt


# ============================================================================
# EMPLOYEE POLICY CHAT PROMPT
# ============================================================================

def get_employee_chat_prompt() -> ChatPromptTemplate:
    """
    Get LangChain prompt template for employee policy questions.

    Returns:
        ChatPromptTemplate for policy Q&A
    """
    system_template = """You are a professional HR policy analyst who helps employees understand company policies.

**You will receive:**
1. Employee details (leaves balance, department, etc.)
2. Employee's query
3. Policy documents containing HR policies

**Your responsibilities:**
- Search for relevant information in the policy documents
- Cross-verify with employee data
- Answer only if you have complete information
- Be elaborate and provide all relevant details

**If information is missing:**
Say: "My knowledge base doesn't include that information, please ask a different query, or reword your current query"

**Output format:**
* Response: [Your detailed answer]
* Reference: [Policy title used OR "Employee details"]

**Employee Data:**
{employee_data}

**Policy Content:**
{policy_content}"""

    user_template = """Employee Query: {query}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", user_template)
    ])

    return prompt


# ============================================================================
# HR CONTENT GENERATION PROMPT
# ============================================================================

def get_hr_content_prompt() -> ChatPromptTemplate:
    """
    Get LangChain prompt template for HR content generation.

    Returns:
        ChatPromptTemplate for creating emails, job descriptions, policies
    """
    system_template = """You are an expert content creator for an HR team.

**You create:**
- Professional emails
- Job descriptions
- Corporate policies
- HR announcements

**Guidelines:**
- Always use professional and corporate tone
- Refer to employee information and policies when personalizing
- Respond to every part of the query elaborately
- If query is not HR-related, say: "That is not in my knowledge base."

**Output format:**
Content: [Complete content as requested]
Description: [Select ONE: "EMAIL" | "JOB_DESCRIPTION" | "POLICY" | "NONE"]

**Employee Information:**
{employee_data}

**Policy Context:**
{policy_content}"""

    user_template = """HR Task: {query}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", user_template)
    ])

    return prompt


# ============================================================================
# CONVERSATIONAL PROMPT WITH MEMORY
# ============================================================================

def get_conversational_hrms_prompt() -> ChatPromptTemplate:
    """
    Get conversational prompt template with message history support.

    Use this with RunnableWithMessageHistory for multi-turn conversations.

    Returns:
        ChatPromptTemplate with MessagesPlaceholder for history
    """
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%Y-%m-%d")

    system_template = """You are an HRMS AI assistant helping with leave applications, attendance, and HR queries.

**Context:**
- Today: {current_date}
- Year: {current_year}
- Available leave types: {leave_types}

**Your job:**
- Understand what user wants from conversation history
- Extract and accumulate information across messages
- Ask for missing information one field at a time
- Execute operation when all required fields are collected

**Previous conversation context:**
{previous_data}

Extract intent and data, considering the full conversation history."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_message}")
    ])

    return prompt


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_previous_context(context_dict: dict) -> str:
    """
    Format previous context dictionary for prompt injection.

    Args:
        context_dict: Dictionary with extracted_data, intent, etc.

    Returns:
        Formatted string for prompt
    """
    if not context_dict or not context_dict.get("extracted_data"):
        return ""

    import json
    return f"\nPrevious conversation data: {json.dumps(context_dict.get('extracted_data', {}))}"


def format_leave_types(leave_types_list: list) -> str:
    """
    Format leave types list for prompt.

    Args:
        leave_types_list: List of dicts with leave type info

    Returns:
        Comma-separated string of leave type names
    """
    if not leave_types_list:
        return "None available"

    names = [lt.get('name', '') for lt in leave_types_list if lt.get('name')]
    return ', '.join(names) if names else "None available"


# ============================================================================
# PROMPT REGISTRY (for easy access)
# ============================================================================

PROMPT_REGISTRY = {
    "hrms_extraction": get_hrms_extraction_prompt,
    "employee_chat": get_employee_chat_prompt,
    "hr_content": get_hr_content_prompt,
    "conversational_hrms": get_conversational_hrms_prompt
}


def get_prompt(prompt_name: str) -> ChatPromptTemplate:
    """
    Get prompt template by name from registry.

    Args:
        prompt_name: Name of prompt (hrms_extraction, employee_chat, etc.)

    Returns:
        ChatPromptTemplate instance

    Raises:
        ValueError: If prompt_name not found
    """
    if prompt_name not in PROMPT_REGISTRY:
        raise ValueError(f"Unknown prompt: {prompt_name}. Available: {list(PROMPT_REGISTRY.keys())}")

    return PROMPT_REGISTRY[prompt_name]()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Basic HRMS extraction
---------------------------------
from services.ai.langchain_prompts import get_hrms_extraction_prompt
from services.ai.langchain_config import get_llm, get_json_parser

prompt = get_hrms_extraction_prompt()
llm = get_llm()
parser = get_json_parser()

chain = prompt | llm | parser

result = chain.invoke({
    "user_message": "apply sick leave for 4 nov",
    "current_date": "2025-11-10",
    "current_year": 2025,
    "leave_types": "Sick Leave, Casual Leave, Earned Leave",
    "previous_context": ""
})

print(result)


Example 2: With previous context
---------------------------------
previous_data = {"from_date": "2025-11-22"}
formatted_context = format_previous_context({"extracted_data": previous_data})

result = chain.invoke({
    "user_message": "sick leave",
    "current_date": "2025-11-10",
    "current_year": 2025,
    "leave_types": "Sick Leave, Casual Leave",
    "previous_context": formatted_context
})


Example 3: Employee policy chat
--------------------------------
from services.ai.langchain_prompts import get_employee_chat_prompt

prompt = get_employee_chat_prompt()
chain = prompt | llm

result = chain.invoke({
    "employee_data": "Name: Akash, Department: IT, Sick Leave: 3.72 days",
    "policy_content": "Employees can take sick leave with medical certificate...",
    "query": "How many sick leaves do I have?"
})

print(result.content)


Example 4: Using prompt registry
---------------------------------
from services.ai.langchain_prompts import get_prompt

# Get any prompt by name
hrms_prompt = get_prompt("hrms_extraction")
chat_prompt = get_prompt("employee_chat")
"""
