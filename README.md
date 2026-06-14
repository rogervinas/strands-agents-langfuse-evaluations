# Banking Sentinel — Strands Agents + Langfuse Evaluations

A Python banking assistant agent built with [Strands Agents](https://strandsagents.com) (AWS), demonstrating two evaluation approaches using [Langfuse](https://langfuse.com):

1. **Native (Strands Evals SDK)** — local reports, no infrastructure required
2. **Langfuse delegated** — scores persisted in Langfuse dashboard, CI/CD integration

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose
- A model provider (see [Model Providers](#model-providers))

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` to set your model provider and credentials. See [Model Providers](#model-providers).

### 3. Start Langfuse

Required for tracing and Langfuse evaluations. Skip if only using Strands Evals.

```bash
docker compose -f docker-compose-langfuse.yml up -d
```

Langfuse UI: [http://localhost:3000](http://localhost:3000)

**Pre-provisioned credentials:**

| | |
|---|---|
| Email | `admin@local.dev` |
| Password | `password` |
| Public key | `publickey-local` |
| Secret key | `secretkey-local` |

Wait for all services to be healthy:

```bash
docker compose -f docker-compose-langfuse.yml ps
```

To stop:

```bash
docker compose -f docker-compose-langfuse.yml down
```

To stop and remove all data:

```bash
docker compose -f docker-compose-langfuse.yml down -v
```

## Model Providers

Set `MODEL_PROVIDER` in `.env`:

| Provider | `MODEL_PROVIDER` | Requirements |
|---|---|---|
| Ollama (default) | `ollama` | `ollama serve` + `ollama pull llama3.1:8b` |
| AWS Bedrock | `bedrock` | AWS credentials configured |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` in `.env` |

## Running the Agent

```bash
uv run uvicorn banking_sentinel.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000) to use the chat UI.

Agent traces are sent to Langfuse automatically via OpenTelemetry when `LANGFUSE_*` and `OTEL_*` env vars are set.

## Evaluations

Both evaluation approaches support two targets:

- **Embedded** — agent runs in-process, no server needed. Ideal for local dev and mocking specific scenarios (inject any `CardState`, `DisputeStore`, or transactions).
- **API** — evaluates a deployed agent via HTTP, treating it as a black box. Suitable for staging or production.

### Approach 1: Native Strands Evals

Uses the Strands Evals SDK with `Case`, `Experiment`, and `OutputEvaluator`. Runs locally, no Langfuse required.

```bash
uv run python -m evals.strands.run_evaluations embedded

uv run python -m evals.strands.run_evaluations api --url http://localhost:8000
uv run python -m evals.strands.run_evaluations api --url https://your-agent.example.com
```

### Approach 2: Langfuse Experiments

Requires Langfuse running (`docker compose -f docker-compose-langfuse.yml up -d`).

The dataset is created automatically on first run, but can also be created explicitly (idempotent):

```bash
uv run python -m evals.langfuse.create_dataset
```

Run the experiment:

```bash
uv run python -m evals.langfuse.run_experiment embedded

uv run python -m evals.langfuse.run_experiment api --url http://localhost:8000
uv run python -m evals.langfuse.run_experiment api --url https://your-agent.example.com
```

View results at [http://localhost:3000](http://localhost:3000) → project `banking-sentinel` → Datasets.

### Online Evaluations (LLM-as-judge on live traces)

Langfuse automatically scores live production traces as they arrive.
See: [Langfuse LLM-as-judge docs](https://langfuse.com/docs/scores/model-based-evals)

All chat traces are tagged `banking-sentinel` and named `chat`, making them easy to target.

**Step 1 — Add LLM Connection (UI only, no API available):**

Go to **Settings → LLM Connections** → add your model provider API key (e.g. Gemini, OpenAI).

**Step 2 — Set default evaluation model (UI only):**

Go to **LLM-as-a-Judge**. The first time you visit it will prompt you to set the **Default Evaluation Model** — select the LLM connection you added in step 1.

**Step 3 — Create evaluator and rule (UI):**

1. Go to **LLM-as-a-Judge** → click `Create Evaluator`
2. In the **Set up evaluator** wizard, click on a managed evaluator:
   - For **`Observations` target (live traces)**: use evaluators that only need `input` and `output`, e.g. **Hallucination** or **Helpfulness** — ground truth is not available for live production traces
   - For **`Experiments` target**: use **Correctness** — `expected_output` from the dataset is available as `ground_truth` and can be mapped to `{{ground_truth}}`
3. In step **Run Evaluator**, set target to `Observations`, filter by `Type = GENERATION`
4. Click `Add filter` → select `Tags` → operator `any of` → value `banking-sentinel`
5. Set **Sampling** (100% is fine for this PoC — reduce in production to control costs)
6. **Run on live incoming observations** is enabled by default — keep it on to score new traces continuously
7. Map prompt variables to observation fields ([docs](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)):
   - `input` variable → source `input` (no JSONPath — full messages array including system prompt)
   - `output` variable → source `output` (no JSONPath — full response object)
   Use the live preview to verify the mapping looks correct with your real traces before activating
8. Click `Execute` — scores existing matching observations immediately and all new ones going forward

Results appear as scores on each trace in the Langfuse UI.

> **Note:** Langfuse provides an [unstable API](https://langfuse.com/docs/scores/model-based-evals) to create evaluators and rules programmatically, but it is currently only available on Langfuse Cloud — not in self-hosted deployments.

## User Feedback

The chat UI includes 👍 / 👎 buttons on every assistant message. Clicking one sends a score to Langfuse immediately.
See: [Langfuse user feedback docs](https://langfuse.com/docs/scores/user-feedback)

**How it works:**

1. The `/chat` endpoint returns a `trace_id` alongside the response — derived from the active OpenTelemetry span
2. The UI attaches thumbs up/down buttons to each message, keyed to that `trace_id`
3. On click, the UI posts to `/feedback`:
   - `1.0` = thumbs up
   - `0.0` = thumbs down
4. The backend calls `langfuse.create_score(trace_id=..., name="user-feedback", value=...)` — the score appears on the trace in the Langfuse UI immediately

View feedback scores at [http://localhost:3000](http://localhost:3000) → Traces → click any trace → **Scores** tab. The score also appears as a small badge on the root span in the trace tree.

## Annotation Queues

Annotation queues are a human review workflow — domain experts manually score traces to build ground truth, validate LLM-as-judge results, or investigate failures.
See: [Langfuse annotation queues docs](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues)

**Key concept:** Langfuse provides the queue infrastructure, but **your code decides what goes in and when**. There is no automatic routing — items only enter a queue through an explicit call, either from the UI or from your code.

### Setup (once, idempotent)

Create the score config and queue:

```bash
uv run python -m evals.langfuse.create_annotation_queue
```

### Adding items to the queue

**Option A — Manually via UI:**

Go to **Traces** → select one or more traces → **Actions** → **Add to annotation queue**.
Use this for ad-hoc review of interesting traces.

**Option B — Programmatically (your code decides when):**

Your code calls `langfuse.api.annotation_queues.create_queue_item(...)` explicitly. Common triggers:

- **User gives 👎** — route negative feedback traces for human investigation
- **Experiment score below threshold** — after `run_experiment()`, enqueue failing traces to build better ground truth
- **Online evaluator scores low** — poll scores and enqueue traces below a quality threshold
- **Specific intent detected** — route traces matching certain patterns (e.g. complaints, edge cases) for review
- **Random sampling** — periodically enqueue a % of production traces for ongoing quality checks

### Implementation: triggered by 👎

This PoC implements the first use case — when a user gives negative feedback, the trace is automatically added to the queue for human investigation.

Setup (creates the score config and queue, idempotent):

```bash
uv run python -m evals.langfuse.create_annotation_queue
```

The `/feedback` endpoint in `api.py` calls `create_queue_item` when `value == 0.0`:

```python
if request.value == 0.0:
    langfuse.api.annotation_queues.create_queue_item(
        queue_id=QUEUE_ID,
        object_id=request.trace_id,
        object_type=AnnotationQueueObjectType.TRACE,
    )
```

### Human review workflow

1. Go to **Annotation Queues** in the Langfuse UI
2. Open the `banking-sentinel-review` queue
3. For each trace: review the conversation, assign a score, click **Complete + next**
4. Scores appear on the trace and contribute to your evaluation dashboard

## Project Structure

```
src/banking_sentinel/
├── models.py          # Pydantic models (ChatResponse, SuggestedAction)
├── data.py            # Mock transactions, card state, dispute store
├── knowledge_base.py  # Policy documents (embedded in system prompt)
├── tools.py           # 7 Strands @tool functions (factory pattern)
├── agent.py           # Agent factory (ollama/bedrock/gemini) + chat()
└── api.py             # FastAPI app + session management + Langfuse tracing
evals/
├── strands/
│   └── run_evaluations.py   # Native Strands Evals (embedded + api targets)
└── langfuse/
    ├── create_dataset.py    # Create Langfuse dataset (idempotent)
    └── run_experiment.py    # Run Langfuse experiment (embedded + api targets)
static/
└── index.html         # Chat UI
docker-compose-langfuse.yml  # Langfuse stack (postgres, clickhouse, minio, redis)
```
