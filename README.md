# my-scraper

[![CI](https://github.com/MyThingsLab/my-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-scraper/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-scraper/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-scraper) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Given a URL and a question, fetches the page and extracts structured data
answering it — a stateless, single-page utility (no discovery, no crawling,
no corpus) built for reuse by later [MyThingsLab](../my-things-core) tools
that need to pull a fact off a specific page.

## How it works

Deterministic pre-work:

1. Check `robots.txt` for the URL's origin — a disallow skips the fetch
   entirely.
2. Fetch the page over stdlib HTTP (`urllib.request`).
3. Strip HTML to visible text (stdlib `html.parser`), dropping
   `<script>`/`<style>`/`<nav>`/`<footer>` content.
4. Size-cap the cleaned text (default 20,000 chars) before it reaches the
   Engine prompt.

If the fetch and cleaning succeed, **one Engine call** turns the page text +
question into `{answer, fields, confidence, quote}` — `quote` must be a
verbatim substring of the fetched text, or it's dropped and `confidence` is
forced to `"low"`. Against `NoopEngine`, the reply is the raw cleaned text
verbatim (`fields.raw_text`) — no extraction, same honest degrade as
MyResearcher/MyKnowledger.

No `Workspace` worktree — read-only, no edits, no PR. The only side effect is
an optional `--comment`, which posts the extracted record to a GitHub issue as
`Action(kind="bash", ...)` routed through `Policy` (`ALLOW` by default).
Writes exactly one `kind=scrape` ledger entry per run.

## Usage

```bash
myscraper extract --url https://example.com/product --question "price and availability" --json
myscraper extract --url https://example.com/post --question "author and date" --issue 12 --comment
```

## In the fleet loop

Standalone today (no other tool calls it yet) — a building block designed per
the [design doc](../my-things-core/docs/tools/my-scraper.md). See the
[org README](../README.md) for how the shipped tools chain together.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
