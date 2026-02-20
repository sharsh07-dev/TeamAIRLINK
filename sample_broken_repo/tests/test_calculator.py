"""
tests/test_calculator.py — Test suite for calculator module.
These tests are CORRECT — the bugs are in the source.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.calculator import add, subtract, multiply, divide, factorial, square_root


class TestCalculator:

    def test_add(self):
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0

    def test_subtract(self):
        assert subtract(10, 4) == 6
        assert subtract(0, 5) == -5

    def test_multiply(self):
        assert multiply(3, 4) == 12
        assert multiply(-2, 5) == -10

    def test_divide_returns_float(self):
        result = divide(10, 2)
        assert result == 5.0
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_divide_by_zero(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(5, 0)

    def test_factorial_zero(self):
        assert factorial(0) == 1

    def test_factorial_positive(self):
        assert factorial(5) == 120
        assert factorial(1) == 1

    def test_factorial_negative(self):
        with pytest.raises(ValueError):
            factorial(-1)

    def test_square_root(self):
        assert square_root(9) == 3.0
        assert square_root(0) == 0.0

    def test_square_root_negative(self):
        with pytest.raises(ValueError):
            square_root(-1)
