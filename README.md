# Banking Sentinel — Strands Agents + Langfuse Evaluations

A Python banking assistant agent built with [Strands Agents](https://strandsagents.com) (AWS), demonstrating two evaluation approaches using [Langfuse](https://langfuse.com):

1. **Native (Strands Evals SDK)** — local reports, no infrastructure required
2. **Langfuse delegated** — scores persisted in Langfuse dashboard, CI/CD gate via GitHub Actions

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) or pip
- Docker + Docker Compose
- [Ollama](https://ollama.com) (for local LLM, default provider)

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` as needed. Defaults work out of the box for local dev with Ollama + Langfuse.

### 3. Start Langfuse

```bash
docker compose up -d
```

Langfuse UI will be available at [http://localhost:3000](http://localhost:3000).

**Pre-provisioned credentials:**

| | |
|---|---|
| URL | http://localhost:3000 |
| Email | `admin@local.dev` |
| Password | `password` |
| Public key | `publickey-local` |
| Secret key | `secretkey-local` |

Wait for all services to be healthy:

```bash
docker compose ps
```

To stop:

```bash
docker compose down
```

To stop and remove all data:

```bash
docker compose down -v
```

### 4. Start Ollama (default model provider)

```bash
ollama serve
ollama pull llama3.1:8b
```

Alternatively, set `MODEL_PROVIDER=bedrock` or `MODEL_PROVIDER=gemini` in `.env`.

## Running the Agent

```bash
uv run uvicorn banking_sentinel.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000) to use the chat UI.

## Model Providers

| Provider | `MODEL_PROVIDER` | Requirements |
|---|---|---|
| Ollama (default) | `ollama` | `ollama serve` + `ollama pull llama3.1:8b` |
| AWS Bedrock | `bedrock` | AWS credentials configured |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` in `.env` |

## Evaluations

### Approach 1: Native Strands Evals (local)

Runs evaluation cases locally using the Strands Evals SDK. No Langfuse required.

```bash
uv run python -m evals.strands.run_evaluations
```

### Approach 2: Langfuse Experiments (delegated)

Requires Langfuse running (`docker compose up -d`).

Create the dataset (idempotent, safe to re-run):

```bash
uv run python -m evals.langfuse.create_dataset
```

Run the experiment:

```bash
uv run python -m evals.langfuse.run_experiment
```

View results at [http://localhost:3000](http://localhost:3000) → project `banking-sentinel` → Datasets.

### Bash alternative (dataset creation)

```bash
bash scripts/create-dataset.sh
```

## Project Structure

```
src/banking_sentinel/
├── models.py          # Pydantic models (ChatResponse, SuggestedAction)
├── data.py            # Mock transactions, card state, dispute store
├── knowledge_base.py  # Policy documents (embedded in system prompt)
├── tools.py           # 7 Strands @tool functions
├── agent.py           # Agent factory (ollama/bedrock/gemini)
└── api.py             # FastAPI app + chat UI
evals/
├── strands/
│   └── run_evaluations.py   # Native Strands Evals
└── langfuse/
    ├── create_dataset.py    # Create Langfuse dataset
    └── run_experiment.py    # Run Langfuse experiment
static/
└── chat.html          # Chat UI
scripts/
└── create-dataset.sh  # Bash dataset creation via Langfuse REST API
docker-compose.yml     # Langfuse stack (postgres, clickhouse, minio, redis)
```
