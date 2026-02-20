"""
run_polyglot_demo.py
====================
Demonstrates the Polyglot CI Agent healing a broken Node.js repository.
Uses Rule-Based patching for demo purposes (simulating the LLM).
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

# Force minimal env
os.environ.setdefault("OPENAI_API_KEY", "sk-demo-mode")

try:
    from backend.utils.logger import logger, setup_logger
    from backend.utils.models import AgentState, CIStatus, Fix, FailureType, PatchType
    from backend.agents.repo_analyzer_agent import RepoAnalyzerAgent
    from backend.agents.test_runner_agent import TestRunnerAgent
    from backend.agents.failure_classifier_agent import FailureClassifierAgent
    from backend.agents.scoring_agent import ScoringAgent
    from config.settings import settings
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("Run with: export PYTHONPATH=$PWD && .venv/bin/python run_polyglot_demo.py")
    exit(1)


# ─────────────────────────────────────────────────────────────
# Rule-based patches for the demo
# ─────────────────────────────────────────────────────────────
RULE_PATCHES = {
    "index.js": {
        "fix": lambda code: code.replace("a + b; // BUG: accidentally addition", "a - b;"),
        "description": "Fixed: logic error in subtract() function (changed + to -)"
    }
}

def apply_polyglot_patches(repo_path: str) -> list:
    applied = []
    for fname, info in RULE_PATCHES.items():
        for root, _, files in os.walk(repo_path):
            if fname in files:
                full_path = os.path.join(root, fname)
                original = Path(full_path).read_text(encoding="utf-8")
                patched = info["fix"](original)
                if patched != original:
                    Path(full_path).write_text(patched, encoding="utf-8")
                    applied.append((fname, full_path, info["description"]))
                    logger.success(f"[DEMO] Applied patch to {fname}")
    return applied

def main():
    # Setup test repo
    repo_src = Path("sample_broken_node_repo").resolve()
    if not repo_src.exists():
        print("❌ sample_broken_node_repo not found! Run setup commands first.")
        return

    # Use a fresh workspace copy so we don't mutate original sample
    run_id = f"polyglot-{uuid.uuid4().hex[:8]}"
    workspace_dir = Path(f"/tmp/cicd_workspace/{run_id}")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    repo_path = workspace_dir / "broken-node-app"
    try:
        if repo_path.exists():
            shutil.rmtree(repo_path)
        shutil.copytree(repo_src, repo_path)
    except Exception as e:
        print(f"Failed to setup workspace: {e}")
        return
    
    branch_name = "fix/node-bug"
    repo_url = "local://sample/broken-node-app"

    # Logger setup
    log_dir = Path("backend/results") / run_id / "logs"
    setup_logger(run_id, log_dir)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🌐 POLYGLOT CI AGENT — Node.js Healing Demo                ║
╠══════════════════════════════════════════════════════════════╣
║  Run ID   : {run_id:<48}║
║  Repo     : {str(repo_path):<48}║
╚══════════════════════════════════════════════════════════════╝
    """)

    state = AgentState(
        run_id=run_id,
        repo_url=repo_url,
        repo_path=str(repo_path),
        branch_name=branch_name,
        max_retries=3,
    )

    # ── PHASE 1: Analyze (Should detect Node.js) ─────────────
    print("\n🔍 PHASE 1: Analyzing Repository...")
    state = RepoAnalyzerAgent(state).run()
    lang = getattr(state, "repo_language", "UNKNOWN")
    tool = getattr(state, "test_runner_tool", "UNKNOWN")
    print(f"   Detected Language : {lang}")
    print(f"   Test Runner Tool  : {tool}")
    print(f"   Source Files      : {len(state.source_files)}")

    # ── PHASE 2: Test (Should fail) ──────────────────────────
    print("\n🧪 PHASE 2: Running Tests (Initial)...")
    state = TestRunnerAgent(state).run()
    print(f"   Exit Code: {state.pytest_exit_code}")
    print(f"   Passed: {state.pytest_pass_count} | Failed: {state.pytest_fail_count}")
    # print raw output snippet
    out = state.pytest_output.strip()
    print(f"   Output:\n   > {out.replace(chr(10), chr(10)+'   > ')}")

    # ── PHASE 3: Classify ────────────────────────────────────
    print("\n🧐 PHASE 3: Classifying Failures...")
    state = FailureClassifierAgent(state).run()
    print(f"   Classified {len(state.failures)} failures:")
    for f in state.failures:
        print(f"   [{f.severity}] {f.failure_type} in {Path(f.file_path).name}: {f.message}")

    # ── PHASE 4: Patch (Rule-based) ──────────────────────────
    print("\n🔧 PHASE 4: Generating & Applying Patches...")
    patches = apply_polyglot_patches(repo_path)
    for p in patches:
        print(f"   🩹 {p[2]}")
        # Add to state for scoring
        state.fixes.append(Fix(
            failure_id="demo", patch_id="demo", failure_type=FailureType.LOGIC,
            file_path=p[1], line_number=1, description=p[2],
            patch_type=PatchType.LOGIC_CORRECTION, diff="...", validated=True
        ))

    # ── PHASE 5: Verify ──────────────────────────────────────
    print("\n✅ PHASE 5: Verifying Fixes...")
    state = TestRunnerAgent(state).run()
    if state.pytest_exit_code == 0:
        print("   🎉 SUCCESS: All tests passed!")
        state.ci_status = CIStatus.SUCCESS
    else:
        print(f"   ⚠️  STILL FAILING: {state.pytest_fail_count} failures")

    # ── PHASE 6: Metrics ─────────────────────────────────────
    print("\n📊 PHASE 6: Scoring & Results")
    state = ScoringAgent(state).run()
    print(f"   Total Score: {state.scoring.total_score if state.scoring else 0}")
    
    # Write JSON results manually since ResultsWriter is missing
    res_path = Path("backend/results") / f"{run_id}.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    print(f"   Results saved to: {res_path}")

if __name__ == "__main__":
    main()
