from dataclasses import dataclass
from datetime import date


@dataclass
class Transaction:
    id: str
    date: date
    amount: float
    merchant: str
    category: str


@dataclass
class Dispute:
    id: str
    account_id: str
    transaction_id: str
    amount: float
    reason: str
    status: str


def build_transactions(reference_date: date) -> dict[str, list[Transaction]]:
    return {
        "ACC-1001": [
            Transaction("TXN-ACC-1001-1", reference_date - __days(20), -50.00, "Amazon", "Shopping"),
            Transaction("TXN-ACC-1001-2", reference_date - __days(15), -120.00, "Hilton Hotels", "Travel"),
            Transaction("TXN-ACC-1001-3", reference_date - __days(6), -9.99, "Netflix", "Entertainment"),
            Transaction("TXN-ACC-1001-4", reference_date - __days(4), -35.50, "Whole Foods", "Groceries"),
            Transaction("TXN-ACC-1001-5", reference_date - __days(2), 2500.00, "Employer Inc.", "Income"),
        ],
        "ACC-1002": [
            Transaction("TXN-ACC-1002-1", reference_date - __days(28), -200.00, "Best Buy", "Electronics"),
            Transaction("TXN-ACC-1002-2", reference_date - __days(21), -85.00, "Restaurant Le Fancy", "Dining"),
            Transaction("TXN-ACC-1002-3", reference_date - __days(7), -15.99, "Spotify", "Entertainment"),
            Transaction("TXN-ACC-1002-4", reference_date - __days(5), -450.00, "Delta Airlines", "Travel"),
            Transaction("TXN-ACC-1002-5", reference_date - __days(1), -62.30, "Shell Gas Station", "Transport"),
        ],
        "ACC-1003": [
            Transaction("TXN-ACC-1003-1", reference_date - __days(30), -1200.00, "Rent Payment", "Housing"),
            Transaction("TXN-ACC-1003-2", reference_date - __days(22), -75.00, "Electric Company", "Utilities"),
            Transaction("TXN-ACC-1003-3", reference_date - __days(17), -42.00, "Unknown Merchant XYZ", "Other"),
            Transaction("TXN-ACC-1003-4", reference_date - __days(6), -1200.00, "Rent Payment", "Housing"),
            Transaction("TXN-ACC-1003-5", reference_date - __days(3), 3200.00, "Freelance Client", "Income"),
        ],
    }


def __days(n: int):
    from datetime import timedelta
    return timedelta(days=n)


class CardState:
    def __init__(self):
        self._frozen: set[str] = set()

    def freeze(self, account_id: str) -> None:
        self._frozen.add(account_id)

    def unfreeze(self, account_id: str) -> None:
        self._frozen.discard(account_id)

    def is_frozen(self, account_id: str) -> bool:
        return account_id in self._frozen


class DisputeStore:
    def __init__(self, transactions: dict[str, list[Transaction]]):
        self._transactions = transactions
        self._disputes: dict[str, Dispute] = {}
        self._next_id = 1

    def open_dispute(self, account_id: str, transaction_id: str, reason: str) -> Dispute:
        dispute_id = f"DSP-{account_id}-{self._next_id}"
        self._next_id += 1
        amount = next(
            (t.amount for t in self._transactions.get(account_id, []) if t.id == transaction_id),
            0.0,
        )
        dispute = Dispute(dispute_id, account_id, transaction_id, amount, reason, "OPEN")
        self._disputes[dispute_id] = dispute
        return dispute

    def get_status(self, dispute_id: str) -> Dispute | None:
        dispute = self._disputes.get(dispute_id)
        if dispute is None:
            return None
        if dispute.status == "OPEN":
            dispute = Dispute(dispute.id, dispute.account_id, dispute.transaction_id, dispute.amount, dispute.reason, "PENDING")
            self._disputes[dispute_id] = dispute
        elif dispute.status == "PENDING":
            status = "REJECTED" if abs(dispute.amount) > 10 else "ACCEPTED"
            dispute = Dispute(dispute.id, dispute.account_id, dispute.transaction_id, dispute.amount, dispute.reason, status)
            self._disputes[dispute_id] = dispute
        return dispute

    def list_disputes(self, account_id: str) -> list[str]:
        return [d.id for d in self._disputes.values() if d.account_id == account_id]
