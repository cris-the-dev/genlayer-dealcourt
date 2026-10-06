"""Integration tests against Studio / localnet (real consensus).

    gltest tests/integration/ -v -s
"""

import json

import pytest
from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded

DAY = 24 * 3600
ESCROW = 10**15
TERMS = "Publish a short public web page that explains what an Intelligent Contract is."
RUBRIC = json.dumps(["Page is publicly reachable", "Explains Intelligent Contracts accurately"])


def _setup():
    court = get_contract_factory("DealCourt").deploy(args=[])
    accounts = get_accounts()
    client, provider = accounts[0], accounts[1]
    assert tx_execution_succeeded(
        court.create_deal(args=[provider.address, "Explainer", TERMS, RUBRIC, 7 * DAY, DAY]).transact(
            value=ESCROW
        )
    )
    as_provider = court.connect(provider)
    assert tx_execution_succeeded(as_provider.accept_deal(args=[0]).transact())
    return court, as_provider


@pytest.mark.integration
def test_happy_path_without_ai():
    court, as_provider = _setup()
    assert tx_execution_succeeded(
        as_provider.deliver(args=[0, "https://example.com", "Delivered"]).transact()
    )
    assert tx_execution_succeeded(court.approve(args=[0]).transact())
    assert court.get_deal(args=[0]).call()["status"] == "SETTLED"


@pytest.mark.integration
def test_dispute_is_adjudicated_by_validators():
    court, as_provider = _setup()
    as_provider.deliver(args=[0, "https://example.com", "Delivered"]).transact()
    court.open_dispute(args=[0, "The page does not explain Intelligent Contracts at all.", "[]"]).transact()
    as_provider.submit_evidence(args=[0, "The page is live and public as agreed.", "[]"]).transact()

    receipt = court.adjudicate(args=[0]).transact(wait_interval=10_000, wait_retries=30)
    assert tx_execution_succeeded(receipt)
    deal = court.get_deal(args=[0]).call()
    assert deal["status"] == "RULED"
    # example.com says nothing about Intelligent Contracts: expect a low share.
    assert deal["ruling_1"]["provider_share_bps"] <= 6000


@pytest.mark.integration
def test_outsider_cannot_dispute():
    court, _ = _setup()
    outsider = court.connect(get_accounts()[2])
    assert tx_execution_failed(outsider.open_dispute(args=[0, "I am not part of this deal", "[]"]).transact())
