"""Audit trail for clinicians' match decisions.

An append-only log, one JSON object per line. Every entry records who decided what, when, what
the matcher's score was at the time, and what the decision replaced. Nothing is ever edited or
deleted: undoing a decision, or resetting the demo, adds a new entry.

The log is hash-chained. Each entry stores the SHA-256 of the entry before it, plus its own hash,
so editing or deleting an earlier entry breaks the chain and `verify()` reports where. (Cutting
entries off the end can't be detected this way; a real system would also keep a copy elsewhere.)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64  # the "previous hash" of the very first entry


class AuditLog:
    def __init__(self, path: Path | None = None):
        """With no path the log lives in memory only (used by tests)."""
        self.path = path
        self.events: list[dict] = []
        if path and path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            self.events = [json.loads(line) for line in lines if line.strip()]

    def record_review(self, record_a: str, record_b: str, same_person: bool, *, reviewer: str,
                      score: float, previous: bool | None, note: str | None = None,
                      username: str | None = None) -> dict:
        return self._append({
            "action": "review",
            "reviewer": reviewer,
            "username": username,
            "record_a": record_a,
            "record_b": record_b,
            "decision": _decision(same_person),
            "previous": None if previous is None else _decision(previous),
            "score": score,
            "note": note,
        })

    def record_reset(self, reviewer: str, username: str | None = None) -> dict:
        """Clears every decision before this point, without deleting them from the log."""
        return self._append({"action": "reset", "reviewer": reviewer, "username": username})

    def record_access(self, action: str, record_ids: list[str], *, reviewer: str,
                      username: str | None = None, reason: str | None = None) -> dict:
        """Someone opened a patient ("view") or unmasked their contact details ("reveal")."""
        return self._append({"action": action, "reviewer": reviewer, "username": username,
                             "records": list(record_ids), "reason": reason})

    def current_reviews(self) -> dict[frozenset[str], bool]:
        """Replay the log: the latest decision for each pair since the last reset (True = same).

        Only the trusted part is replayed. If an entry fails the hash check, it and everything
        after it are ignored, so a forged or edited decision never changes a patient's record.
        """
        broken = self._first_broken()
        trusted = self.events if broken is None else self.events[:broken]
        reviews: dict[frozenset[str], bool] = {}
        for event in trusted:
            if event["action"] == "reset":
                reviews.clear()
            elif event["action"] == "review":
                reviews[frozenset((event["record_a"], event["record_b"]))] = event["decision"] == "same"
        return reviews

    def verify(self) -> int | None:
        """The `seq` of the first entry that breaks the hash chain, or None if the log is intact."""
        broken = self._first_broken()
        return None if broken is None else self.events[broken].get("seq", broken + 1)

    def _first_broken(self) -> int | None:
        previous = GENESIS
        for i, event in enumerate(self.events):
            if event.get("prev_hash") != previous or _digest(event) != event.get("hash"):
                return i
            previous = event["hash"]
        return None

    def _append(self, fields: dict) -> dict:
        event = {
            "seq": len(self.events) + 1,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **fields,
            "prev_hash": self.events[-1]["hash"] if self.events else GENESIS,
        }
        event["hash"] = _digest(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        self.events.append(event)
        return event


def _decision(same_person: bool) -> str:
    return "same" if same_person else "different"


def _digest(event: dict) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
