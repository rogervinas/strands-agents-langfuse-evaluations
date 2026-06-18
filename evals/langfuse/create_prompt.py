"""
Create or update the banking sentinel system prompt in Langfuse.
Each run creates a new version — use this to iterate on the prompt without redeploying.
The 'production' label marks the version fetched at runtime.
See: https://langfuse.com/docs/prompt-management/get-started
"""
from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client

from banking_sentinel.knowledge_base import KNOWLEDGE_BASE

PROMPT_NAME = "banking-sentinel-system"

# Same prompt as agent.py but using Langfuse {{variable}} syntax (Mustache)
PROMPT_TEMPLATE = """
You are the "Sentinel," a secure banking assistant for ROGERVINAS bank.

### MISSION:
Provide accurate account support and perform banking actions. Your answers must be grounded strictly in the retrieved context and the user's real-time account data.

### OPERATIONAL PROTOCOLS:
1. TRUTH SOURCE: Use the provided documentation for policy questions (fees, deadlines, disputes). If the context doesn't contain the answer, politely explain that you don't have that information.
2. ACTION HANDLING: Before executing any sensitive tool (like freezing a card or changing limits), summarize the action and ask for the user's explicit confirmation.
3. SECURITY: If the user indicates a lost card or fraud, prioritize offering the "Freeze Card" tool immediately.
4. DATE REASONING: When assessing deadlines (like disputes), use the "Current Date" provided below to calculate if the transaction falls within the policy window found in the retrieved documents.

### CONTEXT:
- User Tier: {{user_tier}}
- Current Date: {{current_date}}
- Account ID: {{account_id}}

{{knowledge_base}}
""".strip()


def create_prompt():
    langfuse = get_client()

    prompt = langfuse.create_prompt(
        name=PROMPT_NAME,
        prompt=PROMPT_TEMPLATE,
        labels=["production"],
        type="text",
        config={"knowledge_base": KNOWLEDGE_BASE},
        commit_message="Banking sentinel system prompt",
    )
    print(f"✅ Prompt '{PROMPT_NAME}' created (version {prompt.version})")
    print(f"   Variables: {prompt.variables}")
    print(f"   View at: http://localhost:3000 → Prompts")


if __name__ == "__main__":
    create_prompt()