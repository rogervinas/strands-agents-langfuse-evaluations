import json
from datetime import date, timedelta

import pytest

from banking_sentinel.data import CardState, DisputeStore, Transaction, build_transactions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REF = date(2025, 1, 31)


def make_transactions():
    return build_transactions(REF)


def make_store(transactions=None):
    if transactions is None:
        transactions = make_transactions()
    return DisputeStore(transactions)


# ---------------------------------------------------------------------------
# build_transactions
# ---------------------------------------------------------------------------


class TestBuildTransactions:
    def test_returns_three_accounts(self):
        txns = make_transactions()
        assert set(txns.keys()) == {"ACC-1001", "ACC-1002", "ACC-1003"}

    def test_each_account_has_five_transactions(self):
        txns = make_transactions()
        for account_id, account_txns in txns.items():
            assert len(account_txns) == 5, f"{account_id} should have 5 transactions"

    def test_reference_date_offsets(self):
        txns = make_transactions()
        # ACC-1001 txn 1 is 20 days before REF
        assert txns["ACC-1001"][0].date == REF - timedelta(days=20)
        # ACC-1001 txn 5 is 2 days before REF
        assert txns["ACC-1001"][4].date == REF - timedelta(days=2)
        # ACC-1003 txn 1 is 30 days before REF
        assert txns["ACC-1003"][0].date == REF - timedelta(days=30)


# ---------------------------------------------------------------------------
# CardState
# ---------------------------------------------------------------------------


class TestCardState:
    def test_card_not_frozen_by_default(self):
        cs = CardState()
        assert cs.is_frozen("ACC-1001") is False

    def test_freeze_card(self):
        cs = CardState()
        cs.freeze("ACC-1001")
        assert cs.is_frozen("ACC-1001") is True

    def test_unfreeze_card(self):
        cs = CardState()
        cs.freeze("ACC-1001")
        cs.unfreeze("ACC-1001")
        assert cs.is_frozen("ACC-1001") is False

    def test_freeze_is_idempotent(self):
        cs = CardState()
        cs.freeze("ACC-1001")
        cs.freeze("ACC-1001")
        assert cs.is_frozen("ACC-1001") is True

    def test_unfreeze_when_not_frozen_is_noop(self):
        cs = CardState()
        cs.unfreeze("ACC-1001")  # should not raise
        assert cs.is_frozen("ACC-1001") is False

    def test_accounts_are_isolated(self):
        cs = CardState()
        cs.freeze("ACC-1001")
        assert cs.is_frozen("ACC-1002") is False
        assert cs.is_frozen("ACC-1003") is False


# ---------------------------------------------------------------------------
# DisputeStore.open_dispute
# ---------------------------------------------------------------------------


class TestDisputeStoreOpenDispute:
    def test_dispute_id_format(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        assert dispute.id == "DSP-ACC-1001-1"

    def test_dispute_id_counter_increments(self):
        store = make_store()
        d1 = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        d2 = store.open_dispute("ACC-1001", "TXN-ACC-1001-2", "duplicate")
        assert d1.id == "DSP-ACC-1001-1"
        assert d2.id == "DSP-ACC-1001-2"

    def test_initial_status_is_open(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        assert dispute.status == "OPEN"

    def test_amount_resolved_from_transaction(self):
        store = make_store()
        # TXN-ACC-1001-1 amount is -50.00
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        assert dispute.amount == -50.00

    def test_amount_zero_when_transaction_not_found(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-UNKNOWN-999", "fraud")
        assert dispute.amount == 0.0

    def test_fields_match_inputs(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-2", "double charge")
        assert dispute.account_id == "ACC-1001"
        assert dispute.transaction_id == "TXN-ACC-1001-2"
        assert dispute.reason == "double charge"


# ---------------------------------------------------------------------------
# DisputeStore.get_status — state machine
# ---------------------------------------------------------------------------


class TestDisputeStoreGetStatus:
    def test_unknown_dispute_returns_none(self):
        store = make_store()
        assert store.get_status("DSP-UNKNOWN") is None

    def test_open_transitions_to_pending(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        assert dispute.status == "OPEN"

        result = store.get_status(dispute.id)
        assert result is not None
        assert result.status == "PENDING"

    def test_pending_transitions_to_rejected_when_amount_above_threshold(self):
        store = make_store()
        # TXN-ACC-1001-1 amount is -50.00 → abs > 10 → REJECTED
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        store.get_status(dispute.id)  # OPEN → PENDING
        result = store.get_status(dispute.id)  # PENDING → REJECTED
        assert result is not None
        assert result.status == "REJECTED"

    def test_pending_transitions_to_accepted_when_amount_at_or_below_threshold(self):
        store = make_store()
        # TXN-ACC-1001-3 amount is -9.99 → abs <= 10 → ACCEPTED
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-3", "fraud")
        store.get_status(dispute.id)  # OPEN → PENDING
        result = store.get_status(dispute.id)  # PENDING → ACCEPTED
        assert result is not None
        assert result.status == "ACCEPTED"

    def test_terminal_status_does_not_change(self):
        store = make_store()
        dispute = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        store.get_status(dispute.id)  # OPEN → PENDING
        store.get_status(dispute.id)  # PENDING → REJECTED
        result = store.get_status(dispute.id)  # should stay REJECTED
        assert result is not None
        assert result.status == "REJECTED"


# ---------------------------------------------------------------------------
# DisputeStore.list_disputes
# ---------------------------------------------------------------------------


class TestDisputeStoreListDisputes:
    def test_empty_list_for_account_with_no_disputes(self):
        store = make_store()
        assert store.list_disputes("ACC-1001") == []

    def test_lists_disputes_for_account(self):
        store = make_store()
        d1 = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        d2 = store.open_dispute("ACC-1001", "TXN-ACC-1001-2", "duplicate")
        ids = store.list_disputes("ACC-1001")
        assert d1.id in ids
        assert d2.id in ids
        assert len(ids) == 2

    def test_filters_by_account_id(self):
        store = make_store()
        d1 = store.open_dispute("ACC-1001", "TXN-ACC-1001-1", "fraud")
        store.open_dispute("ACC-1002", "TXN-ACC-1002-1", "fraud")
        ids = store.list_disputes("ACC-1001")
        assert ids == [d1.id]
