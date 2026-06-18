from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client

DATASET_NAME = "banking-sentinel-evals"

ITEMS = [
    {
        "id": "banking-sentinel-evals-unauthorized-netflix-charge",
        "input": {
            "userId": "langfuse-eval-user-1001",
            "accountId": "ACC-1001",
            "accountTier": "Standard",
            "message": "I don't have Netflix but I see a charge on my account",
        },
        "expected_output": {
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Netflix charge of 9.99 and offered the user to open a dispute",
        },
        "metadata": {"scenario": "unauthorized-netflix-charge"},
    },
    {
        "id": "banking-sentinel-evals-expired-dispute-window",
        "input": {
            "userId": "langfuse-eval-user-1002",
            "accountId": "ACC-1002",
            "accountTier": "Standard",
            "message": "I see a Best Buy charge on my account but I never bought anything there",
        },
        "expected_output": {
            "suggestedActions": ["FREEZE_CARD"],
            "claim": "The AI agent found a Best Buy charge of 200.00 and explained that the dispute window has expired because the transaction is older than 14 days",
        },
        "metadata": {"scenario": "expired-dispute-window"},
    },
]


def create_dataset():
    langfuse = get_client()

    try:
        langfuse.get_dataset(DATASET_NAME)
        print(f"Dataset '{DATASET_NAME}' already exists")
    except Exception:
        langfuse.create_dataset(name=DATASET_NAME, description="Banking sentinel evaluation dataset")
        print(f"Dataset '{DATASET_NAME}' created")

    for item in ITEMS:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=item["id"],
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item["metadata"],
        )
        print(f"  ✅ Upserted item: {item['metadata']['scenario']}")

    langfuse.flush()
    print("Done")


if __name__ == "__main__":
    create_dataset()
