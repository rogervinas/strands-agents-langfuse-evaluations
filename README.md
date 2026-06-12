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
