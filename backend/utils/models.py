"""
backend/utils/models.py
========================
Shared Pydantic data models (the strict contract) used by all agents.
These are the canonical data structures flowing through the LangGraph graph.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class FailureType(str, Enum):
    LINTING = "LINTING"
    SYNTAX = "SYNTAX"
    LOGIC = "LOGIC"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT = "IMPORT"
    INDENTATION = "INDENTATION"
    RUNTIME = "RUNTIME"
    TEST_FAILURE = "TEST_FAILURE"
    DEPENDENCY = "DEPENDENCY"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PatchType(str, Enum):
    SYNTAX_CORRECTION = "syntax_correction"
    IMPORT_REPAIR = "import_repair"
    NULL_GUARD = "null_guard"
    TYPE_FIX = "type_fix"
    DEPENDENCY_FIX = "dependency_fix"
    LOGIC_CORRECTION = "logic_correction"


class LanguageMode(str, Enum):
    PYTHON   = "PYTHON"
    NODE_JS  = "NODE_JS"
    JAVA     = "JAVA"
    UNKNOWN  = "UNKNOWN"


class CIStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


# ─────────────────────────────────────────────
# Core Failure Model
# ─────────────────────────────────────────────

class Failure(BaseModel):
    failure_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_type: FailureType
    severity: Severity
    file_path: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    message: str
    raw_trace: Optional[str] = None
    test_name: Optional[str] = None
    root_cause_file: Optional[str] = None
    root_cause_line: Optional[int] = None
    classified_at: float = Field(default_factory=time.time)


# ─────────────────────────────────────────────
# Patch Model
# ─────────────────────────────────────────────

class Patch(BaseModel):
    patch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_id: str
    patch_type: PatchType
    file_path: str
    original_code: str
    patched_code: str
    diff: str
    line_start: int
    line_end: int
    reasoning: str
    deterministic: bool = True
    applied: bool = False
    validated: bool = False
    generated_at: float = Field(default_factory=time.time)


# ─────────────────────────────────────────────
# Validation Result
# ─────────────────────────────────────────────

class ValidationResult(BaseModel):
    patch_id: str
    passed: bool
    new_failures_introduced: int = 0
    tests_before: int = 0
    tests_after: int = 0
    tests_fixed: int = 0
    tests_regressed: int = 0
    deterministic: bool = True
    rejection_reason: Optional[str] = None
    validated_at: float = Field(default_factory=time.time)


# ─────────────────────────────────────────────
# Fix Record (results.json contract)
# ─────────────────────────────────────────────

class Fix(BaseModel):
    fix_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_id: str
    patch_id: str
    failure_type: FailureType
    file_path: str
    line_number: Optional[int]
    description: str
    patch_type: PatchType
    diff: str
    original_code: str = ""
    patched_code: str = ""
    validated: bool
    commit_sha: Optional[str] = None
    fixed_at: float = Field(default_factory=time.time)


# ─────────────────────────────────────────────
# CI Timeline Event
# ─────────────────────────────────────────────

class CITimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    iteration: int
    event_type: str  # "ANALYSIS", "PATCH", "VALIDATION", "RETRY", "SUCCESS"
    description: str
    failures_before: int = 0
    failures_after: int = 0
    timestamp: float = Field(default_factory=time.time)
    duration_seconds: float = 0.0


# ─────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────

class Scoring(BaseModel):
    base_score: float
    speed_factor: float
    fix_efficiency: float
    regression_penalty: float
    ci_success_score: float
    total_score: float
    iterations_used: int
    total_possible_fixes: int
    actual_fixes: int
    computation_method: str = "deterministic"


# ─────────────────────────────────────────────
# Master Agent State (LangGraph state dict)
# ─────────────────────────────────────────────

class AgentState(BaseModel):
    """Canonical state flowing through the LangGraph graph."""

    # Identity
    run_id: str
    repo_url: str
    repo_path: str
    branch_name: str
    ci_logs: Optional[str] = None

    # Discovery
    python_files: List[str] = Field(default_factory=list)   # kept for back-compat
    source_files: List[str] = Field(default_factory=list)   # all scanned source files
    test_files: List[str] = Field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = Field(default_factory=dict)
    config_files: List[str] = Field(default_factory=list)
    repo_language: str = LanguageMode.UNKNOWN   # detected language mode
    test_runner_tool: str = "pytest"            # pytest | npm | mvn

    # Analysis
    failures: List[Failure] = Field(default_factory=list)
    patches: List[Patch] = Field(default_factory=list)
    validation_results: List[ValidationResult] = Field(default_factory=list)
    fixes: List[Fix] = Field(default_factory=list)

    # Test runner output (persisted so FailureClassifier can read it)
    pytest_output: str = ""                          # raw stdout/stderr
    pytest_json_report: Dict[str, Any] = Field(default_factory=dict)  # JSON report
    pytest_exit_code: int = 0
    pytest_pass_count: int = 0
    pytest_fail_count: int = 0

    # Orchestration
    iteration: int = 0
    max_retries: int = 5
    ci_status: CIStatus = CIStatus.PENDING
    timeline: List[CITimelineEvent] = Field(default_factory=list)

    # LLM tuning across retries
    current_temperature: float = 0.2
    temperature_min: float = 0.05

    # Scoring
    scoring: Optional[Scoring] = None
    start_time: float = Field(default_factory=time.time)

    # LLM Strategy
    primary_model: str = "unknown"
    fallback_model: str = "unknown"
    fallback_triggered: bool = False
    
    # Error state
    fatal_error: Optional[str] = None
    convergence_reached: bool = False

    model_config = ConfigDict(use_enum_values=True)


# ─────────────────────────────────────────────
# results.json — STRICT CONTRACT
# ─────────────────────────────────────────────

class ResultsContract(BaseModel):
    """Strict output schema for results.json. No extra fields allowed."""

    repo_url: str
    branch_name: str
    run_id: str
    total_failures: int
    total_fixes: int
    ci_status: str
    fixes: List[Dict[str, Any]]
    ci_timeline: List[Dict[str, Any]]
    scoring: Dict[str, Any]
    llm_usage: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")
