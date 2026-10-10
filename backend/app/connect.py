"""Connecting a new hospital: check an uploaded FHIR R4 bundle before any of it is used.

An upload is untrusted input. The whole bundle is checked first, and it's either accepted
completely or rejected with a list of plain-English problems, so a half-read file never ends up
in a patient's record. The checks cover what Constellation relies on: one Organization (the
hospital), at least one Patient, every allergy, condition and medication pointing at a Patient
in the same bundle, and ids that don't clash with records already loaded.
"""
from __future__ import annotations

import re
from collections import Counter

from .records import ClinicalItem, Dataset, Hospital, PatientRecord, parse_bundle

MAX_ENTRIES = 5_000
MAX_PROBLEMS = 8  # list the first few; one bad export usually repeats the same mistake
HOSPITAL_ID = re.compile(r"[a-z][a-z0-9-]{1,39}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Resource type -> (the field that points at the patient, a check that it has its main text)
CLINICAL_TYPES = {
    "AllergyIntolerance": ("patient", lambda r: _text(r.get("code"))),
    "Condition": ("subject", lambda r: _text(r.get("code"))),
    "MedicationRequest": ("subject", lambda r: _text(r.get("medicationCodeableConcept"))),
}


class BundleError(ValueError):
    """The bundle can't be used. `problems` says why, one sentence each."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def read_bundle(bundle: object, dataset: Dataset) -> tuple[Hospital, list[PatientRecord], list[ClinicalItem]]:
    """Check an uploaded bundle against the loaded `dataset`, then parse it. Raises BundleError."""
    problems = check_bundle(bundle, dataset)
    if problems:
        if len(problems) > MAX_PROBLEMS:
            problems = problems[:MAX_PROBLEMS] + [f"...and {len(problems) - MAX_PROBLEMS} more problems."]
        raise BundleError(problems)
    try:
        return parse_bundle(bundle)
    except (KeyError, TypeError, AttributeError, IndexError) as e:
        raise BundleError([f"Part of the bundle couldn't be read ({type(e).__name__}: {e})."]) from e


def check_bundle(bundle: object, dataset: Dataset) -> list[str]:
    """Every problem found, or an empty list if the bundle is fine."""
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        return ['This isn\'t a FHIR Bundle: its "resourceType" must be "Bundle".']
    problems = []
    hospital_id = bundle.get("id")
    if not isinstance(hospital_id, str) or not HOSPITAL_ID.fullmatch(hospital_id):
        problems.append('The bundle\'s "id" names the hospital and must be lowercase letters, digits and '
                        'dashes, like "polaris".')
    elif hospital_id in dataset.hospitals:
        problems.append(f'A hospital with the id "{hospital_id}" is already connected.')

    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        return problems + ["The bundle has no entries."]
    if len(entries) > MAX_ENTRIES:
        return problems + [f"The bundle has {len(entries):,} entries; the limit is {MAX_ENTRIES:,}."]

    resources = []
    for n, entry in enumerate(entries, start=1):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if (not isinstance(resource, dict) or not isinstance(resource.get("resourceType"), str)
                or not isinstance(resource.get("id"), str) or not resource["id"]):
            problems.append(f"Entry {n} has no resource with a resourceType and an id.")
        else:
            resources.append(resource)

    ids = Counter(r["id"] for r in resources)
    problems += [f'The id "{i}" is used more than once.' for i, count in ids.items() if count > 1]
    taken = {*dataset.records, *(item.id for item in dataset.items)}
    problems += [f'The id "{i}" is already used by a record from another hospital.' for i in ids if i in taken]

    orgs = [r for r in resources if r["resourceType"] == "Organization"]
    if len(orgs) != 1 or not _nonblank(orgs[0].get("name")):
        problems.append("The bundle needs exactly one Organization with a name: the hospital itself.")

    patients = {r["id"] for r in resources if r["resourceType"] == "Patient"}
    if not patients:
        problems.append("The bundle has no Patient records.")
    for r in resources:
        kind = r["resourceType"]
        if kind == "Patient":
            problems += _check_patient(r)
        elif kind in CLINICAL_TYPES:
            field, has_text = CLINICAL_TYPES[kind]
            reference = r.get(field, {}).get("reference") if isinstance(r.get(field), dict) else None
            if not (isinstance(reference, str) and reference.startswith("Patient/")
                    and reference.removeprefix("Patient/") in patients):
                problems.append(f'{kind} "{r["id"]}" must point at a Patient in this bundle '
                                f'("{field}": {{"reference": "Patient/<id>"}}).')
            if not has_text(r):
                problems.append(f'{kind} "{r["id"]}" has no text saying what it is.')
    return problems


def _check_patient(r: dict) -> list[str]:
    problems = []
    names = r.get("name")
    name = names[0] if isinstance(names, list) and names and isinstance(names[0], dict) else None
    given = name.get("given", []) if name else None
    if (name is None or not isinstance(name.get("family", ""), str)
            or not isinstance(given, list) or not all(isinstance(g, str) for g in given)
            or not (_nonblank(name.get("family")) or any(g.strip() for g in given))):
        problems.append(f'Patient "{r["id"]}" has no readable name.')
    birth_date = r.get("birthDate")
    if birth_date is not None and (not isinstance(birth_date, str) or not DATE.fullmatch(birth_date)):
        problems.append(f'Patient "{r["id"]}" has a birthDate that isn\'t YYYY-MM-DD.')
    for field in ("identifier", "telecom", "address"):
        value = r.get(field, [])
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            problems.append(f'Patient "{r["id"]}" has an unreadable "{field}".')
    return problems


def _text(concept: object) -> bool:
    return isinstance(concept, dict) and _nonblank(concept.get("text"))


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
