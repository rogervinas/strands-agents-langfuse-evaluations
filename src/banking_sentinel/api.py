from datetime import date

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from banking_sentinel.agent import create_model, create_sentinel_agent, chat
from banking_sentinel.data import CardState, DisputeStore, build_transactions
from banking_sentinel.models import ChatResponse
from banking_sentinel.tools import create_tools

app = FastAPI()


class ChatRequest(BaseModel):
    user_id: str
    account_id: str
    user_tier: str = "Standard"
    message: str


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    reference_date = date.today()
    transactions = build_transactions(reference_date)
    card_state = CardState()
    dispute_store = DisputeStore(transactions)
    tools = create_tools(card_state, dispute_store, transactions, reference_date)
    model = create_model()
    agent = create_sentinel_agent(model, tools, request.user_tier, request.account_id, reference_date)
    return chat(agent, request.message)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
