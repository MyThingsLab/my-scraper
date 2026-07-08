from __future__ import annotations

import pytest

from myscraper.fetcher import fetch, strip_html


def test_strip_html_drops_script_style_nav_footer() -> None:
    html = (
        "<html><head><style>.a{}</style></head><body>"
        "<nav>menu</nav><p>Hello <b>world</b></p>"
        "<script>evil()</script><footer>bye</footer></body></html>"
    )
    assert strip_html(html) == "Hello world"


def test_strip_html_collapses_whitespace() -> None:
    assert strip_html("<p>a\n\n  b\t c</p>") == "a b c"


def test_fetch_returns_cleaned_text_on_success() -> None:
    result = fetch(
        "https://example.com/page",
        get=lambda url: "<p>Price: $9</p>",
        robots_allowed=lambda url, ua: True,
    )
    assert result.ok
    assert result.text == "Price: $9"


def test_fetch_skips_when_robots_disallow() -> None:
    calls: list[str] = []
    result = fetch(
        "https://example.com/page",
        get=lambda url: calls.append(url) or "<p>x</p>",  # type: ignore[func-returns-value]
        robots_allowed=lambda url, ua: False,
    )
    assert not result.ok
    assert result.reason == "robots_disallowed"
    assert calls == []


def test_fetch_skips_on_fetch_error() -> None:
    def _raise(url: str) -> str:
        raise OSError("boom")

    result = fetch("https://example.com/page", get=_raise, robots_allowed=lambda url, ua: True)
    assert not result.ok
    assert result.reason == "fetch_error"


def test_fetch_skips_on_empty_text() -> None:
    result = fetch(
        "https://example.com/page",
        get=lambda url: "<script>only()</script>",
        robots_allowed=lambda url, ua: True,
    )
    assert not result.ok
    assert result.reason == "empty"


@pytest.mark.slow
def test_fetch_over_real_network() -> None:
    result = fetch("https://example.com/")
    assert result.ok
    assert "Example Domain" in result.text

