"""Privacy-preserving record linkage: match patients without seeing who they are.

Each hospital turns its patients' identifiers into encrypted fingerprints *before* anything
leaves the building, using a secret key the hospitals share and the matcher never sees:

- Names (and the digits of the birth date) become sets of keyed letter-pair hashes. Every pair
  of neighbouring letters ("_m", "ma", "ar", ...) is hashed with the key (HMAC-SHA256). Similar
  names share most of their hashes, so the matcher can measure how alike two names are (the Dice
  coefficient, exactly as matching.py does on the letters) without being able to read them.
- Whole values (the name as written, the birth date and its parts, sex, phone, ZIP) become
  keyed hashes too: equal values give equal fingerprints, and nothing else can be learned.
- Blocking keys (see matching.py) are hashed the same way, so blocking still works.

The matcher scores the fingerprints with the same rubric as matching.py (rubric.py), and gets
exactly the same levels and points for every pair, because every fact it needs has an exact
fingerprint equivalent. This is the keyed q-gram approach to privacy-preserving linkage; Bloom
filters (Schnell, Bachteler and Reiher, 2009) are a common variant that blurs the hashes further
at the cost of exactness. Real deployments add hardening against frequency attacks on letter-pair
fingerprints; that is out of scope here.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Iterable

from .matching import (NICKNAMES, Pair, _letters, _tokens, bigrams, blocking_keys, date_parts, dice,
                       phone_digits)
from .records import PatientRecord
from .rubric import (FieldScore, MatchResult, birth_date_level, decide, exact_level, first_name_level,
                     last_name_level, score)

# Hospitals would agree on a real secret out of band. This default is for the demo only.
DEMO_KEY = os.environ.get("CONSTELLATION_LINKAGE_KEY", "constellation-demo-linkage-key").encode()


@dataclass(frozen=True)
class EncodedRecord:
    """Everything the matcher gets about one record: fingerprints, never names or dates."""

    id: str
    hospital_id: str
    first: frozenset[str]  # letter-pair hashes of the (nickname-resolved) first name
    first_raw: str | None  # the name as written, to tell "same" from "nickname"
    first_canon: str | None  # the nickname-resolved name
    first_initial: str | None
    first_is_initial: bool
    last: frozenset[str]  # letter-pair hashes of the whole last name
    last_whole: str | None
    last_parts: frozenset[str]  # one hash per part of a hyphenated or multi-word last name
    dob: str | None
    dob_year: str | None
    dob_month_day: str | None  # the same for 11-02 and 02-11, so swapped dates can be spotted
    dob_year_month: str | None
    dob_digits: frozenset[str]  # letter-pair hashes of the date's digits, so typos still look close
    sex: str | None
    phone: str | None
    postal_code: str | None
    blocking: frozenset[str]


# --- at the hospital

def encode(record: PatientRecord, key: bytes = DEMO_KEY) -> EncodedRecord:
    raw_first = _letters(record.given)
    first = NICKNAMES.get(raw_first, raw_first)
    last_tokens = _tokens(record.family)
    dob = record.birth_date or ""
    year, month, day = date_parts(dob) if dob else ("", "", "")
    return EncodedRecord(
        id=record.id,
        hospital_id=record.hospital_id,
        first=_grams(first, key),
        first_raw=_token("first", raw_first, key),
        first_canon=_token("first-canonical", first, key),
        first_initial=_token("initial", raw_first[:1], key),
        first_is_initial=len(raw_first) == 1,
        last=_grams("".join(last_tokens), key),
        last_whole=_token("last", "".join(last_tokens), key),
        last_parts=frozenset(_token("last-part", t, key) for t in last_tokens if len(t) > 1),
        dob=_token("dob", dob, key),
        dob_year=_token("year", year, key),
        dob_month_day=_token("month-day", "-".join(sorted((month, day))), key) if month and day else None,
        dob_year_month=_token("year-month", f"{year}-{month}", key) if year and month else None,
        dob_digits=_grams(dob.replace("-", ""), key),
        sex=_token("sex", (record.gender or "").lower(), key),
        phone=_token("phone", phone_digits(record.phone or ""), key),
        postal_code=_token("zip", (record.postal_code or "").strip()[:5], key),
        blocking=frozenset(_token("block", k, key) for k in blocking_keys(record)),
    )


def _token(kind: str, value: str, key: bytes) -> str | None:
    if not value:
        return None
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def _grams(text: str, key: bytes) -> frozenset[str]:
    """One keyed hash per letter pair of `text` (the same pairs matching.py uses)."""
    return frozenset(hmac.new(key, f"pair:{pair}".encode(), hashlib.sha256).hexdigest()[:16]
                     for pair in bigrams(text))


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
    """The same rubric as matching.compare_records, with the facts worked out from fingerprints."""
    return decide([
        _first_name(a, b),
        _last_name(a, b),
        _birth_date(a, b),
        _same("sex", a.sex, b.sex),
        _same("phone", a.phone, b.phone),
        _same("postal_code", a.postal_code, b.postal_code),
    ])


def _first_name(a: EncodedRecord, b: EncodedRecord) -> FieldScore:
    if not a.first or not b.first:
        return score("first_name", "missing")
    return score("first_name", first_name_level(
        same=a.first_raw == b.first_raw,
        nickname=a.first_canon == b.first_canon,
        initial_only=a.first_is_initial or b.first_is_initial,
        initials_match=a.first_initial == b.first_initial,
        spelling=dice(a.first, b.first),
    ))


def _last_name(a: EncodedRecord, b: EncodedRecord) -> FieldScore:
    if not a.last or not b.last:
        return score("last_name", "missing")
    parts_a, parts_b = a.last_parts, b.last_parts
    return score("last_name", last_name_level(
        same=a.last_whole == b.last_whole,
        contains=bool(parts_a and parts_b and (parts_a <= parts_b or parts_b <= parts_a)),
        spelling=dice(a.last, b.last),
    ))


def _birth_date(a: EncodedRecord, b: EncodedRecord) -> FieldScore:
    if not a.dob or not b.dob:
        return score("birth_date", "missing")
    return score("birth_date", birth_date_level(
        same=a.dob == b.dob,
        swapped=a.dob_year == b.dob_year and a.dob_month_day == b.dob_month_day,
        digits=dice(a.dob_digits, b.dob_digits),
        same_year_month=a.dob_year_month == b.dob_year_month,
    ))


def _same(field_name: str, a: str | None, b: str | None) -> FieldScore:
    if not a or not b:
        return score(field_name, "missing")
    return score(field_name, exact_level(a == b))


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
