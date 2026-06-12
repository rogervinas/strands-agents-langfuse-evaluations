import logging
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from langfuse import get_client
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

load_dotenv()
langfuse = get_client()
logger.info("Model provider: %s", os.getenv("MODEL_PROVIDER", "ollama"))

from banking_sentinel.agent import create_model, create_sentinel_agent, chat
from banking_sentinel.data import CardState, DisputeStore, build_transactions
from banking_sentinel.models import ChatResponse
from banking_sentinel.tools import create_tools

app = FastAPI()

_model = create_model()
_sessions: dict[str, object] = {}


class ChatRequest(BaseModel):
    user_id: str
    account_id: str
    user_tier: str = "Standard"
    message: str


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    session_key = f"{request.user_id}:{request.account_id}"
    if session_key not in _sessions:
        reference_date = date.today()
        transactions = build_transactions(reference_date)
        card_state = CardState()
        dispute_store = DisputeStore(transactions)
        tools = create_tools(card_state, dispute_store, transactions, reference_date)
        _sessions[session_key] = create_sentinel_agent(_model, tools, request.user_tier, request.account_id, reference_date)
        logger.info("New session: %s", session_key)
    return chat(_sessions[session_key], request.message)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
