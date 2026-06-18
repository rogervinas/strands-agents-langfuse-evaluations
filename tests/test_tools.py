import json
from datetime import date

import pytest

from banking_sentinel.data import CardState, DisputeStore, build_transactions
from banking_sentinel.tools import create_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REF = date(2025, 1, 31)


def make_tools(card_state=None, dispute_store=None, transactions=None, reference_date=None):
    if transactions is None:
        transactions = build_transactions(REF)
    if card_state is None:
        card_state = CardState()
    if dispute_store is None:
        dispute_store = DisputeStore(transactions)
    if reference_date is None:
        reference_date = REF
    return create_tools(card_state, dispute_store, transactions, reference_date)


def named(tools):
    """Return a dict of tool name → tool for easier lookup."""
    return {t.tool_name: t for t in tools}


# ---------------------------------------------------------------------------
# freeze_card / unfreeze_card / is_card_frozen
# ---------------------------------------------------------------------------


class TestCardTools:
    def test_freeze_card_returns_frozen_status(self):
        tools = named(make_tools())
        result = json.loads(tools["freeze_card"]("ACC-1001", "lost card"))
        assert result["account_id"] == "ACC-1001"
        assert result["status"] == "frozen"
        assert result["reason"] == "lost card"

    def test_is_card_frozen_reflects_freeze(self):
        cs = CardState()
        tools = named(make_tools(card_state=cs))
        tools["freeze_card"]("ACC-1001", "fraud")
        result = json.loads(tools["is_card_frozen"]("ACC-1001"))
        assert result["frozen"] is True

    def test_unfreeze_card_returns_unfrozen_status(self):
        cs = CardState()
        tools = named(make_tools(card_state=cs))
        tools["freeze_card"]("ACC-1001", "precaution")
        result = json.loads(tools["unfreeze_card"]("ACC-1001"))
        assert result["account_id"] == "ACC-1001"
        assert result["status"] == "unfrozen"

    def test_is_card_frozen_reflects_unfreeze(self):
        cs = CardState()
        tools = named(make_tools(card_state=cs))
        tools["freeze_card"]("ACC-1001", "precaution")
        tools["unfreeze_card"]("ACC-1001")
        result = json.loads(tools["is_card_frozen"]("ACC-1001"))
        assert result["frozen"] is False

    def test_card_not_frozen_by_default(self):
        tools = named(make_tools())
        result = json.loads(tools["is_card_frozen"]("ACC-1001"))
        assert result["frozen"] is False


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------


class TestGetTransactions:
    def test_returns_transactions_within_date_range_inclusive(self):
        tools = named(make_tools())
        # ACC-1001 has txns at REF-20, REF-15, REF-6, REF-4, REF-2
        # Query REF-6 to REF-2 should return 3 transactions
        date_from = (REF - _days(6)).isoformat()
        date_to = REF.isoformat()
        result = json.loads(tools["get_transactions"]("ACC-1001", date_from, date_to))
        assert result["account_id"] == "ACC-1001"
        assert len(result["transactions"]) == 3

    def test_excludes_transactions_outside_range(self):
        tools = named(make_tools())
        # Only the REF-2 transaction
        date_from = (REF - _days(2)).isoformat()
        date_to = REF.isoformat()
        result = json.loads(tools["get_transactions"]("ACC-1001", date_from, date_to))
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["merchant"] == "Employer Inc."

    def test_returns_empty_list_when_no_transactions_in_range(self):
        tools = named(make_tools())
        # Far future range — no transactions
        date_from = (REF + _days(10)).isoformat()
        date_to = (REF + _days(20)).isoformat()
        result = json.loads(tools["get_transactions"]("ACC-1001", date_from, date_to))
        assert result["transactions"] == []

    def test_returns_empty_list_for_unknown_account(self):
        tools = named(make_tools())
        result = json.loads(tools["get_transactions"]("ACC-9999", "2025-01-01", "2025-01-31"))
        assert result["account_id"] == "ACC-9999"
        assert result["transactions"] == []

    def test_transaction_shape(self):
        tools = named(make_tools())
        date_from = (REF - _days(2)).isoformat()
        date_to = REF.isoformat()
        result = json.loads(tools["get_transactions"]("ACC-1001", date_from, date_to))
        txn = result["transactions"][0]
        assert set(txn.keys()) == {"id", "date", "amount", "merchant", "category"}


# ---------------------------------------------------------------------------
# open_dispute / get_dispute_status / list_disputes
# ---------------------------------------------------------------------------


class TestDisputeTools:
    def test_open_dispute_json_shape(self):
        tools = named(make_tools())
        result = json.loads(tools["open_dispute"]("ACC-1001", "TXN-ACC-1001-1", "unauthorized"))
        assert set(result.keys()) == {"dispute_id", "account_id", "transaction_id", "amount", "reason", "status"}
        assert result["account_id"] == "ACC-1001"
        assert result["transaction_id"] == "TXN-ACC-1001-1"
        assert result["status"] == "OPEN"

    def test_get_dispute_status_not_found_returns_error(self):
        tools = named(make_tools())
        result = json.loads(tools["get_dispute_status"]("DSP-UNKNOWN"))
        assert "error" in result

    def test_get_dispute_status_returns_dispute_fields(self):
        txns = build_transactions(REF)
        cs = CardState()
        ds = DisputeStore(txns)
        tools = named(create_tools(cs, ds, txns, REF))
        opened = json.loads(tools["open_dispute"]("ACC-1001", "TXN-ACC-1001-1", "fraud"))
        result = json.loads(tools["get_dispute_status"](opened["dispute_id"]))
        assert result["dispute_id"] == opened["dispute_id"]
        assert "status" in result

    def test_list_disputes_returns_dispute_ids(self):
        txns = build_transactions(REF)
        cs = CardState()
        ds = DisputeStore(txns)
        tools = named(create_tools(cs, ds, txns, REF))
        d1 = json.loads(tools["open_dispute"]("ACC-1001", "TXN-ACC-1001-1", "fraud"))
        d2 = json.loads(tools["open_dispute"]("ACC-1001", "TXN-ACC-1001-2", "duplicate"))
        result = json.loads(tools["list_disputes"]("ACC-1001"))
        assert result["account_id"] == "ACC-1001"
        assert d1["dispute_id"] in result["dispute_ids"]
        assert d2["dispute_id"] in result["dispute_ids"]

    def test_list_disputes_filters_by_account(self):
        txns = build_transactions(REF)
        cs = CardState()
        ds = DisputeStore(txns)
        tools = named(create_tools(cs, ds, txns, REF))
        tools["open_dispute"]("ACC-1002", "TXN-ACC-1002-1", "fraud")
        result = json.loads(tools["list_disputes"]("ACC-1001"))
        assert result["dispute_ids"] == []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _days(n: int):
    from datetime import timedelta
    return timedelta(days=n)
