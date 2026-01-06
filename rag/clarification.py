"""Clarification detection and handling utilities for RAG system."""

import re
from typing import Optional, Dict


def detect_clarification(response: str) -> Optional[Dict]:
    """
    Detect if the LLM response contains a clarification question.
    
    Args:
        response: The LLM response text
        
    Returns:
        Dictionary with clarification details if detected, None otherwise
        Format: {
            "clarification_question": str,
            "original_context": str,
            "detected": bool
        }
    """
    if not response or not isinstance(response, str):
        return None
    
    response_lower = response.lower()
    
    # Pattern 1: Direct clarification questions about Acts
    act_clarification_patterns = [
        r'section\s+\d+[^\s]*\s+exists\s+in\s+multiple\s+gst\s+acts[^?]*\?',
        r'which\s+act\s+(?:are\s+you\s+)?referring\s+to\??',
        r'which\s+gst\s+act[^?]*\??',
        r'please\s+specify\s+(?:which\s+)?(?:act|gst\s+act)[^?]*\??',
    ]
    
    # Pattern 2: General clarification requests
    general_clarification_patterns = [
        r'please\s+clarify[^?]*\??',
        r'could\s+you\s+(?:please\s+)?(?:clarify|specify)[^?]*\??',
        r'would\s+you\s+(?:please\s+)?(?:clarify|specify)[^?]*\??',
        r'i\s+need\s+(?:more\s+)?(?:information|clarification)[^?]*\??',
        r'which\s+(?:one|option|act|version)[^?]*\??',
    ]
    
    # Pattern 3: Questions ending with "?" that indicate clarification needed
    # But exclude questions that are part of explanations
    clarification_indicators = [
        r'which\s+act',
        r'which\s+gst\s+act',
        r'please\s+clarify',
        r'could\s+you\s+specify',
        r'which\s+one',
    ]
    
    # Check for Act-specific clarifications (highest priority)
    for pattern in act_clarification_patterns:
        match = re.search(pattern, response_lower, re.IGNORECASE)
        if match:
            # Extract the clarification question
            clarification_question = _extract_clarification_question(response, match)
            return {
                "clarification_question": clarification_question,
                "original_context": response,
                "detected": True,
                "type": "act_clarification"
            }
    
    # Check for general clarifications
    for pattern in general_clarification_patterns:
        match = re.search(pattern, response_lower, re.IGNORECASE)
        if match:
            clarification_question = _extract_clarification_question(response, match)
            return {
                "clarification_question": clarification_question,
                "original_context": response,
                "detected": True,
                "type": "general_clarification"
            }
    
    # Check for clarification indicators followed by question mark
    # Look for sentences ending with "?" that contain clarification indicators
    sentences = re.split(r'[.!?]\s+', response)
    for sentence in sentences:
        sentence_lower = sentence.lower().strip()
        if sentence_lower.endswith('?'):
            for indicator in clarification_indicators:
                if indicator in sentence_lower:
                    return {
                        "clarification_question": sentence.strip(),
                        "original_context": response,
                        "detected": True,
                        "type": "indicator_based"
                    }
    
    return None


def _extract_clarification_question(response: str, match: re.Match) -> str:
    """
    Extract the clarification question from the response.
    Preserves context and explanation around the question.
    
    Args:
        response: Full response text
        match: Regex match object
        
    Returns:
        Extracted clarification question with context
    """
    # Get the sentence containing the match
    start_pos = match.start()
    end_pos = match.end()
    
    # Find sentence boundaries - look for the start of the paragraph/section
    # Try to include preceding context if it's part of the clarification
    sentence_start = max(0, response.rfind('.', 0, start_pos), response.rfind('!', 0, start_pos), response.rfind('?', 0, start_pos))
    if sentence_start == -1:
        sentence_start = 0
    else:
        sentence_start += 1
    
    # Include the sentence with the question mark
    sentence_end = min(len(response), response.find('.', end_pos), response.find('!', end_pos), response.find('?', end_pos))
    if sentence_end == -1:
        sentence_end = len(response)
    else:
        sentence_end += 1
    
    # Extract the sentence(s) containing the clarification
    question = response[sentence_start:sentence_end].strip()
    
    # If the sentence doesn't end with "?", try to find the question mark
    if not question.endswith('?'):
        # Look for question mark in the next sentence
        next_q = response.find('?', sentence_end)
        if next_q != -1:
            question = response[sentence_start:next_q + 1].strip()
    
    # If we found a short question, try to include preceding context sentence
    # This helps preserve explanations like "Section X exists in multiple Acts..."
    if len(question) < 100 and sentence_start > 0:
        # Look for preceding sentence that might provide context
        prev_sentence_start = max(0, response.rfind('.', 0, sentence_start - 1), 
                                  response.rfind('!', 0, sentence_start - 1),
                                  response.rfind('?', 0, sentence_start - 1))
        if prev_sentence_start > 0:
            prev_sentence_start += 1
            prev_sentence = response[prev_sentence_start:sentence_start].strip()
            # If preceding sentence mentions "section" or "act", include it
            if any(keyword in prev_sentence.lower() for keyword in ['section', 'act', 'gst', 'cgst', 'igst', 'utgst']):
                question = prev_sentence + " " + question
    
    return question if question else response[match.start():match.end()]


def extract_clarification_context(response: str) -> Dict:
    """
    Extract clarification question and original question context.
    
    Args:
        response: The LLM response text
        
    Returns:
        Dictionary with clarification details
    """
    clarification = detect_clarification(response)
    
    if clarification:
        return clarification
    
    return {
        "clarification_question": None,
        "original_context": response,
        "detected": False,
        "type": None
    }


def combine_question_with_clarification(original_question: str, clarification_response: str) -> str:
    """
    Combine the original question with the user's clarification response.
    
    Args:
        original_question: The original ambiguous question
        clarification_response: User's response to the clarification
        
    Returns:
        Enhanced question that includes the clarification
    """
    original_lower = original_question.lower()
    clarification_lower = clarification_response.lower().strip()
    
    # Extract Act name from clarification response
    act_name = None
    if 'cgst' in clarification_lower:
        act_name = 'CGST Act'
    elif 'igst' in clarification_lower:
        act_name = 'IGST Act'
    elif 'utgst' in clarification_lower:
        act_name = 'UTGST Act'
    elif 'central' in clarification_lower and 'gst' in clarification_lower:
        act_name = 'CGST Act'
    elif 'integrated' in clarification_lower and 'gst' in clarification_lower:
        act_name = 'IGST Act'
    elif 'union' in clarification_lower and 'gst' in clarification_lower:
        act_name = 'UTGST Act'
    
    # If we found an Act name, enhance the original question
    if act_name:
        # Check if question already mentions an Act
        if 'cgst' in original_lower or 'igst' in original_lower or 'utgst' in original_lower:
            # Replace existing Act mention
            enhanced = re.sub(
                r'\b(cgst|igst|utgst|central\s+gst|integrated\s+gst|union\s+territory\s+gst)\s+act\b',
                act_name,
                original_question,
                flags=re.IGNORECASE
            )
            return enhanced
        else:
            # Add Act name to the question
            # Try to insert before "of GST act" or "of the GST act"
            if 'of gst act' in original_lower or 'of the gst act' in original_lower:
                enhanced = re.sub(
                    r'\bof\s+(?:the\s+)?gst\s+act\b',
                    f'of {act_name}',
                    original_question,
                    flags=re.IGNORECASE
                )
                return enhanced
            else:
                # Append Act specification
                return f"{original_question} ({act_name})"
    
    # If no Act name found, try to incorporate the clarification response directly
    # This handles cases where user provides more specific information
    if len(clarification_response) < 50:  # Short response, likely just an answer
        return f"{original_question} - {clarification_response}"
    
    # For longer responses, just append
    return f"{original_question}\n\nUser clarification: {clarification_response}"

