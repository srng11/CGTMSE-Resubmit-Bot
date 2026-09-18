"""Offline checks — no portal, no Playwright."""

from __future__ import annotations

from bot.status import BLOCKED, CERTIFIED, FORWARDED, classify_checker_text, summary_counts
from bot.parse import merge_password_chain, split_passwords


def test_split_passwords():
    assert split_passwords("a, b, a") == ["a", "b"]
    assert split_passwords("") == []


def test_password_chain_excel_first():
    assert merge_password_chain("excel", ["fb1", "excel"]) == ["excel", "fb1"]


def test_checker_select_atleast_is_not_success():
    text = "Please select atleast one(Accepet or Reject) Certify the Content of DandU For claim to approve."
    assert classify_checker_text(text) == "no_tick"


def test_checker_approved_claims_word_alone_is_not_enough():
    assert classify_checker_text("Claim Returned By CGTMSE") == "other"


def test_checker_certified_phrase():
    assert classify_checker_text("The selected claim(s) have been approved.") == "ok"
    assert classify_checker_text("D&U has been certified successfully") == "ok"


def test_summary_does_not_lump_forwarded_with_certified():
    q = [
        {"status": FORWARDED},
        {"status": CERTIFIED},
        {"status": BLOCKED},
        {"status": "queued"},
    ]
    c = summary_counts(q)
    assert c[FORWARDED] == 1
    assert c[CERTIFIED] == 1
    assert c[BLOCKED] == 1
    assert c["queued"] == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("all offline tests passed")
