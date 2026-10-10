"""Load hospital FHIR R4 bundles into simple Python objects."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import knowledge


@dataclass(frozen=True)
class Hospital:
    id: str
    name: str


@dataclass
class PatientRecord:
    """One hospital's record for a patient (a FHIR Patient resource)."""

    id: str
    hospital_id: str
    mrn: str | None
    given: str
    family: str
    birth_date: str | None
    gender: str | None
    phone: str | None
    postal_code: str | None
    address: str | None

    @property
    def display_name(self) -> str:
        return f"{self.given} {self.family}".strip()


@dataclass
class ClinicalItem:
    """An allergy, medication or condition attached to one patient record."""

    id: str
    record_id: str
    hospital_id: str
    kind: str  # "allergy" | "medication" | "condition"
    text: str
    detail: str
    date: str | None
    drug: str | None = None  # normalized drug key (medications only)
    dose_mg: float | None = None


@dataclass
class Dataset:
    hospitals: dict[str, Hospital]
    records: dict[str, PatientRecord]
    items: list[ClinicalItem]


def load_dataset(data_dir: Path) -> Dataset:
    hospitals: dict[str, Hospital] = {}
    records: dict[str, PatientRecord] = {}
    items: list[ClinicalItem] = []
    for path in sorted(data_dir.glob("*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        hospital_id = bundle["id"]
        resources = [entry["resource"] for entry in bundle.get("entry", [])]
        org = next((r for r in resources if r["resourceType"] == "Organization"), None)
        hospitals[hospital_id] = Hospital(hospital_id, org["name"] if org else hospital_id)
        for resource in resources:
            if resource["resourceType"] == "Patient":
                records[resource["id"]] = _parse_patient(resource, hospital_id)
            elif item := _parse_item(resource, hospital_id):
                items.append(item)
    return Dataset(hospitals, records, items)


def _parse_patient(r: dict, hospital_id: str) -> PatientRecord:
    name = (r.get("name") or [{}])[0]
    address = (r.get("address") or [{}])[0]
    address_text = ", ".join([*address.get("line", []), address.get("city", "")]).strip(", ")
    return PatientRecord(
        id=r["id"],
        hospital_id=hospital_id,
        mrn=next((i["value"] for i in r.get("identifier", [])), None),
        given=" ".join(name.get("given", [])),
        family=name.get("family", ""),
        birth_date=r.get("birthDate"),
        gender=r.get("gender"),
        phone=next((t["value"] for t in r.get("telecom", []) if t.get("system") == "phone"), None),
        postal_code=address.get("postalCode"),
        address=address_text or None,
    )


def _ref_id(reference: dict) -> str:
    return reference["reference"].split("/", 1)[1]


def _parse_item(r: dict, hospital_id: str) -> ClinicalItem | None:
    kind = r["resourceType"]
    if kind == "AllergyIntolerance":
        reactions = [m["text"] for rx in r.get("reaction", []) for m in rx.get("manifestation", [])]
        detail = ", ".join(reactions) or "reaction not recorded"
        if r.get("criticality"):
            detail += f", {r['criticality']} criticality"
        return ClinicalItem(r["id"], _ref_id(r["patient"]), hospital_id, "allergy",
                            r["code"]["text"], detail, r.get("recordedDate"))
    if kind == "MedicationRequest":
        text = r["medicationCodeableConcept"]["text"]
        dosage = " ".join(d.get("text", "") for d in r.get("dosageInstruction", []))
        return ClinicalItem(r["id"], _ref_id(r["subject"]), hospital_id, "medication", text, dosage,
                            r.get("authoredOn"), drug=knowledge.normalize_drug(text),
                            dose_mg=knowledge.parse_dose_mg(dosage))
    if kind == "Condition":
        return ClinicalItem(r["id"], _ref_id(r["subject"]), hospital_id, "condition",
                            r["code"]["text"], "", r.get("onsetDateTime"))
    return None
