from enum import Enum

from pydantic import BaseModel, Field


class SuggestedAction(str, Enum):
    FREEZE_CARD = "FREEZE_CARD"
    UNFREEZE_CARD = "UNFREEZE_CARD"
    OPEN_DISPUTE = "OPEN_DISPUTE"
    CHECK_DISPUTE_STATUS = "CHECK_DISPUTE_STATUS"
    GET_TRANSACTIONS = "GET_TRANSACTIONS"


class ChatResponse(BaseModel):
    answer: str = Field(description="The response to the user")
    suggested_actions: list[SuggestedAction] = Field(description="Suggested next actions")


class ChatApiResponse(BaseModel):
    answer: str
    suggested_actions: list[SuggestedAction]
    trace_id: str | None = None
