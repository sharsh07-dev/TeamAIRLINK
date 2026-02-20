"""
tests/test_failure_classifier.py
===================================
Unit tests for FailureClassifierAgent.
Tests classification accuracy across all FailureType categories.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.utils.models import AgentState, FailureType, Severity


def make_state(**kwargs):
    defaults = dict(
        run_id="test-run-001",
        repo_url="https://github.com/test/repo",
        repo_path="/tmp/test_repo",
        branch_name="ai-test",
    )
    defaults.update(kwargs)
    return AgentState(**defaults)


class TestFailureClassifierAgent:
    """Tests for the failure classification pipeline."""

    def test_syntax_error_classified(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent
        from backend.agents.test_runner_agent import TestRunResult

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        result = agent._detect_type("SyntaxError: invalid syntax at line 5")
        ftype, severity, msg = result
        assert ftype == FailureType.SYNTAX
        assert severity == Severity.CRITICAL

    def test_import_error_classified(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        ftype, severity, msg = agent._detect_type(
            "ModuleNotFoundError: No module named 'numpy'"
        )
        assert ftype == FailureType.IMPORT
        assert severity == Severity.HIGH

    def test_type_error_classified(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        ftype, severity, msg = agent._detect_type(
            "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
        )
        assert ftype == FailureType.TYPE_ERROR
        assert severity == Severity.HIGH

    def test_runtime_error_classified(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        ftype, severity, msg = agent._detect_type(
            "AttributeError: 'NoneType' object has no attribute 'split'"
        )
        assert ftype == FailureType.RUNTIME
        assert severity == Severity.MEDIUM

    def test_deduplication(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent
        from backend.utils.models import Failure

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        failures = [
            Failure(
                failure_type=FailureType.SYNTAX,
                severity=Severity.CRITICAL,
                file_path="a.py",
                line_number=5,
                message="SyntaxError: invalid syntax",
            ),
            Failure(
                failure_type=FailureType.SYNTAX,
                severity=Severity.CRITICAL,
                file_path="a.py",
                line_number=5,
                message="SyntaxError: invalid syntax",
            ),
        ]
        deduped = agent._deduplicate(failures)
        assert len(deduped) == 1

    def test_extract_file_line(self):
        from backend.agents.failure_classifier_agent import FailureClassifierAgent

        state = make_state(python_files=[], test_files=[])
        agent = FailureClassifierAgent(state)

        trace = 'File "/path/to/my_file.py", line 42, in <module>'
        fp, ln = agent._extract_file_line(trace)
        assert fp == "/path/to/my_file.py"
        assert ln == 42


class TestScoringAgent:
    """Tests for the deterministic scoring engine."""

    @pytest.fixture(autouse=True)
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-for-unit-tests")

    def test_perfect_score(self):
        from backend.agents.scoring_agent import ScoringAgent
        from backend.utils.models import Fix, FailureType, PatchType, Failure, Severity

        failure = Failure(
            failure_type=FailureType.SYNTAX,
            severity=Severity.CRITICAL,
            file_path="a.py",
            message="test",
        )
        fix = Fix(
            failure_id=failure.failure_id,
            patch_id="p1",
            failure_type=FailureType.SYNTAX,
            file_path="a.py",
            line_number=1,
            description="fixed syntax",
            patch_type=PatchType.SYNTAX_CORRECTION,
            diff="--- a\n+++ b\n",
            validated=True,
        )
        from backend.utils.models import CIStatus
        state = make_state(
            failures=[failure],
            fixes=[fix],
            iteration=1,
            max_retries=5,
        )
        state.ci_status = CIStatus.SUCCESS.value

        agent = ScoringAgent(state)
        scoring = agent._compute_score()

        assert scoring.total_score > 0
        assert scoring.computation_method == "deterministic"
        assert scoring.actual_fixes == 1

    def test_regression_penalty_applied(self):
        from backend.agents.scoring_agent import ScoringAgent
        from backend.utils.models import ValidationResult

        vr = ValidationResult(
            patch_id="p1",
            passed=False,
            tests_regressed=2,
        )
        state = make_state(
            failures=[],
            fixes=[],
        )
        state.validation_results = [vr]
        agent = ScoringAgent(state)
        scoring = agent._compute_score()
        assert scoring.regression_penalty > 0


class TestASTParser:
    """Tests for the AST analysis engine."""

    def test_parse_valid_file(self, tmp_path):
        from backend.utils.ast_parser import ASTParser

        f = tmp_path / "valid.py"
        f.write_text("x = 1\ny = x + 2\n")
        parser = ASTParser(str(tmp_path))
        tree, err = parser.parse_file(str(f))
        assert tree is not None
        assert err is None

    def test_parse_syntax_error(self, tmp_path):
        from backend.utils.ast_parser import ASTParser

        f = tmp_path / "broken.py"
        f.write_text("def foo(\n    pass\n")
        parser = ASTParser(str(tmp_path))
        tree, err = parser.parse_file(str(f))
        assert tree is None
        assert err is not None
        assert err.issue_type == "SYNTAX"

    def test_extract_imports(self, tmp_path):
        from backend.utils.ast_parser import ASTParser

        f = tmp_path / "imports.py"
        f.write_text("import os\nfrom pathlib import Path\n")
        parser = ASTParser(str(tmp_path))
        ig = parser.extract_imports(str(f))
        assert "os" in ig.imports
        assert ("pathlib", "Path") in ig.from_imports

    def test_source_window(self, tmp_path):
        from backend.utils.ast_parser import ASTParser

        f = tmp_path / "source.py"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        parser = ASTParser(str(tmp_path))
        window = parser.get_source_window(str(f), line=3, window=1)
        assert "line2" in window
        assert "line3" in window
        assert "line4" in window
