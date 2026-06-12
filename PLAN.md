# Plan: Banking Sentinel with Strands Agents + Langfuse Evaluations

## Context

Replicate the Spring Boot AI banking sentinel project (`/Users/roger/Projects/fastzink/rogervinas/spring-boot-ai-langfuse-evaluations`) as a Python project using **Strands Agents** (AWS) with two evaluation approaches:

1. **Native (Strands Evals SDK)** — `Case`, `Experiment`, built-in evaluators (`OutputEvaluator`, deterministic), `run_evaluations()` → local reports
2. **Langfuse delegated** — same scenarios as a Langfuse dataset, `run_experiment()` with inline evaluators → scores in dashboard

The key demonstration: the **same evaluation scenarios** run natively via Strands Evals (local, no infrastructure) and delegated to Langfuse (persisted, visual, collaborative).

---

## Implementation Steps (in order)

### Step 1: Project scaffolding

Create `pyproject.toml` with:
- `strands-agents[ollama,gemini,otel]` — Strands SDK + Ollama & Gemini providers + OpenTelemetry (Bedrock is built-in)
- `strands-agents-tools` — tool utilities
- `strands-agents-evals` — Strands Evals SDK (native evaluators)
- `langfuse` — Python SDK for datasets/experiments/tracing
- `fastapi` + `uvicorn` — chat API + static file serving
- `pydantic>=2.0` — structured output

Also create `.gitignore`, `.env.example`.

**Structure:**
```
src/banking_sentinel/
├── __init__.py
├── agent.py
├── api.py                      # FastAPI app (chat endpoint + static)
├── data.py
├── knowledge_base.py
├── models.py
└── tools.py
static/
└── chat.html                   # Chat UI (migrated from Spring Boot)
evals/
├── __init__.py
├── strands/                    # Approach 1: Native Strands Evals
│   ├── __init__.py
│   └── run_evaluations.py
└── langfuse/                   # Approach 2: Langfuse delegated
    ├── __init__.py
    ├── create_dataset.py
    └── run_experiment.py
scripts/
└── create-dataset.sh
docker-compose.yml
README.md
```

### Step 2: Docker Compose (Langfuse stack)

Copy `docker-compose-langfuse.yml` from the reference project. Pre-provisioned with:
- Org: `rogervinas-bank`, Project: `banking-sentinel`
- Keys: `publickey-local` / `secretkey-local`
- Admin: `admin@local.dev` / `password`
- UI: http://localhost:3000

### Step 3: `src/banking_sentinel/models.py` — Pydantic models

```python
from enum import Enum
from pydantic import BaseModel, Field

class SuggestedAction(str, Enum):
    FREEZE_CARD = "FREEZE_CARD"
    UNFREEZE_CARD = "UNFREEZE_CARD"
    OPEN_DISPUTE = "OPEN_DISPUTE"
    CHECK_DISPUTE_STATUS = "CHECK_DISPUTE_STATUS"
    GET_TRANSACTIONS = "GET_TRANSACTIONS"

class ChatResponse(BaseModel):
    answer: str = Field(description="The response to the user")
    suggested_actions: list[SuggestedAction] = Field(description="Suggested next actions")
```

### Step 4: `src/banking_sentinel/data.py` — Mock data

- `Transaction` dataclass with id, date, amount, merchant, category
- `Dispute` dataclass with id, account_id, transaction_id, reason, status
- `build_transactions(reference_date)` — returns dict of account_id -> list[Transaction]
  - ACC-1001: Netflix $9.99 at `ref_date - 6 days` (within 14-day window)
  - ACC-1002: Best Buy $200.00 at `ref_date - 28 days` (outside window)
  - ACC-1003: Unknown Merchant $42.00 at `ref_date - 17 days`
- `CardState` class: freeze/unfreeze/is_frozen (backed by a set)
- `DisputeStore` class: open_dispute/get_status/list_disputes (backed by dict)

### Step 5: `src/banking_sentinel/knowledge_base.py` — Policy documents

Single `KNOWLEDGE_BASE` string with the 8 policy docs (Ref-DISP-001 through Ref-FEE-002) embedded in system prompt instead of vector DB.

### Step 6: `src/banking_sentinel/tools.py` — 7 tools (factory pattern)

`create_tools(card_state, dispute_store, transactions, reference_date)` returns list of `@tool`-decorated functions that close over provided state:

1. `freeze_card(account_id, reason)` 
2. `unfreeze_card(account_id)`
3. `is_card_frozen(account_id)`
4. `get_transactions(account_id, date_from, date_to)`
5. `open_dispute(account_id, transaction_id, reason)`
6. `get_dispute_status(dispute_id)`
7. `list_disputes(account_id)`

Each returns a JSON string for the LLM to parse.

### Step 7: `src/banking_sentinel/agent.py` — Agent orchestration

```python
from strands import Agent
from strands.models.ollama import OllamaModel
from strands.models.gemini import GeminiModel
from strands.models import BedrockModel

def create_model(provider: str = "ollama"):
    """Create model based on MODEL_PROVIDER env var (ollama|bedrock|gemini)."""
    if provider == "ollama":
        return OllamaModel(host="http://localhost:11434", model_id="llama3.1:8b")
    elif provider == "bedrock":
        return BedrockModel(model_id="anthropic.claude-sonnet-4-20250514-v1:0")
    elif provider == "gemini":
        return GeminiModel(model_id="gemini-2.5-flash")

def create_sentinel_agent(model, tools, user_tier, account_id, reference_date) -> Agent:
    """Creates agent with formatted system prompt including knowledge base + context."""
    return Agent(model=model, tools=tools, system_prompt=system_prompt)

def chat(agent, message) -> ChatResponse:
    """Invokes agent and returns structured response."""
    result = agent(message, structured_output_model=ChatResponse)
    return result.structured_output
```

Model provider is selected via `MODEL_PROVIDER` env var (defaults to `ollama`):
- **ollama**: `OllamaModel(host, model_id)` — local dev, needs `ollama serve`
- **bedrock**: `BedrockModel(model_id)` — needs AWS credentials
- **gemini**: `GeminiModel(model_id)` — needs `GOOGLE_API_KEY` env var

System prompt mirrors the Spring Boot version: mission, operational protocols, context variables (user_tier, current_date, account_id), and knowledge base documents inline.

### Step 7b: Chat UI (FastAPI + static HTML)

Strands is a pure SDK (no web server). Add a lightweight FastAPI layer:

**`src/banking_sentinel/api.py`**:
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from banking_sentinel.agent import create_model, create_sentinel_agent, chat

app = FastAPI()

@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    model = create_model()
    agent = create_sentinel_agent(model, tools, request.user_tier, request.account_id, reference_date)
    return chat(agent, request.message)

app.mount("/", StaticFiles(directory="static", html=True))
```

**`static/chat.html`**: Migrate from Spring Boot project — simple HTML/JS chat interface calling `/chat`.

Run with: `uvicorn banking_sentinel.api:app`

### Step 7c: Langfuse prompt management (optional enhancement)

Store the system prompt in Langfuse instead of hardcoding it:

```python
from langfuse import get_client

langfuse = get_client()

# Create versioned prompt (once, or in setup script)
langfuse.create_prompt(
    name="banking-sentinel-system",
    type="text",
    prompt="You are the Sentinel... User Tier: {{user_tier}}, Date: {{current_date}}, Account: {{account_id}}...",
    labels=["production"]
)

# Fetch at runtime
prompt = langfuse.get_prompt("banking-sentinel-system")
compiled = prompt.compile(user_tier="Standard", current_date="2025-04-15", account_id="ACC-1001")
agent = Agent(model=model, tools=tools, system_prompt=compiled)
```

Benefits:
- Version the system prompt independently of code
- Track which prompt version was used in each experiment run
- Iterate on prompt wording without redeploying
- A/B test different prompt versions via Langfuse experiments

See: https://langfuse.com/docs/prompt-management/get-started

### Step 7c: Langfuse tracing (via OpenTelemetry)

Tracing is automatic — just set env vars and install the `otel` extra:

```bash
export LANGFUSE_PUBLIC_KEY=publickey-local
export LANGFUSE_SECRET_KEY=secretkey-local
export LANGFUSE_BASE_URL=http://localhost:3000
```

No code changes needed in the agent. All LLM calls, tool usage, inputs, outputs, latencies and costs flow to Langfuse automatically. Same pattern as Spring Boot AI (OTel-based).

Optionally use Langfuse SDK decorators to add `user_id`, `session_id`, `metadata` to spans.

### Step 8: `evals/strands/run_evaluations.py` — Approach 1: Native Strands Evals

Uses Strands Evals SDK with `Case`, `Experiment`, and built-in evaluators:

```python
from strands_evals import Case, Experiment
from strands_evals.evaluators import OutputEvaluator

# Define test cases (same scenarios as Langfuse dataset)
cases = [
    Case(
        name="unauthorized-netflix-charge",
        input={"userId": "user-1001", "accountId": "ACC-1001", "accountTier": "Standard",
               "message": "I don't have Netflix but I see a charge on my account"},
        expected_output={"suggestedActions": ["FREEZE_CARD"],
                        "claim": "The AI agent found a Netflix charge of 9.99 and offered the user to open a dispute"},
    ),
    Case(
        name="expired-dispute-window",
        input={"userId": "user-1002", "accountId": "ACC-1002", "accountTier": "Standard",
               "message": "I see a Best Buy charge on my account but I never bought anything there"},
        expected_output={"suggestedActions": ["FREEZE_CARD"],
                        "claim": "The AI agent found a Best Buy charge of 200.00 and explained that the dispute window has expired because the transaction is older than 14 days"},
    ),
]

# Evaluators
correctness_evaluator = OutputEvaluator(rubric="""
Score 1.0 if the suggested actions contain all expected actions.
Score 0.0 if any expected action is missing.
""")

claim_evaluator = OutputEvaluator(rubric="""
Score 1.0 if the agent's answer matches the claim.
Score 0.0 if the answer does not match.
""")

# Task function: invokes the banking sentinel agent
def task(case: Case) -> str:
    response = chat(...)  # invoke agent with case.input
    return response.answer

# Run
experiment = Experiment(cases=cases, evaluators=[correctness_evaluator, claim_evaluator])
reports = experiment.run_evaluations(task)
```

Run with: `python -m evals.strands.run_evaluations`

### Step 9: `evals/langfuse/create_dataset.py` — Approach 2: Langfuse dataset creation

Creates "banking-sentinel-evals" dataset in Langfuse with the same 2 scenarios.
Must be **idempotent** — skips if dataset/items already exist (safe to re-run in CI).

```python
from langfuse import Langfuse

langfuse = Langfuse()
langfuse.create_dataset(name="banking-sentinel-evals")
langfuse.create_dataset_item(
    dataset_name="banking-sentinel-evals",
    input={"userId": "user-1001", "accountId": "ACC-1001", ...},
    expected_output={"suggestedActions": ["FREEZE_CARD"], "claim": "..."},
)
```

**How to trigger in CI (decide later):**
- **Option A**: Standalone script as a CI step before `run_experiment.py` — explicit, visible in pipeline
- **Option B**: Called from within `run_experiment.py` itself (ensure dataset before running) — single command
- **Option C**: pytest autouse session fixture if we wrap Langfuse evals in pytest — transparent, no extra step

Run with: `python -m evals.langfuse.create_dataset`

### Step 10: `evals/langfuse/run_experiment.py` — Approach 2: Langfuse experiment runner

Same evaluation logic, delegated to Langfuse `run_experiment()`:

```python
from langfuse import Langfuse

langfuse = Langfuse()
dataset = langfuse.get_dataset("banking-sentinel-evals")

def task(*, item, **kwargs):
    response = chat(...)  # invoke agent with item.input
    return {"answer": response.answer, "suggested_actions": response.suggested_actions}

def correctness_evaluator(*, output, expected_output, **kwargs):
    expected = set(expected_output["suggestedActions"])
    actual = set(output.get("suggested_actions", []))
    score = len(expected & actual) / len(expected) if expected else 1.0
    return {"name": "correctness", "value": score}

def claim_evaluator(*, output, expected_output, **kwargs):
    # LLM-as-judge using a Strands agent
    result = llm_judge(answer=output["answer"], claim=expected_output["claim"])
    return {"name": "claim_match", "value": 1.0 if result else 0.0}

result = dataset.run_experiment(
    name="baseline-v1",
    task=task,
    evaluators=[correctness_evaluator, claim_evaluator]
)
```

Run with: `python -m evals.langfuse.run_experiment`
Fails with exit code 1 if any score < 0.8 (CI gate).

### Step 13: `scripts/create-dataset.sh` — Bash alternative

curl-based dataset creation via Langfuse REST API (same as reference project).

### Step 14: `README.md`

Setup instructions, running the agent, running evaluations (both approaches).

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Knowledge base in system prompt | 8 small docs; avoids PGVector/RAG dependency |
| Factory pattern for tools | Per-test state isolation (fresh mutable state) |
| Fixed reference_date (2025-04-15) | Deterministic date reasoning for evaluations |
| Three providers (ollama/bedrock/gemini) | Matches Spring Boot project; env var switch |
| Ollama as default provider | Local dev, no cloud credentials needed |
| Same scenarios in both eval approaches | Core demonstration point of the project |
| Structured output via Pydantic | Native Strands feature; enables programmatic assertions |

---

## Critical Files

- **Copy from reference**: `/Users/roger/Projects/fastzink/rogervinas/spring-boot-ai-langfuse-evaluations/docker-compose-langfuse.yml`
- **Core agent**: `src/banking_sentinel/agent.py`
- **Tools**: `src/banking_sentinel/tools.py`
- **Strands Evals (native)**: `evals/strands/run_evaluations.py`
- **Langfuse evals (delegated)**: `evals/langfuse/run_experiment.py`

---

## Verification

1. `docker compose up -d` — Langfuse at http://localhost:3000
2. `ollama serve` + `ollama pull llama3.1:8b` — local LLM
3. `python -m evals.strands.run_evaluations` — native Strands Evals pass
4. `python -m evals.langfuse.create_dataset` — dataset visible in Langfuse UI
5. `python -m evals.langfuse.run_experiment` — experiment scores in Langfuse dashboard

---

## CI Integration

Both evaluation approaches are CI-friendly (synchronous, exit code based):

**Strands Evals in CI:**
```python
reports = experiment.run_evaluations(task)
for report in reports:
    for case_result in report.case_results:
        assert case_result.evaluation_output.test_pass, f"Failed: {case_result.case.name}"
```

**Langfuse `run_experiment()` in CI:**
```python
result = dataset.run_experiment(name="ci-check", task=task, evaluators=[...])
# Scores returned synchronously — fail CI if below threshold
```

**Langfuse GitHub Action** (`langfuse/experiment-action`):
- Runs experiments on every PR
- Posts score summary as a PR comment
- Fails the check if scores drop below threshold
- See: https://langfuse.com/docs/scores/external-evaluation/github-actions

---

## Strands Agents Documentation

- **Quickstart**: https://strandsagents.com/docs/user-guide/quickstart/python/
- **Tools (custom @tool)**: https://strandsagents.com/docs/user-guide/concepts/tools/
- **Structured output**: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/
- **Model providers (overview)**: https://strandsagents.com/docs/user-guide/concepts/model-providers/
- **Ollama provider**: https://strandsagents.com/docs/user-guide/concepts/model-providers/ollama/
- **Gemini provider**: https://strandsagents.com/docs/user-guide/concepts/model-providers/google/
- **Langfuse integration (OTel)**: https://langfuse.com/integrations/frameworks/strands-agents
- **Langfuse prompt management**: https://langfuse.com/docs/prompt-management/get-started
- **Evals SDK quickstart**: https://strandsagents.com/docs/user-guide/evals-sdk/quickstart/
- **Evals SDK evaluators**: https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/
- **Evals SDK trace providers (Langfuse, CloudWatch, OpenSearch)**: https://strandsagents.com/docs/user-guide/evals-sdk/how-to/trace_providers/
- **GitHub (Python SDK)**: https://github.com/strands-agents/sdk-python

---

## Strands Evals SDK vs Langfuse Evaluations

| Aspect | Strands Evals SDK | Langfuse `run_experiment()` |
|--------|-------------------|----------------------------|
| Install | `strands-agents-evals` | `langfuse` |
| Concept | `Case` → `Experiment` → `run_evaluations()` | Dataset → `run_experiment()` |
| Built-in judges | `OutputEvaluator`, `CorrectnessEvaluator`, `TrajectoryEvaluator`, `HelpfulnessEvaluator`, deterministic (`Equals`, `Contains`, `ToolCalled`) | None (you write evaluator functions) |
| Judge model | Bedrock Claude (default) | Bring your own (any LLM) |
| Results | Local reports (score, pass/fail, reason) | Scores persisted in Langfuse dashboard |
| Dashboard | None (CLI/code only) | Full UI: trends, A/B comparison, drill-down |
| Production monitoring | No | Yes (async LLM-as-judge on live traces) |
| CI gate | `assert result.test_pass` | `assert score >= threshold` |
| Collaboration | JSON files, version control | Datasets + experiments in shared UI |

**What we demonstrate in THIS project:**
1. **Tracing** — agent execution flows to Langfuse via OTel (automatic)
2. **Strands Evals (native)** — `Case`/`Experiment`/`OutputEvaluator`, local reports, CI gate
3. **Langfuse experiments (delegated)** — same scenarios via `run_experiment()`, scores in dashboard, CI gate via GitHub Action

**What a separate Strands Evals PoC would cover:**
- `Case`/`Experiment` abstractions for test organization
- Built-in evaluators (no custom code needed for common checks)
- `TrajectoryEvaluator` for verifying tool call sequences
- `@eval_task` decorator for cleaner test code
- `LangfuseProvider` — pull traces FROM Langfuse, evaluate with Strands built-in judges:
  ```python
  from strands_evals.providers import LangfuseProvider
  provider = LangfuseProvider()  # uses LANGFUSE_* env vars
  data = provider.get_evaluation_data(session_id="my-session-id")
  # Then evaluate with CoherenceEvaluator, OutputEvaluator, etc.
  ```

**The bridge**: Agent → OTel → Langfuse (tracing) → Strands Evals `LangfuseProvider` (evaluation).
See: https://strandsagents.com/docs/user-guide/evals-sdk/how-to/trace_providers/