import argparse
import sys
import uuid
from datetime import date

import httpx
from dotenv import load_dotenv
from strands_evals import Case, Experiment
from strands_evals.evaluators import OutputEvaluator

load_dotenv()

from banking_sentinel.agent import create_model, create_sentinel_agent, chat
from banking_sentinel.data import CardState, DisputeStore, build_transactions
from banking_sentinel.tools import create_tools

REFERENCE_DATE = date(2025, 4, 15)

CASES = [
    Case(
        name="unauthorized-netflix-charge",
        input={
            "userId": "user-1001",
            "accountId": "ACC-1001",
            "accountTier": "Standard",
            "message": "I don't have Netflix but I see a charge on my account",
        },
        expected_output={
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Netflix charge of 9.99 and offered the user to open a dispute",
        },
    ),
    Case(
        name="expired-dispute-window",
        input={
            "userId": "user-1002",
            "accountId": "ACC-1002",
            "accountTier": "Standard",
            "message": "I see a Best Buy charge on my account but I never bought anything there",
        },
        expected_output={
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Best Buy charge of 200.00 and explained that the dispute window has expired because the transaction is older than 14 days",
        },
    ),
]

_model = create_model()

correctness_evaluator = OutputEvaluator(
    model=_model,
    rubric="""
Score 1.0 if the actual output's suggested_actions contains all actions listed in expected_output's suggestedActions.
Score 0.0 if any expected action is missing from the actual output.
""".strip(),
)

claim_evaluator = OutputEvaluator(
    model=_model,
    rubric="""
Score 1.0 if the actual output's answer matches the claim in expected_output.
Score 0.0 if the answer does not match the claim.
""".strip(),
)


def embedded_task(case: Case) -> dict:
    """Runs the agent in-process. Useful for local dev and unit-style evals.
    Inject any CardState/DisputeStore/transactions to mock specific scenarios."""
    inp = case.input
    transactions = build_transactions(REFERENCE_DATE)
    card_state = CardState()
    dispute_store = DisputeStore(transactions)
    tools = create_tools(card_state, dispute_store, transactions, REFERENCE_DATE)
    agent = create_sentinel_agent(_model, tools, inp["accountTier"], inp["accountId"], REFERENCE_DATE)
    response = chat(agent, inp["message"])
    return {
        "output": {
            "answer": response.answer,
            "suggested_actions": [a.value for a in response.suggested_actions],
        }
    }


def api_task(api_url: str):
    """Returns a task function that calls the deployed agent via HTTP.
    Treats the agent as a black box — suitable for staging/production evals."""
    run_id = uuid.uuid4().hex[:8]

    def task(case: Case) -> dict:
        inp = case.input
        response = httpx.post(
            f"{api_url}/chat",
            json={
                "user_id": f"test-user-{run_id}",
                "account_id": inp["accountId"],
                "user_tier": inp["accountTier"],
                "message": inp["message"],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "output": {
                "answer": data["answer"],
                "suggested_actions": data["suggested_actions"],
            }
        }
    return task


def run(task):
    experiment = Experiment(cases=CASES, evaluators=[correctness_evaluator, claim_evaluator])
    reports = experiment.run_evaluations(task)

    failed = False
    for report in reports:
        print(f"\n{'='*60}")
        print(f"Evaluator: {report.evaluator_name}")
        print(f"Overall score: {report.overall_score:.2f}")
        for i, case in enumerate(CASES):
            icon = "✅" if report.test_passes[i] else "❌"
            print(f"  {icon} {case.name}: score={report.scores[i]:.2f} — {report.reasons[i]}")
        if report.overall_score < 0.8:
            failed = True

    if failed:
        print("\n❌ Evaluation FAILED: one or more scores below 0.8")
        sys.exit(1)
    else:
        print("\n✅ Evaluation PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="target", required=True)

    subparsers.add_parser("embedded", help="Run agent in-process (no server needed)")

    api_parser = subparsers.add_parser("api", help="Run against a deployed agent via HTTP")
    api_parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the deployed agent")

    args = parser.parse_args()

    if args.target == "embedded":
        print("Target: embedded")
        run(embedded_task)
    else:
        print(f"Target: api ({args.url})")
        run(api_task(args.url))
