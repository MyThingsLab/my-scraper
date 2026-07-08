from __future__ import annotations

import re
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

USER_AGENT = "MyScraper/0.1 (+https://github.com/MyThingsLab/my-scraper)"

# A Getter takes a URL and returns the raw response body as text, or raises.
# The default shells out to urllib; tests inject a fake so the network is the
# only thing mocked (same pattern as github.Runner/_gh and engine.Runner).
Getter = Callable[[str], str]

# A RobotsChecker takes (url, user_agent) and returns whether fetching is
# allowed. The default fetches robots.txt over urllib; tests inject a fake.
RobotsChecker = Callable[[str, str], bool]

_SKIP_TAGS = {"script", "style", "nav", "footer"}


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    # set when ok is False: "robots_disallowed" | "fetch_error" | "empty"
    reason: str = ""
    text: str = ""


def _default_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _default_robots_allowed(url: str, user_agent: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except OSError:
        # robots.txt unreachable -- default to allowed, don't punish a site
        # that has none rather than one that explicitly disallows us.
        return True
    return parser.can_fetch(user_agent, url)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        return " ".join(self._chunks)


def strip_html(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return re.sub(r"\s+", " ", extractor.text()).strip()


def fetch(
    url: str,
    *,
    get: Getter = _default_get,
    robots_allowed: RobotsChecker = _default_robots_allowed,
    user_agent: str = USER_AGENT,
) -> FetchResult:
    if not robots_allowed(url, user_agent):
        return FetchResult(ok=False, reason="robots_disallowed")
    try:
        html = get(url)
    except (urllib.error.URLError, OSError, ValueError):
        return FetchResult(ok=False, reason="fetch_error")
    text = strip_html(html)
    if not text:
        return FetchResult(ok=False, reason="empty")
    return FetchResult(ok=True, text=text)
