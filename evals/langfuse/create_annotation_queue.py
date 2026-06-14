"""
Create the score config and annotation queue for human review.
Idempotent — safe to run multiple times.
See: https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues
"""
from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client
from langfuse.api.commons.types.score_config_data_type import ScoreConfigDataType

SCORE_CONFIG_NAME = "quality"
QUEUE_NAME = "banking-sentinel-review"


def setup():
    langfuse = get_client()

    # Step 1: Create score config (defines what reviewers score on)
    all_configs = langfuse.api.score_configs.get()
    existing = [c for c in all_configs.data if c.name == SCORE_CONFIG_NAME]
    if existing:
        score_config = existing[0]
        print(f"Score config '{SCORE_CONFIG_NAME}' already exists (id: {score_config.id})")
    else:
        score_config = langfuse.api.score_configs.create(
            name=SCORE_CONFIG_NAME,
            data_type=ScoreConfigDataType.NUMERIC,
            min_value=0.0,
            max_value=1.0,
            description="Overall quality of the agent response (0 = poor, 1 = good)",
        )
        print(f"✅ Score config created: '{SCORE_CONFIG_NAME}' (id: {score_config.id})")

    # Step 2: Create annotation queue
    all_queues = langfuse.api.annotation_queues.list_queues()
    existing_queues = [q for q in all_queues.data if q.name == QUEUE_NAME]
    if existing_queues:
        queue = existing_queues[0]
        print(f"Queue '{QUEUE_NAME}' already exists (id: {queue.id})")
    else:
        queue = langfuse.api.annotation_queues.create_queue(
            name=QUEUE_NAME,
            description="Traces flagged for human review (e.g. negative user feedback)",
            score_config_ids=[score_config.id],
        )
        print(f"✅ Queue created: '{QUEUE_NAME}' (id: {queue.id})")

    print(f"\nAdd this to your .env:")
    print(f"ANNOTATION_QUEUE_ID={queue.id}")


if __name__ == "__main__":
    setup()