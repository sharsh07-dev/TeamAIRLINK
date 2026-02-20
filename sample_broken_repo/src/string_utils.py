"""string_utils.py — DELIBERATELY BROKEN"""

VOWELS = "aeiouAEIOU"

import math  # Added missing import

def reverse_string(s: str) -> str:
    return s[::-1]  # Fixed indentation


def to_upper(s: str) -> str:
    return s.upper()


def count_vowels(s: str) -> int:
    count = 0
    for ch in s:
        if ch in VOWELS:  # Fixed inverted logic
            count += 1
    return count


def is_palindrome(s: str) -> bool:
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]