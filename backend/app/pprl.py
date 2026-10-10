"""Privacy-preserving record linkage: match patients without seeing who they are.

Each hospital turns its patients' identifiers into encrypted fingerprints *before* anything
leaves the building, using a secret key the hospitals share and the matcher never sees:

- Names (and the digits of the birth date) become Bloom filters. Every pair of neighbouring
  letters ("_m", "ma", "ar", ...) is hashed with the key into 20 of 1,000 bits. Similar names
  set mostly the same bits, so the matcher can measure how alike two names are (the Dice
  coefficient of their bits) without being able to read them.
- Exact facts (the full birth date, its year, sex, phone, ZIP) become keyed hashes
  (HMAC-SHA256): equal values give equal fingerprints, and nothing else can be learned.
- Blocking keys (see matching.py) are hashed the same way, so blocking still works.

The matcher then runs the same Fellegi-Sunter scoring as matching.py on the fingerprints.
This follows Schnell, Bachteler and Reiher (2009), the Bloom-filter method used in real
health-data linkage. Real deployments add "hardening" against frequency attacks on Bloom filters;
that is out of scope here.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Iterable

from .matching import (NICKNAMES, FieldComparison, MatchResult, Pair, _letters, _tokens,
                       blocking_keys, decide, weigh)
from .records import PatientRecord

BITS = 1000
HASHES = 20
# Hospitals would agree on a real secret out of band. This default is for the demo only.
DEMO_KEY = os.environ.get("CONSTELLATION_LINKAGE_KEY", "constellation-demo-linkage-key").encode()


@dataclass(frozen=True)
class EncodedRecord:
    """Everything the matcher gets about one record: fingerprints, never names or dates."""

    id: str
    hospital_id: str
    first: int  # Bloom filter of the (nickname-resolved) first name
    first_initial: str | None
    first_is_initial: bool
    last: int  # Bloom filter of the whole last name
    last_parts: tuple[int, ...]  # one per part of a hyphenated or multi-word last name
    dob: str | None
    dob_year: str | None
    dob_month_day: str | None  # the same for 11-02 and 02-11, so swapped dates can be spotted
    dob_digits: int  # Bloom filter of the date's digits, so one-digit typos still look close
    sex: str | None
    phone: str | None
    postal_code: str | None
    blocking: frozenset[str]


# --- at the hospital

def encode(record: PatientRecord, key: bytes = DEMO_KEY) -> EncodedRecord:
    first = _letters(record.given)
    first = NICKNAMES.get(first, first)
    last_tokens = _tokens(record.family)
    dob = record.birth_date or ""
    year, month, day = (dob.split("-") + ["", "", ""])[:3] if dob else ("", "", "")
    phone = "".join(ch for ch in record.phone or "" if ch.isdigit())[-10:]
    return EncodedRecord(
        id=record.id,
        hospital_id=record.hospital_id,
        first=_bloom(first, key),
        first_initial=_token("initial", first[:1], key),
        first_is_initial=len(first) == 1,
        last=_bloom("".join(last_tokens), key),
        last_parts=tuple(_bloom(t, key) for t in last_tokens if len(t) > 1),
        dob=_token("dob", dob, key),
        dob_year=_token("year", year, key),
        dob_month_day=_token("month-day", "-".join(sorted((month, day))), key) if month and day else None,
        dob_digits=_bloom(dob.replace("-", ""), key),
        sex=_token("sex", (record.gender or "").lower(), key),
        phone=_token("phone", phone, key),
        postal_code=_token("zip", (record.postal_code or "").strip()[:5], key),
        blocking=frozenset(_token("block", k, key) for k in blocking_keys(record)),
    )


def _token(kind: str, value: str, key: bytes) -> str | None:
    if not value:
        return None
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def _bloom(text: str, key: bytes) -> int:
    """Set HASHES bits per letter pair of `text`, chosen by a keyed hash (double hashing)."""
    bits = 0
    padded = f"_{text}_"
    for i in range(len(padded) - 1):
        digest = hmac.new(key, padded[i:i + 2].encode(), hashlib.sha256).digest()
        h1, h2 = int.from_bytes(digest[:8], "big"), int.from_bytes(digest[8:16], "big") | 1
        for k in range(HASHES):
            bits |= 1 << ((h1 + k * h2) % BITS)
    return bits if text else 0


# --- at the matcher

def candidate_pairs(encoded: Iterable[EncodedRecord]) -> set[Pair]:
    """Blocking on hashed keys: the same pairs as matching.candidate_pairs, without the values."""
    blocks: dict[str, list[str]] = {}
    for record in encoded:
        for key in record.blocking:
            blocks.setdefault(key, []).append(record.id)
    pairs = set()
    for ids in blocks.values():
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                pairs.add((a, b) if a < b else (b, a))
    return pairs


def compare_encoded(a: EncodedRecord, b: EncodedRecord) -> MatchResult:
    """The same evidence as matching.compare_records, worked out from fingerprints alone."""
    return decide([
        weigh("first_name", *_first_name(a, b)),
        weigh("last_name", *_last_name(a, b)),
        weigh("birth_date", *_birth_date(a, b)),
        weigh("sex", *_same("Sex", a.sex, b.sex)),
        weigh("phone", *_same("Phone", a.phone, b.phone)),
        weigh("postal_code", *_same("ZIP", a.postal_code, b.postal_code)),
    ])


def dice(a: int, b: int) -> float:
    """How many bits two Bloom filters share, from 0 (none) to 1 (identical)."""
    total = a.bit_count() + b.bit_count()
    return 2 * (a & b).bit_count() / total if total else 0.0


def _scaled(similarity: float) -> float:
    """Dice of letter pairs is harsher than Jaro-Winkler; below 0.4 counts as unrelated.
    (0.4 had the best recall-to-review balance in `python -m app.benchmark --private`.)"""
    return max(0.0, (similarity - 0.4) / (1 - 0.4))


def _first_name(a: EncodedRecord, b: EncodedRecord) -> tuple[float | None, str | None]:
    if not a.first or not b.first:
        return None, "First name missing in one record"
    if a.first_is_initial or b.first_is_initial:
        if a.first_initial == b.first_initial:
            return 0.6, "First name is only an initial in one record"
        return 0.0, "First initials differ"
    if a.first == b.first:
        return 1.0, None
    sim = _scaled(dice(a.first, b.first))
    return sim, f"First names {'similar' if sim else 'differ'} (compared as encrypted fingerprints)"


def _last_name(a: EncodedRecord, b: EncodedRecord) -> tuple[float | None, str | None]:
    if not a.last or not b.last:
        return None, "Last name missing in one record"
    if a.last == b.last:
        return 1.0, None
    parts_a, parts_b = set(a.last_parts), set(b.last_parts)
    if parts_a and parts_b and (parts_a <= parts_b or parts_b <= parts_a):
        return 0.9, "One last name contains the other: hyphenated or married name?"
    sim = _scaled(dice(a.last, b.last))
    return sim, f"Last names {'similar' if sim else 'differ'} (compared as encrypted fingerprints)"


def _birth_date(a: EncodedRecord, b: EncodedRecord) -> tuple[float | None, str | None]:
    if not a.dob or not b.dob:
        return None, "Date of birth missing in one record"
    if a.dob == b.dob:
        return 1.0, None
    if a.dob_year == b.dob_year and a.dob_month_day == b.dob_month_day:
        return 0.8, "Date of birth has day and month swapped"
    if dice(a.dob_digits, b.dob_digits) >= 0.75:
        return 0.7, "Date of birth is very close, likely a typo"
    return 0.0, "Dates of birth differ"


def _same(label: str, a: str | None, b: str | None) -> tuple[float | None, str | None]:
    if not a or not b:
        return None, f"{label} missing in one record"
    return (1.0, None) if a == b else (0.0, f"{label} differs")


def link_privately(records: Iterable[PatientRecord], key: bytes = DEMO_KEY) -> tuple[dict, dict[Pair, MatchResult]]:
    """Encode every record (the hospitals' job), then score candidate pairs on the
    fingerprints alone (the matcher's job). Returns the encoded records by id and the scores."""
    encoded = {r.id: encode(r, key) for r in records}
    scored = {}
    for a, b in candidate_pairs(encoded.values()):
        result = compare_encoded(encoded[a], encoded[b])
        if result.tier != "non-match":
            scored[(a, b)] = result
    return encoded, scored
