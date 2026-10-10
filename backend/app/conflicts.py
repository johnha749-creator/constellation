"""Find clinically risky contradictions across one patient's combined records."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Hashable

from . import knowledge
from .knowledge import SEVERITY_RANK
from .records import ClinicalItem, Hospital


@dataclass
class Conflict:
    id: str
    type: str  # "allergy" | "duplicate_therapy" | "interaction" | "condition" | "dose_mismatch"
    severity: str  # "high" | "moderate" | "low"
    title: str
    explanation: str
    item_ids: tuple[str, str]
    hospital_ids: tuple[str, str]
    unconfirmed: bool  # depends on a patient match that still needs human review

    @property
    def cross_hospital(self) -> bool:
        return self.hospital_ids[0] != self.hospital_ids[1]


def find_conflicts(
    items: list[ClinicalItem],
    hospitals: dict[str, Hospital],
    same_person: Callable[[str, str], bool],
) -> list[Conflict]:
    """`same_person(record_a, record_b)` says whether two records are a confirmed match."""
    allergies = [i for i in items if i.kind == "allergy"]
    meds = [i for i in items if i.kind == "medication" and i.drug]
    conditions = [i for i in items if i.kind == "condition"]
    found: dict[Hashable, Conflict] = {}

    def where(item: ClinicalItem) -> str:
        return hospitals[item.hospital_id].name

    def add(key: Hashable, kind: str, severity: str, title: str, explanation: str,
            a: ClinicalItem, b: ClinicalItem) -> None:
        conflict = Conflict("", kind, severity, title, explanation, (a.id, b.id),
                            (a.hospital_id, b.hospital_id),
                            unconfirmed=not same_person(a.record_id, b.record_id))
        # The same problem can show up via several copies of a record; keep the most telling one.
        if key not in found or _rank(conflict) > _rank(found[key]):
            found[key] = conflict

    for allergy in allergies:
        for med in meds:
            if risk := knowledge.allergy_risk(allergy.text, med.drug):
                severity, drug_class = risk
                what = knowledge.with_article(knowledge.label(drug_class)) if drug_class else "the same drug"
                note = " Cross-reactivity is uncommon but worth confirming." if severity == "low" else ""
                add(("allergy", allergy.text.lower(), med.drug), "allergy", severity,
                    f"{allergy.text} allergy vs {med.text}",
                    f"{where(allergy)} records a {allergy.text} allergy ({allergy.detail}). "
                    f"{where(med)} ordered {med.text} {med.detail}{_on(med.date)}, which is {what}.{note}",
                    allergy, med)

    for a, b in combinations(meds, 2):
        if a.drug == b.drug:
            if a.dose_mg and b.dose_mg and a.dose_mg != b.dose_mg:
                add(("dose", a.drug, frozenset({a.dose_mg, b.dose_mg})), "dose_mismatch", "low",
                    f"{a.text} dose differs",
                    f"{where(a)} lists {a.text} {a.detail}; {where(b)} lists {b.text} {b.detail}. "
                    "Confirm which dose the patient actually takes.",
                    a, b)
            continue
        pair = frozenset({a.drug, b.drug})
        if duplicate := knowledge.duplicate_class(a.drug, b.drug):
            severity, drug_class = duplicate
            plural = f"{knowledge.label(drug_class)}s"
            add(("duplicate", pair), "duplicate_therapy", severity,
                f"Two {plural}: {a.text} + {b.text}",
                f"{a.text} ({where(a)}) and {b.text} ({where(b)}) are both {plural}. "
                "The patient may be taking both.",
                a, b)
        if hit := knowledge.interaction(a.drug, b.drug):
            severity, message = hit
            add(("interaction", pair), "interaction", severity, f"{a.text} + {b.text}",
                f"{message} {a.text} is from {where(a)}; {b.text} is from {where(b)}.",
                a, b)

    for condition in conditions:
        for med in meds:
            if risk := knowledge.condition_risk(condition.text, med.drug):
                severity, message = risk
                add(("condition", condition.text.lower(), med.drug), "condition", severity,
                    f"{med.text} with {condition.text}",
                    f"{message} {where(condition)} records {condition.text}; "
                    f"{where(med)} ordered {med.text}{_on(med.date)}.",
                    condition, med)

    conflicts = sorted(found.values(),
                       key=lambda c: (-SEVERITY_RANK[c.severity], not c.cross_hospital, c.type))
    for n, conflict in enumerate(conflicts, start=1):
        conflict.id = f"k{n}"
    return conflicts


def _rank(conflict: Conflict) -> tuple[int, bool, bool]:
    return SEVERITY_RANK[conflict.severity], conflict.cross_hospital, not conflict.unconfirmed


def _on(date: str | None) -> str:
    return f" on {date}" if date else ""
