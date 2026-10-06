"""Fixtures for DealCourt direct-mode tests.

`ledger` wraps the direct-mode gl_call handler so tests can assert the exact
native transfers (`EthSend`) and events (`EmitEvent`) a call produced.
"""

import json

import pytest

ESCROW = 10 * 10**18
DAY = 24 * 3600
TERMS = "Write a 1,500-word technical blog post about GenLayer's Equivalence Principle."
RUBRIC = json.dumps(
    [
        "Post is at least 1,500 words",
        "Explains leader/validator roles correctly",
        "Includes at least one runnable code example",
        "Original work, no plagiarism",
    ]
)
DELIVERABLE = "https://blog.example.com/genlayer-eq"


def to_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from genlayer.py.types import Address

    return Address(addr).as_hex


class Ledger:
    def __init__(self):
        self.transfers = []  # (address_hex, value)
        self.events = []  # blob dicts

    def clear(self):
        self.transfers.clear()
        self.events.clear()

    def paid_to(self, addr) -> int:
        h = to_hex(addr).lower()
        return sum(v for a, v in self.transfers if a.lower() == h)


@pytest.fixture
def ledger():
    import gltest.direct.wasi_mock as wm

    book = Ledger()
    original = wm._handle_gl_call

    def spy(vm, request):
        if isinstance(request, dict):
            if "EthSend" in request:
                req = request["EthSend"]
                book.transfers.append((to_hex(req["address"]), int(req["value"])))
            if "EmitEvent" in request:
                book.events.append(request["EmitEvent"]["blob"])
        return original(vm, request)

    wm._handle_gl_call = spy
    yield book
    wm._handle_gl_call = original


@pytest.fixture
def court(direct_vm, direct_deploy):
    direct_vm.warp("2030-01-01T00:00:00Z")
    return direct_deploy("contracts/deal_court.py")


def make_deal(vm, court, client, provider, escrow=ESCROW):
    vm.sender = client
    vm.value = escrow
    deal_id = court.create_deal(to_hex(provider), "Blog post", TERMS, RUBRIC, 7 * DAY, 3 * DAY)
    vm.value = 0
    return deal_id


def active_delivered(vm, court, client, provider):
    deal_id = make_deal(vm, court, client, provider)
    vm.sender = provider
    court.accept_deal(deal_id)
    court.deliver(deal_id, DELIVERABLE, "Draft attached, 1,620 words.")
    return deal_id


def mock_ruling(vm, share, met=3, pattern=r"neutral arbitrator"):
    criteria = [{"criterion": i + 1, "met": i < met} for i in range(4)]
    vm.mock_llm(
        pattern,
        json.dumps(
            {
                "criteria": criteria,
                "provider_share": share,
                "violations": [] if share > 50 else ["missing code example"],
                "reasoning": f"Provider earned {share}%.",
            }
        ),
    )


def mock_docs(vm):
    vm.mock_web(r"blog\.example\.com", {"status": 200, "body": "GenLayer EQ post ... 1620 words"})
    vm.mock_web(r"evidence\.example\.com", {"status": 200, "body": "Screenshot transcript"})
