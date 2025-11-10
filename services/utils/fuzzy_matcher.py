"""
Simple fuzzy matching service for leave types - focused on spelling mistakes and basic translations
"""

import logging
from typing import List, Dict, Optional, Tuple
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

class SimpleFuzzyMatcher:
    """Simple fuzzy matcher focused on practical use cases"""

    def __init__(self):
        # Comprehensive translations for common words and phrases
        self.translations = {
            # Hindi/Hinglish leave-related terms
            'छुट्टी': 'leave',
            'अवकाश': 'leave',
            'बीमारी': 'sick',
            'बीमार': 'sick',
            'chutti': 'leave',
            'avkash': 'leave',
            'bimari': 'sick',
            'bimar': 'sick',
            'lagwa': 'apply',
            'lagao': 'apply',
            'karna': 'do',
            'karni': 'do',
            'chahiye': 'need',
            'leni': 'take',
            'lena': 'take',

            # Hindi/Hinglish attendance terms
            'हाजिरी': 'attendance',
            'उपस्थिति': 'attendance',
            'haaziri': 'attendance',
            'upsthiti': 'attendance',
            'mark': 'mark',
            'maar': 'mark',
            'punch': 'punch',

            # Hindi/Hinglish balance inquiry terms
            'कितना': 'how much',
            'कितनी': 'how many',
            'बची': 'remaining',
            'हिसाब': 'balance',
            'kitna': 'how much',
            'kitni': 'how many',
            'bachi': 'remaining',
            'hisab': 'balance',
            'dekho': 'check',
            'batao': 'tell',

            # Common typos and variations
            'leav': 'leave',
            'aplly': 'apply',
            'requist': 'request',
            'attendence': 'attendance',
            'atendance': 'attendance',
            'balanc': 'balance',
            'remainig': 'remaining',

            # Spanish
            'enfermedad': 'sick',
            'vacaciones': 'vacation',

            # French
            'maladie': 'sick',
            'congé': 'leave',

            # German
            'krankheit': 'sick',
            'urlaub': 'leave',

            # Polish
            'chorobowy': 'sick',
            'urlop': 'leave',
        }

        # Common Hinglish phrases and patterns
        self.hinglish_phrases = {
            # Leave application phrases
            'merai leave apply krro': 'apply my leave',
            'meri chutti lagwa do': 'apply my leave',
            'chutti kr do': 'apply leave',
            'leave lagwa do': 'apply leave',
            'time off chahiye': 'need time off',
            'absent rahunga': 'will be absent',
            'chutti leni hai': 'need to take leave',
            'leave apply karna hai': 'need to apply leave',

            # Attendance phrases
            'attendance kr do': 'mark attendance',
            'punch maar do': 'punch in',
            'office mai hu': 'in office',
            'haaziri lagao': 'mark attendance',
            'present mark karo': 'mark present',
            'check in kr do': 'check in',

            # Balance inquiry phrases
            'kitni chutti bachi hai': 'how many leaves remaining',
            'leave balance dekho': 'check leave balance',
            'kitna leave hai': 'how much leave available',
            'chutti ka hisab': 'leave balance',
            'leaves check karo': 'check leaves',
            'balance batao': 'tell balance',
        }

    def translate_text(self, text: str) -> str:
        """Enhanced translation of common terms and phrases"""
        text_lower = text.lower().strip()

        # First check for complete phrase translations
        for hinglish_phrase, english_phrase in self.hinglish_phrases.items():
            if hinglish_phrase in text_lower:
                text_lower = text_lower.replace(hinglish_phrase, english_phrase)

        # Then check for individual word translations
        for foreign_word, english_word in self.translations.items():
            if foreign_word in text_lower:
                text_lower = text_lower.replace(foreign_word, english_word)

        return text_lower

    def detect_intent_from_text(self, text: str) -> Optional[str]:
        """Detect HR intent from text with enhanced multilingual support"""
        translated_text = self.translate_text(text)
        text_lower = translated_text.lower()

        # Leave-related patterns
        leave_patterns = [
            'apply leave', 'take leave', 'need leave', 'request leave',
            'apply my leave', 'will be absent', 'need time off',
            'book leave', 'vacation', 'holiday'
        ]

        # Attendance-related patterns
        attendance_patterns = [
            'mark attendance', 'punch in', 'punch out', 'check in', 'check out',
            'mark present', 'in office', 'clock in', 'clock out'
        ]

        # Balance inquiry patterns (enhanced)
        balance_patterns = [
            'leave balance', 'check leaves', 'how many leaves', 'remaining leaves',
            'tell balance', 'how much leave', 'available leaves', 'leave policy',
            'kitni chutti bachi', 'kitna leave hai', 'chutti ka hisab',
            'leaves check karo', 'balance dekho', 'कितनी छुट्टी बची है'
        ]

        # Check patterns
        for pattern in leave_patterns:
            if pattern in text_lower:
                return "apply_leave"

        for pattern in attendance_patterns:
            if pattern in text_lower:
                return "mark_attendance"

        for pattern in balance_patterns:
            if pattern in text_lower:
                return "leave_balance"

        return None

    def fuzzy_match_leave_type(self, user_input: str, available_leave_types: List[Dict]) -> Optional[Tuple[Dict, int]]:
        """
        Find best matching leave type with fuzzy matching

        Args:
            user_input: User's input text
            available_leave_types: List of available leave types

        Returns:
            Tuple of (matched_leave_type, confidence_score) or None
        """
        if not user_input or not available_leave_types:
            return None

        # Translate basic terms first
        translated_input = self.translate_text(user_input)
        user_input_lower = translated_input.lower().strip()

        best_match = None
        best_score = 0

        for leave_type in available_leave_types:
            if not isinstance(leave_type, dict):
                continue

            leave_name = leave_type.get('name', '').lower().strip()
            if not leave_name:
                continue

            # Strategy 1: Direct fuzzy matching with full leave name
            score1 = fuzz.ratio(user_input_lower, leave_name)
            score2 = fuzz.partial_ratio(user_input_lower, leave_name)
            score3 = fuzz.token_sort_ratio(user_input_lower, leave_name)
            score4 = fuzz.token_set_ratio(user_input_lower, leave_name)

            # Strategy 2: Match against individual distinctive words
            leave_words = [word for word in leave_name.split() if len(word) > 3 and word != 'leave']
            word_scores = []

            for word in leave_words:
                word_scores.append(fuzz.ratio(user_input_lower, word))
                # Check if word is contained in user input
                if word in user_input_lower or user_input_lower in word:
                    word_scores.append(85)

            # Strategy 3: Check if user input contains key terms
            user_words = [word for word in user_input_lower.split() if len(word) > 2]
            for user_word in user_words:
                for leave_word in leave_words:
                    if fuzz.ratio(user_word, leave_word) > 80:
                        word_scores.append(90)

            # Combine all scores
            all_scores = [score1, score2, score3, score4] + word_scores
            max_score = max(all_scores) if all_scores else 0

            if max_score > best_score:
                best_score = max_score
                best_match = leave_type

        # Validation: avoid generic matches
        if best_match and best_score >= 70:
            # Extra validation for very short or generic inputs
            if (len(user_input.strip()) <= 3 or
                user_input.lower().strip() in ['xyz', 'abc', 'test', 'xyz leave']):
                if best_score < 95:  # Require very high confidence for generic inputs
                    return None

            logger.info(f"Fuzzy matched '{user_input}' to '{best_match.get('name')}' with score {best_score}")
            return best_match, best_score

        return None

    def is_leave_type_mention(self, user_input: str, available_leave_types: List[Dict]) -> bool:
        """Check if user input mentions any leave type"""
        match = self.fuzzy_match_leave_type(user_input, available_leave_types)
        return match is not None and match[1] >= 75


# Global instance
simple_fuzzy_matcher = SimpleFuzzyMatcher()