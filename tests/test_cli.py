from __future__ import annotations

import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, NoopEngine

from myscraper import cli
from myscraper.scraper import Result


def test_build_engine_noop_by_default() -> None:
    assert isinstance(cli.build_engine("noop"), NoopEngine)


def test_build_engine_claude_cli() -> None:
    assert isinstance(cli.build_engine("claude-cli"), ClaudeCLIEngine)


def test_extract_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    result = Result(
        outcome="success",
        url="https://example.com/x",
        question="q?",
        fields={"price": "$9"},
        answer="$9",
        confidence="high",
        detail="extracted from https://example.com/x",
    )

    class _StubScraper:
        def __init__(self, **kwargs: object) -> None:
            pass

        def extract(self, url: str, question: str, *, issue=None, comment=False) -> Result:
            return result

    monkeypatch.setattr(cli, "Scraper", _StubScraper)
    code = cli.main(
        [
            "extract",
            "--url",
            "https://example.com/x",
            "--question",
            "q?",
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
            "--json",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["fields"] == {"price": "$9"}
    assert out["answer"] == "$9"


def test_extract_prints_answer_without_json_flag(monkeypatch, tmp_path: Path, capsys) -> None:
    result = Result(
        outcome="success",
        url="https://example.com/x",
        question="q?",
        fields={},
        answer="the answer",
        detail="d",
    )

    class _StubScraper:
        def __init__(self, **kwargs: object) -> None:
            pass

        def extract(self, url: str, question: str, *, issue=None, comment=False) -> Result:
            return result

    monkeypatch.setattr(cli, "Scraper", _StubScraper)
    cli.main(
        [
            "extract",
            "--url",
            "https://example.com/x",
            "--question",
            "q?",
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
        ]
    )
    assert capsys.readouterr().out.strip() == "the answer"
