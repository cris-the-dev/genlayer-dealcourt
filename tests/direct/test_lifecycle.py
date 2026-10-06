"""Agreement, delivery and the AI-free happy paths."""

from tests.direct.conftest import (
    DAY,
    DELIVERABLE,
    ESCROW,
    RUBRIC,
    TERMS,
    active_delivered,
    make_deal,
    to_hex,
)


def test_create_deal_escrows(direct_vm, court, direct_alice, direct_bob, ledger):
    deal_id = make_deal(direct_vm, court, direct_alice, direct_bob)
    d = court.get_deal(deal_id)
    assert d["status"] == "PROPOSED"
    assert d["client"] == to_hex(direct_alice)
    assert d["provider"] == to_hex(direct_bob)
    assert d["amount"] == ESCROW
    assert len(d["rubric"]) == 4
    assert d["ruling_1"] is None
    assert court.get_deal_count() == 1


def test_event_indexed_fields_are_not_swapped(direct_vm, court, direct_alice, direct_bob, ledger):
    """Regression for the SDK's alphabetical binding of indexed event args."""
    make_deal(direct_vm, court, direct_alice, direct_bob)
    proposed = ledger.events[0]
    assert to_hex(proposed["client"]) == to_hex(direct_alice)
    assert to_hex(proposed["provider"]) == to_hex(direct_bob)
    assert int(proposed["deal_id"]) == 0
    assert proposed["amount"] == ESCROW


def test_create_validation(direct_vm, court, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    p = to_hex(direct_bob)
    with direct_vm.expect_revert("Escrow must be greater than zero"):
        court.create_deal(p, "t", TERMS, RUBRIC, DAY, DAY)
    direct_vm.value = ESCROW
    with direct_vm.expect_revert("Invalid provider"):
        court.create_deal(to_hex(direct_alice), "t", TERMS, RUBRIC, DAY, DAY)
    with direct_vm.expect_revert("Terms must be"):
        court.create_deal(p, "t", "short", RUBRIC, DAY, DAY)
    with direct_vm.expect_revert("Rubric must"):
        court.create_deal(p, "t", TERMS, "not json", DAY, DAY)
    with direct_vm.expect_revert("Rubric must have 1-8"):
        court.create_deal(p, "t", TERMS, "[]", DAY, DAY)
    with direct_vm.expect_revert("Periods must be"):
        court.create_deal(p, "t", TERMS, RUBRIC, 60, DAY)


def test_only_provider_accepts_and_delivers(direct_vm, court, direct_alice, direct_bob, direct_charlie):
    deal_id = make_deal(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Not authorised"):
        court.accept_deal(deal_id)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("expected ACTIVE"):
        court.deliver(deal_id, DELIVERABLE, "")
    court.accept_deal(deal_id)
    with direct_vm.expect_revert("http(s)"):
        court.deliver(deal_id, "ipfs://abc", "")
    court.deliver(deal_id, DELIVERABLE, "done")
    d = court.get_deal(deal_id)
    assert d["status"] == "DELIVERED"
    assert d["review_deadline"] > 0


def test_withdraw_unaccepted_proposal(direct_vm, court, direct_alice, direct_bob, ledger):
    deal_id = make_deal(direct_vm, court, direct_alice, direct_bob)
    court.withdraw_proposal(deal_id)
    assert court.get_deal(deal_id)["status"] == "REFUNDED"
    assert ledger.paid_to(direct_alice) == ESCROW


def test_client_approval_pays_provider(direct_vm, court, direct_alice, direct_bob, ledger):
    deal_id = active_delivered(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    court.approve(deal_id)
    assert court.get_deal(deal_id)["status"] == "SETTLED"
    assert ledger.paid_to(direct_bob) == ESCROW
    assert ledger.paid_to(direct_alice) == 0
    assert court.get_reputation(to_hex(direct_bob))["completed"] == 1


def test_silence_is_consent(direct_vm, court, direct_alice, direct_bob, direct_charlie, ledger):
    deal_id = active_delivered(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Review window still open"):
        court.release_after_review(deal_id)
    direct_vm.warp("2030-01-05T00:00:00Z")
    court.release_after_review(deal_id)
    assert ledger.paid_to(direct_bob) == ESCROW


def test_reclaim_if_never_delivered(direct_vm, court, direct_alice, direct_bob, ledger):
    deal_id = make_deal(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    court.accept_deal(deal_id)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Delivery deadline not reached"):
        court.reclaim_undelivered(deal_id)
    direct_vm.warp("2030-01-09T00:00:00Z")
    court.reclaim_undelivered(deal_id)
    assert court.get_deal(deal_id)["status"] == "REFUNDED"
    assert ledger.paid_to(direct_alice) == ESCROW
    # A provider who accepted and then missed delivery takes a reputation hit.
    assert court.get_reputation(to_hex(direct_bob))["disputes_lost"] == 1


def test_late_delivery_rejected(direct_vm, court, direct_alice, direct_bob):
    deal_id = make_deal(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    court.accept_deal(deal_id)
    direct_vm.warp("2030-01-09T00:00:00Z")
    with direct_vm.expect_revert("Delivery deadline passed"):
        court.deliver(deal_id, DELIVERABLE, "")


def test_mutual_settlement_needs_identical_proposals(direct_vm, court, direct_alice, direct_bob, ledger):
    deal_id = active_delivered(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    assert court.propose_settlement(deal_id, 6000) is False
    direct_vm.sender = direct_bob
    assert court.propose_settlement(deal_id, 8000) is False
    assert court.get_proposal(deal_id, "provider") == 8000
    direct_vm.sender = direct_alice
    assert court.propose_settlement(deal_id, 8000) is True

    assert court.get_deal(deal_id)["status"] == "SETTLED"
    assert ledger.paid_to(direct_bob) == ESCROW * 8 // 10
    assert ledger.paid_to(direct_alice) == ESCROW * 2 // 10

    with direct_vm.expect_revert("Nothing to settle"):
        court.propose_settlement(deal_id, 5000)  # already settled


def test_outsider_cannot_propose(direct_vm, court, direct_alice, direct_bob, direct_charlie):
    deal_id = active_delivered(direct_vm, court, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Not a party"):
        court.propose_settlement(deal_id, 5000)


def test_split_has_no_dust(direct_vm, court, direct_alice, direct_bob, ledger):
    direct_vm.sender = direct_alice
    direct_vm.value = 1_000_003  # not divisible by 10_000
    deal_id = court.create_deal(to_hex(direct_bob), "odd", TERMS, RUBRIC, DAY * 2, DAY)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    court.accept_deal(deal_id)
    court.deliver(deal_id, DELIVERABLE, "")
    court.propose_settlement(deal_id, 3333)
    direct_vm.sender = direct_alice
    court.propose_settlement(deal_id, 3333)
    assert ledger.paid_to(direct_bob) + ledger.paid_to(direct_alice) == 1_000_003
