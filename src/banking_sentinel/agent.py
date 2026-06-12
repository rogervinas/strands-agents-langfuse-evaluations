import logging
import os
from datetime import date

from strands import Agent

logger = logging.getLogger(__name__)

from banking_sentinel.knowledge_base import KNOWLEDGE_BASE
from banking_sentinel.models import ChatResponse

_SYSTEM_PROMPT_TEMPLATE = """
You are the "Sentinel," a secure banking assistant for ROGERVINAS bank.

### MISSION:
Provide accurate account support and perform banking actions. Your answers must be grounded strictly in the retrieved context and the user's real-time account data.

### OPERATIONAL PROTOCOLS:
1. TRUTH SOURCE: Use the provided documentation for policy questions (fees, deadlines, disputes). If the context doesn't contain the answer, politely explain that you don't have that information.
2. ACTION HANDLING: Before executing any sensitive tool (like freezing a card or changing limits), summarize the action and ask for the user's explicit confirmation.
3. SECURITY: If the user indicates a lost card or fraud, prioritize offering the "Freeze Card" tool immediately.
4. DATE REASONING: When assessing deadlines (like disputes), use the "Current Date" provided below to calculate if the transaction falls within the policy window found in the retrieved documents.

### CONTEXT:
- User Tier: {user_tier}
- Current Date: {current_date}
- Account ID: {account_id}

{knowledge_base}
""".strip()


def create_model(provider: str | None = None):
    provider = provider or os.getenv("MODEL_PROVIDER", "ollama")

    if provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        )
    elif provider == "bedrock":
        from strands.models import BedrockModel
        return BedrockModel(
            model_id=os.getenv("BEDROCK_MODEL", "anthropic.claude-sonnet-4-20250514-v1:0"),
        )
    elif provider == "gemini":
        from strands.models.gemini import GeminiModel
        return GeminiModel(
            model_id=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {provider!r}. Use 'ollama', 'bedrock' or 'gemini'.")


def create_sentinel_agent(model, tools, user_tier: str, account_id: str, reference_date: date) -> Agent:
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        user_tier=user_tier,
        current_date=reference_date.isoformat(),
        account_id=account_id,
        knowledge_base=KNOWLEDGE_BASE,
    )
    return Agent(model=model, tools=tools, system_prompt=system_prompt, callback_handler={})


def chat(agent: Agent, message: str) -> ChatResponse:
    result = agent(message, structured_output_model=ChatResponse)
    return result.structured_output
