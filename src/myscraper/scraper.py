from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mythings.engine import Engine, EngineRequest, NoopEngine
from mythings.github import Runner, _gh
from mythings.isolation import in_github_actions
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Decision, Policy, PolicyResult

from myscraper.fetcher import Getter, RobotsChecker, _default_get, _default_robots_allowed, fetch

_ENGINE_SYSTEM = (
    "You extract structured data from a web page's text to answer a question. "
    'Reply with only a JSON object: {"answer": str, "fields": {...}, '
    '"confidence": "high"|"low", "quote": str}. The quote must be a verbatim '
    "substring of the given page text -- never invent one."
)

_DEFAULT_MAX_CHARS = 20_000


class _AllowPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


@dataclass(frozen=True)
class Result:
    outcome: str  # success | skipped
    url: str
    question: str
    fields: dict[str, Any]
    answer: str = ""
    confidence: str = ""
    quote: str = ""
    detail: str = ""
    comment_url: str | None = None


class Scraper:
    def __init__(
        self,
        *,
        ledger: Ledger,
        repo: str | None = None,
        runner: Runner = _gh,
        engine: Engine | None = None,
        policy: Policy | None = None,
        get: Getter = _default_get,
        robots_allowed: RobotsChecker = _default_robots_allowed,
        max_chars: int = _DEFAULT_MAX_CHARS,
    ) -> None:
        self.ledger = ledger
        self.repo = repo
        self.runner = runner
        self.engine: Engine = engine or NoopEngine()
        self.policy: Policy = policy or _AllowPolicy()
        self._get = get
        self._robots_allowed = robots_allowed
        self.max_chars = max_chars

    def extract(
        self,
        url: str,
        question: str,
        *,
        issue: int | None = None,
        comment: bool = False,
    ) -> Result:
        fetched = fetch(url, get=self._get, robots_allowed=self._robots_allowed)
        if not fetched.ok:
            result = Result(
                outcome="skipped",
                url=url,
                question=question,
                fields={},
                detail=f"skipped: {fetched.reason}",
            )
            self._record(result)
            return result

        text = fetched.text
        truncated = len(text) > self.max_chars
        if truncated:
            text = text[: self.max_chars]

        reply = self._extract(text, question, url, truncated)
        comment_url = self._comment(issue, url, reply) if comment else None

        result = Result(
            outcome="success",
            url=url,
            question=question,
            fields=reply["fields"],
            answer=reply["answer"],
            confidence=reply["confidence"],
            quote=reply.get("quote", ""),
            detail=f"extracted from {url}",
            comment_url=comment_url,
        )
        self._record(result)
        return result

    def _extract(self, text: str, question: str, url: str, truncated: bool) -> dict[str, Any]:
        prompt = f"Question: {question}\n\nPage text:\n{text}"
        reply = self.engine.run(
            EngineRequest(
                prompt=prompt,
                system=_ENGINE_SYSTEM,
                context={"url": url, "fetched_chars": len(text), "truncated": truncated},
            )
        )
        parsed = _parse_reply(reply.text, text)
        if parsed is not None:
            return parsed
        return {"answer": "", "fields": {"raw_text": text}, "confidence": ""}

    def _comment(self, issue: int | None, url: str, reply: dict[str, Any]) -> str | None:
        if self.repo is None or issue is None:
            return None
        body = f"Extracted from {url}:\n\n```json\n{json.dumps(reply, indent=2)}\n```"
        argv = ["issue", "comment", str(issue), "--repo", self.repo, "--body", body]
        action = Action(kind="bash", payload={"command": "gh " + " ".join(argv)})
        decision = self.policy.evaluate(action).under(unattended=in_github_actions())
        if decision is not Decision.ALLOW:
            return None
        return self.runner(argv).strip() or None

    def _record(self, result: Result) -> None:
        self.ledger.record(
            tool="myscraper",
            kind="scrape",
            outcome=result.outcome,
            detail=result.detail,
            url=result.url,
            question=result.question,
            fields=result.fields,
            quote=result.quote,
            comment_url=result.comment_url,
        )


def _parse_reply(text: str, source_text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    fields = obj.get("fields")
    fields = fields if isinstance(fields, dict) else {}
    answer = obj.get("answer") if isinstance(obj.get("answer"), str) else ""
    confidence = obj.get("confidence")
    confidence = confidence if confidence in ("high", "low") else "low"
    quote = obj.get("quote") if isinstance(obj.get("quote"), str) else ""

    # The model may only quote verbatim from the fetched text -- an invented
    # quote is dropped and confidence forced down, never trusted silently.
    if quote and quote not in source_text:
        quote = ""
        confidence = "low"

    return {"answer": answer, "fields": fields, "confidence": confidence, "quote": quote}
