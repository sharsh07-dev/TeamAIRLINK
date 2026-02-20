# Deployment: Deterministic Autonomous CI/CD Agent

## ⚡ Overview
This document outlines the **deterministic deployment configuration** for the Autonomous CI/CD Healing Intelligence Core. This mode is optimized for production stability, ensuring reproducible fixes and transparent model usage tracking.

## 🎛 Deterministic Mode Configuration

To ensure zero non-deterministic drift, the system is hardcoded with the following constraints:

| Component | Setting | Reason |
|DIFFERENT|---|---|
| **Model** | `gemini-1.5-flash` | **Recommended**. 1M tokens/min free limit. Rock solid stability. |
| **Provider** | `gemini` | Supports `google-generativeai` SDK. |

## 🚀 How to Run

### 1. Configure Environment (Best Practice)
Use Gemini Flash for high-volume demos:

```bash
# .env
GEMINI_API_KEY=AIza...
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-1.5-flash
```

Or use Groq (Low Volume):
```bash
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.1-8b-instant
```

### 2. Execute Pipeline
Run the agent on your target repository:

```bash
python main.py \
    --repo-path /path/to/repo \
    --repo-url  https://github.com/org/repo \
    --run-id    prod-deploy-v1 \
    --branch    main
```

The system will automatically:
1.  Detect failures (Syntax, Runtime, Logic).
2.  Attempt fixes using the **Primary Model** (`8b-instant`).
3.  If rate limits are hit, auto-switch to **Fallback Engine**.
4.  Validate fixes deterministically.

## 📊 Verifying Determinism (results.json)

Check the output `results.json` for the `llm_usage` block to confirm the execution strategy:

```json
{
  "llm_usage": {
    "primary_model": "llama-3.1-8b-instant",
    "fallback_model": "static-analysis-engine",
    "fallback_triggered": false   // true if rate limit was hit
  },
  "scoring": {
    "computation_method": "deterministic",
    "total_score": 100.0
  }
}
```

## 🛡 Safety Mechanisms
*   **Syntax Masking Protection**: Validates syntax fixes even if they reveal new logic bugs (progress > perfection).
*   **Atomic file writes**: `ValidationAgent` writes to `.tmp` first, then moves.
*   **Strict JSON Contract**: `ResultsWriter` enforces exact schema matching.
