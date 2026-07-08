from __future__ import annotations

import argparse
import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.ledger import Ledger

from myscraper.scraper import Scraper

_ENGINE_NAMES = ("noop", "claude-cli")


def build_engine(name: str, *, model: str | None = None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return NoopEngine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="myscraper",
        description="Given a URL and a question, fetch the page and extract structured data.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract = sub.add_parser("extract", help="extract structured data from one page")
    extract.add_argument("--url", required=True)
    extract.add_argument("--question", required=True)
    extract.add_argument("--repo", help="GitHub slug owner/name, needed for --comment")
    extract.add_argument("--issue", type=int, help="issue to comment on with --comment")
    extract.add_argument(
        "--comment", action="store_true", help="also post the extracted record to the issue"
    )
    extract.add_argument("--max-chars", type=int, default=20_000)
    extract.add_argument("--json", action="store_true")
    extract.add_argument("--ledger", type=Path, default=Path(".mythings/ledger.jsonl"))
    extract.add_argument("--engine", choices=sorted(_ENGINE_NAMES), default="noop")
    extract.add_argument("--engine-model", help="model for --engine claude-cli")

    args = parser.parse_args(argv)
    engine = build_engine(args.engine, model=args.engine_model)

    scraper = Scraper(
        ledger=Ledger(args.ledger),
        repo=args.repo,
        engine=engine,
        max_chars=args.max_chars,
    )
    result = scraper.extract(
        args.url, args.question, issue=args.issue, comment=args.comment
    )

    if args.json:
        print(
            json.dumps(
                {
                    "outcome": result.outcome,
                    "url": result.url,
                    "question": result.question,
                    "answer": result.answer,
                    "fields": result.fields,
                    "confidence": result.confidence,
                    "detail": result.detail,
                    "comment_url": result.comment_url,
                }
            )
        )
    else:
        print(result.answer or result.detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
