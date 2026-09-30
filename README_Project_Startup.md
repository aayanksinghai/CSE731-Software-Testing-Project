# AI-Assisted Unit Testing — CSE731 Mini Project

## Project Objective

This project implements an agentic AI pipeline for coverage-guided unit testing. A benchmark programming problem is passed to a **Code Generator Agent**, the generated implementation is passed to a **Test Case Generator Agent** together with a user-specified **decision/branch coverage** goal, and the generated tests are executed by a **Test Case Executor Agent**. Actual coverage is measured independently of the LLM's claims, and the pipeline produces an objective verdict.

The project is intentionally implemented from first principles. It does **not** use RAG, vector databases, LangGraph, CrewAI, AutoGen, or chain-of-thought frameworks.

## Architecture

```text
HumanEval / MBPP
       |
       v
+----------------------+
| Code Generator Agent |
+----------+-----------+
           |
           v
     Generated Code
           |
           v
+--------------------------+
| Test Case Generator     |
| Agent                   |
| Goal: Decision Coverage |
+------------+-------------+
             |
             v
       Generated Tests
             |
             v
+--------------------------+
| Test Case Executor      |
| Agent / Execution Layer |
+------------+-------------+
             |
             v
   Test + Coverage Results
             |
             v
+--------------------------+
| Coverage Evaluator      |
+------------+-------------+
             |
       Target achieved?
          /       \
        YES        NO
         |          |
       PASS    Feedback Loop
                    |
                    +----> Test Generator
```

The pipeline supports a bounded feedback loop. If the generated tests do not reach the required coverage target, the measured coverage information is returned to the Test Case Generator for another attempt, up to a configurable maximum number of iterations.

## Benchmark Data

The project supports:

- **HumanEval**
- **MBPP**

The initial experiment should use a curated subset rather than arbitrary trivial examples. Prefer problems containing meaningful control flow:

- multiple `if`/`elif` decisions
- true and false branches
- early returns
- loops with meaningful conditions
- nested conditions
- boundary conditions
- multiple logical execution paths

Avoid using only toy examples such as simple addition, basic maximum-of-two, or straightforward string concatenation.

A deterministic selection file should be used so that the experiment can be reproduced.

## Testing Goal

The selected testing criterion is:

> **Decision / branch coverage**

The target should be configurable. A typical experiment can use:

```text
100% measurable branch coverage
```

The LLM is not trusted to determine whether the goal was achieved. The system executes the generated tests and calculates actual coverage using the configured coverage tool.

A result is successful only when:

1. The generated implementation is syntactically valid.
2. The generated tests are syntactically valid.
3. The tests execute successfully.
4. The requested coverage criterion can be measured.
5. The measured coverage reaches the configured target.

Possible final verdicts include:

```text
PASS
TARGET_NOT_MET
TEST_FAILURE
CODE_GENERATION_FAILURE
TEST_GENERATION_FAILURE
EXECUTION_ERROR
COVERAGE_UNSUPPORTED
```

## Project Structure

Recommended structure:

```text
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

The exact structure may differ if the implementation remains modular and the README stays consistent with the code.

## Prerequisites

Recommended:

- Python 3.11+
- Git
- Internet access for the selected LLM provider and benchmark dataset
- An API key for an OpenAI-compatible provider

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Linux/macOS:

```bash
source .venv/bin/activate
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Copy the environment template:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Set the required provider configuration in `.env`.

Example:

```text
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://your-openai-compatible-provider.example/v1
LLM_MODEL=your-coding-model
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000
```

Never commit `.env` or a real API key.

The model/provider should remain configurable rather than hard-coded.

## Dataset Preparation

The implementation should provide adapters for HumanEval and MBPP.

The dataset layer should normalize both formats into a common internal representation containing at least:

```text
problem_id
prompt
canonical_solution/reference_solution (when available)
entry_point/function_name
dataset_name
```

Use the repository's dataset setup command if provided:

```bash
python main.py setup
```

If the environment cannot download the benchmark automatically, place the downloaded dataset files in the location documented by the dataset adapter and run the selection step.

The project must never fabricate benchmark records when a real dataset is unavailable.

## Selecting Good Problems

Run:

```bash
python main.py list-problems
```

The selector should favor problems with meaningful control flow.

The final experiment should use a manageable curated subset, for example 15–25 problems.

The selection should be deterministic and stored in:

```text
config/selected_problems.json
```

## Smoke Test

Before using an API key, verify the local pipeline:

```bash
python main.py smoke-test
```

The smoke test should verify:

- configuration loading
- dataset normalization
- response/schema validation
- generated-code parsing
- generated-test parsing
- subprocess execution
- timeout handling
- coverage measurement
- verdict calculation
- output-directory creation

A mock/dry-run mode may be provided:

```bash
python main.py run-one --problem-id <ID> --mock
```

Mock mode is only for checking the pipeline infrastructure. It must not be presented as an AI experiment.

## Run One Real Problem

After configuring the API provider:

```bash
python main.py run-one --problem-id <ID>
```

The pipeline should:

1. Load the selected benchmark problem.
2. Send the problem to the Code Generator Agent.
3. Validate the generated implementation.
4. Send the implementation and testing goal to the Test Case Generator Agent.
5. Validate the generated tests.
6. Execute the tests in a controlled subprocess.
7. Measure actual branch/decision coverage.
8. Compare coverage with the target.
9. If necessary, send measured coverage feedback back to the Test Generator Agent.
10. Stop when the target is achieved or the maximum iteration count is reached.
11. Save the final result.

## Run the Curated Experiment

Run:

```bash
python main.py run-experiment
```

The experiment should process the deterministic selected-problem list.

A result should be saved for each problem, along with an aggregate experiment result.

Useful aggregate metrics include:

- number of problems attempted
- number of successful problems
- target-achievement rate
- average achieved branch coverage
- median achieved branch coverage
- average number of generated tests
- average feedback iterations
- test execution failures
- code-generation failures
- test-generation failures
- unsupported coverage cases
- average execution time

Do not report an aggregate metric unless it was actually calculated from the experiment output.

## Output

A recommended output structure is:

```text
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

The exact names can differ, but every run should retain enough information to reproduce and inspect the result.

A result should contain fields similar to:

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

The actual schema should be defined by the implementation and kept consistent throughout the project.

## Agent Responsibilities

### Code Generator Agent

Input:

```text
Benchmark problem
Function/entry-point information
```

Output:

```text
Executable Python implementation
```

The agent must not return hidden reasoning or unnecessary prose.

### Test Case Generator Agent

Input:

```text
Generated implementation
Testing goal
Previous measured coverage feedback, if retrying
```

Output:

```text
Executable pytest tests
Coverage-target metadata
```

The LLM's claimed coverage is advisory only.

### Test Case Executor Agent

The executor is primarily deterministic.

It should:

- execute generated code/tests
- enforce a timeout
- capture stdout/stderr
- collect test results
- collect branch coverage
- identify missing branches when supported
- produce a structured execution result
- calculate the final verdict

The executor must never override measured coverage based on an LLM-generated claim.

## Safety

Generated code must not be executed directly inside the main process.

Use a subprocess with:

- timeout
- isolated working directory
- controlled environment
- captured stdout/stderr

Do not add mechanisms intended to bypass operating-system protections.

This project is intended for controlled academic benchmark programs.

## Prompts

Keep agent prompts as versioned files under:

```text
prompts/
```

At minimum:

```text
prompts/code_generator.txt
prompts/test_generator.txt
```

Prompts should require structured outputs and should explicitly state:

- expected programming language
- expected function signature
- testing criterion
- output format
- restrictions
- no chain-of-thought
- no explanatory prose where executable output is expected

## Development Tests

The repository should have its own tests separate from generated benchmark tests.

Run:

```bash
pytest tests/
```

These tests should cover at least:

- dataset normalization
- configuration loading
- LLM response validation
- malformed JSON handling
- generated-code validation
- generated-test validation
- coverage parsing
- verdict calculation
- timeout handling
- retry/feedback logic

## Troubleshooting

### API errors

Check:

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

Also verify that the selected provider supports the requested API format and model.

### Generated code has syntax errors

The pipeline should record the failure and either retry according to the configured policy or mark the problem as failed. Never silently modify the generated implementation and claim it came from the model.

### Tests fail

Save the complete test failure information. A failed generated test suite should not automatically be considered a successful coverage result.

### Coverage cannot be measured

Return:

```text
COVERAGE_UNSUPPORTED
```

or the project's equivalent status. Never invent a coverage percentage.

### Timeout

Terminate the subprocess and record a timeout failure. Do not allow an individual generated program to block the entire experiment.

## Reproducibility

Record:

- dataset
- selected problem IDs
- model
- provider/base URL
- temperature
- maximum output tokens
- maximum feedback iterations
- coverage target
- timestamp
- generated code
- generated tests
- execution result
- coverage result
- final verdict

Do not store API secrets in experiment results.

## Scope

This repository currently focuses only on the working implementation of the agentic AI unit-testing pipeline.

It intentionally does **not** include:

- project report generation
- presentation/demo generation
- RAG
- vector databases
- LangGraph
- CrewAI
- AutoGen
- chain-of-thought frameworks

The implementation should remain focused on demonstrating a first-principles agentic pipeline for generating and executing unit tests against a concrete testing requirement.
