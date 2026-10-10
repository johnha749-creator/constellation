"""Patient record linkage: which records at different hospitals are the same person?

Each pair of records is scored field by field with the match rubric (rubric.py): every field
lands on one named level ("Nickname of the same name", "Day and month swapped", ...) worth a
fixed number of points, and the total decides same person / clinician decides / different
people. This module gathers the facts from the real values; pprl.py gathers the same facts from
encrypted fingerprints, and both use the same rubric rules, so they reach the same levels.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import combinations
from typing import Callable, Iterable

from .records import PatientRecord
from .rubric import (FieldScore, MatchResult, birth_date_level, decide, exact_level, first_name_level,
                     last_name_level, score)

NICKNAMES = {
    "jim": "james", "jimmy": "james", "jamie": "james",
    "bob": "robert", "bobby": "robert", "rob": "robert", "robbie": "robert",
    "bill": "william", "will": "william", "billy": "william",
    "liz": "elizabeth", "beth": "elizabeth", "lizzie": "elizabeth", "betty": "elizabeth",
    "kate": "katherine", "katie": "katherine", "kathy": "katherine",
    "mike": "michael", "mikey": "michael",
    "tom": "thomas", "tommy": "thomas",
    "dan": "daniel", "danny": "daniel",
    "tony": "anthony", "sam": "samuel", "alex": "alexander", "chris": "christopher",
    "matt": "matthew", "nick": "nicholas", "joe": "joseph", "dave": "david",
    "steve": "steven", "rick": "richard", "dick": "richard",
    "maggie": "margaret", "peggy": "margaret", "jen": "jennifer", "jenny": "jennifer", "sue": "susan",
}


def compare_records(a: PatientRecord, b: PatientRecord) -> MatchResult:
    return decide([
        _first_name(a.given, b.given),
        _last_name(a.family, b.family),
        _birth_date(a.birth_date, b.birth_date),
        _exact("sex", a.gender, b.gender, str.lower),
        _exact("phone", a.phone, b.phone, phone_digits),
        _exact("postal_code", a.postal_code, b.postal_code, lambda s: s.strip()[:5]),
    ])


# --- the facts for each field, from the real values

def _first_name(a: str, b: str) -> FieldScore:
    letters_a, letters_b = _letters(a), _letters(b)
    if not letters_a or not letters_b:
        return score("first_name", "missing")
    canon_a, canon_b = NICKNAMES.get(letters_a, letters_a), NICKNAMES.get(letters_b, letters_b)
    level = first_name_level(
        same=letters_a == letters_b,
        nickname=canon_a == canon_b,
        initial_only=len(letters_a) == 1 or len(letters_b) == 1,
        initials_match=letters_a[0] == letters_b[0],
        spelling=dice(bigrams(canon_a), bigrams(canon_b)),
    )
    return score("first_name", level, (a, b))


def _last_name(a: str, b: str) -> FieldScore:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return score("last_name", "missing")
    joined_a, joined_b = "".join(tokens_a), "".join(tokens_b)
    words_a, words_b = {t for t in tokens_a if len(t) > 1}, {t for t in tokens_b if len(t) > 1}
    level = last_name_level(
        same=joined_a == joined_b,
        contains=bool(words_a and words_b and (words_a <= words_b or words_b <= words_a)),
        spelling=dice(bigrams(joined_a), bigrams(joined_b)),
    )
    if level == "same" and a != b:  # O'Brien and OBrien: the same name, worth saying why
        return FieldScore("last_name", "same", f"Last name: same once punctuation and spaces are ignored ({a} vs {b})",
                          f"{a} vs {b}")
    return score("last_name", level, (a, b))


def _birth_date(a: str | None, b: str | None) -> FieldScore:
    if not a or not b:
        return score("birth_date", "missing")
    year_a, month_a, day_a = date_parts(a)
    year_b, month_b, day_b = date_parts(b)
    level = birth_date_level(
        same=a == b,
        swapped=year_a == year_b and sorted((month_a, day_a)) == sorted((month_b, day_b)),
        digits=dice(bigrams(a.replace("-", "")), bigrams(b.replace("-", ""))),
        same_year_month=(year_a, month_a) == (year_b, month_b),
    )
    return score("birth_date", level, (a, b))


def _exact(field_name: str, a: str | None, b: str | None, normalize: Callable[[str], str]) -> FieldScore:
    if not a or not b:
        return score(field_name, "missing")
    return score(field_name, exact_level(normalize(a) == normalize(b)), (a, b))


# --- string helpers, shared with pprl.py so both matchers see identical letter pairs

def bigrams(text: str) -> set[str]:
    """Neighbouring letter pairs, with the start and end marked: "ann" -> _a, an, nn, n_."""
    padded = f"_{text}_"
    return {padded[i:i + 2] for i in range(len(padded) - 1)} if text else set()


def dice(a: set, b: set) -> float:
    """How much two sets of letter pairs overlap, from 0 (nothing) to 1 (identical)."""
    total = len(a) + len(b)
    return 2 * len(a & b) / total if total else 0.0


def date_parts(date: str) -> tuple[str, str, str]:
    year, month, day = (date.split("-") + ["", "", ""])[:3]
    return year, month, day


def phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)[-10:]


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", _strip_accents(text).lower())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", _strip_accents(text).lower())


# --- clustering

@dataclass
class MatchEdge:
    a: str
    b: str
    result: MatchResult


@dataclass
class Cluster:
    """All the records believed to belong to one person."""

    id: str
    record_ids: list[str]
    edges: list[MatchEdge]
    confirmed_group: dict[str, str]  # record id -> its group when only "match"-tier links count

    def confirmed(self, record_a: str, record_b: str) -> bool:
        return self.confirmed_group[record_a] == self.confirmed_group[record_b]

    @property
    def needs_review(self) -> bool:
        return any(e.result.tier == "review" for e in self.edges)


# --- blocking: decide which pairs are worth comparing at all
#
# Comparing every record with every other is n²/2 comparisons: 5 billion for 100,000 records.
# Instead, two records are compared only if they share at least one "blocking key". Each key
# survives a different kind of mistake, so a pair is missed only if all of them fail at once.

Pair = tuple[str, str]  # two record ids, smaller first


def blocking_keys(record: PatientRecord) -> set[str]:
    keys = set()
    # Same birth date: survives any name change, nickname or move.
    if record.birth_date:
        keys.add(f"dob:{record.birth_date}")
    # Same phone: survives a name change and a birth-date typo.
    phone = re.sub(r"\D", "", record.phone or "")[-10:]
    if len(phone) >= 7:
        keys.add(f"phone:{phone}")
    # Last name that sounds alike, plus birth year: survives misspellings, swapped day/month
    # and day typos. Each part of a hyphenated name counts, so "Patel-Khan" meets "Patel".
    year = (record.birth_date or "")[:4]
    tokens = _tokens(record.family)
    for name in {"".join(tokens), *(t for t in tokens if len(t) > 1)}:
        if name:
            keys.add(f"name:{soundex(name)}:{year}")
    return keys


def candidate_pairs(records: Iterable[PatientRecord]) -> set[Pair]:
    blocks: dict[str, list[str]] = defaultdict(list)
    for record in records:
        for key in blocking_keys(record):
            blocks[key].append(record.id)
    pairs = set()
    for ids in blocks.values():
        for a, b in combinations(ids, 2):
            pairs.add((a, b) if a < b else (b, a))
    return pairs


_SOUNDEX = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"),
            "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}


def soundex(name: str) -> str:
    """American Soundex: names that sound alike share a code (Whittaker, Whitaker -> W326)."""
    letters = _letters(name)
    if not letters:
        return ""
    code, last = letters[0].upper(), _SOUNDEX.get(letters[0], "")
    for ch in letters[1:]:
        digit = _SOUNDEX.get(ch, "")
        if digit and digit != last:
            code += digit
        if ch not in "hw":  # h and w don't separate letters with the same code; vowels do
            last = digit
    return (code + "000")[:4]


def score_pairs(records_by_id: dict, pairs: Iterable[Pair],
                compare: Callable = compare_records) -> dict[Pair, MatchResult]:
    """Score each pair, keeping only the ones that could be the same person. `compare` can be
    swapped for pprl.compare_encoded to score encrypted fingerprints instead."""
    scored = {}
    for a, b in pairs:
        result = compare(records_by_id[a], records_by_id[b])
        if result.tier != "non-match":
            scored[(a, b)] = result
    return scored


# --- clustering

def cluster_records(records: list,
                    reviews: dict[frozenset[str], bool] | None = None,
                    scored: dict[Pair, MatchResult] | None = None,
                    compare: Callable = compare_records) -> list[Cluster]:
    """Group records into people.

    `reviews` holds clinicians' decisions on record pairs (True = same person) and overrides
    the score for those pairs. Pass `scored` (from score_pairs) to skip re-scoring: after a
    review only the decisions change, so relinking is then roughly linear in the record count.
    """
    reviews = reviews or {}
    by_id = {r.id: r for r in records}
    if scored is None:
        scored = score_pairs(by_id, candidate_pairs(records), compare)
    reviewed_pairs = {tuple(sorted(p)) for p in reviews if len(p) == 2 and all(i in by_id for i in p)}

    edges = []
    for pair in sorted(scored.keys() | reviewed_pairs):
        result = scored.get(pair) or compare(by_id[pair[0]], by_id[pair[1]])
        decision = reviews.get(frozenset(pair))
        if decision is not None:
            # Copy, so cached scores stay untouched when the decision is later undone.
            result = replace(result, tier="match" if decision else "non-match",
                             reviewed="same" if decision else "different")
        if result.tier != "non-match":
            edges.append(MatchEdge(pair[0], pair[1], result))

    linked = _UnionFind(by_id)
    confirmed = _UnionFind(by_id)
    for edge in edges:
        linked.union(edge.a, edge.b)
        if edge.result.tier == "match":
            confirmed.union(edge.a, edge.b)

    groups: dict[str, list[str]] = defaultdict(list)
    for record in records:
        groups[linked.find(record.id)].append(record.id)
    edges_by_group: dict[str, list[MatchEdge]] = defaultdict(list)
    for edge in edges:
        edges_by_group[linked.find(edge.a)].append(edge)
    return [
        Cluster(id=f"c-{min(ids)}", record_ids=ids, edges=edges_by_group[root],
                confirmed_group={i: confirmed.find(i) for i in ids})
        for root, ids in groups.items()
    ]


class _UnionFind:
    def __init__(self, items: Iterable[str]):
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)
