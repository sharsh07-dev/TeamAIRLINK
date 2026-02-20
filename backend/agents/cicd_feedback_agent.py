"""
backend/agents/cicd_feedback_agent.py
=======================================
CICDFeedbackAgent — Consumes GitHub Actions CI logs and extracts
structured signals to feed into retry/priority logic.
Identifies: failing job steps, env mismatches, flaky steps.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger
from backend.utils.models import AgentState, CITimelineEvent


@dataclass
class CISignal:
    job_name: str
    step_name: str
    failure_message: str
    is_env_issue: bool = False
    is_dependency_issue: bool = False
    is_test_failure: bool = False
    raw_log_excerpt: str = ""


ENV_PATTERNS = [
    re.compile(r"environment variable .+? not set", re.I),
    re.compile(r"No such file or directory", re.I),
    re.compile(r"command not found", re.I),
    re.compile(r"Permission denied", re.I),
    re.compile(r"ENOENT", re.I),
]

DEP_PATTERNS = [
    re.compile(r"ModuleNotFoundError", re.I),
    re.compile(r"No module named", re.I),
    re.compile(r"pip install", re.I),
    re.compile(r"requirements", re.I),
    re.compile(r"dependency", re.I),
]

STEP_HEADER = re.compile(r"##\[group\](.+?)$", re.MULTILINE)
ERROR_HEADER = re.compile(r"##\[error\](.+?)$", re.MULTILINE)


class CICDFeedbackAgent:
    """
    Parses GitHub Actions log format (or raw CI output) into CISignals.
    These signals adjust:
    - Failure priority boost (env issues = high priority)
    - Patch strategy (dep issues → import repair)
    - Retry temperature adjustment
    """

    def __init__(self, state: AgentState):
        self.state = state

    def run(self) -> AgentState:
        t0 = time.time()
        ci_logs = self.state.ci_logs

        if not ci_logs:
            logger.info("[CICDFeedbackAgent] No CI logs provided, skipping")
            return self.state

        logger.info("[CICDFeedbackAgent] Parsing CI logs...")
        signals = self._parse_ci_logs(ci_logs)
        self._apply_signals(signals)

        elapsed = time.time() - t0
        self.state.timeline.append(CITimelineEvent(
            iteration=self.state.iteration,
            event_type="CI_FEEDBACK",
            description=f"Parsed {len(signals)} CI signals from logs",
            duration_seconds=elapsed,
        ))

        logger.info(f"[CICDFeedbackAgent] {len(signals)} signals extracted in {elapsed:.2f}s")
        return self.state

    # ─────────────────────────────────────────
    def _parse_ci_logs(self, raw_logs: str) -> List[CISignal]:
        signals: List[CISignal] = []
        lines = raw_logs.splitlines()
        current_step = "unknown"

        for i, line in enumerate(lines):
            # Detect step headers
            m = STEP_HEADER.search(line)
            if m:
                current_step = m.group(1).strip()
                continue

            # Detect errors
            err_m = ERROR_HEADER.search(line)
            if err_m:
                error_msg = err_m.group(1).strip()
                excerpt = "\n".join(lines[max(0, i-2):i+3])

                signal = CISignal(
                    job_name="ci-build",
                    step_name=current_step,
                    failure_message=error_msg,
                    raw_log_excerpt=excerpt[:500],
                )
                signal.is_env_issue = any(p.search(error_msg) for p in ENV_PATTERNS)
                signal.is_dependency_issue = any(p.search(error_msg) for p in DEP_PATTERNS)
                signal.is_test_failure = "test" in error_msg.lower() or "pytest" in error_msg.lower()

                signals.append(signal)

        return signals

    def _apply_signals(self, signals: List[CISignal]) -> None:
        """
        Adjust failure priorities and agent parameters based on CI signals.
        """
        for signal in signals:
            if signal.is_env_issue:
                logger.warning(f"[CICDFeedbackAgent] ENV issue in step '{signal.step_name}': {signal.failure_message}")
                # Boost DEPENDENCY failures to CRITICAL
                for failure in self.state.failures:
                    if failure.failure_type in ("IMPORT", "DEPENDENCY"):
                        failure.severity = "CRITICAL"

            if signal.is_dependency_issue:
                logger.info(f"[CICDFeedbackAgent] Dependency issue detected in step '{signal.step_name}'")
                # Signal that import_repair patches should be prioritized
                for failure in self.state.failures:
                    if failure.failure_type == "IMPORT":
                        # Move to front
                        self.state.failures.remove(failure)
                        self.state.failures.insert(0, failure)
                        break
