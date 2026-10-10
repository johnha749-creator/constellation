"""Turn matched records and their conflicts into the JSON the frontend draws."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .conflicts import Conflict, find_conflicts
from .matching import Cluster, cluster_records
from .records import ClinicalItem, load_dataset

KIND_LABELS = {"allergy": "Allergy", "medication": "Medication", "condition": "Condition"}


class PatientIndex:
    """Loads every hospital bundle, links records into patients, and finds their conflicts."""

    def __init__(self, data_dir: Path):
        self.dataset = load_dataset(data_dir)
        self.items_by_record: dict[str, list[ClinicalItem]] = defaultdict(list)
        for item in self.dataset.items:
            self.items_by_record[item.record_id].append(item)
        self.clusters = {c.id: c for c in cluster_records(list(self.dataset.records.values()))}
        self.conflicts: dict[str, list[Conflict]] = {
            c.id: find_conflicts(
                [item for rid in c.record_ids for item in self.items_by_record[rid]],
                self.dataset.hospitals,
                c.confirmed,
            )
            for c in self.clusters.values()
        }

    def summaries(self, query: str | None = None) -> list[dict]:
        clusters = self.clusters.values()
        if query:
            q = query.strip().lower()
            clusters = [c for c in clusters if any(
                q in r.display_name.lower() or q in (r.birth_date or "")
                for r in (self.dataset.records[rid] for rid in c.record_ids))]
        summaries = [self._summary(c) for c in clusters]
        return sorted(summaries, key=lambda s: (-s["conflicts"]["high"], -s["conflicts"]["moderate"],
                                                -s["conflicts"]["low"], s["name"]))

    def find(self, name: str, birth_date: str) -> Cluster | None:
        """The patient with a record under this exact name and birth date (handy in tests)."""
        for cluster in self.clusters.values():
            records = (self.dataset.records[rid] for rid in cluster.record_ids)
            if any(r.display_name == name and r.birth_date == birth_date for r in records):
                return cluster
        return None

    def constellation(self, cluster_id: str) -> dict | None:
        cluster = self.clusters.get(cluster_id)
        if cluster is None:
            return None
        hospitals, records = self.dataset.hospitals, self.dataset.records
        nodes, links = [], []
        for rid in cluster.record_ids:
            record = records[rid]
            hospital = hospitals[record.hospital_id]
            nodes.append({
                "id": record.id, "kind": "record", "hospital": record.hospital_id,
                "label": record.display_name, "sublabel": f"{hospital.name} · MRN {record.mrn}",
                "details": _details(("Hospital", hospital.name), ("MRN", record.mrn),
                                    ("Date of birth", record.birth_date), ("Sex", record.gender),
                                    ("Phone", record.phone), ("Address", record.address),
                                    ("ZIP", record.postal_code)),
            })
            for item in self.items_by_record[rid]:
                nodes.append({
                    "id": item.id, "kind": item.kind, "hospital": item.hospital_id, "record": record.id,
                    "label": item.text,
                    "sublabel": " · ".join(filter(None, [KIND_LABELS[item.kind], item.detail])),
                    "details": _details(("Type", KIND_LABELS[item.kind]), ("Details", item.detail),
                                        ("Date", item.date), ("Hospital", hospital.name)),
                })
                links.append({"source": record.id, "target": item.id, "kind": "has"})
        for edge in cluster.edges:
            links.append({
                "source": edge.a, "target": edge.b, "kind": "match",
                "probability": round(edge.result.probability, 4), "tier": edge.result.tier,
                "agrees_on": edge.result.agrees_on, "reasons": edge.result.reasons,
            })
        conflicts = self.conflicts[cluster.id]
        for conflict in conflicts:
            source, target = conflict.item_ids
            links.append({"source": source, "target": target, "kind": "conflict",
                          "severity": conflict.severity, "conflict_id": conflict.id})
        present = {records[rid].hospital_id for rid in cluster.record_ids}
        return {
            "patient": self._summary(cluster),
            "hospitals": [{"id": h.id, "name": h.name} for h in hospitals.values() if h.id in present],
            "nodes": nodes,
            "links": links,
            "conflicts": [{
                "id": c.id, "type": c.type, "severity": c.severity, "title": c.title,
                "explanation": c.explanation, "item_ids": list(c.item_ids),
                "hospitals": [hospitals[h].name for h in dict.fromkeys(c.hospital_ids)],
                "cross_hospital": c.cross_hospital, "unconfirmed": c.unconfirmed,
            } for c in conflicts],
        }

    def _summary(self, cluster: Cluster) -> dict:
        records = [self.dataset.records[rid] for rid in cluster.record_ids]
        # Show the record most others agree with: the majority birth date and last name,
        # then the fullest spelling ("Maria" over "M.", "James" over "Jim", "O'Brien" over "OBrien").
        dob_votes = Counter(r.birth_date for r in records)
        family_votes = Counter(_letters(r.family) for r in records)
        best = max(records, key=lambda r: (dob_votes[r.birth_date], family_votes[_letters(r.family)],
                                           len(r.given.rstrip(".")), len(r.family)))
        hospital_ids = {r.hospital_id for r in records}
        counts = Counter(c.severity for c in self.conflicts[cluster.id])
        return {
            "id": cluster.id,
            "name": best.display_name,
            "birth_date": best.birth_date,
            "gender": best.gender,
            "hospitals": [h for h in self.dataset.hospitals if h in hospital_ids],
            "record_count": len(records),
            "conflicts": {s: counts.get(s, 0) for s in ("high", "moderate", "low")},
            "needs_review": cluster.needs_review,
        }


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _details(*pairs: tuple[str, str | None]) -> list[list[str]]:
    return [[label, value] for label, value in pairs if value]
