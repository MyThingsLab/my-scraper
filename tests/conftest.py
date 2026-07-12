from __future__ import annotations

# Shared fakes come from mythings.testing; only the comment-URL wiring is local.
from mythings.testing import FakeGh, ScriptedEngine

__all__ = ["ScriptedEngine"]


def fake_gh(comment_url: str = "https://github.com/owner/name/issues/1#comment") -> FakeGh:
    return FakeGh({("issue", "comment"): comment_url + "\n"})
