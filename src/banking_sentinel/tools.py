import json
from datetime import date

from strands import tool

from banking_sentinel.data import CardState, DisputeStore, Transaction


def create_tools(card_state: CardState, dispute_store: DisputeStore, transactions: dict[str, list[Transaction]], reference_date: date):

    @tool
    def freeze_card(account_id: str, reason: str) -> str:
        """Freeze the card associated with an account."""
        card_state.freeze(account_id)
        return json.dumps({"account_id": account_id, "status": "frozen", "reason": reason})

    @tool
    def unfreeze_card(account_id: str) -> str:
        """Unfreeze the card associated with an account."""
        card_state.unfreeze(account_id)
        return json.dumps({"account_id": account_id, "status": "unfrozen"})

    @tool
    def is_card_frozen(account_id: str) -> str:
        """Check if the card associated with an account is frozen."""
        return json.dumps({"account_id": account_id, "frozen": card_state.is_frozen(account_id)})

    @tool
    def get_transactions(account_id: str, date_from: str, date_to: str) -> str:
        """Retrieve transactions for an account between two dates (YYYY-MM-DD)."""
        from_date = date.fromisoformat(date_from)
        to_date = date.fromisoformat(date_to)
        results = [
            {"id": t.id, "date": t.date.isoformat(), "amount": t.amount, "merchant": t.merchant, "category": t.category}
            for t in transactions.get(account_id, [])
            if from_date <= t.date <= to_date
        ]
        return json.dumps({"account_id": account_id, "transactions": results})

    @tool
    def open_dispute(account_id: str, transaction_id: str, reason: str) -> str:
        """Open a dispute for a transaction."""
        dispute = dispute_store.open_dispute(account_id, transaction_id, reason)
        return json.dumps({"dispute_id": dispute.id, "account_id": dispute.account_id, "transaction_id": dispute.transaction_id, "amount": dispute.amount, "reason": dispute.reason, "status": dispute.status})

    @tool
    def get_dispute_status(dispute_id: str) -> str:
        """Check the status of a dispute."""
        dispute = dispute_store.get_status(dispute_id)
        if dispute is None:
            return json.dumps({"error": f"Dispute {dispute_id} not found"})
        return json.dumps({"dispute_id": dispute.id, "account_id": dispute.account_id, "transaction_id": dispute.transaction_id, "amount": dispute.amount, "reason": dispute.reason, "status": dispute.status})

    @tool
    def list_disputes(account_id: str) -> str:
        """List all dispute IDs for an account."""
        return json.dumps({"account_id": account_id, "dispute_ids": dispute_store.list_disputes(account_id)})

    return [freeze_card, unfreeze_card, is_card_frozen, get_transactions, open_dispute, get_dispute_status, list_disputes]
