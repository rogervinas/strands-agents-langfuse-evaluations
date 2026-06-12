import logging
import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langfuse import get_client, propagate_attributes
from pydantic import BaseModel
from strands.session.file_session_manager import FileSessionManager

logger = logging.getLogger("uvicorn.error")

load_dotenv()
langfuse = get_client()
logger.info("Model provider: %s", os.getenv("MODEL_PROVIDER", "ollama"))

from banking_sentinel.agent import create_model, create_sentinel_agent, chat
from banking_sentinel.data import CardState, DisputeStore, Transaction, build_transactions
from banking_sentinel.models import ChatResponse
from banking_sentinel.tools import create_tools

app = FastAPI()

_model = create_model()


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


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
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
    tools = create_tools(state.card_state, state.dispute_store, state.transactions, state.reference_date)
    session_manager = FileSessionManager(session_id=session_id, storage_dir="sessions")
    agent = create_sentinel_agent(_model, tools, state.user_tier, request.account_id, state.reference_date, session_manager=session_manager)

    with propagate_attributes(user_id=request.user_id, session_id=session_id, trace_name="chat", tags=["banking-sentinel"]):
        return chat(agent, request.message)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
