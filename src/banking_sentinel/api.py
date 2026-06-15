import logging
import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langfuse import get_client, propagate_attributes
from langfuse.api.annotation_queues.types.annotation_queue_object_type import AnnotationQueueObjectType
from pydantic import BaseModel
from strands.session.file_session_manager import FileSessionManager

logger = logging.getLogger("uvicorn.error")

load_dotenv()
langfuse = get_client()
logger.info("Model provider: %s", os.getenv("MODEL_PROVIDER", "ollama"))


from banking_sentinel.agent import create_agent, create_model, chat
from banking_sentinel.data import CardState, DisputeStore, Transaction, build_transactions
from banking_sentinel.models import ChatApiResponse, ChatResponse
from banking_sentinel.tools import create_tools

app = FastAPI()

_model = create_model()
_annotation_queue_id = os.getenv("ANNOTATION_QUEUE_ID")


@dataclass
class _SessionState:
    card_state: CardState
    dispute_store: DisputeStore
    transactions: dict[str, list[Transaction]]
    reference_date: date
    user_tier: str


_tool_states: dict[str, _SessionState] = {}


class ChatRequest(BaseModel):
    user_id: str
    account_id: str
    user_tier: str = "Standard"
    session_id: str | None = None
    message: str


class FeedbackRequest(BaseModel):
    trace_id: str
    value: float  # 1.0 = thumbs up, 0.0 = thumbs down
    comment: str | None = None


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatApiResponse:
    session_id = request.session_id or f"{request.user_id}-{request.account_id}"

    if session_id not in _tool_states:
        reference_date = date.today()
        transactions = build_transactions(reference_date)
        _tool_states[session_id] = _SessionState(
            card_state=CardState(),
            dispute_store=DisputeStore(transactions),
            transactions=transactions,
            reference_date=reference_date,
            user_tier=request.user_tier,
        )
        logger.info("New session: %s", session_id)

    state = _tool_states[session_id]

    # start_as_current_observation creates a root Langfuse span with proper input/output
    # visible in annotation queues and the trace view.
    # See: https://langfuse.com/docs/sdk/python/sdk-v3
    with langfuse.start_as_current_observation(name="chat", as_type="span") as span:
        with propagate_attributes(user_id=request.user_id, session_id=session_id, trace_name="chat", tags=["banking-sentinel"]):
            tools = create_tools(state.card_state, state.dispute_store, state.transactions, state.reference_date)
            session_manager = FileSessionManager(session_id=session_id, storage_dir="sessions")
            agent, prompt_obj = create_agent(langfuse, _model, tools, state.user_tier, request.account_id, state.reference_date, session_manager=session_manager)
            response = chat(agent, request.message)
            if prompt_obj:
                langfuse.update_current_generation(prompt=prompt_obj)
        span.set_trace_io(input=request.message, output=response.answer)
        trace_id = span.trace_id
        logger.info("Chat trace_id: %s", trace_id)
        return ChatApiResponse(answer=response.answer, suggested_actions=response.suggested_actions, trace_id=trace_id)



@app.post("/feedback")
def feedback_endpoint(request: FeedbackRequest):
    logger.info("Feedback: trace_id=%s value=%s", request.trace_id, request.value)
    try:
        langfuse.create_score(
            trace_id=request.trace_id,
            name="user-feedback",
            value=request.value,
            comment=request.comment,
        )
        if request.value == 0.0 and _annotation_queue_id:
            langfuse.api.annotation_queues.create_queue_item(
                _annotation_queue_id,
                object_id=request.trace_id,
                object_type=AnnotationQueueObjectType.TRACE,
            )
            logger.info("Trace added to annotation queue: %s", request.trace_id)
        langfuse.flush()
    except Exception as e:
        logger.error("Failed to process feedback: %s", e)
        raise
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
