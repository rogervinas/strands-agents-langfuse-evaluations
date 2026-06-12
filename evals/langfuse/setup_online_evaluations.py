"""
Set up online evaluations (LLM-as-judge on live traces) in Langfuse.

WARNING: Uses the Langfuse unstable API — may break with future SDK updates.
WARNING: Only works on Langfuse Cloud — the unstable API is not available in self-hosted.
See: https://langfuse.com/docs/scores/model-based-evals

Prerequisites (UI only — no API available):
  Settings → LLM Connections → add your model provider API key

This script creates:
  1. An evaluator: "banking-sentinel-claim-match" — scores whether the agent's
     answer matches its intended behaviour
  2. An evaluation rule: targets live observations tagged "banking-sentinel"
"""
from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client
from langfuse.api.unstable.commons.types import (
    EvaluationRuleMappingSource,
    EvaluationRuleStringFilterOperator,
    EvaluationRuleTarget,
    EvaluatorOutputDefinition_Numeric,
    EvaluatorOutputFieldDefinition,
)
from langfuse.api.unstable.commons.types.string_evaluation_rule_filter import (
    StringEvaluationRuleFilter,
)
from langfuse.api.unstable.evaluation_rules.types import (
    EvaluationRuleEvaluatorReference,
)
from langfuse.api.unstable.commons.types.evaluation_rule_mapping import (
    EvaluationRuleMapping,
)
from langfuse.api.unstable.commons.types.evaluator_model_config import EvaluatorModelConfig
from langfuse.api.unstable.commons.types.evaluator_scope import EvaluatorScope

EVALUATOR_NAME = "banking-sentinel-claim-match"
RULE_NAME = "banking-sentinel-live"

EVALUATOR_PROMPT = """
You are evaluating a banking assistant's response.

Input: {{input}}
Output: {{output}}

Score 1.0 if the response is helpful, accurate, and appropriate for a banking context.
Score 0.5 if the response is partially helpful or contains minor issues.
Score 0.0 if the response is unhelpful, inaccurate, or inappropriate.
""".strip()


def _get_model_config(langfuse) -> EvaluatorModelConfig:
    """Fetches the first configured LLM connection and pairs it with the MODEL env var."""
    connections = langfuse.api.llm_connections.list()
    if not connections.data:
        raise RuntimeError(
            "No LLM connections found. Add one in Langfuse UI: Settings → LLM Connections"
        )
    conn = connections.data[0]
    provider = conn.provider

    model_env = {
        "gemini": "GEMINI_MODEL",
        "openai": "OPENAI_MODEL",
        "anthropic": "ANTHROPIC_MODEL",
        "bedrock": "BEDROCK_MODEL",
    }
    import os
    model = os.getenv(model_env.get(provider, ""), "") or _default_model(provider)
    print(f"  Using LLM connection: provider={provider}, model={model}")
    return EvaluatorModelConfig(provider=provider, model=model)


def _default_model(provider: str) -> str:
    defaults = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5-20251001",
    }
    return defaults.get(provider, "unknown")


def setup():
    langfuse = get_client()
    unstable = langfuse.api.unstable

    model_config = _get_model_config(langfuse)

    # Step 1: Create evaluator (idempotent — Langfuse creates a new version if name exists)
    print(f"Creating evaluator '{EVALUATOR_NAME}' ...")
    evaluator = unstable.evaluators.create(
        name=EVALUATOR_NAME,
        prompt=EVALUATOR_PROMPT,
        model_config=model_config,
        output_definition=EvaluatorOutputDefinition_Numeric(
            reasoning=EvaluatorOutputFieldDefinition(
                description="Explain why the response is helpful or not.",
            ),
            score=EvaluatorOutputFieldDefinition(
                description="Score between 0.0 and 1.0 for response quality.",
            ),
        ),
    )
    print(f"  ✅ Evaluator created: {evaluator.name} (version {evaluator.version})")
    print(f"     Variables: {evaluator.variables}")

    # Step 2: Create evaluation rule targeting live observations tagged "banking-sentinel"
    # If a rule with the same name already exists, Langfuse returns 409 — skip gracefully.
    print(f"\nCreating evaluation rule '{RULE_NAME}' ...")
    try:
        rule = unstable.evaluation_rules.create(
            name=RULE_NAME,
            evaluator=EvaluationRuleEvaluatorReference(
                name=evaluator.name,
                scope=EvaluatorScope.PROJECT,
            ),
            target=EvaluationRuleTarget.OBSERVATION,
            enabled=True,
            sampling=1.0,
            filter=[
                StringEvaluationRuleFilter(
                    column="tags",
                    operator=EvaluationRuleStringFilterOperator.CONTAINS,
                    value="banking-sentinel",
                )
            ],
            mapping=[
                EvaluationRuleMapping(variable=v, source=_source_for(v))
                for v in evaluator.variables
            ],
        )
        print(f"  ✅ Rule created: {rule.name} (id: {rule.id})")
    except Exception as e:
        if "409" in str(e):
            print(f"  ⚠️  Rule '{RULE_NAME}' already exists — skipping")
        else:
            raise

    print("\nDone. Every new trace tagged 'banking-sentinel' will be scored automatically.")
    print("View evaluators at: http://localhost:3000 → Settings → Evaluators")


def _source_for(variable: str) -> EvaluationRuleMappingSource:
    mapping = {
        "input": EvaluationRuleMappingSource.INPUT,
        "output": EvaluationRuleMappingSource.OUTPUT,
        "metadata": EvaluationRuleMappingSource.METADATA,
    }
    return mapping.get(variable, EvaluationRuleMappingSource.OUTPUT)


if __name__ == "__main__":
    setup()
