import argparse
import sys
import uuid

from datetime import date

import httpx
from dotenv import load_dotenv
from strands import Agent

load_dotenv()

from langfuse import get_client
from langfuse.experiment import Evaluation

from banking_sentinel.agent import create_model, create_sentinel_agent, chat
from banking_sentinel.data import CardState, DisputeStore, build_transactions
from banking_sentinel.tools import create_tools
from evals.langfuse.create_dataset import DATASET_NAME, create_dataset

REFERENCE_DATE = date(2025, 4, 15)

_model = create_model()


# --- Task functions ---

def embedded_task(*, item, **kwargs):
    """Runs the agent in-process. No server needed."""
    inp = item.input
    transactions = build_transactions(REFERENCE_DATE)
    card_state = CardState()
    dispute_store = DisputeStore(transactions)
    tools = create_tools(card_state, dispute_store, transactions, REFERENCE_DATE)
    agent = create_sentinel_agent(_model, tools, inp["accountTier"], inp["accountId"], REFERENCE_DATE)
    response = chat(agent, inp["message"])
    return {
        "answer": response.answer,
        "suggested_actions": [a.value for a in response.suggested_actions],
    }


def api_task(api_url: str):
    """Returns a task function that calls the deployed agent via HTTP."""
    run_id = uuid.uuid4().hex[:8]

    def task(*, item, **kwargs):
        inp = item.input
        response = httpx.post(
            f"{api_url}/chat",
            json={
                "user_id": f"langfuse-eval-user-{run_id}",
                "account_id": inp["accountId"],
                "user_tier": inp["accountTier"],
                "message": inp["message"],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "answer": data["answer"],
            "suggested_actions": data["suggested_actions"],
        }
    return task


# --- Evaluators ---

def correctness_evaluator(*, output, expected_output, **kwargs):
    """Deterministic: checks if all expected suggested actions are present."""
    expected = set(expected_output.get("suggestedActions", []))
    actual = set(output.get("suggested_actions", []))
    score = len(expected & actual) / len(expected) if expected else 1.0
    return Evaluation(
        name="correctness",
        value=score,
        comment=f"Expected {expected}, got {actual}",
    )


def claim_evaluator(*, output, expected_output, **kwargs):
    """LLM-as-judge: checks if the agent's answer matches the expected claim."""
    answer = output.get("answer", "")
    claim = expected_output.get("claim", "")
    judge = Agent(model=_model, callback_handler=lambda **_: None)
    result = judge(
        f"Does the following answer match the claim? Reply with YES or NO only.\n\n"
        f"Answer: {answer}\n\n"
        f"Claim: {claim}"
    )
    passed = "YES" in str(result).upper()
    return Evaluation(
        name="claim_match",
        value=1.0 if passed else 0.0,
        comment=f"Claim: {claim}",
    )


# --- Runner ---

def run(task):
    langfuse = get_client()
    dataset = langfuse.get_dataset(DATASET_NAME)

    result = langfuse.run_experiment(
        name="banking-sentinel",
        data=dataset.items,
        task=task,
        evaluators=[correctness_evaluator, claim_evaluator],
        max_concurrency=1,
    )

    print(f"\nRun: {result.run_name}")
    if result.dataset_run_url:
        print(f"Results: {result.dataset_run_url}")

    failed = False
    for item_result in result.item_results:
        metadata = getattr(item_result.item, "metadata", None) or {}
        scenario = metadata.get("scenario", "unknown")
        for evaluation in item_result.evaluations:
            passed = evaluation.value >= 0.8
            icon = "✅" if passed else "❌"
            print(f"  {icon} {scenario} [{evaluation.name}]: score={evaluation.value:.2f} — {evaluation.comment}")
            if not passed:
                failed = True

    langfuse.flush()

    if failed:
        print("\n❌ Experiment FAILED: one or more scores below 0.8")
        sys.exit(1)
    else:
        print("\n✅ Experiment PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="target", required=True)

    subparsers.add_parser("embedded", help="Run agent in-process (no server needed)")

    api_parser = subparsers.add_parser("api", help="Run against a deployed agent via HTTP")
    api_parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the deployed agent")

    args = parser.parse_args()

    create_dataset()

    if args.target == "embedded":
        print("Target: embedded")
        run(embedded_task)
    else:
        print(f"Target: api ({args.url})")
        run(api_task(args.url))
