import logging
import os
import textwrap
from datetime import date

from strands import Agent

logger = logging.getLogger("uvicorn.error")

from banking_sentinel.knowledge_base import KNOWLEDGE_BASE
from banking_sentinel.models import ChatResponse

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


def _create_system_prompt(user_tier: str, account_id: str, reference_date: date) -> str:
    """Creates system prompt from hardcoded template in source."""
    return textwrap.dedent(f"""
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
        - Current Date: {reference_date.isoformat()}
        - Account ID: {account_id}

        {KNOWLEDGE_BASE}
    """).strip()


def _get_system_prompt_from_langfuse(langfuse, user_tier: str, account_id: str, reference_date: date) -> tuple:
    """Fetches system prompt from Langfuse (label='production') and compiles it.
    Returns (compiled_str, prompt_obj) — prompt_obj is needed to link the prompt to traces.
    See: https://langfuse.com/docs/prompt-management/get-started
    See: https://langfuse.com/docs/prompt-management/features/link-to-traces
    Run evals/langfuse/create_prompt.py to create/update the prompt in Langfuse.
    """
    prompt = langfuse.get_prompt("banking-sentinel-system", label="production")
    logger.info("Fetched Langfuse prompt: name=%s version=%s", prompt.name, prompt.version)
    compiled = prompt.compile(
        user_tier=user_tier,
        current_date=reference_date.isoformat(),
        account_id=account_id,
        knowledge_base=KNOWLEDGE_BASE,
    )
    return compiled, prompt


def create_agent(langfuse, model, tools, user_tier: str, account_id: str, reference_date: date, session_manager=None) -> tuple:
    """Creates agent using hardcoded or Langfuse-managed prompt (USE_LANGFUSE_PROMPT=true).
    Returns (agent, prompt_obj) — prompt_obj is not None when using Langfuse prompts,
    pass it to langfuse.update_current_generation(prompt=prompt_obj) to link to traces.
    See: https://langfuse.com/docs/prompt-management/features/link-to-traces
    """
    if os.getenv("USE_LANGFUSE_PROMPT", "false").lower() == "true":
        logger.info("Using Langfuse prompt management")
        system_prompt, prompt_obj = _get_system_prompt_from_langfuse(langfuse, user_tier, account_id, reference_date)
    else:
        logger.info("Using hardcoded prompt")
        system_prompt, prompt_obj = _create_system_prompt(user_tier, account_id, reference_date), None
    return Agent(model=model, tools=tools, system_prompt=system_prompt, session_manager=session_manager, callback_handler=lambda **_: None), prompt_obj


def chat(agent: Agent, message: str) -> ChatResponse:
    result = agent(message, structured_output_model=ChatResponse)
    return result.structured_output
