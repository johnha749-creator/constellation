"""Turn matched records and their conflicts into the JSON the frontend draws."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .audit import AuditLog
from .conflicts import Conflict, find_conflicts
from .matching import Cluster, candidate_pairs, cluster_records, compare_records, score_pairs
from .pprl import compare_encoded, link_privately
from .privacy import masker
from .records import ClinicalItem, load_dataset

KIND_LABELS = {"allergy": "Allergy", "medication": "Medication", "condition": "Condition"}


class PatientIndex:
    """Loads every hospital bundle, links records into patients, and finds their conflicts."""

    def __init__(self, data_dir: Path, audit: AuditLog | None = None, matching: str = "standard"):
        """`matching="private"` links records on encrypted fingerprints only (see pprl.py)."""
        if matching not in ("standard", "private"):
            raise ValueError(f"Unknown matching mode: {matching}")
        self.matching = matching
        self.dataset = load_dataset(data_dir)
        self.items_by_record: dict[str, list[ClinicalItem]] = defaultdict(list)
        for item in self.dataset.items:
            self.items_by_record[item.record_id].append(item)
        # Score candidate pairs once (see blocking in matching.py); reviews only change decisions.
        records = self.dataset.records
        if matching == "private":
            self._subjects, self.scored = link_privately(records.values())
            self._compare = compare_encoded
        else:
            self._subjects = records
            self.scored = score_pairs(records, candidate_pairs(records.values()))
            self._compare = compare_records
        # Clinicians' decisions, replayed from the audit log so they survive a restart.
        self.audit = audit or AuditLog()
        self.reviews = self.audit.current_reviews()
        self._conflict_cache: dict[frozenset, list[Conflict]] = {}
        self._link()

    def _link(self) -> None:
        clusters = cluster_records(list(self._subjects.values()), self.reviews, self.scored, self._compare)
        self.clusters: dict[str, Cluster] = {}
        self.conflicts: dict[str, list[Conflict]] = {}
        self._cluster_of: dict[str, str] = {}
        cache, self._conflict_cache = self._conflict_cache, {}
        for cluster in clusters:
            # A patient's conflicts only change if its records or confirmed links change, so
            # after a review only the one or two affected patients are re-checked.
            key = _confirmed_partition(cluster)
            found = cache.get(key)
            if found is None:
                found = find_conflicts(self.items_of(cluster), self.dataset.hospitals, cluster.confirmed)
            self._conflict_cache[key] = found
            self.clusters[cluster.id] = cluster
            self.conflicts[cluster.id] = found
            for rid in cluster.record_ids:
                self._cluster_of[rid] = cluster.id

    def items_of(self, cluster: Cluster) -> list[ClinicalItem]:
        """Every allergy, medication and condition on any of the patient's records."""
        return [item for rid in cluster.record_ids for item in self.items_by_record[rid]]

    def review_match(self, record_a: str, record_b: str, same_person: bool,
                     reviewer: str = "Unknown reviewer", note: str | None = None,
                     username: str | None = None) -> str | None:
        """Apply and log a clinician's decision about two records. Returns record_a's patient id."""
        records = self.dataset.records
        if record_a not in records or record_b not in records:
            return None
        pair = frozenset((record_a, record_b))
        result = (self.scored.get(tuple(sorted(pair)))
                  or self._compare(self._subjects[record_a], self._subjects[record_b]))
        self.audit.record_review(record_a, record_b, same_person, reviewer=reviewer, username=username,
                                 score=round(result.probability, 4), previous=self.reviews.get(pair), note=note)
        self.reviews[pair] = same_person
        self._link()
        return self.cluster_of(record_a).id

    def reset_reviews(self, reviewer: str = "Unknown reviewer", username: str | None = None) -> None:
        """Undo every decision (for re-running the demo). The log keeps them, plus a reset entry."""
        self.audit.record_reset(reviewer, username)
        self.reviews = {}
        self._link()

    def log_access(self, cluster_id: str, action: str, reviewer: str, username: str | None = None,
                   reason: str | None = None) -> bool:
        """Record that someone opened this patient ("view") or unmasked their details ("reveal")."""
        cluster = self.clusters.get(cluster_id)
        if cluster is None:
            return False
        self.audit.record_access(action, cluster.record_ids, reviewer=reviewer, username=username, reason=reason)
        return True

    def cluster_of(self, record_id: str) -> Cluster:
        return self.clusters[self._cluster_of[record_id]]

    def audit_status(self) -> dict:
        broken = self.audit.verify()
        return {"total_events": len(self.audit.events), "verified": broken is None, "first_bad_seq": broken}

    def audit_log(self, limit: int = 100) -> dict:
        """The whole log, newest first."""
        events = [self._describe(e) for e in self.audit.events[::-1][:limit]]
        return {"events": events, **self.audit_status()}

    def audit_for(self, cluster_id: str) -> dict | None:
        """Everything logged about this patient's records, newest first: who opened them, who
        unmasked contact details and why, match decisions, and any resets after those."""
        cluster = self.clusters.get(cluster_id)
        if cluster is None:
            return None
        mine = set(cluster.record_ids)
        events, involved = [], False
        for event in self.audit.events:
            if event["action"] == "reset":
                if involved:
                    events.append(self._describe(event))
            elif _records_of(event) & mine:
                involved = True
                events.append(self._describe(event))
        return {"events": events[::-1], **self.audit_status()}

    def _describe(self, event: dict) -> dict:
        """An audit entry, with readable names for the records it mentions."""
        described = {k: event.get(k) for k in ("seq", "at", "action", "reviewer", "username", "decision",
                                               "previous", "score", "note", "reason", "hash")}
        if event["action"] == "review":
            described["records"] = [self._record_label(event[k]) for k in ("record_a", "record_b")]
        return described

    def _record_label(self, record_id: str) -> dict:
        record = self.dataset.records.get(record_id)
        if record is None:  # the data files changed since the decision was made
            return {"id": record_id, "name": None, "hospital": None}
        return {"id": record_id, "name": record.display_name,
                "hospital": self.dataset.hospitals[record.hospital_id].name}

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

    def stats(self) -> dict:
        """Totals across every patient, for the header."""
        conflicts = [c for found in self.conflicts.values() for c in found]
        counts = Counter(c.severity for c in conflicts)
        return {
            "hospitals": len(self.dataset.hospitals),
            "records": sum(len(c.record_ids) for c in self.clusters.values()),
            "patients": len(self.clusters),
            "needs_review": sum(c.needs_review for c in self.clusters.values()),
            "conflicts": {s: counts.get(s, 0) for s in ("high", "moderate", "low")},
            "cross_hospital_conflicts": sum(c.cross_hospital for c in conflicts),
        }

    def find(self, name: str, birth_date: str) -> Cluster | None:
        """The patient with a record under this exact name and birth date (handy in tests)."""
        for cluster in self.clusters.values():
            records = (self.dataset.records[rid] for rid in cluster.record_ids)
            if any(r.display_name == name and r.birth_date == birth_date for r in records):
                return cluster
        return None

    def constellation(self, cluster_id: str, reveal: bool = False) -> dict | None:
        """The patient's graph. Contact details (phone, address, ZIP, MRN) are masked everywhere,
        including inside match explanations, unless `reveal` is set (see privacy.py)."""
        cluster = self.clusters.get(cluster_id)
        if cluster is None:
            return None
        hospitals, records = self.dataset.hospitals, self.dataset.records
        mask = (lambda text: text) if reveal else masker(records[rid] for rid in cluster.record_ids)
        nodes, links = [], []
        for rid in cluster.record_ids:
            record = records[rid]
            hospital = hospitals[record.hospital_id]
            nodes.append({
                "id": record.id, "kind": "record", "hospital": record.hospital_id,
                "label": record.display_name, "sublabel": mask(f"{hospital.name} · MRN {record.mrn}"),
                "details": [[label, mask(value)] for label, value in _details(
                    ("Hospital", hospital.name), ("MRN", record.mrn),
                    ("Date of birth", record.birth_date), ("Sex", record.gender),
                    ("Phone", record.phone), ("Address", record.address), ("ZIP", record.postal_code))],
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
                "reviewed": edge.result.reviewed, "agrees_on": edge.result.agrees_on,
                "reasons": [mask(reason) for reason in edge.result.reasons],
            })
        conflicts = self.conflicts[cluster.id]
        for conflict in conflicts:
            source, target = conflict.item_ids
            links.append({"source": source, "target": target, "kind": "conflict",
                          "severity": conflict.severity, "conflict_id": conflict.id})
        present = {records[rid].hospital_id for rid in cluster.record_ids}
        return {
            "patient": self._summary(cluster),
            "contact_details_visible": reveal,
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


def _records_of(event: dict) -> set[str]:
    if event["action"] == "review":
        return {event["record_a"], event["record_b"]}
    return set(event.get("records") or ())


def _confirmed_partition(cluster: Cluster) -> frozenset:
    """The cluster's records, grouped by confirmed links. Same partition = same conflicts."""
    groups: dict[str, set[str]] = defaultdict(set)
    for rid, group in cluster.confirmed_group.items():
        groups[group].add(rid)
    return frozenset(frozenset(g) for g in groups.values())


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _details(*pairs: tuple[str, str | None]) -> list[list[str]]:
    return [[label, value] for label, value in pairs if value]
