"""The match rubric: how much each piece of evidence counts, in points.

Every comparison of two records is scored with this one table, whether the matcher sees the real
values (matching.py) or only encrypted fingerprints (pprl.py). Each field lands on exactly one
level, each level is worth a fixed number of points, and the total decides the outcome:

    start at -10        most pairs of records belong to different people
    + points for first name, last name, date of birth, sex, phone and ZIP
    total >= +4.2       same person, linked automatically (about 95% likely or more)
    total >=  0         possible match: a clinician decides (50% to 95%)
    total <   0         different people

The points are Fellegi-Sunter weights: for each field, m is how often it agrees between two
records of the same person, u how often it agrees between different people, and full agreement
is worth log2(m/u) points. A partial level (a typo, an initial) counts as a fixed fraction of
agreement. The level is decided by the same rules (the *_level functions below) in both matchers,
so the same pair of records always gets the same levels and the same total.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

PRIOR = -10.0  # log2 of 1-in-1000 odds, rounded
LINK_AT = 4.2  # 2^4.2 is about 18:1 odds, about 95%
REVIEW_AT = 0.0  # even odds

# Spelling closeness is the Dice coefficient of the two names' letter pairs ("ma", "ar", ...):
# 1 when identical, 0 when nothing is shared. Both matchers measure it the same way.
CLOSE_SPELLING = 0.75
SIMILAR_SPELLING = 0.5


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    agreement: float  # 1 = full agreement, 0 = full disagreement


@dataclass(frozen=True)
class FieldRule:
    label: str
    m: float
    u: float
    levels: tuple[Level, ...]

    def level(self, key: str) -> Level:
        return next(level for level in self.levels if level.key == key)

    def points(self, key: str) -> float:
        if key == MISSING.key:
            return 0.0
        agreement = self.level(key).agreement
        agree, disagree = math.log2(self.m / self.u), math.log2((1 - self.m) / (1 - self.u))
        return round(agreement * agree + (1 - agreement) * disagree, 1)


MISSING = Level("missing", "Missing in one record", 0.0)  # no evidence either way: 0 points
_SAME, _DIFFERENT = Level("same", "Same", 1.0), Level("different", "Different", 0.0)
_CLOSE = Level("close", "Close spelling, likely a typo", 0.85)
_SIMILAR = Level("similar", "Similar spelling", 0.4)

RUBRIC: dict[str, FieldRule] = {
    "first_name": FieldRule("First name", 0.95, 0.02, (
        _SAME,
        Level("nickname", "Nickname of the same name", 1.0),
        _CLOSE,
        Level("initial", "Only an initial, and it matches", 0.6),
        _SIMILAR,
        _DIFFERENT,
    )),
    "last_name": FieldRule("Last name", 0.95, 0.01, (
        _SAME,
        Level("contains", "One contains the other (hyphenated or married name)", 0.9),
        _CLOSE,
        _SIMILAR,
        _DIFFERENT,
    )),
    "birth_date": FieldRule("Date of birth", 0.97, 0.001, (
        _SAME,
        Level("swapped", "Day and month swapped", 0.8),
        Level("digit", "One digit off, likely a typo", 0.7),
        Level("year_month", "Same year and month, different day", 0.5),
        _DIFFERENT,
    )),
    "sex": FieldRule("Sex", 0.98, 0.5, (_SAME, _DIFFERENT)),
    "phone": FieldRule("Phone", 0.80, 0.0001, (_SAME, _DIFFERENT)),
    "postal_code": FieldRule("ZIP", 0.85, 0.05, (_SAME, _DIFFERENT)),
}


# --- the rules that pick a level. Both matchers gather the facts their own way, then call these.

def spelling_level(dice: float) -> str:
    if dice >= CLOSE_SPELLING:
        return "close"
    return "similar" if dice >= SIMILAR_SPELLING else "different"


def first_name_level(*, same: bool, nickname: bool, initial_only: bool, initials_match: bool,
                     spelling: float) -> str:
    """`nickname`: equal once nicknames are resolved (Jim -> James). `initial_only`: either
    record has just one letter. `spelling`: Dice of the nickname-resolved names."""
    if same:
        return "same"
    if nickname:
        return "nickname"
    if initial_only:
        return "initial" if initials_match else "different"
    return spelling_level(spelling)


def last_name_level(*, same: bool, contains: bool, spelling: float) -> str:
    """`same`: equal once punctuation and spaces are ignored. `contains`: every part of one name
    appears in the other (Patel, Patel-Khan)."""
    if same:
        return "same"
    if contains:
        return "contains"
    return spelling_level(spelling)


def birth_date_level(*, same: bool, swapped: bool, digits: float, same_year_month: bool) -> str:
    """`swapped`: same year, and day and month swapped. `digits`: Dice of the YYYYMMDD digit pairs
    (one wrong digit leaves about 0.78)."""
    if same:
        return "same"
    if swapped:
        return "swapped"
    if digits >= CLOSE_SPELLING:
        return "digit"
    return "year_month" if same_year_month else "different"


def exact_level(same: bool) -> str:
    return "same" if same else "different"


# --- scores

@dataclass
class FieldScore:
    field: str
    level: str
    note: str | None = None
    values: str | None = None  # "Gonzales vs Gonzalez", when the matcher can see them

    @property
    def points(self) -> float:
        return RUBRIC[self.field].points(self.level)

    @property
    def label(self) -> str:
        return MISSING.label if self.level == MISSING.key else RUBRIC[self.field].level(self.level).label


def score(field_name: str, level: str, values: tuple[str, str] | None = None) -> FieldScore:
    """A field's score, with a readable note for anything short of "same". `values` are shown in
    the note when the matcher can see them (never in encrypted mode)."""
    rule = RUBRIC[field_name]
    if level == MISSING.key:
        return FieldScore(field_name, level, f"{rule.label} missing in one record")
    if level == "same":
        return FieldScore(field_name, level)
    label = rule.level(level).label
    shown = f"{values[0]} vs {values[1]}" if values else None
    note = f"{rule.label}: {label[0].lower()}{label[1:]}" + (f" ({shown})" if shown else "")
    return FieldScore(field_name, level, note, shown)


@dataclass
class MatchResult:
    points: float  # the rubric total, starting from PRIOR
    tier: str  # "match" | "review" | "non-match"
    fields: list[FieldScore]
    reviewed: str | None = None  # "same" | "different" once a clinician has decided

    @property
    def probability(self) -> float:
        return 1 / (1 + 2 ** -self.points)

    @property
    def reasons(self) -> list[str]:
        return [f.note for f in self.fields if f.note]

    @property
    def agrees_on(self) -> list[str]:
        return [RUBRIC[f.field].label.lower() for f in self.fields
                if f.level in ("same", "nickname")]

    def breakdown(self) -> list[dict]:
        return [{"field": RUBRIC[f.field].label, "level": f.label, "values": f.values, "points": f.points}
                for f in self.fields]


def decide(fields: list[FieldScore]) -> MatchResult:
    total = round(PRIOR + sum(f.points for f in fields), 1)
    if total >= LINK_AT:
        tier = "match"
    elif total >= REVIEW_AT:
        tier = "review"
    else:
        tier = "non-match"
    return MatchResult(total, tier, fields)


def as_table() -> dict:
    """The whole rubric, for the API and the "How scoring works" panel."""
    return {
        "start": PRIOR,
        "link_at": LINK_AT,
        "review_at": REVIEW_AT,
        "fields": [
            {"field": rule.label,
             "levels": [{"level": level.label, "points": rule.points(level.key)} for level in rule.levels]
                       + [{"level": MISSING.label, "points": 0.0}]}
            for rule in RUBRIC.values()
        ],
    }
