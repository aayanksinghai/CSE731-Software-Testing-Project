# CSE731 Mini Project — Comprehensive Analysis

## 1. Source Document Summary

| Document | Purpose |
|---|---|
| `AI-assisted-unit-testing-project.pdf` | Official course problem statement (IIITB, CSE731) |
| `AI_Assisted_Unit_Testing_Code_Generation_Prompt.md` | Detailed build prompt — full spec for the agentic pipeline |
| `README_Project_Startup.md` | Project startup guide — architecture, CLI, output schema, dev tests |

---

## 2. Problem Statement (from PDF)

**Course:** CSE731 Software Testing, Mid-term Project, Term I (2026-27)  
**Institute:** International Institute of Information Technology Bangalore  
**Dates:** Starts 29 Sep 2026 → Closes 1 Oct 2026; Demos on 1, 6, 8 Oct 2026  
**Team size:** 2 members

### Core Requirement
Build a simple **agentic AI pipeline** with at minimum 3 agents:
1. **Code Generator Agent** — generates unit-level code
2. **Test Case Generator Agent** — generates unit tests satisfying one requirement (coverage/property/statistical)
3. **Test Case Executor Agent** — executes tests and provides a verdict

### Testing Goal Choices (pick one)
| Option | Description |
|---|---|
| (1) Coverage criterion | Statement, loop, decision coverage, etc. |
| (2) Property-based | Expected output for given inputs (e.g., found/not-found) |
| (3) Statistical | Estimate probability that at least one suite is correct |

**Chosen approach (per prompt):** Option (1) → **Decision/Branch Coverage**

### Datasets
- **MBPP** (Most Basic Python Problems)
- **HumanEval**

### Submission Requirements
1. Agentic pipeline description (dataset + test-case generator functionality)
2. User prompts + system prompts + settings (temperature, parameters)
3. Format of generated code, test cases, and verdict + actual examples
4. Execution results of test case generator and executor agents
5. Each member's contribution

### Hard Constraints
- ❌ No RAG pipelines
- ❌ No Chain-of-Thought frameworks
- ❌ No LangGraph, CrewAI, AutoGen, or similar orchestration frameworks
- ✅ First-principles pipeline construction only

---

## 3. Build Prompt Analysis (Key Technical Requirements)

### 3.1 Pipeline Architecture

```
Dataset Problem
    → Code Generator Agent         (LLM call 1)
    → Generated Code
    → Test Case Generator Agent    (LLM call 2, optionally repeated)
    → Generated Tests
    → Test Case Executor Agent     (deterministic subprocess)
    → Test + Coverage Results
    → Coverage Evaluator
    → PASS / FAIL / TARGET_NOT_MET
           ↑
    Bounded Feedback Loop (max 2–3 iterations)
```

### 3.2 Agent Responsibilities

#### Agent 1: Code Generator Agent
- **Input:** Benchmark problem, function/entry-point info
- **Output:** Executable Python implementation (JSON-structured)
- **Constraints:** No hidden reasoning, no prose — only the implementation

#### Agent 2: Test Case Generator Agent
- **Input:** Generated code + testing goal (`decision_coverage`) + optional coverage feedback
- **Output:** Executable pytest tests + coverage-target metadata (machine-readable)
- **Constraints:** Must NOT override actual measured coverage

#### Agent 3: Test Case Executor Agent (primarily deterministic)
- **Executes** generated code & tests in **isolated subprocess** with timeout
- **Measures** actual branch/decision coverage (not LLM's claimed coverage)
- **Captures:** stdout, stderr, exit status, test pass/fail counts, tracebacks, branch coverage %, total branches, covered branches, missing branches
- **Produces:** Structured verdict

### 3.3 Verdict Types
```
PASS
TARGET_NOT_MET
TEST_FAILURE
CODE_GENERATION_FAILURE
TEST_GENERATION_FAILURE
EXECUTION_ERROR
COVERAGE_UNSUPPORTED
```

### 3.4 Bounded Feedback Loop
- If coverage target not met → send measured coverage back to Agent 2
- Configurable max iterations (2–3)
- Loop terminates on: target achieved | max iterations reached | unrecoverable failure
- **This is what makes the system truly agentic**

### 3.5 Dataset Requirements
- Support both HumanEval AND MBPP via clean adapters
- Normalize both into a **common internal representation:**
  - `problem_id`, `prompt`, `canonical_solution`, `entry_point/function_name`, `dataset_name`
- **Curated subset** of 15–25 problems (not arbitrary)
- Problems must have meaningful control flow:
  - Multiple `if`/`elif`, true/false branches
  - Early returns
  - Loops with meaningful conditions
  - Nested conditions, boundary conditions
- Deterministic selection stored in `config/selected_problems.json`
- **Never fabricate benchmark records**

### 3.6 Coverage Mechanism
- Use a Python coverage library capable of **branch measurement** (e.g., `coverage.py` with `--branch`)
- Actual coverage is measured from subprocess execution — never from LLM claims
- If branch coverage cannot be measured → mark as `COVERAGE_UNSUPPORTED`
- Configurable target (default: 100% of measurable branches)

### 3.7 Safety
- ❌ Never execute generated code directly inside the main process
- ✅ Always use subprocess with: timeout + isolated working directory + controlled environment + captured stdout/stderr

---

## 4. README / Project Structure Analysis

### 4.1 Recommended Directory Structure
```
ai-unit-testing/
├── agents/
│   ├── code_generator.py
│   ├── test_generator.py
│   └── test_executor.py
├── datasets/
│   ├── base.py
│   ├── humaneval.py
│   ├── mbpp.py
│   └── selector.py
├── execution/
│   ├── sandbox.py
│   └── runner.py
├── evaluation/
│   ├── coverage.py
│   └── verdict.py
├── models/
│   └── schemas.py
├── prompts/
│   ├── code_generator.txt
│   └── test_generator.txt
├── config/
│   ├── config.yaml
│   └── selected_problems.json
├── experiments/
├── tests/
├── outputs/
├── .env.example
├── requirements.txt
├── main.py
└── README.md
```

### 4.2 CLI Commands Required
| Command | Purpose |
|---|---|
| `python main.py setup` | Download/prepare datasets |
| `python main.py list-problems` | List curated problems with control-flow filter |
| `python main.py smoke-test` | Verify pipeline infra without API key |
| `python main.py run-one --problem-id <ID>` | Run one real problem |
| `python main.py run-one --problem-id <ID> --mock` | Dry-run / mock mode |
| `python main.py run-experiment` | Run full curated experiment |

### 4.3 Output Structure per Problem
```
outputs/
├── <problem-id>/
│   ├── generated_code.py
│   ├── generated_tests.py
│   ├── execution.log
│   ├── coverage.json
│   ├── coverage.html
│   └── result.json
└── experiment_summary.json
```

### 4.4 Result JSON Schema
```json
{
  "problem_id": "example",
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
  "verdict": "PASS"
}
```

### 4.5 Configuration (`.env`)
```
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://your-openai-compatible-provider.example/v1
LLM_MODEL=your-coding-model
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000
```

---

## 5. Dev Tests Required (Project's Own Unit Tests)
The repo must have its own `tests/` separate from generated benchmark tests, covering:
- Dataset normalization
- Configuration loading
- LLM response validation
- Malformed JSON handling
- Generated-code validation
- Generated-test validation
- Coverage parsing
- Verdict calculation
- Timeout handling
- Retry/feedback logic

---

## 6. Key Technical Decisions (From Prompt)

| Concern | Decision |
|---|---|
| Coverage type | Decision/Branch coverage |
| Coverage tool | Python `coverage.py` with `--branch` flag |
| Test framework | pytest |
| LLM provider | OpenRouter or any OpenAI-compatible endpoint |
| LLM output format | Structured JSON — validated before passing to next stage |
| Orchestration | Pure Python — no frameworks |
| Problem selection | Curated 15–25 problems, deterministic, stored in config |
| Code execution | Subprocess only, with timeout + isolation |
| Feedback loop | Bounded, max 2–3 iterations, configurable |
| Prompts | Stored as versioned `.txt` files in `prompts/` |
| Credentials | Via `.env` / environment variables only |

---

## 7. What Needs to Be Built

### Files to Create (Minimum)
1. `main.py` — CLI entry point
2. `agents/code_generator.py` — Agent 1
3. `agents/test_generator.py` — Agent 2
4. `agents/test_executor.py` — Agent 3
5. `datasets/base.py` — Abstract dataset adapter
6. `datasets/humaneval.py` — HumanEval adapter
7. `datasets/mbpp.py` — MBPP adapter
8. `datasets/selector.py` — Curated problem selector
9. `execution/sandbox.py` — Subprocess execution isolation
10. `execution/runner.py` — Test runner orchestration
11. `evaluation/coverage.py` — Coverage result parsing
12. `evaluation/verdict.py` — Verdict calculation logic
13. `models/schemas.py` — Internal data models (Pydantic or dataclasses)
14. `prompts/code_generator.txt` — Code generator system prompt
15. `prompts/test_generator.txt` — Test generator system prompt
16. `config/config.yaml` — Model/provider config
17. `config/selected_problems.json` — Curated problem IDs
18. `tests/` — Project's own unit tests
19. `.env.example` — Env template (no real key)
20. `requirements.txt` — Dependencies
21. `README.md` — Full project documentation

---

## 8. Compliance Checklist

| Requirement | Status |
|---|---|
| 3 distinct agents with I/O contracts | Must implement |
| No RAG/LangGraph/CrewAI/AutoGen | Must avoid |
| No CoT frameworks | Must avoid |
| LLM via configurable API (env vars) | Must implement |
| Structured JSON from LLM | Must implement |
| HumanEval + MBPP adapters | Must implement |
| 15–25 curated problems | Must implement |
| Decision/branch coverage | Must implement |
| Actual coverage measurement (not LLM's claim) | Must implement |
| Bounded feedback loop | Must implement |
| Subprocess execution with timeout | Must implement |
| Per-problem output files | Must implement |
| CLI commands (setup, list, run-one, run-experiment) | Must implement |
| Smoke test / mock mode | Must implement |
| Project's own unit tests | Must implement |
| `.env.example` | Must implement |
| `requirements.txt` | Must implement |
| `README.md` | Must implement |
| Prompts as versioned files | Must implement |
| Deterministic problem selection | Must implement |

---

## 9. Recommended Python Dependencies

```
openai          # OpenAI-compatible client
coverage        # Branch coverage measurement
pytest          # Test execution framework
pytest-json-report  # Structured test results
pydantic        # Data model validation
python-dotenv   # .env loading
datasets        # HuggingFace datasets (for HumanEval/MBPP)
pyyaml          # Config file parsing
click           # CLI framework
```
