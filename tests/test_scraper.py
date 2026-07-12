from __future__ import annotations

import json
from pathlib import Path

from mythings.engine import NoopEngine
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, PolicyResult

from conftest import ScriptedEngine, fake_gh
from myscraper.scraper import Scraper


class DenyPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.DENY, reason="no", rule="test")


def _get(html: str):
    return lambda url: html


def test_extract_uses_engine_reply(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(
        json.dumps(
            {
                "answer": "$9",
                "fields": {"price": "$9"},
                "confidence": "high",
                "quote": "Price: $9",
            }
        )
    )
    scraper = Scraper(
        ledger=ledger,
        engine=engine,
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "what is the price?")
    assert result.outcome == "success"
    assert result.fields == {"price": "$9"}
    assert result.answer == "$9"
    assert result.confidence == "high"
    assert result.quote == "Price: $9"
    entries = list(ledger)
    assert entries[-1].kind == "scrape"
    assert entries[-1].data["url"] == "https://example.com/x"
    assert entries[-1].data["quote"] == "Price: $9"


def test_extract_falls_back_to_raw_text_against_noop_engine(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    scraper = Scraper(
        ledger=ledger,
        engine=NoopEngine(),
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "what is the price?")
    assert result.outcome == "success"
    assert result.fields == {"raw_text": "Price: $9"}


def test_extract_skips_engine_call_when_robots_disallow(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine("should never be called")
    scraper = Scraper(
        ledger=ledger,
        engine=engine,
        get=_get("<p>x</p>"),
        robots_allowed=lambda url, ua: False,
    )
    result = scraper.extract("https://example.com/x", "q?")
    assert result.outcome == "skipped"
    assert "robots_disallowed" in result.detail
    assert engine.calls == []
    entries = list(ledger)
    assert entries[-1].outcome == "skipped"


def test_extract_skips_engine_call_on_fetch_failure(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine("should never be called")

    def _raise(url: str) -> str:
        raise OSError("boom")

    scraper = Scraper(
        ledger=ledger, engine=engine, get=_raise, robots_allowed=lambda url, ua: True
    )
    result = scraper.extract("https://example.com/x", "q?")
    assert result.outcome == "skipped"
    assert engine.calls == []


def test_invented_quote_is_dropped_and_confidence_forced_low(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(
        json.dumps(
            {
                "answer": "$9",
                "fields": {"price": "$9"},
                "confidence": "high",
                "quote": "this text is not on the page",
            }
        )
    )
    scraper = Scraper(
        ledger=ledger,
        engine=engine,
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "what is the price?")
    assert result.confidence == "low"
    assert result.quote == ""


def test_comment_posts_extracted_record_when_requested(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = fake_gh()
    scraper = Scraper(
        ledger=ledger,
        repo="owner/name",
        runner=fake,
        engine=NoopEngine(),
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?", issue=5, comment=True)
    assert result.comment_url is not None
    assert fake.calls[0][:2] == ["issue", "comment"]


def test_comment_policy_sees_full_gh_command(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = fake_gh()

    class CapturePolicy:
        def __init__(self) -> None:
            self.actions: list[Action] = []

        def evaluate(self, action: Action) -> PolicyResult:
            self.actions.append(action)
            return PolicyResult(Decision.ALLOW, reason="ok", rule="test")

    policy = CapturePolicy()
    scraper = Scraper(
        ledger=ledger,
        repo="owner/name",
        runner=fake,
        engine=NoopEngine(),
        policy=policy,
        get=_get("<p>x</p>"),
        robots_allowed=lambda url, ua: True,
    )
    scraper.extract("https://example.com/x", "q?", issue=5, comment=True)
    command = policy.actions[0].payload["command"]
    assert "--repo owner/name" in command
    assert "--body" in command


def test_comment_skipped_without_issue(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    scraper = Scraper(
        ledger=ledger,
        repo="owner/name",
        engine=NoopEngine(),
        get=_get("<p>x</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?", comment=True)
    assert result.comment_url is None


def test_comment_skipped_without_repo(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    scraper = Scraper(
        ledger=ledger,
        engine=NoopEngine(),
        get=_get("<p>x</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?", issue=5, comment=True)
    assert result.comment_url is None


def test_comment_denied_by_policy_is_not_posted(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = fake_gh()
    scraper = Scraper(
        ledger=ledger,
        repo="owner/name",
        runner=fake,
        engine=NoopEngine(),
        policy=DenyPolicy(),
        get=_get("<p>x</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?", issue=5, comment=True)
    assert result.comment_url is None
    assert fake.calls == []


def test_json_but_non_dict_engine_reply_falls_back_to_raw_text(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    scraper = Scraper(
        ledger=ledger,
        engine=ScriptedEngine(json.dumps(["not", "a", "dict"])),
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?")
    assert result.fields == {"raw_text": "Price: $9"}


def test_non_json_engine_reply_falls_back_to_raw_text(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    scraper = Scraper(
        ledger=ledger,
        engine=ScriptedEngine("not json"),
        get=_get("<p>Price: $9</p>"),
        robots_allowed=lambda url, ua: True,
    )
    result = scraper.extract("https://example.com/x", "q?")
    assert result.fields == {"raw_text": "Price: $9"}


def test_max_chars_truncates_before_engine_prompt(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(
        json.dumps({"fields": {}, "answer": "", "confidence": "low", "quote": ""})
    )
    scraper = Scraper(
        ledger=ledger,
        engine=engine,
        get=_get("<p>" + "a" * 100 + "</p>"),
        robots_allowed=lambda url, ua: True,
        max_chars=10,
    )
    scraper.extract("https://example.com/x", "q?")
    assert engine.calls[0].context["truncated"] is True
    assert engine.calls[0].context["fetched_chars"] == 10
