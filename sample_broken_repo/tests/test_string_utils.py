"""
tests/test_string_utils.py — Test suite for string_utils module.
All assertions are correct — bugs are in source.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.string_utils import reverse_string, to_upper, count_vowels, is_palindrome


class TestStringUtils:

    def test_reverse_string(self):
        assert reverse_string("hello") == "olleh"
        assert reverse_string("") == ""
        assert reverse_string("a") == "a"

    def test_to_upper(self):
        assert to_upper("hello") == "HELLO"
        assert to_upper("") == ""

    def test_count_vowels_hello(self):
        # "hello" has 2 vowels: e, o
        assert count_vowels("hello") == 2

    def test_count_vowels_aeiou(self):
        assert count_vowels("aeiou") == 5

    def test_count_vowels_empty(self):
        assert count_vowels("") == 0

    def test_is_palindrome_true(self):
        assert is_palindrome("racecar") is True
        assert is_palindrome("A man a plan a canal Panama") is True

    def test_is_palindrome_false(self):
        assert is_palindrome("hello") is False
