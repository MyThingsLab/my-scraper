from __future__ import annotations


class FakeRunner:
    def __init__(self, comment_url: str = "https://github.com/owner/name/issues/1#comment") -> None:
        self.calls: list[list[str]] = []
        self._comment_url = comment_url

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[:2] == ["issue", "comment"]:
            return self._comment_url + "\n"
        raise AssertionError(f"unexpected gh call: {argv}")
