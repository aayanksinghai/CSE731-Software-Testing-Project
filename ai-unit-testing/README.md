# AI-Assisted Unit Testing — CSE731 Mini Project

> **IIIT Bangalore · CSE731 Software Testing · Mid-term Project (2026-27)**

## Overview

This repository implements a **first-principles agentic AI pipeline** for
coverage-guided unit test generation. It deliberately does **not** use RAG,
vector databases, LangGraph, CrewAI, AutoGen, or chain-of-thought frameworks,
in compliance with the course brief.

---

## Architecture

```
HumanEval / MBPP
       |
       v
+-------------------------+
| Code Generator Agent    |  ← Agent 1 (LLM call)
+----------+--------------+
           |
     Generated Code
           |
           v
+-------------------------+
| Test Case Generator     |  ← Agent 2 (LLM call, repeated on feedback)
| Agent                   |
| Goal: decision_coverage |
+----------+--------------+
           |
     Generated Tests
           |
           v
+-------------------------+
| Test Case Executor      |  ← Agent 3 (deterministic subprocess)
| Agent / Execution Layer |
+----------+--------------+
           |
  Test + Coverage Results
           |
           v
+-------------------------+
| Coverage Evaluator      |  ← Pure Python logic
+----------+--------------+
           |
     Target achieved?
          / \
        YES  NO
         |    |
       PASS  Feedback Loop (bounded, max 3 iter)
                  |
                  +----> Test Generator (Agent 2)
```

**Data flow:**
```
Dataset Problem → Code Generator → Generated Code
→ Test Generator → Generated Tests
→ Test Executor → Actual Coverage
→ Coverage Evaluator → PASS / FAIL / TARGET_NOT_MET
```

---

## Possible Verdicts

| Verdict | Meaning |
|---|---|
| `PASS` | Tests run cleanly, target branch coverage achieved |
| `TARGET_NOT_MET` | Tests ran but coverage < target |
| `TEST_FAILURE` | One or more generated tests failed |
| `CODE_GENERATION_FAILURE` | Generated implementation has syntax errors |
| `TEST_GENERATION_FAILURE` | Generated tests have syntax errors |
| `EXECUTION_ERROR` | Timeout, subprocess crash, or errors in test collection |
| `COVERAGE_UNSUPPORTED` | Branch coverage could not be measured |

---

## Prerequisites

- **Python 3.11+**
- **Git**
- Internet access (for dataset download and LLM API)
- API key for an OpenAI-compatible provider (e.g. [OpenRouter](https://openrouter.ai))

---

## Setup

### 1. Clone / enter the project

```powershell
cd "ai-unit-testing"
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On Linux/macOS:
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000
```

> **Free tokens:** [OpenRouter.ai](https://openrouter.ai) offers free-tier models.
> **Never** commit `.env` or a real API key.

### 5. Download the benchmark dataset

```bash
python main.py setup
```

This downloads MBPP (or HumanEval if configured) from HuggingFace and caches
it locally so subsequent runs are offline-capable.

---

## Quick Start

### Smoke test (no API key needed)

Verifies the pipeline infrastructure locally without any LLM calls:

```bash
python main.py smoke-test
```

Checks: configuration loading, dataset normalization, response validation,
subprocess execution, timeout handling, coverage measurement, verdict
calculation, and output directory creation.

### List available problems

```bash
python main.py list-problems
```

Shows problems with meaningful control flow (recommended for experiments).
Use `--all` to see every problem in the dataset.

### Mock dry-run on one problem

```bash
python main.py run-one --problem-id mbpp_11 --mock
```

> ⚠ Mock mode is for pipeline testing only. Do **not** present mock results
> as an AI experiment.

---

## Running with a Real API Key

### Run one problem

```bash
python main.py run-one --problem-id mbpp_11
```

Pipeline steps:
1. Load the benchmark problem from the dataset.
2. Send to **Code Generator Agent** → get executable Python implementation.
3. Validate syntax.
4. Send code + testing goal to **Test Generator Agent** → get pytest tests.
5. Validate tests.
6. Run tests in **isolated subprocess** via **Test Executor Agent**.
7. Measure actual branch/decision coverage with `coverage.py`.
8. Calculate verdict.
9. If `TARGET_NOT_MET`: send coverage feedback back to Agent 2 (up to 3 iterations).
10. Save all artifacts to `outputs/mbpp_11/`.

### Run the full curated experiment

```bash
python main.py run-experiment
```

Processes the 20 curated problems in `config/selected_problems.json`.
Saves per-problem results and an aggregate `experiment_summary.json`.

---

## Output Structure

```
outputs/
├── <problem-id>/
│   ├── generated_code.py       ← AI-generated implementation
│   ├── generated_tests.py      ← AI-generated pytest suite (best run)
│   ├── execution.log           ← stdout/stderr from test run
│   ├── coverage.json           ← coverage.py JSON report
│   ├── htmlcov/                ← HTML coverage report
│   ├── result.json             ← Final verdict + all metrics
│   ├── run_1/                  ← Iteration 1 artifacts
│   ├── run_2/                  ← Iteration 2 artifacts (if feedback loop ran)
│   └── run_3/                  ← Iteration 3 artifacts (if needed)
└── experiment_summary.json     ← Aggregate experiment metrics
```

### Example `result.json`

```json
{
  "problem_id": "mbpp_11",
  "dataset": "MBPP",
  "testing_goal": "decision_coverage",
  "target_coverage": 100.0,
  "iterations": 2,
  "tests_generated": 6,
  "tests_passed": 6,
  "tests_failed": 0,
  "branch_coverage": 100.0,
  "total_branches": 8,
  "covered_branches": 8,
  "missing_branches": [],
  "verdict": "PASS",
  "model": "openai/gpt-4o-mini",
  "temperature": 0.2,
  "max_tokens": 4000,
  "timestamp": "2026-10-01T00:00:00+00:00"
}
```

---

## Project's Own Tests

The `tests/` directory contains unit tests for the **project components**
(not for generated benchmark code). These are completely separate from the
generated tests.

```bash
pytest tests/ -v
```

Covers:
- Data model schemas
- Dataset normalisation and control-flow heuristic
- LLM response JSON extraction and malformed-input handling
- Code validation (syntax checking)
- Coverage JSON parsing
- Verdict calculation logic (all 7 verdict types)
- Timeout handling
- Feedback message construction

---

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | *(required)* | API key for the LLM provider |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | `openai/gpt-4o-mini` | Model identifier |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `LLM_MAX_TOKENS` | `4000` | Max tokens per LLM call |
| `TESTING_GOAL` | `decision_coverage` | Testing criterion |
| `TARGET_COVERAGE` | `100.0` | Required branch coverage % |
| `MAX_FEEDBACK_ITERATIONS` | `3` | Max feedback loop iterations |
| `SUBPROCESS_TIMEOUT_S` | `30` | Subprocess timeout in seconds |
| `DATASET_NAME` | `MBPP` | `MBPP` or `HumanEval` |
| `RANDOM_SEED` | `42` | Determinism seed |

All variables can also be set in `config/config.yaml` (env vars take priority).

---

## Agent Details

### Agent 1 — Code Generator

| | |
|---|---|
| **Input** | Problem description, function name |
| **Output** | Executable Python function (JSON-wrapped) |
| **Prompt** | `prompts/code_generator.txt` |
| **Validation** | `ast.parse()` syntax check before passing downstream |
| **LLM calls** | 1 per problem |

### Agent 2 — Test Case Generator

| | |
|---|---|
| **Input** | Generated code, testing goal, optional coverage feedback |
| **Output** | pytest test suite + coverage metadata (JSON) |
| **Prompt** | `prompts/test_generator.txt` |
| **Validation** | `ast.parse()` syntax check |
| **LLM calls** | 1–3 per problem (feedback loop) |
| **Note** | LLM's claimed coverage is advisory only — never used for verdict |

### Agent 3 — Test Case Executor

| | |
|---|---|
| **Input** | Generated code + tests |
| **Process** | Subprocess: `coverage run --branch -m pytest` → `coverage json` |
| **Output** | `ExecutionResult` (pass/fail counts, branch coverage, missing branches) |
| **LLM calls** | **None** — fully deterministic |
| **Note** | Verdict is always based on measured results |

---

## Safety

Generated code is **never** executed inside the main Python process.

The executor uses:
- `subprocess.run()` with a configurable timeout
- Isolated working directory per run
- Captured stdout/stderr
- Stripped sensitive environment variables

---

## Troubleshooting

### API errors
Check `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in your `.env`.
Verify the provider supports the OpenAI chat-completion format.

### Dataset not found
Run `python main.py setup` first.
If the network is unavailable, place `datasets/mbpp_data.json` manually
(see the MBPP HuggingFace page for the raw JSON format).

### Generated code has syntax errors
The pipeline records a `CODE_GENERATION_FAILURE` verdict. Try a more capable model
or increase `LLM_MAX_TOKENS`.

### Coverage shows 0% or `COVERAGE_UNSUPPORTED`
Ensure `coverage` is installed (`pip install coverage`) and that the test file
actually calls the function under test.

### Subprocess timeout
Increase `SUBPROCESS_TIMEOUT_S` in `.env` or `config/config.yaml`.

---

## Reproducibility

Every `result.json` records:
- Dataset and problem ID
- Model, provider URL, temperature, max tokens
- Maximum feedback iterations
- Coverage target
- Timestamp
- Generated code and tests
- Execution and coverage results
- Final verdict

API keys are never stored in result files.

---

## What This Project Does NOT Include

As required by the course brief:
- ❌ RAG / vector databases / retrieval
- ❌ LangGraph
- ❌ CrewAI
- ❌ AutoGen
- ❌ Chain-of-thought frameworks
- ❌ Report / presentation generation

Orchestration is implemented from first principles using plain Python
modules, classes, functions, and explicit control flow.
