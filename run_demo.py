"""
run_demo.py
============
DEMO MODE — Runs the full pipeline with a stubbed LLM.
Use this if you don't have an OpenAI key set up yet.
The RootCauseAgent and PatchGeneratorAgent use rule-based
fixes instead of GPT-4o, so everything else runs real.

For full LLM mode:
    cp .env.example .env   # add your OPENAI_API_KEY
    python main.py --repo-path ./sample_broken_repo --repo-url https://github.com/demo/repo
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

# ── Force demo env ───────────────────────────────────────────
os.environ.setdefault("OPENAI_API_KEY", "sk-demo-mode-no-real-calls")

from backend.utils.logger import logger, setup_logger
from backend.utils.models import AgentState, CIStatus
from backend.agents.repo_analyzer_agent import RepoAnalyzerAgent
from backend.agents.test_runner_agent import TestRunnerAgent
from backend.agents.failure_classifier_agent import FailureClassifierAgent
from backend.agents.scoring_agent import ScoringAgent
from backend.results.results_writer import ResultsWriter
from config.settings import settings


# ─────────────────────────────────────────────────────────────
# Rule-based patch engine (no LLM needed for demo)
# ─────────────────────────────────────────────────────────────

RULE_PATCHES = {
    "calculator.py": {
        "fix": lambda code: (
            code
            .replace(
                "def subtract(a: float, b: float) -> float\n",
                "def subtract(a: float, b: float) -> float:\n"
            )
            .replace("return str(a / b)", "return a / b")
            .replace("for i in range(1, num + 1):", "for i in range(1, n + 1):")
            .replace("return math.sqrt(x)", "__import__('math').sqrt(x)")
            # also add import math at top
        ),
        "description": "Fixed: missing colon in subtract(), str→float in divide(), 'num'→'n' in factorial(), added math import"
    },
    "string_utils.py": {
        "fix": lambda code: (
            code
            .replace(
                "        return s[::-1]   # BUG: IndentationError — extra indent",
                "    return s[::-1]"
            )
            .replace(
                "        if ch not in VOWELS:   # BUG: logic inverted — should be 'in'",
                "        if ch in VOWELS:"
            )
        ),
        "description": "Fixed: indentation in reverse_string(), 'not in'→'in' in count_vowels()"
    }
}


def apply_rule_patches(repo_path: str) -> list:
    """Apply deterministic rule-based patches (demo mode)."""
    applied = []
    for fname, info in RULE_PATCHES.items():
        for root, _, files in os.walk(repo_path):
            for f in files:
                if f == fname:
                    full_path = os.path.join(root, f)
                    original = Path(full_path).read_text(encoding="utf-8")
                    patched = info["fix"](original)
                    if patched != original:
                        Path(full_path).write_text(patched, encoding="utf-8")
                        applied.append((fname, full_path, info["description"]))
                        logger.success(f"[DEMO-PATCH] Applied rule patch to {fname}")
    return applied


def main():
    repo_path = str(Path("sample_broken_repo").resolve())
    repo_url = "https://github.com/demo/sample-broken-repo"
    run_id = f"demo-{uuid.uuid4().hex[:8]}"
    branch_name = "ai-healing-demo"

    log_dir = Path("backend/results") / run_id / "logs"
    setup_logger(run_id, log_dir)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🧠 CI/CD Healing Agent — DEMO MODE (Rule-Based Patches)    ║
║  Full LLM mode: add OPENAI_API_KEY to .env and run main.py  ║
╠══════════════════════════════════════════════════════════════╣
║  run_id   : {run_id:<50}║
║  repo     : {repo_path:<50}║
╚══════════════════════════════════════════════════════════════╝
    """)

    state = AgentState(
        run_id=run_id,
        repo_url=repo_url,
        repo_path=repo_path,
        branch_name=branch_name,
        max_retries=3,
        current_temperature=0.2,
        temperature_min=0.05,
    )

    # ── PHASE 1: Repo Analysis ──────────────────────────────
    print("\n" + "─"*60)
    print("📁 PHASE 1 — Repository Analysis")
    print("─"*60)
    state = RepoAnalyzerAgent(state).run()
    print(f"  ✅ Found {len(state.python_files)} Python files")
    print(f"  ✅ Found {len(state.test_files)} test files")
    for f in state.python_files:
        print(f"     → {Path(f).relative_to(repo_path)}")

    # ── PHASE 2: Run Tests BEFORE ────────────────────────────
    print("\n" + "─"*60)
    print("🧪 PHASE 2 — Running Tests (BEFORE healing)")
    print("─"*60)
    state = TestRunnerAgent(state).run()
    result_before = getattr(state, "_pytest_result", None)
    if result_before:
        print(f"  ❌ Exit code : {result_before.exit_code}")
        print(f"  ❌ Passed    : {result_before.passed}")
        print(f"  ❌ Failed    : {result_before.failed}")
        print(f"  ❌ Errors    : {result_before.errors}")
        print(f"\n  Raw output (first 800 chars):")
        print("  " + result_before.raw_output[:800].replace("\n", "\n  "))

    # ── PHASE 3: Classify Failures ───────────────────────────
    print("\n" + "─"*60)
    print("🔍 PHASE 3 — Failure Classification")
    print("─"*60)
    state = FailureClassifierAgent(state).run()
    print(f"  Classified {len(state.failures)} failures:")
    for f in state.failures:
        print(f"  [{f.severity:8}] [{f.failure_type:15}] {Path(f.file_path).name}:{f.line_number or '?'} — {f.message[:70]}")

    # ── PHASE 4: Apply Patches (Rule-Based) ──────────────────
    print("\n" + "─"*60)
    print("🔧 PHASE 4 — Applying Patches (Demo Rule Engine)")
    print("─"*60)
    print("  (In full mode, GPT-4o generates targeted diffs for each failure)")
    patches_applied = apply_rule_patches(repo_path)
    for fname, fp, desc in patches_applied:
        print(f"  🩹 {fname}")
        print(f"     {desc}")

    # ── PHASE 5: Run Tests AFTER ─────────────────────────────
    print("\n" + "─"*60)
    print("✅ PHASE 5 — Validation (Re-run Tests AFTER healing)")
    print("─"*60)
    state.iteration = 1
    state = TestRunnerAgent(state).run()
    result_after = getattr(state, "_pytest_result", None)
    if result_after:
        status_icon = "✅" if result_after.exit_code == 0 else "⚠️"
        print(f"  {status_icon} Exit code : {result_after.exit_code}")
        print(f"  {status_icon} Passed    : {result_after.passed}")
        print(f"  {status_icon} Failed    : {result_after.failed}")
        print(f"  {status_icon} Errors    : {result_after.errors}")

        if result_after.exit_code == 0:
            print("\n  🎉 ALL TESTS PASS — Repo successfully healed!")
            state.ci_status = CIStatus.SUCCESS
        elif result_after.passed > 0:
            print(f"\n  ⚠️  Partial heal: {result_after.passed} tests now pass")
            state.ci_status = CIStatus.PARTIAL
        else:
            state.ci_status = CIStatus.FAILED

    # ── PHASE 6: Score ───────────────────────────────────────
    print("\n" + "─"*60)
    print("📊 PHASE 6 — Scoring")
    print("─"*60)

    # Build minimal fix records for scoring
    from backend.utils.models import Fix, FailureType, PatchType
    for i, (fname, fp, desc) in enumerate(patches_applied):
        failure = state.failures[i] if i < len(state.failures) else None
        fix = Fix(
            failure_id=failure.failure_id if failure else str(uuid.uuid4()),
            patch_id=str(uuid.uuid4()),
            failure_type=FailureType.SYNTAX,
            file_path=fp,
            line_number=1,
            description=desc,
            patch_type=PatchType.SYNTAX_CORRECTION,
            diff=f"[demo diff for {fname}]",
            validated=result_after.exit_code == 0 if result_after else False,
        )
        state.fixes.append(fix)

    state = ScoringAgent(state).run()
    if state.scoring:
        s = state.scoring
        print(f"  Base Score         : {s.base_score:.1f}")
        print(f"  Fix Score          : {(s.actual_fixes * 10):.1f}  ({s.actual_fixes} fixes × 10)")
        print(f"  Speed Bonus        : {s.speed_factor * 10 * settings.SCORE_SPEED_FACTOR:.1f}")
        print(f"  Regression Penalty : -{s.regression_penalty:.1f}")
        print(f"  CI Success Bonus   : +{s.ci_success_score:.1f}")
        print(f"  ───────────────────────────────")
        print(f"  🏆 TOTAL SCORE     : {s.total_score:.2f}")

    # ── PHASE 7: Write results.json ──────────────────────────
    print("\n" + "─"*60)
    print("💾 PHASE 7 — Writing results.json")
    print("─"*60)
    writer = ResultsWriter(state)
    output_path = writer.write()
    print(f"  ✅ Written: {output_path}")

    # Print the results.json content
    print("\n  === results.json PREVIEW ===")
    content = json.loads(output_path.read_text())
    print(json.dumps(content, indent=2)[:1500])
    if len(json.dumps(content)) > 1500:
        print("  ... (truncated, see full file)")

    # ── FINAL SUMMARY ────────────────────────────────────────
    print("\n" + "═"*60)
    print("🏁 HEALING COMPLETE")
    print("═"*60)
    print(f"  CI Status   : {state.ci_status}")
    print(f"  Total Score : {state.scoring.total_score:.2f}" if state.scoring else "")
    print(f"  Results     : {output_path}")
    print(f"\n  Next steps for FULL LLM mode:")
    print(f"    1. cp .env.example .env")
    print(f"    2. Add your OPENAI_API_KEY to .env")
    print(f"    3. python main.py \\")
    print(f"         --repo-path ./sample_broken_repo \\")
    print(f"         --repo-url  https://github.com/you/repo")
    print("═"*60)


if __name__ == "__main__":
    main()
