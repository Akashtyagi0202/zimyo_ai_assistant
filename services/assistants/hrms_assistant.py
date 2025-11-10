"""
HRMS Conversational AI Assistant
Comprehensive intent detection and handling system for HR-related queries
"""

import json
import logging
import re
import redis
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

class Intent(Enum):
    """Supported HR intents"""
    # Employee operations
    POLICY_QUERY = "policy_query"  # Generic policy query - supports ANY company policy
    APPLY_LEAVE = "apply_leave"
    MARK_ATTENDANCE = "mark_attendance"
    CHECK_LEAVE_BALANCE = "check_leave_balance"
    CREATE_JOB_DESCRIPTION = "create_job_description"

    # Admin operations - Payroll & Financial
    RUN_PAYROLL = "run_payroll"
    PROCESS_FNF = "process_fnf"
    PUBLISH_PAYSLIPS = "publish_payslips"
    GENERATE_SALARY_REPORT = "generate_salary_report"

    # Admin operations - Employee Management
    SEND_OFFER_LETTER = "send_offer_letter"
    ONBOARD_EMPLOYEE = "onboard_employee"
    TERMINATE_EMPLOYEE = "terminate_employee"
    UPDATE_EMPLOYEE_DATA = "update_employee_data"

    # Admin operations - Leave Management
    APPROVE_LEAVE = "approve_leave"
    REJECT_LEAVE = "reject_leave"
    BULK_LEAVE_OPERATIONS = "bulk_leave_operations"

    # Admin operations - Attendance & Compliance
    GENERATE_ATTENDANCE_REPORT = "generate_attendance_report"
    MARK_BULK_ATTENDANCE = "mark_bulk_attendance"
    COMPLIANCE_REPORT = "compliance_report"

    # Admin operations - Policy & Configuration
    UPDATE_POLICY = "update_policy"
    CREATE_ANNOUNCEMENT = "create_announcement"
    CONFIGURE_SYSTEM = "configure_system"

    UNKNOWN = "unknown"

class Language(Enum):
    """Supported languages"""
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"
    AUTO = "auto"

class Role(Enum):
    """User roles with access levels"""
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR_ADMIN = "hr_admin"
    SUPER_ADMIN = "super_admin"
    PAYROLL_ADMIN = "payroll_admin"

class OperationType(Enum):
    """Types of operations"""
    QUERY = "query"           # Read-only operations
    ACTION = "action"         # State-changing operations
    ADMIN_ACTION = "admin_action"  # Administrative operations
    BULK_ACTION = "bulk_action"    # Bulk operations

@dataclass
class DetectionResult:
    """Result of intent detection"""
    intent: Intent
    confidence: float
    language: Language
    extracted_entities: Dict[str, Any]
    clarification_needed: bool = False
    clarification_question: Optional[str] = None

@dataclass
class UserContext:
    """User context from Redis"""
    user_id: str
    role: str
    user_info: Dict[str, Any]
    user_policies: Dict[str, str]
    policy_embeddings: Dict[str, List[float]]
    token: str

class LanguageDetector:
    """Advanced language detection for multilingual queries"""

    def __init__(self):
        # Language patterns with weights
        self.language_patterns = {
            Language.HINDI: {
                'words': ['छुट्टी', 'नीति', 'हाजिरी', 'नौकरी', 'कंपनी', 'मेरा', 'क्या', 'कैसे', 'कब', 'कहाँ'],
                'patterns': [r'[\u0900-\u097F]+']  # Devanagari script
            },
            Language.HINGLISH: {
                'words': ['chutti', 'policy', 'haaziri', 'mera', 'kya', 'kaise', 'kar', 'do', 'batao', 'dekho'],
                'patterns': [r'\b(kar|do|hai|mera|kya|kaise|chutti|haaziri)\b']
            },
            Language.ENGLISH: {
                'words': ['leave', 'policy', 'attendance', 'job', 'company', 'my', 'what', 'how', 'when', 'where'],
                'patterns': [r'\b(leave|policy|attendance|job|company)\b']
            }
        }

    def detect(self, text: str) -> Tuple[Language, float]:
        """Detect language with confidence score"""
        text_lower = text.lower().strip()
        scores = {lang: 0.0 for lang in Language if lang != Language.AUTO}

        for lang, config in self.language_patterns.items():
            # Word matching
            word_matches = sum(1 for word in config['words'] if word in text_lower)
            scores[lang] += word_matches * 2  # Higher weight for word matches

            # Pattern matching
            for pattern in config['patterns']:
                matches = len(re.findall(pattern, text_lower))
                scores[lang] += matches * 1.5

        # Determine best language
        if all(score == 0 for score in scores.values()):
            return Language.ENGLISH, 0.5  # Default fallback

        best_lang = max(scores, key=scores.get)
        max_score = scores[best_lang]
        total_score = sum(scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.5

        return best_lang, confidence

class IntentClassifier:
    """Advanced intent classification with multilingual support"""

    def __init__(self):
        self.intent_patterns = self._build_intent_patterns()
        self.confidence_threshold = 0.7
        self.min_confidence_threshold = 0.4

    def _build_intent_patterns(self) -> Dict[Intent, Dict[str, List[str]]]:
        """Build comprehensive intent patterns for all languages"""
        return {
            Intent.POLICY_QUERY: {
                'english': [
                    # Generic policy queries - supports ANY company policy
                    r'\b(what|what\'s|whats).*?(is|are).*?(my|the|our).*?policy\b',
                    r'\b(what|tell|explain|show|describe).*?policy\b',
                    r'\bpolicy.*?(about|for|regarding)\b',
                    r'\bmy.*?policy\b',
                    r'\bcompany.*?policy\b',
                    r'\bwhat.*?policy.*?(applicable|applies)\b',

                    # Specific policy types
                    r'\b(leave|chutti|vacation).*?policy\b',
                    r'\bpolicy.*?(leave|chutti|vacation)\b',
                    r'\b(travel|trip|journey).*?policy\b',
                    r'\b(expense|reimbursement).*?policy\b',
                    r'\b(wfh|work from home|remote).*?policy\b',
                    r'\b(attendance|presence).*?policy\b',
                    r'\b(code of conduct|conduct|behavior|behaviour)\b',
                    r'\b(social media|facebook|twitter|linkedin).*?policy\b',
                    r'\b(dress code|attire).*?policy\b',
                    r'\b(performance|appraisal|review).*?policy\b',
                    r'\b(salary|compensation|increment).*?policy\b',
                    r'\b(benefits?|insurance|medical|health).*?policy\b',

                    # Specific scenarios
                    r'\bsandwich.*?(leave|chutti)\b',
                    r'\bfriday.*?monday.*?(leave|chutti)\b',
                    r'\b(approval|approve).*?(process|policy|workflow)\b',
                    r'\b(notice|advance).*?(period|requirement)\b',
                    r'\brules?.*?(regarding|about|for)\b',
                    r'\bguidelines?.*?(for|about|regarding)\b'
                ],
                'hindi': [
                    # Generic
                    r'नीति.*?(क्या|बताओ|दिखाओ)',
                    r'(क्या|बताओ).*?नीति',
                    r'मेरी.*?नीति',
                    r'कंपनी.*?नीति',

                    # Specific
                    r'छुट्टी.*?नीति',
                    r'नीति.*?छुट्टी',
                    r'अवकाश.*?नीति',
                    r'यात्रा.*?नीति',
                    r'खर्च.*?नीति',
                    r'व्यवहार.*?संहिता',
                    r'नियम.*?(क्या|बताओ)',
                    r'दिशानिर्देश'
                ],
                'hinglish': [
                    # Generic
                    r'\b(kya|batao|dikha|bata).*?policy\b',
                    r'\bpolicy.*?(kya|hai|batao)\b',
                    r'\bmeri.*?policy\b',
                    r'\bcompany.*?(policy|niti)\b',

                    # Specific
                    r'\b(leave|chutti).*?(policy|niti)\b',
                    r'\b(policy|niti).*?(leave|chutti)\b',
                    r'\btravel.*?(policy|niti)\b',
                    r'\bexpense.*?(policy|niti)\b',
                    r'\bwfh.*?(policy|niti)\b',
                    r'\bsocial media.*?(policy|niti)\b',
                    r'\bsandwich.*?chutti\b',
                    r'\bapproval.*?(process|policy)\b',
                    r'\b(niyam|rules).*?(kya|batao)\b'
                ]
            },
            Intent.APPLY_LEAVE: {
                'english': [
                    r'\b(apply|request|take|book|need|want).*?leave\b',
                    r'\bleave.*?(apply|request|book)\b',
                    r'\bi.*?(need|want).*?(time off|leave|vacation)\b',
                    r'\b(from|to).*?(friday|monday|tomorrow|today)\b.*?leave'
                ],
                'hindi': [
                    r'छुट्टी.*?(चाहिए|करना|लेना|आवेदन)',
                    r'(आवेदन|अप्लाई).*?छुट्टी',
                    r'मुझे.*?छुट्टी.*?चाहिए'
                ],
                'hinglish': [
                    r'\b(apply|lagwa|kar).*?chutti\b',
                    r'\bchutti.*?(apply|lagwa|kar)\b',
                    r'\b(chahiye|leni|karna).*?chutti\b',
                    r'\bchutti.*?(chahiye|leni)\b'
                ]
            },
            Intent.MARK_ATTENDANCE: {
                'english': [
                    r'\b(mark|punch|clock|record).*?attendance\b',
                    r'\battendance.*?(mark|punch|clock)\b',
                    r'\b(check|punch).*?in\b',
                    r'\bpresent.*?mark\b'
                ],
                'hindi': [
                    r'हाजिरी.*?(लगा|मार्क|दर्ज)',
                    r'उपस्थिति.*?दर्ज',
                    r'हाजिरी.*?करना'
                ],
                'hinglish': [
                    r'\b(mark|lagao|maar).*?(haaziri|attendance)\b',
                    r'\b(haaziri|attendance).*?(mark|lagao|maar)\b',
                    r'\bpunch.*?kar\b'
                ]
            },
            Intent.CHECK_LEAVE_BALANCE: {
                'english': [
                    r'\b(check|show|how many|remaining).*?leave.*?balance\b',
                    r'\bleave.*?balance.*?(check|show)\b',
                    r'\b(available|remaining).*?leaves?\b',
                    r'\bhow many.*?leaves?.*?(left|remaining)\b'
                ],
                'hindi': [
                    r'छुट्टी.*?(बची|उपलब्ध|बैलेंस)',
                    r'कितनी.*?छुट्टी.*?बची',
                    r'छुट्टी.*?बैलेंस.*?दिखा'
                ],
                'hinglish': [
                    r'\b(kitni|kitna).*?(chutti|leave).*?(bachi|balance)\b',
                    r'\b(chutti|leave).*?balance.*?(dekho|batao|check)\b',
                    r'\bbalance.*?(chutti|leave)\b'
                ]
            },
            Intent.CREATE_JOB_DESCRIPTION: {
                'english': [
                    r'\b(create|write|make|generate).*?job.*?description\b',
                    r'\bjob.*?description.*?(create|write|for)\b',
                    r'\b(jd|job description).*?(create|write)\b',
                    r'\b(node.*?js|python|java|developer).*?(job|jd)\b'
                ],
                'hindi': [
                    r'नौकरी.*?विवरण.*?(बना|लिख)',
                    r'(जॉब|नौकरी).*?(डिस्क्रिप्शन|विवरण)',
                    r'पद.*?विवरण.*?बना'
                ],
                'hinglish': [
                    r'\b(banao|likho|create).*?(job|jd)\b',
                    r'\bjob.*?(description|jd).*?(banao|likho)\b',
                    r'\b(developer|engineer).*?job\b'
                ]
            },
            # Admin Operations - Payroll & Financial
            Intent.RUN_PAYROLL: {
                'english': [
                    r'\b(run|process|execute|generate).*?payroll\b',
                    r'\bpayroll.*?(run|process|for).*?(month|august|september)\b',
                    r'\b(hey|hi).*?zim.*?run.*?payroll\b',
                    r'\bprocess.*?salary.*?(month|august|september)\b'
                ],
                'hindi': [
                    r'वेतन.*?(चला|प्रोसेस|महीने)',
                    r'पेरोल.*?(चला|करना)'
                ],
                'hinglish': [
                    r'\b(run|chala|kar).*?payroll\b',
                    r'\bpayroll.*?(kar|chala|do)\b'
                ]
            },

            Intent.PROCESS_FNF: {
                'english': [
                    r'\b(run|process|execute).*?(fnf|full.*?final)\b',
                    r'\b(fnf|full.*?final).*?(run|process)\b',
                    r'\bfinal.*?settlement.*?(process|run)\b',
                    r'\b(hey|hi).*?zim.*?(run|process).*?fnf\b'
                ],
                'hindi': [
                    r'अंतिम.*?निपटान.*?(चला|प्रोसेस)',
                    r'एफएनएफ.*?(चला|करना)'
                ],
                'hinglish': [
                    r'\b(run|chala|kar).*?fnf\b',
                    r'\bfnf.*?(kar|chala|do)\b'
                ]
            },

            Intent.PUBLISH_PAYSLIPS: {
                'english': [
                    r'\b(publish|send|distribute|release).*?payslips?\b',
                    r'\bpayslips?.*?(publish|send|distribute)\b',
                    r'\b(hey|hi).*?zim.*?(publish|send).*?payslips?\b',
                    r'\bsalary.*?slips?.*?(publish|send|distribute)\b'
                ],
                'hindi': [
                    r'वेतन.*?पर्ची.*?(भेज|प्रकाशित)',
                    r'पेस्लिप.*?(भेज|प्रकाशित)'
                ],
                'hinglish': [
                    r'\b(send|bhej|publish).*?payslips?\b',
                    r'\bpayslips?.*?(send|bhej|kar)\b'
                ]
            },

            Intent.SEND_OFFER_LETTER: {
                'english': [
                    r'\b(send|generate|create).*?offer.*?letter\b',
                    r'\boffer.*?letter.*?(send|to).*?(employee|emp|code)\b',
                    r'\b(hey|hi).*?zim.*?send.*?offer.*?letter\b',
                    r'\boffer.*?letter.*?employee.*?(xyz|[a-z0-9]+)\b'
                ],
                'hindi': [
                    r'नियुक्ति.*?पत्र.*?(भेज|देना)',
                    r'ऑफर.*?लेटर.*?(भेज|देना)'
                ],
                'hinglish': [
                    r'\b(send|bhej).*?offer.*?letter\b',
                    r'\boffer.*?letter.*?(bhej|send|kar)\b'
                ]
            },

            Intent.APPROVE_LEAVE: {
                'english': [
                    r'\b(approve|accept).*?leave\b',
                    r'\bleave.*?(approve|accept|approval)\b',
                    r'\b(hey|hi).*?zim.*?approve.*?leave\b',
                    r'\bapprove.*?leave.*?(request|application)\b'
                ],
                'hindi': [
                    r'छुट्टी.*?(मंजूर|स्वीकार)',
                    r'अवकाश.*?स्वीकृति'
                ],
                'hinglish': [
                    r'\b(approve|manjoor|accept).*?(chutti|leave)\b',
                    r'\b(chutti|leave).*?(approve|manjoor|kar)\b'
                ]
            },

            Intent.GENERATE_ATTENDANCE_REPORT: {
                'english': [
                    r'\b(generate|create|show).*?attendance.*?report\b',
                    r'\battendance.*?report.*?(generate|create|for)\b',
                    r'\b(hey|hi).*?zim.*?attendance.*?report\b',
                    r'\breport.*?attendance.*?(month|august|september)\b'
                ],
                'hindi': [
                    r'उपस्थिति.*?रिपोर्ट.*?(बना|दिखा)',
                    r'हाजिरी.*?रिपोर्ट.*?(बना|दिखा)'
                ],
                'hinglish': [
                    r'\b(generate|bana|create).*?attendance.*?report\b',
                    r'\battendance.*?report.*?(bana|show|kar)\b'
                ]
            },

            Intent.CREATE_ANNOUNCEMENT: {
                'english': [
                    r'\b(create|make|post).*?announcement\b',
                    r'\bannouncement.*?(create|make|post)\b',
                    r'\b(hey|hi).*?zim.*?create.*?announcement\b',
                    r'\b(notify|inform).*?all.*?employees\b'
                ],
                'hindi': [
                    r'घोषणा.*?(बना|कर|भेज)',
                    r'सूचना.*?(बना|भेज)'
                ],
                'hinglish': [
                    r'\b(create|bana|post).*?announcement\b',
                    r'\bannouncement.*?(bana|post|kar)\b'
                ]
            }
        }

    def classify(self, text: str, language: Language, user_id: str = None) -> Tuple[Intent, float, Dict[str, Any]]:
        """
        Classify intent with confidence and extract entities

        Args:
            text: User message text
            language: Detected language
            user_id: User ID for organization-specific entity extraction (e.g., leave types)

        Returns:
            Tuple of (Intent, confidence, entities)
        """
        text_lower = text.lower().strip()
        scores = {}
        entities = {}

        # Map language to pattern keys
        lang_key = self._get_pattern_key(language)

        for intent, patterns_dict in self.intent_patterns.items():
            score = 0
            intent_entities = {}

            # Get patterns for detected language and fallback to English
            patterns = patterns_dict.get(lang_key, []) + patterns_dict.get('english', [])

            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    score += len(matches) * 2

            # Extract entities based on intent
            if intent == Intent.APPLY_LEAVE:
                intent_entities.update(self._extract_date_entities(text))
                # Pass user_id for dynamic leave type extraction
                intent_entities.update(self._extract_leave_type_entities(text, user_id=user_id))
            elif intent == Intent.CREATE_JOB_DESCRIPTION:
                intent_entities.update(self._extract_job_entities(text))

            if intent_entities:
                entities.update(intent_entities)
                score += 1  # Bonus for entity extraction

            scores[intent] = score

        # Find best intent
        if all(score == 0 for score in scores.values()):
            return Intent.UNKNOWN, 0.0, {}

        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        total_score = sum(scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.0

        return best_intent, confidence, entities

    def _get_pattern_key(self, language: Language) -> str:
        """Map language enum to pattern dictionary key"""
        mapping = {
            Language.ENGLISH: 'english',
            Language.HINDI: 'hindi',
            Language.HINGLISH: 'hinglish'
        }
        return mapping.get(language, 'english')

    def _extract_date_entities(self, text: str) -> Dict[str, Any]:
        """Extract date-related entities"""
        entities = {}
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',  # DD/MM/YYYY or DD-MM-YYYY
            r'\b(today|tomorrow|yesterday)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b'
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                entities['dates'] = matches
                break

        return entities

    def _extract_leave_type_entities(self, text: str, user_id: str = None) -> Dict[str, Any]:
        """
        Extract leave type entities dynamically from organization's actual leave types

        Args:
            text: User message text
            user_id: User ID to fetch organization-specific leave types

        Returns:
            Dictionary with extracted leave type
        """
        entities = {}

        # If user_id is provided, fetch organization-specific leave types
        if user_id:
            try:
                import asyncio
                from services.integration.mcp_integration import mcp_client

                # Create event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Fetch organization's leave types
                result = loop.run_until_complete(
                    mcp_client.call_tool("get_leave_types", {"user_id": user_id})
                )

                if result.get("status") == "success":
                    available_leave_types = result.get("leave_types", [])

                    if available_leave_types:
                        # Use fuzzy matching to find leave type in text
                        from fuzzywuzzy import fuzz

                        text_lower = text.lower()
                        best_match = None
                        best_score = 0

                        for leave_type in available_leave_types:
                            leave_name = leave_type.get("name", "").lower()

                            # Try exact match first
                            if leave_name in text_lower:
                                entities['leave_type'] = leave_type.get("name")
                                logger.info(f"✅ Exact match found: {leave_type.get('name')}")
                                return entities

                            # Try fuzzy matching for each word in text
                            for word in text_lower.split():
                                if len(word) > 2:  # Skip short words
                                    score = fuzz.ratio(word, leave_name)
                                    if score > best_score and score >= 70:  # 70% similarity threshold
                                        best_score = score
                                        best_match = leave_type.get("name")

                        if best_match:
                            entities['leave_type'] = best_match
                            logger.info(f"✅ Fuzzy match found: {best_match} (score: {best_score})")
                            return entities
                        else:
                            logger.info(f"❌ No leave type match found in text: '{text}'")

            except Exception as e:
                logger.warning(f"Error fetching dynamic leave types: {e}. Falling back to static list.")

        # Fallback to static list if dynamic fetch fails or user_id not provided
        static_leave_types = ['sick', 'casual', 'earned', 'annual', 'emergency', 'maternity', 'paternity']

        for leave_type in static_leave_types:
            if leave_type in text.lower():
                entities['leave_type'] = leave_type
                logger.info(f"⚠️ Using static fallback match: {leave_type}")
                break

        return entities

    def _extract_job_entities(self, text: str) -> Dict[str, Any]:
        """Extract job-related entities"""
        entities = {}

        # Extract technology/skills
        tech_pattern = r'\b(node\.?js|react|python|java|javascript|angular|vue|mongodb|mysql|aws|docker)\b'
        tech_matches = re.findall(tech_pattern, text.lower())
        if tech_matches:
            entities['technologies'] = tech_matches

        # Extract experience
        exp_pattern = r'(\d+)\s*(year|yr)s?\s*(experience|exp)'
        exp_matches = re.findall(exp_pattern, text.lower())
        if exp_matches:
            entities['experience_years'] = exp_matches[0][0]

        # Extract job titles
        title_pattern = r'\b(developer|engineer|manager|analyst|designer|architect|lead|senior|junior)\b'
        title_matches = re.findall(title_pattern, text.lower())
        if title_matches:
            entities['job_titles'] = title_matches

        return entities

class HRMSAIAssistant:
    """Main HRMS AI Assistant class"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.language_detector = LanguageDetector()
        self.intent_classifier = IntentClassifier()
        logger.info("HRMS AI Assistant initialized")

    def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """Retrieve user context from Redis"""
        try:
            user_data_raw = self.redis_client.get(user_id)
            if not user_data_raw:
                logger.warning(f"No session found for user: {user_id}")
                return None

            user_data = json.loads(user_data_raw)
            return UserContext(
                user_id=user_id,
                role=user_data.get("role", "employee"),
                user_info=user_data.get("user_info", {}),
                user_policies=user_data.get("user_policies", {}),
                policy_embeddings=user_data.get("policy_embeddings", {}),
                token=user_data.get("token", "")
            )
        except Exception as e:
            logger.error(f"Error retrieving user context for {user_id}: {e}")
            return None

    def detect_intent(self, query: str, user_context: UserContext) -> DetectionResult:
        """Main intent detection pipeline"""
        try:
            # Step 1: Language detection
            language, lang_confidence = self.language_detector.detect(query)
            logger.info(f"Detected language: {language.value} (confidence: {lang_confidence:.2f})")

            # Step 2: Intent classification with user_id for dynamic entity extraction
            intent, intent_confidence, entities = self.intent_classifier.classify(
                query, language, user_id=user_context.user_id
            )
            logger.info(f"Detected intent: {intent.value} (confidence: {intent_confidence:.2f})")

            # Step 3: Determine if clarification is needed
            needs_clarification = False
            clarification_question = None

            if intent_confidence < self.intent_classifier.min_confidence_threshold:
                needs_clarification = True
                clarification_question = self._generate_clarification_question(query, language)
            elif intent_confidence < self.intent_classifier.confidence_threshold:
                # Check if we have enough context to proceed
                if intent in [Intent.APPLY_LEAVE, Intent.CREATE_JOB_DESCRIPTION] and not entities:
                    needs_clarification = True
                    clarification_question = self._generate_clarification_question(query, language, intent)

            return DetectionResult(
                intent=intent,
                confidence=intent_confidence,
                language=language,
                extracted_entities=entities,
                clarification_needed=needs_clarification,
                clarification_question=clarification_question
            )

        except Exception as e:
            logger.error(f"Error in intent detection: {e}")
            return DetectionResult(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                language=Language.ENGLISH,
                extracted_entities={},
                clarification_needed=True,
                clarification_question="I didn't understand your request. Could you please rephrase it?"
            )

    def _generate_clarification_question(self, query: str, language: Language, intent: Optional[Intent] = None) -> str:
        """Generate appropriate clarification questions"""
        clarification_templates = {
            Language.ENGLISH: {
                Intent.UNKNOWN: "I didn't quite understand your request. Could you please tell me what you'd like help with? For example: leave policy, apply for leave, check attendance, or job descriptions.",
                Intent.APPLY_LEAVE: "I understand you want to apply for leave. Could you please specify the dates and type of leave?",
                Intent.CREATE_JOB_DESCRIPTION: "I can help create a job description. Could you specify the role, required skills, and experience level?",
                "general": "Could you please be more specific about what you need help with?"
            },
            Language.HINDI: {
                Intent.UNKNOWN: "मैं आपका अनुरोध समझ नहीं सका। कृपया बताएं कि आपको किस चीज़ में मदद चाहिए? जैसे: छुट्टी नीति, छुट्टी आवेदन, हाजिरी, या नौकरी विवरण।",
                Intent.APPLY_LEAVE: "मैं समझ गया कि आप छुट्टी के लिए आवेदन करना चाहते हैं। कृपया तारीख और छुट्टी का प्रकार बताएं।",
                Intent.CREATE_JOB_DESCRIPTION: "मैं नौकरी विवरण बनाने में मदद कर सकता हूं। कृपया भूमिका, आवश्यक कौशल और अनुभव स्तर बताएं।",
                "general": "कृपया बताएं कि आपको किस चीज़ में मदद चाहिए?"
            },
            Language.HINGLISH: {
                Intent.UNKNOWN: "Main aapka request samajh nahi paya. Please batao ki aapko kya help chahiye? Jaise: leave policy, leave apply karna, attendance, ya job description.",
                Intent.APPLY_LEAVE: "Main samjha ki aap leave apply karna chahte hai. Please dates aur leave type batao.",
                Intent.CREATE_JOB_DESCRIPTION: "Main job description banane mein help kar sakta hu. Please role, skills aur experience level batao.",
                "general": "Please specific batao ki aapko kya help chahiye?"
            }
        }

        templates = clarification_templates.get(language, clarification_templates[Language.ENGLISH])
        if intent and intent in templates:
            return templates[intent]
        return templates.get("general", templates[Intent.UNKNOWN])

    async def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """Main entry point for processing user queries"""
        try:
            # Get user context
            user_context = self.get_user_context(user_id)
            if not user_context:
                return {
                    "error": "User session not found. Please login first.",
                    "status": "error"
                }

            # Detect intent
            detection_result = self.detect_intent(query, user_context)

            # Handle clarification if needed
            if detection_result.clarification_needed:
                return {
                    "response": detection_result.clarification_question,
                    "intent": detection_result.intent.value,
                    "confidence": detection_result.confidence,
                    "language": detection_result.language.value,
                    "requires_clarification": True
                }

            # Route to appropriate handler
            return await self._route_to_handler(detection_result, user_context, query)

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "error": "An error occurred while processing your request.",
                "status": "error"
            }

    async def _route_to_handler(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """Route to appropriate intent handler"""
        handler_map = {
            Intent.POLICY_QUERY: self._handle_policy_query,  # Generic policy handler for ALL policies
            Intent.APPLY_LEAVE: self._handle_apply_leave,
            Intent.MARK_ATTENDANCE: self._handle_mark_attendance,
            Intent.CHECK_LEAVE_BALANCE: self._handle_check_leave_balance,
            Intent.CREATE_JOB_DESCRIPTION: self._handle_create_job_description
        }

        handler = handler_map.get(detection_result.intent)
        if handler:
            return await handler(detection_result, user_context, query)
        else:
            return {
                "response": "I'm sorry, I couldn't understand your request. Please try again.",
                "intent": detection_result.intent.value,
                "confidence": detection_result.confidence,
                "language": detection_result.language.value
            }

    async def _handle_policy_query(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """
        Handle comprehensive policy queries with context-aware responses - GENERIC for ALL policies

        Supports ANY company policy:
        - Leave Policy: "What is my leave policy?", "Sandwich leave?", "Friday-Monday leave?"
        - Travel Policy: "What is the travel policy?", "Can I book business class?"
        - Expense Policy: "What is the reimbursement policy?", "How to claim expenses?"
        - WFH Policy: "What is work from home policy?", "Can I work remotely?"
        - Social Media: "What policy applies if I post on social media?"
        - Code of Conduct: "What is the code of conduct?", "Company behavior policy?"
        - Dress Code: "What is the dress code?", "Can I wear casual clothes?"
        - Attendance: "What is the attendance policy?", "Late coming policy?"
        - Performance: "What is the appraisal policy?", "How does performance review work?"
        - Benefits: "What are company benefits?", "Insurance policy?"
        - Salary: "What is the increment policy?", "Compensation structure?"
        - ... ANY other company policy
        """
        try:
            # Use AI to generate comprehensive response using all policy data
            from services.ai.chat import get_chat_response

            # Detect the type of policy query for better context
            query_lower = query.lower()

            # Identify query category
            query_context = self._identify_policy_query_context(query_lower)

            # Build comprehensive system prompt for AI
            system_instruction = """You are an expert HR Policy Assistant. Your job is to provide clear, accurate, and helpful policy information to employees.

IMPORTANT GUIDELINES:
1. **Be Specific**: Always reference the exact policy name and relevant sections
2. **Be Clear**: Use simple language, avoid jargon
3. **Be Contextual**: Address the specific scenario in the employee's question
4. **Be Helpful**: Provide examples when relevant
5. **Be Complete**: Cover all aspects of the question (eligibility, process, restrictions, exceptions)
6. **Use Formatting**: Use bullet points, numbering, and emojis for readability

RESPONSE STRUCTURE:
📋 **Direct Answer** (1-2 sentences answering the question)

📖 **Policy Details** (relevant policy sections with specifics)

✅ **What You Can Do** (allowed actions)

❌ **What You Cannot Do** (restrictions, if any)

💡 **Examples** (real-world scenarios, if applicable)

⚠️ **Important Notes** (edge cases, exceptions, or things to remember)

📞 **Need Help?** (when to contact HR)

LANGUAGE:
- Match the user's language (English/Hindi/Hinglish)
- Use bilingual responses when user uses Hinglish
- Keep tone friendly and professional"""

            # Build enriched prompt with context
            enriched_prompt = f"""{system_instruction}

---

EMPLOYEE DETAILS:
{json.dumps(user_context.user_info, indent=2)}

EMPLOYEE'S QUESTION:
"{query}"

QUERY CONTEXT:
{query_context}

AVAILABLE POLICIES:
"""

            # Add all policies with clear structure
            for policy_name, policy_text in user_context.user_policies.items():
                enriched_prompt += f"\n{'='*60}\n"
                enriched_prompt += f"📋 POLICY: {policy_name}\n"
                enriched_prompt += f"{'='*60}\n"
                enriched_prompt += f"{policy_text}\n"

            enriched_prompt += f"\n{'='*60}\n\n"
            enriched_prompt += "Now, provide a comprehensive, helpful response following the structure above."

            logger.info(f"Policy query context: {query_context}")
            logger.debug(f"Full prompt length: {len(enriched_prompt)} chars")

            # Get AI-generated response
            ai_response = get_chat_response(role='employee', prompt=enriched_prompt)

            return {
                "response": ai_response,
                "intent": detection_result.intent.value,
                "confidence": detection_result.confidence,
                "language": detection_result.language.value,
                "query_context": query_context,
                "ai_handled": True
            }

        except Exception as e:
            logger.error(f"Error handling leave policy query: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Fallback response
            fallback_message = self._generate_fallback_policy_response(detection_result.language)

            return {
                "response": fallback_message,
                "intent": detection_result.intent.value,
                "confidence": detection_result.confidence,
                "language": detection_result.language.value,
                "status": "fallback",
                "error": str(e)
            }

    def _identify_policy_query_context(self, query_lower: str) -> str:
        """
        Identify the specific context/category of the policy query - GENERIC for ALL policies

        Returns a description of what kind of policy question this is
        Supports leave, travel, expense, WFH, social media, and ANY other company policy
        """
        contexts = []

        # === LEAVE POLICY CONTEXTS ===

        # Sandwich leave detection
        if any(keyword in query_lower for keyword in ['sandwich', 'friday', 'monday', 'weekend', 'club', 'consecutive']):
            contexts.append("🥪 SANDWICH LEAVE - Taking leave adjacent to weekends/holidays")

        # Approval process
        if any(keyword in query_lower for keyword in ['approval', 'approve', 'manager', 'who approves', 'permission']):
            contexts.append("✅ APPROVAL PROCESS - Leave/request approval workflow")

        # Notice period
        if any(keyword in query_lower for keyword in ['notice', 'advance', 'how many days', 'short notice', 'emergency']):
            contexts.append("⏰ NOTICE PERIOD - Advance notice requirements")

        # Leave types
        if any(keyword in query_lower for keyword in ['sick', 'casual', 'earned', 'privilege', 'maternity', 'paternity', 'leave type']):
            contexts.append("📝 LEAVE TYPES - Different leave categories")

        # Leave balance / entitlement
        if any(keyword in query_lower for keyword in ['balance', 'entitled', 'how many', 'quota', 'allowance']):
            contexts.append("💰 ENTITLEMENT - Leave balance/quota")

        # Carry forward / Encashment
        if any(keyword in query_lower for keyword in ['carry', 'encash', 'lapse', 'expire', 'next year']):
            contexts.append("🔄 CARRY FORWARD/ENCASHMENT - Unused leave handling")

        # Medical certificate
        if any(keyword in query_lower for keyword in ['medical', 'certificate', 'doctor', 'proof', 'document']):
            contexts.append("🏥 MEDICAL DOCUMENTATION - Certificate requirements")

        # Half day / Short leave
        if any(keyword in query_lower for keyword in ['half', 'half day', 'short leave', 'few hours']):
            contexts.append("⏱️ HALF DAY/SHORT LEAVE - Partial day leave")

        # === TRAVEL POLICY CONTEXTS ===

        if any(keyword in query_lower for keyword in ['travel', 'trip', 'journey', 'flight', 'hotel', 'business class', 'economy']):
            contexts.append("✈️ TRAVEL POLICY - Business travel guidelines")

        # === EXPENSE/REIMBURSEMENT POLICY CONTEXTS ===

        if any(keyword in query_lower for keyword in ['expense', 'reimbursement', 'claim', 'bill', 'receipt', 'petrol', 'food']):
            contexts.append("💵 EXPENSE POLICY - Reimbursement and claims")

        # === WORK FROM HOME POLICY CONTEXTS ===

        if any(keyword in query_lower for keyword in ['wfh', 'work from home', 'remote', 'hybrid', 'work remotely']):
            contexts.append("🏠 WORK FROM HOME - Remote work policy")

        # === SOCIAL MEDIA POLICY CONTEXTS ===

        if any(keyword in query_lower for keyword in ['social media', 'facebook', 'twitter', 'instagram', 'linkedin', 'post', 'share']):
            contexts.append("📱 SOCIAL MEDIA - Social media usage guidelines")

        # === CODE OF CONDUCT CONTEXTS ===

        if any(keyword in query_lower for keyword in ['code of conduct', 'conduct', 'behavior', 'behaviour', 'ethics', 'harassment']):
            contexts.append("📜 CODE OF CONDUCT - Workplace behavior policy")

        # === DRESS CODE CONTEXTS ===

        if any(keyword in query_lower for keyword in ['dress code', 'attire', 'clothing', 'uniform', 'casual', 'formal']):
            contexts.append("👔 DRESS CODE - Workplace attire policy")

        # === ATTENDANCE POLICY CONTEXTS ===

        if any(keyword in query_lower for keyword in ['attendance', 'presence', 'late', 'late coming', 'punctuality', 'timing']):
            contexts.append("⏲️ ATTENDANCE - Attendance and punctuality policy")

        # === PERFORMANCE REVIEW CONTEXTS ===

        if any(keyword in query_lower for keyword in ['performance', 'appraisal', 'review', 'rating', 'pms', 'kpi', 'goals']):
            contexts.append("📊 PERFORMANCE REVIEW - Appraisal and evaluation process")

        # === SALARY/COMPENSATION CONTEXTS ===

        if any(keyword in query_lower for keyword in ['salary', 'compensation', 'increment', 'hike', 'bonus', 'ctc', 'pay']):
            contexts.append("💰 SALARY/COMPENSATION - Salary and increment policy")

        # === BENEFITS CONTEXTS ===

        if any(keyword in query_lower for keyword in ['benefit', 'insurance', 'medical', 'health', 'gym', 'perks']):
            contexts.append("🎁 BENEFITS - Company benefits and perks")

        # === PROBATION CONTEXTS ===

        if any(keyword in query_lower for keyword in ['probation', 'new joiner', 'just joined', 'first month', 'probationary']):
            contexts.append("🆕 PROBATION PERIOD - Policies during probation")

        # === NOTICE PERIOD (RESIGNATION) CONTEXTS ===

        if any(keyword in query_lower for keyword in ['resignation', 'resign', 'quit', 'leaving', 'last day', 'notice period']):
            contexts.append("📤 RESIGNATION/NOTICE - Notice period for resignation")

        # === TRAINING & DEVELOPMENT CONTEXTS ===

        if any(keyword in query_lower for keyword in ['training', 'learning', 'course', 'certification', 'upskilling', 'development']):
            contexts.append("📚 TRAINING & DEVELOPMENT - Learning and development policy")

        # === GENERAL POLICY OVERVIEW ===

        if any(keyword in query_lower for keyword in ['my policy', 'what policy', 'applicable', 'company policy', 'all policies']):
            contexts.append("📚 GENERAL POLICY OVERVIEW - Overall policy information")

        # If no specific context identified
        if not contexts:
            contexts.append("❓ GENERAL POLICY QUERY - Company policy question")

        return "\n".join(contexts)

    def _generate_fallback_policy_response(self, language: Language) -> str:
        """Generate fallback response when AI fails"""
        templates = {
            Language.ENGLISH: """📋 I'm having trouble accessing the detailed policy information right now.

Here's what you can do:
• Contact your HR department directly
• Check your company's HR portal/intranet
• Email your manager for policy clarification

I apologize for the inconvenience! 🙏""",

            Language.HINDI: """📋 मुझे अभी विस्तृत नीति जानकारी तक पहुँचने में समस्या हो रही है।

आप यह कर सकते हैं:
• अपने HR विभाग से सीधे संपर्क करें
• अपनी कंपनी के HR पोर्टल/इंट्रानेट की जाँच करें
• नीति स्पष्टीकरण के लिए अपने मैनेजर को ईमेल करें

असुविधा के लिए खेद है! 🙏""",

            Language.HINGLISH: """📋 Mujhe abhi detailed policy information access karne mein problem ho rahi hai.

Aap yeh kar sakte ho:
• Apne HR department se directly contact karo
• Apni company ke HR portal/intranet check karo
• Policy clarification ke liye apne manager ko email karo

Inconvenience ke liye sorry! 🙏"""
        }

        return templates.get(language, templates[Language.ENGLISH])

    def _generate_policy_response(self, policy_content: List[Dict], language: Language, query: str) -> str:
        """Generate appropriate policy response based on language"""
        if not policy_content:
            templates = {
                Language.ENGLISH: "I couldn't find specific policy information for your query. Please contact HR for detailed information.",
                Language.HINDI: "मुझे आपके प्रश्न के लिए विशिष्ट नीति जानकारी नहीं मिली। विस्तृत जानकारी के लिए कृपया HR से संपर्क करें।",
                Language.HINGLISH: "Aapke question ke liye specific policy information nahi mili. Detail ke liye HR se contact karo."
            }
            return templates.get(language, templates[Language.ENGLISH])

        # Build response with policy content
        response_parts = []

        # Add greeting based on language
        greetings = {
            Language.ENGLISH: "📋 Here's the relevant policy information:",
            Language.HINDI: "📋 यहाँ संबंधित नीति की जानकारी है:",
            Language.HINGLISH: "📋 Yahan relevant policy information hai:"
        }

        response_parts.append(greetings.get(language, greetings[Language.ENGLISH]))

        for policy in policy_content:
            response_parts.append(f"\n\n**{policy['policy_name']}:**")
            response_parts.append(policy['content'])

        return "".join(response_parts)

    async def _handle_apply_leave(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """Handle leave application requests"""
        # Signal to use existing leave application system
        return {
            "use_existing_leave_system": True,
            "intent": detection_result.intent.value,
            "confidence": detection_result.confidence,
            "language": detection_result.language.value,
            "extracted_entities": detection_result.extracted_entities
        }

    async def _handle_mark_attendance(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """Handle attendance marking requests"""
        # Signal to use existing attendance system
        return {
            "use_existing_attendance_system": True,
            "intent": detection_result.intent.value,
            "confidence": detection_result.confidence,
            "language": detection_result.language.value
        }

    async def _handle_check_leave_balance(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """Handle leave balance check requests"""
        # Signal to use existing leave balance system
        return {
            "use_existing_balance_system": True,
            "intent": detection_result.intent.value,
            "confidence": detection_result.confidence,
            "language": detection_result.language.value
        }

    async def _handle_create_job_description(self, detection_result: DetectionResult, user_context: UserContext, query: str) -> Dict[str, Any]:
        """Handle job description creation requests"""
        try:
            entities = detection_result.extracted_entities

            # Generate job description based on extracted entities
            job_description = self._generate_job_description(entities, detection_result.language, query)

            return {
                "response": job_description,
                "intent": detection_result.intent.value,
                "confidence": detection_result.confidence,
                "language": detection_result.language.value,
                "extracted_entities": entities
            }

        except Exception as e:
            logger.error(f"Error creating job description: {e}")
            return {
                "error": "Error creating job description",
                "status": "error"
            }

    def _generate_job_description(self, entities: Dict[str, Any], language: Language, query: str) -> str:
        """Generate job description based on extracted entities"""
        # Extract information
        technologies = entities.get('technologies', [])
        experience = entities.get('experience_years', 'Not specified')
        job_titles = entities.get('job_titles', ['Developer'])

        # Build job description
        job_title = job_titles[0].title() if job_titles else 'Software Developer'
        tech_stack = ', '.join(technologies) if technologies else 'relevant technologies'

        templates = {
            Language.ENGLISH: f"""
📋 **Job Description: {job_title}**

**Position:** {job_title}
**Experience Required:** {experience} years
**Key Technologies:** {tech_stack}

**Responsibilities:**
• Develop and maintain software applications
• Collaborate with cross-functional teams
• Write clean, maintainable code
• Participate in code reviews and testing

**Requirements:**
• {experience} years of experience in software development
• Proficiency in {tech_stack}
• Strong problem-solving skills
• Excellent communication skills

**What We Offer:**
• Competitive salary
• Professional development opportunities
• Collaborative work environment
• Growth opportunities
""",
            Language.HINDI: f"""
📋 **नौकरी विवरण: {job_title}**

**पद:** {job_title}
**आवश्यक अनुभव:** {experience} वर्ष
**मुख्य तकनीकें:** {tech_stack}

**जिम्मेदारियां:**
• सॉफ्टवेयर एप्लिकेशन विकसित करना और बनाए रखना
• विभिन्न टीमों के साथ सहयोग करना
• स्वच्छ, बनाए रखने योग्य कोड लिखना
• कोड समीक्षा और परीक्षण में भाग लेना

**आवश्यकताएं:**
• सॉफ्टवेयर विकास में {experience} वर्ष का अनुभव
• {tech_stack} में दक्षता
• मजबूत समस्या समाधान कौशल
• उत्कृष्ट संचार कौशल
""",
            Language.HINGLISH: f"""
📋 **Job Description: {job_title}**

**Position:** {job_title}
**Experience Required:** {experience} saal
**Key Technologies:** {tech_stack}

**Responsibilities:**
• Software applications develop aur maintain karna
• Different teams ke sath collaborate karna
• Clean, maintainable code likhna
• Code reviews aur testing mein participate karna

**Requirements:**
• Software development mein {experience} saal ka experience
• {tech_stack} mein proficiency
• Strong problem-solving skills
• Excellent communication skills
"""
        }

        return templates.get(language, templates[Language.ENGLISH])

