# 🧠 Autonomous CI/CD Healing Intelligence Core

> **Production-grade autonomous AI system** that identifies, reasons about, patches, and validates software failures without human intervention.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Orchestrator                     │
│                                                              │
│  START → CICDFeedback → RepoAnalyzer → TestRunner           │
│            ↓                                                 │
│         FailureClassifier → RootCause → PatchGenerator      │
│            ↓                                                 │
│         Validation → CommitOptimizer ─→ [converged?] ──┐    │
│                              ↑                  YES     │    │
│                              └──── retry ────────── Scoring → END
└─────────────────────────────────────────────────────────────┘
```

## Agent Roster

| Agent | Role | LLM? |
|-------|------|-------|
| `CICDFeedbackAgent` | Parse GitHub Actions logs → adjust priorities | No |
| `RepoAnalyzerAgent` | Discover files, build dep graph | No |
| `TestRunnerAgent` | Execute pytest, capture JSON report | No |
| `FailureClassifierAgent` | Classify failures by type + severity | No (AST+Regex) |
| `RootCauseAgent` | Backward reasoning to minimal root fault | ✅ GPT-4o |
| `PatchGeneratorAgent` | Generate minimal diff patches | ✅ GPT-4o |
| `ValidationAgent` | Apply + rerun tests + rollback on fail | No |
| `CommitOptimizerAgent` | Group fixes into minimal commits | No |
| `ScoringAgent` | Deterministic score computation | No |

## File Structure

```
CodeReborn/
├── main.py                          # CLI entry point
├── requirements.txt
├── .env.example                     # → copy to .env
│
├── config/
│   └── settings.py                  # Pydantic-settings config
│
├── backend/
│   ├── agents/
│   │   ├── repo_analyzer_agent.py
│   │   ├── test_runner_agent.py
│   │   ├── failure_classifier_agent.py
│   │   ├── root_cause_agent.py
│   │   ├── patch_generator_agent.py
│   │   ├── validation_agent.py
│   │   ├── commit_optimizer_agent.py
│   │   ├── cicd_feedback_agent.py
│   │   └── scoring_agent.py
│   │
│   ├── orchestrator/
│   │   └── graph.py                 # LangGraph state machine
│   │
│   ├── sandbox/
│   │   └── docker_runner.py         # Isolated Docker execution
│   │
│   ├── github/
│   │   └── github_client.py         # GitHub API integration
│   │
│   ├── results/
│   │   └── results_writer.py        # results.json contract writer
│   │
│   └── utils/
│       ├── models.py                # All Pydantic data models
│       ├── ast_parser.py            # AST analysis engine
│       └── logger.py                # Structured loguru logging
│
├── docker/
│   └── Dockerfile.sandbox           # Isolated test runner image
│
└── tests/
    └── test_failure_classifier.py   # Unit tests
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Run on a repository
```bash
python main.py \
  --repo-path /path/to/cloned/repo \
  --repo-url  https://github.com/owner/repo \
  --branch    ai-healing
```

### 4. With CI logs
```bash
python main.py \
  --repo-path /path/to/repo \
  --repo-url  https://github.com/owner/repo \
  --run-id    run-20240219-001 \
  --ci-logs   /path/to/actions.log
```

## Output: `results.json` Contract

```json
{
  "repo_url": "https://github.com/org/repo",
  "branch_name": "ai-healing",
  "run_id": "run-abc123",
  "total_failures": 5,
  "total_fixes": 4,
  "ci_status": "SUCCESS",
  "fixes": [...],
  "ci_timeline": [...],
  "scoring": {
    "base_score": 100.0,
    "speed_factor": 0.8,
    "fix_efficiency": 0.8,
    "regression_penalty": 0.0,
    "ci_success_score": 20.0,
    "total_score": 128.0,
    "computation_method": "deterministic"
  }
}
```

## Failure Types Detected

| Type | Detection Method |
|------|-----------------|
| `SYNTAX` | AST parse failure |
| `INDENTATION` | AST IndentationError |
| `IMPORT` | ModuleNotFoundError regex |
| `TYPE_ERROR` | TypeError regex |
| `RUNTIME` | AttributeError / ValueError regex |
| `TEST_FAILURE` | pytest JSON report |
| `LINTING` | pylint pattern matching |
| `DEPENDENCY` | pip/requirements errors |
| `LOGIC` | LLM root cause analysis |

## Autonomy Guarantees

- ✅ No human prompts at any step
- ✅ No hardcoded file paths (dynamic discovery)
- ✅ Deterministic: `PYTHONHASHSEED=42`, `seed=42` in GPT-4o calls
- ✅ Patch rollback on validation failure
- ✅ `[AI-AGENT]` commit prefix enforced
- ✅ Max 5 retries with adaptive temperature cooling
- ✅ Strict `results.json` schema (Pydantic, `extra="forbid"`)

## Running Tests
```bash
pytest tests/ -v --tb=short
```

## Docker Sandbox Build
```bash
docker build -f docker/Dockerfile.sandbox -t cicd-healer-sandbox .
```
