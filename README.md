[![CI](https://github.com/rogervinas/strands-agents-langfuse-evaluations/actions/workflows/ci.yml/badge.svg)](https://github.com/rogervinas/strands-agents-langfuse-evaluations/actions/workflows/ci.yml)
![StrandsAgents](https://img.shields.io/badge/StrandsAgents-1.42.0-blue?labelColor=black)

![Gemini](https://img.shields.io/badge/Gemini-✓-4285F4?labelColor=black)
![Bedrock](https://img.shields.io/badge/Bedrock-✓-FF9900?labelColor=black)
![Ollama](https://img.shields.io/badge/Ollama-✓-FFFFFF?labelColor=black)

# Strands Agents + Langfuse Evaluations

In this project we will build a Python banking assistant agent using [Strands Agents](https://strandsagents.com) (AWS) and connect it to [Langfuse](https://langfuse.com) for tracing, evaluations, prompt management, and human feedback — step by step.

LLM applications are **non-deterministic**: the same input may yield different outputs on each run. Traditional unit tests can verify tool contracts but cannot validate model reasoning or output quality. To operate these systems reliably you need two things: **traces** (a recorded tree of every LLM call, tool call, and sub-agent step — inputs, outputs, duration, cost) and **evaluations** (a repeatable way to measure quality — offline in CI and online against real traffic). Several platforms provide these capabilities — this project uses **Langfuse** because it is open-source and self-hostable with a single `docker compose up`:

| Provider | Self-host | Tracing | Evals | Prompt Mgmt | Best for |
|---|---|---|---|---|---|
| **[Langfuse](https://langfuse.com/docs)** | ✅ | ✅ | ✅ | ✅ | POCs, full control, any stack |
| **[Arize Phoenix](https://docs.arize.com/phoenix)** | ✅ | ✅ | ✅ | ✗ | Open-source, strong eval focus |
| **[MLflow](https://mlflow.org/docs/latest/llms/tracing/index.html)** | ✅ | ✅ | Limited | ✅ | Teams already using MLflow |
| **[LangSmith](https://docs.smith.langchain.com/)** | ✗ | ✅ | ✅ | ✅ | Teams already on LangChain |
| **[W&B Weave](https://weave-docs.wandb.ai/)** | ✗ | ✅ | ✅ | ✗ | Teams already using W&B |
| **[Datadog](https://docs.datadoghq.com/llm_observability/evaluations/)** | ✗ | ✅ | ✅ | ✗ | Observability-first teams |
| **[AWS AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)** | ✗ | Limited | ✅ | ✗ | AWS-native teams |
| **[Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-approach-gen-ai)** | ✗ | Limited | ✅ | ✗ | Azure-native teams |
| **[Google Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview)** | ✗ | Limited | ✅ | ✗ | GCP-native teams |

> **Prompt Mgmt** means versioning prompt templates and pulling them at runtime via SDK — a feature distinct from general observability.

The **banking sentinel** is a customer support agent for ROGERVINAS bank: 3 mock accounts with 5 transactions each, and tools to freeze/unfreeze cards, look up transactions, and open or track disputes. This project demonstrates:

- **[Strands Agents](https://strandsagents.com)** — AWS-native agent SDK with tool use and session memory
- **Langfuse tracing** — hybrid OTel + Langfuse SDK approach for full span hierarchy
- **Offline evaluations** — Strands Evals SDK (standalone, CI-friendly) and Langfuse Experiments (with dashboard)
- **Online LLM-as-judge** — scoring live production traces as they arrive
- **Annotation queues** — human review workflow triggered by negative user feedback
- **Prompt management** — versioned system prompts pulled from Langfuse at runtime

```mermaid
flowchart LR
    User([User]) --> UI["Chat UI"]
    UI -->|"POST /chat"| API["FastAPI"]
    API --> Agent["Strands Agent\n+ Tools"]

    API -->|"traces + scores"| LF[("Langfuse")]
    Agent -->|"OTel spans"| LF
    LF -->|"prompt at runtime"| Agent

    Evals["Offline Evals\n(CI + local)"] -->|"embedded"| Agent
    Evals -->|"experiment results"| LF
    LF -->|"LLM-as-judge"| LF
```

- [Implementation](#implementation)
  - [Step 1: The Banking Agent](#step-1-the-banking-agent)
  - [Step 2: Langfuse Tracing](#step-2-langfuse-tracing)
  - [Step 3: Strands Native Evaluations](#step-3-strands-native-evaluations)
  - [Step 4: Langfuse Experiments](#step-4-langfuse-experiments)
  - [Step 5: Online Evaluations (LLM-as-judge)](#step-5-online-evaluations-llm-as-judge)
  - [Step 6: Annotation Queues](#step-6-annotation-queues)
  - [Step 7: Prompt Management](#step-7-prompt-management)
- [Configuration](#configuration)
- [Run](#run)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Documentation](#documentation)

---

## Implementation

Let's implement this step by step.

### Step 1: The Banking Agent

The domain: a banking customer support agent — the **Sentinel** — for ROGERVINAS bank. It has three mock accounts (`ACC-1001`, `ACC-1002`, `ACC-1003`), each with five transactions, and provides seven tools:

| Tool | Description |
|---|---|
| `freeze_card` | Freeze a card |
| `unfreeze_card` | Unfreeze a card |
| `is_card_frozen` | Check freeze status |
| `get_transactions` | List transactions between two dates |
| `open_dispute` | Open a dispute on a transaction |
| `get_dispute_status` | Check dispute status |
| `list_disputes` | List all disputes for an account |

The domain state (`CardState`, `DisputeStore`) lives per-session and is injected into tools at request time via a factory:

```python
# data.py
class CardState:
    def __init__(self):
        self._frozen: set[str] = set()

    def freeze(self, account_id: str) -> None:
        self._frozen.add(account_id)

class DisputeStore:
    def __init__(self, transactions: dict[str, list[Transaction]]):
        self._disputes: dict[str, Dispute] = {}
```

```python
# tools.py
def create_tools(card_state, dispute_store, transactions, reference_date):

    @tool
    def freeze_card(account_id: str, reason: str) -> str:
        """Freeze the card associated with an account."""
        card_state.freeze(account_id)
        return json.dumps({"account_id": account_id, "status": "frozen", "reason": reason})

    # ... 6 more tools
    return [freeze_card, unfreeze_card, is_card_frozen,
            get_transactions, open_dispute, get_dispute_status, list_disputes]
```

The agent factory creates a `strands.Agent` with a compiled system prompt, tools, and an optional session manager:

```python
# agent.py
def create_agent(langfuse, model, tools, user_tier, account_id, reference_date, session_manager=None) -> tuple:
    system_prompt, prompt_obj = _create_system_prompt(user_tier, account_id, reference_date), None
    return Agent(model=model, tools=tools, system_prompt=system_prompt,
                 session_manager=session_manager, callback_handler=lambda **_: None), prompt_obj

def chat(agent: Agent, message: str) -> ChatResponse:
    result = agent(message, structured_output_model=ChatResponse)
    return result.structured_output
```

`FileSessionManager` persists conversation history to `sessions/` so the agent remembers prior turns within a session.

Run the agent:

```bash
uv run uvicorn banking_sentinel.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000) to use the chat UI.

---

### Step 2: Langfuse Tracing

Start Langfuse (required for Steps 2–7):

```bash
docker compose -f docker-compose-langfuse.yml up -d
```

Langfuse UI: [http://localhost:3000](http://localhost:3000) — pre-provisioned credentials: `admin@local.dev` / `password`.

**The challenge:** Strands uses OTel to emit spans internally, but raw OTel spans may not carry all the context Langfuse expects (e.g. trace-level `input`, `output`). The Strands `[otel]` extra generates spans but does not set `input`/`output` on the root span — you get `undefined` in the annotation queue.

**Pattern used here:** `langfuse.start_as_current_observation()` wraps the entire `/chat` request. This is a Langfuse-native Python method, independent of Strands, that works with any Python code. It ensures `input`/`output` is set on the root trace span, while Strands OTel spans are captured as children automatically:

```python
# api.py
with langfuse.start_as_current_observation(name="banking-sentinel-chat", as_type="generation") as span:
    with propagate_attributes(user_id=request.user_id, session_id=session_id,
                              trace_name="banking-sentinel-chat", tags=["banking-sentinel"]):
        tools = create_tools(state.card_state, state.dispute_store, state.transactions, state.reference_date)
        session_manager = FileSessionManager(session_id=session_id, storage_dir="sessions")
        agent, prompt_obj = create_agent(langfuse, _model, tools, state.user_tier, request.account_id, state.reference_date, session_manager=session_manager)
        response = chat(agent, request.message)
    span.update(input=request.message, output=response.answer, prompt=prompt_obj)
    trace_id = span.trace_id
```

This produces the following span hierarchy in Langfuse:

```
banking-sentinel-chat  ← Langfuse-native root span (input/output/user_id)
  └── propagate_attributes()  ← propagates session/user to all child spans
        └── Strands OTel spans  ← captured automatically
```

Open [http://localhost:3000](http://localhost:3000) → **Traces** to see it.

> **Note:** Token usage and model name are tracked on the inner Strands spans (`invoke_agent`, `chat`), not on the root span — because we don't call the LLM directly. Usage is still visible in the trace, just one level down. Two spans share the `banking-sentinel` tag (root + Strands inner `chat` generation) — keep this in mind when configuring online evaluators in Step 5.

---

### Offline vs Online Evaluations

Before the next steps, a quick framing:

- **Offline evaluations** run against a fixed dataset before or after a change — deterministic, reproducible, suitable for CI. They give you confidence that a code or prompt change didn't regress quality. Covered in Steps 3 and 4.
- **Online evaluations** run in production against real traffic — async, triggered by live traces. They catch issues that didn't appear in your fixed dataset. Covered in Step 5.

---

### Step 3: Strands Native Evaluations

The [Strands Evals SDK](https://strandsagents.com/latest/documentation/docs/deploy/evaluation/) provides `Case`, `Experiment`, and `OutputEvaluator`. No Langfuse required — runs fully offline and produces a local report.

Each `Case` bundles an input and expected output:

```python
# evals/strands/run_evaluations.py
CASES = [
    Case(
        name="unauthorized-netflix-charge",
        input={
            "userId": "user-1001", "accountId": "ACC-1001", "accountTier": "Standard",
            "message": "I don't have Netflix but I see a charge on my account",
        },
        expected_output={
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Netflix charge of 9.99 and offered the user to open a dispute",
        },
    ),
    # ...
]
```

Two evaluators score each result — one deterministic, one LLM-as-judge:

```python
class CorrectnessEvaluator(OutputEvaluator):
    pass

class ClaimEvaluator(OutputEvaluator):
    pass

correctness_evaluator = CorrectnessEvaluator(
    model=_model,
    rubric="Score 1.0 if the actual output's suggested_actions contains all actions listed in expected_output's suggestedActions. Score 0.0 if any expected action is missing.",
)

claim_evaluator = ClaimEvaluator(
    model=_model,
    rubric="Score 1.0 if the actual output's answer matches the claim in expected_output. Score 0.0 if the answer does not match the claim.",
)
```

The task function runs the agent in-process or via HTTP:

```python
def embedded_task(case: Case) -> dict:
    """Runs the agent in-process. Inject any CardState/DisputeStore to mock specific scenarios."""
    inp = case.input
    transactions = build_transactions(REFERENCE_DATE)
    tools = create_tools(CardState(), DisputeStore(transactions), transactions, REFERENCE_DATE)
    agent, _ = create_agent(None, _model, tools, inp["accountTier"], inp["accountId"], REFERENCE_DATE)
    response = chat(agent, inp["message"])
    return {"output": {"answer": response.answer, "suggested_actions": [a.value for a in response.suggested_actions]}}
```

Run:

```bash
# embedded — no server needed
uv run python -m evals.strands.run_evaluations embedded

# against a running server
uv run python -m evals.strands.run_evaluations api --url http://localhost:8000
```

---

### Step 4: Langfuse Experiments

Langfuse Experiments persist evaluation results to the Langfuse dashboard and CI can gate on them. Requires Langfuse running.

**Create the dataset** (idempotent — safe to run repeatedly):

```bash
uv run python -m evals.langfuse.create_dataset
```

This creates a dataset named `banking-sentinel-evals` with two items:

```python
# evals/langfuse/create_dataset.py
ITEMS = [
    {
        "id": "banking-sentinel-evals-unauthorized-netflix-charge",
        "input": {
            "accountId": "ACC-1001", "accountTier": "Standard",
            "message": "I don't have Netflix but I see a charge on my account",
        },
        "expected_output": {
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Netflix charge of 9.99 and offered the user to open a dispute",
        },
        "metadata": {"scenario": "unauthorized-netflix-charge"},
    },
    # ...
]
```

Two evaluators — one deterministic, one LLM-as-judge — score each result:

```python
# evals/langfuse/run_experiment.py
def correctness_evaluator(*, output, expected_output, **kwargs):
    """Deterministic: checks if all expected suggested actions are present."""
    expected = set(expected_output.get("suggestedActions", []))
    actual = set(output.get("suggested_actions", []))
    score = len(expected & actual) / len(expected) if expected else 1.0
    return Evaluation(name="correctness", value=score, comment=f"Expected {expected}, got {actual}")

def claim_evaluator(*, output, expected_output, **kwargs):
    """LLM-as-judge: checks if the agent's answer matches the expected claim."""
    judge = Agent(model=_model, callback_handler=lambda **_: None)
    result = judge(
        f"Does the following answer match the claim? Reply with YES or NO only.\n\n"
        f"Answer: {output['answer']}\n\nClaim: {expected_output['claim']}"
    )
    return Evaluation(name="claim_match", value=1.0 if "YES" in str(result).upper() else 0.0)

result = langfuse.run_experiment(
    name="banking-sentinel",
    data=dataset.items,
    task=embedded_task,
    evaluators=[correctness_evaluator, claim_evaluator],
    max_concurrency=1,
)
```

Run:

```bash
uv run python -m evals.langfuse.run_experiment embedded

uv run python -m evals.langfuse.run_experiment api --url http://localhost:8000
```

Open [http://localhost:3000](http://localhost:3000) → project `banking-sentinel` → **Datasets** to see results.

---

### Step 5: Online Evaluations (LLM-as-judge)

Langfuse can automatically score live traces as they arrive — no code changes needed. All chat traces are tagged `banking-sentinel` and named `banking-sentinel-chat`, making them easy to target.

**Setup (UI only — no stable API for self-hosted):**

**1 — Add LLM Connection:**
Go to **Settings → LLM Connections** → add your model provider API key.

**2 — Set default evaluation model:**
Go to **LLM-as-a-Judge** → set the **Default Evaluation Model** to the connection you just added.

**3 — Create evaluator and rule:**
Go to **LLM-as-a-Judge** → click `Create Evaluator` → select a managed evaluator:

- For **live traces** (`Observations` target): use **Hallucination** or **Helpfulness** — ground truth is not available for live traffic
- For **experiments** (`Experiments` target): use **Correctness** — map `{{ground_truth}}` to the dataset's `expected_output`

**4 — Configure the rule:**
1. Set target to `Observations`, filter by `Type = GENERATION`
2. Add filter: `Tags` → `any of` → `banking-sentinel`
3. Add filter: `Name` → `=` → `banking-sentinel-chat` — targets only the root span; avoids double-scoring the inner Strands generation (both carry the tag but have different names)
4. Set **Sampling** (100% is fine for PoC — reduce in production to control costs)
5. Map prompt variables: `input` → source `input`, `output` → source `output`
6. Click `Execute` — scores existing matching observations immediately and new ones going forward

Results appear as scores on each trace in the Langfuse UI.

> **Note:** The [Langfuse API](https://langfuse.com/docs/scores/model-based-evals) to create evaluators and rules programmatically is unstable and **only available on Langfuse Cloud** — not in self-hosted deployments. Use the UI for self-hosted.

---

### Step 6: Annotation Queues

Annotation queues are a human review workflow — domain experts manually score traces to build ground truth, validate LLM-as-judge results, or investigate failures. Your code decides what enters the queue and when — items only appear through an explicit call.

**Setup (once, idempotent):**

```bash
uv run python -m evals.langfuse.create_annotation_queue
```

This creates the `banking-sentinel-review` queue. Set `ANNOTATION_QUEUE_ID` in `.env` to the returned queue ID.

**Trigger: negative user feedback (👎)**

The chat UI includes 👍 / 👎 buttons on every assistant message. The `/feedback` endpoint scores the trace and — on 👎 — enqueues it for human review:

```python
# api.py
langfuse.create_score(trace_id=request.trace_id, name="user-feedback", value=request.value)

if request.value == 0.0 and _annotation_queue_id:
    langfuse.api.annotation_queues.create_queue_item(
        _annotation_queue_id,
        object_id=request.trace_id,
        object_type=AnnotationQueueObjectType.TRACE,
    )
```

Other common triggers: experiment score below threshold, online evaluator scores low, specific intent detected, random sampling.

**Human review workflow:**
1. Go to **Annotation Queues** in the Langfuse UI
2. Open `banking-sentinel-review`
3. For each trace: review the conversation, assign a score, click **Complete + next**
4. Scores appear on the trace and contribute to your evaluation dashboard

---

### Step 7: Prompt Management

Langfuse can store and version system prompts independently of your code — iterate on the prompt without redeploying the app.

`create_agent()` returns `(agent, prompt_obj)`. When `USE_LANGFUSE_PROMPT=true`, it fetches the prompt from Langfuse; otherwise it uses the hardcoded template:

```python
# agent.py
def create_agent(langfuse, model, tools, user_tier, account_id, reference_date, session_manager=None) -> tuple:
    if langfuse is not None and os.getenv("USE_LANGFUSE_PROMPT", "false").lower() == "true":
        system_prompt, prompt_obj = _get_system_prompt_from_langfuse(langfuse, user_tier, account_id, reference_date)
    else:
        system_prompt, prompt_obj = _create_system_prompt(user_tier, account_id, reference_date), None
    return Agent(model=model, tools=tools, system_prompt=system_prompt,
                 session_manager=session_manager, callback_handler=lambda **_: None), prompt_obj
```

`api.py` passes `prompt_obj` back to Langfuse to link the prompt version to the trace:

```python
span.update(input=request.message, output=response.answer, prompt=prompt_obj)
```

**Create the prompt — Option A (script):**

```bash
uv run python -m evals.langfuse.create_prompt
```

Each run creates a new version. The `production` label is set automatically, so it is served at runtime.

**Create the prompt — Option B (UI):**

Go to **Prompts** → `+ New prompt` → name `banking-sentinel-system`, type `Text` → paste the template using `{{variable}}` syntax (Mustache) → add the `production` label → save.

Then enable Langfuse-managed prompts:

```
USE_LANGFUSE_PROMPT=true
```

Benefits: version history, compare prompt versions across experiments, iterate without redeploying, A/B test prompts.

> **Note:** `span.update(prompt=prompt_obj)` only works on `generation` type spans. The prompt links to our root `banking-sentinel-chat` generation span, not to the inner Strands LLM generation span (which we don't control directly). This is a general limitation of OTel-auto-instrumented frameworks — see [Langfuse Strands Agents integration](https://langfuse.com/integrations/frameworks/strands-agents). To rollback, reassign the `production` label to any previous version in the UI: **Prompts** → select version → set label.

---

## Configuration

### Prerequisites

- Python 3.13 (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose
- A model provider (see below)

### Install dependencies

```bash
uv sync --extra dev --extra evals
```

- `dev` — `pytest`, `pytest-asyncio` (unit tests)
- `evals` — `strands-agents-evals`, `httpx` (evaluations)

### Environment

```bash
cp .env.example .env
```

Edit `.env` to set your model provider and Langfuse credentials.

### Model providers

Set `MODEL_PROVIDER` in `.env`:

| Provider | `MODEL_PROVIDER` | Requirements |
|---|---|---|
| Ollama (default) | `ollama` | `ollama serve` + `ollama pull llama3.1:8b` |
| AWS Bedrock | `bedrock` | AWS credentials configured |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` in `.env` |

### Langfuse

```bash
docker compose -f docker-compose-langfuse.yml up -d
```

Pre-provisioned credentials:

```
Email:      admin@local.dev
Password:   password
Public key: publickey-local
Secret key: secretkey-local
```

Wait for all services to be healthy:

```bash
docker compose -f docker-compose-langfuse.yml ps
```

To stop: `docker compose -f docker-compose-langfuse.yml down`

To stop and delete all data: `docker compose -f docker-compose-langfuse.yml down -v`

---

## Run

```bash
uv run uvicorn banking_sentinel.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000). The chat UI includes 👍 / 👎 buttons on every assistant message — clicking one sends a score to Langfuse immediately and, on 👎, enqueues the trace for human review (Step 6).

Agent traces are sent to Langfuse automatically via OpenTelemetry when `LANGFUSE_*` and `OTEL_*` env vars are set.

---

## Testing

Unit tests cover the core business logic (`data.py`) and tool JSON contracts (`tools.py`). They run fully offline — no LLM or Langfuse required.

```bash
uv run pytest
```

---

## CI/CD

Three sequential jobs gate on each other — each stage must pass before the next starts:

1. **Build** — installs dependencies, builds the package, runs unit tests
2. **Standalone Evals** — runs Strands native evaluations in embedded mode (no Langfuse). Fails if any score drops below 0.8.
3. **Langfuse Evals** — spins up Langfuse via Docker, runs Langfuse experiments, reports results to the dashboard. Fails if any score drops below 0.8.

This means a code or prompt change that degrades agent quality will fail CI before it can reach production.

---

## Documentation

- [Strands Agents docs](https://strandsagents.com/latest/documentation/)
- [Langfuse docs](https://langfuse.com/docs)
- [Langfuse × Strands Agents integration](https://langfuse.com/integrations/frameworks/strands-agents)
- [Langfuse prompt management](https://langfuse.com/docs/prompt-management/get-started)
- [Langfuse annotation queues](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues)
- [Martin Fowler — Patterns of Distributed Systems](https://martinfowler.com/articles/patterns-of-distributed-systems/)

Happy GenAI coding! 💙