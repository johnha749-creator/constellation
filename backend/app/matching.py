"""Patient record linkage: which records at different hospitals are the same person?

A small Fellegi-Sunter style scorer. Each field adds evidence (a log-likelihood
weight) for or against a match, partial agreement is interpolated between the two,
and the total becomes a probability. Thresholds split pairs into
match / needs-review / non-match.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Iterable

from .records import PatientRecord

MATCH_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.50
# Before looking at any field, two random records are very unlikely to be the same person.
PRIOR_LOG2_ODDS = math.log2(1 / 1000)

# field -> (m, u) = P(agree | same person), P(agree | different people)
FIELD_PARAMS = {
    "first_name": (0.95, 0.02),
    "last_name": (0.95, 0.01),
    "birth_date": (0.97, 0.001),
    "sex": (0.98, 0.5),
    "phone": (0.80, 0.0001),
    "postal_code": (0.85, 0.05),
}

FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "birth_date": "date of birth",
    "sex": "sex",
    "phone": "phone",
    "postal_code": "ZIP",
}

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


@dataclass
class FieldComparison:
    field: str
    similarity: float | None  # None = missing in a record, so no evidence either way
    weight: float
    note: str | None = None


@dataclass
class MatchResult:
    probability: float
    tier: str  # "match" | "review" | "non-match"
    fields: list[FieldComparison]

    @property
    def reasons(self) -> list[str]:
        return [f.note for f in self.fields if f.note]

    @property
    def agrees_on(self) -> list[str]:
        return [FIELD_LABELS[f.field] for f in self.fields if f.similarity == 1.0]


def compare_records(a: PatientRecord, b: PatientRecord) -> MatchResult:
    fields = [
        _weigh("first_name", *first_name_similarity(a.given, b.given)),
        _weigh("last_name", *last_name_similarity(a.family, b.family)),
        _weigh("birth_date", *birth_date_similarity(a.birth_date, b.birth_date)),
        _weigh("sex", *_exact("Sex", a.gender, b.gender, str.lower)),
        _weigh("phone", *_exact("Phone", a.phone, b.phone, lambda s: re.sub(r"\D", "", s)[-10:])),
        _weigh("postal_code", *_exact("ZIP", a.postal_code, b.postal_code, lambda s: s.strip()[:5])),
    ]
    log2_odds = PRIOR_LOG2_ODDS + sum(f.weight for f in fields)
    probability = 1 / (1 + 2 ** -log2_odds)
    if probability >= MATCH_THRESHOLD:
        tier = "match"
    elif probability >= REVIEW_THRESHOLD:
        tier = "review"
    else:
        tier = "non-match"
    return MatchResult(probability, tier, fields)


def _weigh(field: str, similarity: float | None, note: str | None) -> FieldComparison:
    if similarity is None:
        return FieldComparison(field, None, 0.0, note)
    m, u = FIELD_PARAMS[field]
    agree, disagree = math.log2(m / u), math.log2((1 - m) / (1 - u))
    return FieldComparison(field, similarity, similarity * agree + (1 - similarity) * disagree, note)


# --- field comparators: each returns (similarity 0..1 or None, human-readable note or None)

def first_name_similarity(a: str, b: str) -> tuple[float | None, str | None]:
    na, nb = _letters(a), _letters(b)
    if not na or not nb:
        return None, "First name missing in one record"
    if na == nb:
        return 1.0, None
    if NICKNAMES.get(na, na) == NICKNAMES.get(nb, nb):
        return 1.0, f"'{a}' and '{b}' treated as the same name (nickname)"
    if len(na) == 1 or len(nb) == 1:
        if na[0] == nb[0]:
            return 0.6, f"First name is only an initial ('{a}' vs '{b}')"
        return 0.0, f"First initials differ ('{a}' vs '{b}')"
    sim = _scaled_jaro_winkler(NICKNAMES.get(na, na), NICKNAMES.get(nb, nb))
    return sim, f"First names {'spelled differently' if sim else 'differ'} ('{a}' vs '{b}')"


def last_name_similarity(a: str, b: str) -> tuple[float | None, str | None]:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return None, "Last name missing in one record"
    joined_a, joined_b = "".join(tokens_a), "".join(tokens_b)
    if joined_a == joined_b:
        return 1.0, None if a == b else f"Last names match once punctuation is ignored ('{a}' vs '{b}')"
    words_a = {t for t in tokens_a if len(t) > 1}
    words_b = {t for t in tokens_b if len(t) > 1}
    if words_a and words_b and (words_a <= words_b or words_b <= words_a):
        return 0.9, f"One last name contains the other ('{a}' vs '{b}'): hyphenated or married name?"
    sim = _scaled_jaro_winkler(joined_a, joined_b)
    return sim, f"Last names {'spelled differently' if sim else 'differ'} ('{a}' vs '{b}')"


def birth_date_similarity(a: str | None, b: str | None) -> tuple[float | None, str | None]:
    if not a or not b:
        return None, "Date of birth missing in one record"
    if a == b:
        return 1.0, None
    if a[:4] == b[:4] and a[5:7] == b[8:10] and a[8:10] == b[5:7]:
        return 0.8, f"Date of birth has day and month swapped ({a} vs {b})"
    digits_a, digits_b = a.replace("-", ""), b.replace("-", "")
    if len(digits_a) == len(digits_b) == 8:
        diffs = [i for i in range(8) if digits_a[i] != digits_b[i]]
        if len(diffs) == 1:
            return 0.7, f"Date of birth differs by one digit, likely a typo ({a} vs {b})"
        if (len(diffs) == 2 and diffs[1] == diffs[0] + 1
                and digits_a[diffs[0]] == digits_b[diffs[1]] and digits_a[diffs[1]] == digits_b[diffs[0]]):
            return 0.7, f"Date of birth has two digits transposed ({a} vs {b})"
    return 0.0, f"Dates of birth differ ({a} vs {b})"


def _exact(label: str, a: str | None, b: str | None,
           normalize: Callable[[str], str]) -> tuple[float | None, str | None]:
    if not a or not b:
        return None, f"{label} missing in one record"
    if normalize(a) == normalize(b):
        return 1.0, None
    return 0.0, f"{label} differs ({a} vs {b})"


# --- string helpers

def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", _strip_accents(text).lower())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", _strip_accents(text).lower())


def _scaled_jaro_winkler(a: str, b: str) -> float:
    """Jaro-Winkler rescaled so that unrelated names (JW < 0.7) count as full disagreement."""
    return max(0.0, (jaro_winkler(a, b) - 0.7) / 0.3)


def jaro_winkler(s1: str, s2: str, prefix_scale: float = 0.1) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if not len1 or not len2:
        return 0.0
    window = max(max(len1, len2) // 2 - 1, 0)
    matched1, matched2 = [False] * len1, [False] * len2
    matches = 0
    for i, ch in enumerate(s1):
        for j in range(max(0, i - window), min(i + window + 1, len2)):
            if not matched2[j] and s2[j] == ch:
                matched1[i] = matched2[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    transpositions, k = 0, 0
    for i in range(len1):
        if matched1[i]:
            while not matched2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3
    prefix = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 != c2:
            break
        prefix += 1
    return jaro + prefix * prefix_scale * (1 - jaro)


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


def cluster_records(records: list[PatientRecord]) -> list[Cluster]:
    # Compares every pair: fine for a demo. At real scale, add "blocking" (only compare
    # records that share e.g. birth year or a phonetic code of the last name).
    edges = []
    for a, b in combinations(records, 2):
        result = compare_records(a, b)
        if result.tier != "non-match":
            edges.append(MatchEdge(a.id, b.id, result))

    linked = _UnionFind(r.id for r in records)
    confirmed = _UnionFind(r.id for r in records)
    for edge in edges:
        linked.union(edge.a, edge.b)
        if edge.result.tier == "match":
            confirmed.union(edge.a, edge.b)

    groups: dict[str, list[str]] = {}
    for record in records:
        groups.setdefault(linked.find(record.id), []).append(record.id)
    clusters = []
    for ids in groups.values():
        members = set(ids)
        clusters.append(Cluster(
            id=f"c-{min(ids)}",
            record_ids=ids,
            edges=[e for e in edges if e.a in members],
            confirmed_group={i: confirmed.find(i) for i in ids},
        ))
    return clusters


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
