# my-scraper — agent instructions

You are developing **my-scraper**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** given a URL and a question, fetch the page deterministically and
  extract structured data answering the question (`myscraper extract`). One URL
  in, one structured record out — no discovery, no crawling, no corpus.
- **The single Engine call:** "given this page's cleaned, size-capped text and a
  question, extract structured data answering it" — replies with
  `{answer, fields, confidence, quote}`. `quote` must be a verbatim substring of
  the fetched text; a quote that doesn't appear in the source is dropped and
  `confidence` forced to `"low"`. Against `NoopEngine`: no extraction — emits
  the raw cleaned text verbatim as `fields.raw_text`.
- **Invariants / rules:**
  - All network is deterministic, stdlib-only HTTP/HTML
    (`urllib.request`, `urllib.robotparser`, `html.parser`) — no new runtime
    SDK, stays outside the one-Engine-call contract. Mocked in the default test
    suite; any real-network test is `@pytest.mark.slow`.
  - **Never crawls.** One URL per invocation, no link-following.
  - `robots.txt` is checked before fetching; a disallow skips the fetch and the
    Engine call (`outcome=skipped`) — never bypassed or spoofed around.
  - **No `Workspace`, no PR.** Read-only utility: output to stdout (`--json`)
    and, if `--issue` is given, an optional issue comment via
    `Action(kind="bash", ...)` routed through `Policy.evaluate()`. Never commits
    to a repo.
  - Stateless: each run is independent, no cross-run corpus, writes exactly one
    `kind=scrape` ledger entry per run.
- **Backlog label:** `my-scraper`.

See the design plan for full detail:
[`my-things-core/docs/tools/my-scraper.md`](../my-things-core/docs/tools/my-scraper.md).
