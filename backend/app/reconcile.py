"""Medication reconciliation: what is this patient actually taking, across every hospital?"""
from __future__ import annotations

from collections import Counter

from .conflicts import Conflict
from .records import ClinicalItem


def medication_list(items: list[ClinicalItem], conflicts: list[Conflict]) -> list[dict]:
    """One row per drug, listing every hospital that prescribed it. `items` are one patient's
    combined items and `conflicts` are that patient's conflicts. Drugs with conflicts come first."""
    by_drug: dict[str, list[ClinicalItem]] = {}
    for item in items:
        if item.kind == "medication":
            # Drugs the knowledge base doesn't know can still be grouped by how they're written.
            by_drug.setdefault(item.drug or item.text.strip().lower(), []).append(item)

    rows = []
    for meds in by_drug.values():
        meds.sort(key=lambda m: m.date or "")  # oldest prescription first
        item_ids = {m.id for m in meds}
        rows.append({
            # The most common spelling; the oldest record wins a tie.
            "name": Counter(m.text for m in meds).most_common(1)[0][0],
            "drug": meds[0].drug,
            "sources": [{"hospital": m.hospital_id, "dosage": m.detail, "date": m.date, "item_id": m.id}
                        for m in meds],
            "conflict_ids": [c.id for c in conflicts if item_ids.intersection(c.item_ids)],
        })
    return sorted(rows, key=lambda row: (not row["conflict_ids"], row["name"].lower()))
