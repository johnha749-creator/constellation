"""Generate synthetic FHIR R4 bundles for three fictional hospitals.

Every patient here is made up. The demo patients carry deliberate data-quality
problems (nicknames, typos, swapped dates, a same-name stranger) and cross-hospital
medication conflicts. The filler patients make the matching problem realistic and
should produce no conflicts.

Regenerate the JSON files with:  python -m app.seed
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# id -> (name, MRN prefix)
HOSPITALS = {
    "orion": ("Orion General Hospital", "OR"),
    "lyra": ("Lyra Medical Center", "LY"),
    "vega": ("Vega Community Clinic", "VG"),
}


def allergy(text: str, reaction: str, criticality: str, date: str) -> dict:
    return {"text": text, "reaction": reaction, "criticality": criticality, "date": date}


def med(name: str, dosage: str, date: str) -> dict:
    return {"name": name, "dosage": dosage, "date": date}


def condition(text: str, date: str) -> dict:
    return {"text": text, "date": date}


# Each inner list is one real (fictional) person; each dict is one hospital's record of them.
DEMO_PATIENTS: list[list[dict]] = [
    # Flagship demo. Orion knows about the penicillin allergy and kidney disease.
    # Lyra's ER prescribes amoxicillin and ibuprofen; Vega adds a second ACE inhibitor.
    [
        {"hospital": "orion", "given": "Maria", "family": "Gonzalez", "gender": "female",
         "birthDate": "1958-03-14", "phone": "415-555-0142", "line": "88 Ocean Ave", "postalCode": "94112",
         "allergies": [allergy("Penicillin", "Anaphylaxis", "high", "2019-06-02")],
         "conditions": [condition("Type 2 diabetes mellitus", "2012-04-10"),
                        condition("Chronic kidney disease, stage 3", "2021-11-03")],
         "medications": [med("Metformin", "500 mg twice daily", "2012-04-10"),
                         med("Lisinopril", "10 mg once daily", "2018-01-22")]},
        {"hospital": "lyra", "given": "Maria", "family": "Gonzales", "gender": "female",
         "birthDate": "1958-03-14", "phone": "(415) 555-0142", "line": "88 Ocean Avenue", "postalCode": "94112",
         "conditions": [condition("Community-acquired pneumonia", "2026-09-28")],
         "medications": [med("Amoxicillin", "875 mg twice daily", "2026-09-28"),
                         med("Ibuprofen", "600 mg every 6 hours as needed", "2026-09-28")]},
        {"hospital": "vega", "given": "M.", "family": "Gonzalez", "gender": "female",
         "birthDate": "1958-03-14", "line": "1450 Noriega St", "postalCode": "94122",
         "conditions": [condition("Essential hypertension", "2024-02-15")],
         "medications": [med("Enalapril", "5 mg once daily", "2024-02-15")]},
    ],
    # A different person with the same name. Must NOT be merged with the Maria above.
    [
        {"hospital": "vega", "given": "Maria", "family": "Gonzalez", "gender": "female",
         "birthDate": "1985-09-30", "phone": "415-555-0198", "line": "302 Valencia St", "postalCode": "94103",
         "conditions": [condition("Hypothyroidism", "2020-05-11")],
         "medications": [med("Levothyroxine", "75 mcg once daily", "2020-05-11")]},
    ],
    # Nickname and punctuation at Lyra, day/month-swapped birth date at Vega.
    # Three hospitals, three blood-thinner problems.
    [
        {"hospital": "orion", "given": "James", "family": "O'Brien", "gender": "male",
         "birthDate": "1947-11-02", "phone": "415-555-0117", "line": "19 Taraval St", "postalCode": "94116",
         "conditions": [condition("Atrial fibrillation", "2020-08-19")],
         "medications": [med("Warfarin", "5 mg once daily", "2020-08-19")]},
        {"hospital": "lyra", "given": "Jim", "family": "OBrien", "gender": "male",
         "birthDate": "1947-11-02", "line": "19 Taraval St", "postalCode": "94116",
         "conditions": [condition("Low back pain", "2026-08-30")],
         "medications": [med("Naproxen", "500 mg twice daily", "2026-08-30")]},
        {"hospital": "vega", "given": "James", "family": "O Brien", "gender": "male",
         "birthDate": "1947-02-11", "phone": "415-555-0163", "line": "19 Taraval St", "postalCode": "94116",
         "conditions": [condition("Atrial fibrillation", "2025-12-04")],
         "medications": [med("Apixaban", "5 mg twice daily", "2025-12-04")]},
    ],
    # Married name, new address and phone, and a birth-date typo: the link needs human review.
    [
        {"hospital": "orion", "given": "Aisha", "family": "Patel", "gender": "female",
         "birthDate": "1990-07-22", "phone": "415-555-0175", "line": "640 Clement St", "postalCode": "94118",
         "allergies": [allergy("Sulfa drugs", "Hives, facial swelling", "high", "2016-03-09")],
         "conditions": [condition("Major depressive disorder", "2023-01-17")],
         "medications": [med("Sertraline", "100 mg once daily", "2023-01-17")]},
        {"hospital": "lyra", "given": "Aisha", "family": "Patel-Khan", "gender": "female",
         "birthDate": "1990-07-27", "phone": "510-555-0129", "line": "2210 Shattuck Ave", "city": "Berkeley",
         "postalCode": "94704",
         "conditions": [condition("Urinary tract infection", "2026-10-01"), condition("Ankle sprain", "2026-10-01")],
         "medications": [med("Sulfamethoxazole-trimethoprim", "800-160 mg twice daily", "2026-10-01"),
                         med("Tramadol", "50 mg every 6 hours as needed", "2026-10-01")]},
    ],
    # Low-stakes reconciliation issue: same statin, different dose.
    [
        {"hospital": "orion", "given": "Robert", "family": "Chen", "gender": "male",
         "birthDate": "1972-05-05", "phone": "415-555-0151", "line": "77 Irving St", "postalCode": "94122",
         "conditions": [condition("Hyperlipidemia", "2019-09-12")],
         "medications": [med("Atorvastatin", "20 mg once daily", "2019-09-12")]},
        {"hospital": "lyra", "given": "Bob", "family": "Chen", "gender": "male",
         "birthDate": "1972-05-05", "phone": "415-555-0151", "line": "77 Irving St", "postalCode": "94122",
         "conditions": [condition("Essential hypertension", "2025-06-03")],
         "medications": [med("Atorvastatin", "40 mg once daily", "2025-06-03"),
                         med("Amlodipine", "5 mg once daily", "2025-06-03")]},
    ],
]

FILLER_FIRST_NAMES = [
    ("Olivia", "female"), ("Liam", "male"), ("Sophia", "female"), ("Noah", "male"), ("Emma", "female"),
    ("Ethan", "male"), ("Ava", "female"), ("Lucas", "male"), ("Mia", "female"), ("Daniel", "male"),
    ("Grace", "female"), ("William", "male"), ("Elizabeth", "female"), ("Michael", "male"),
    ("Katherine", "female"), ("Thomas", "male"), ("Nadia", "female"), ("Kenji", "male"),
    ("Fatima", "female"), ("Mateo", "male"),
]
FILLER_LAST_NAMES = [
    "Nguyen", "Kim", "Johnson", "Okafor", "Rossi", "Haddad", "Silva", "Novak", "Yamamoto", "Murphy",
    "Fischer", "Alvarez", "Kowalski", "Mensah", "Lindqvist", "Dubois", "Ibrahim", "Park", "Santos", "Walsh",
]
FILLER_NICKNAMES = {"William": "Bill", "Elizabeth": "Liz", "Michael": "Mike", "Katherine": "Kate",
                    "Thomas": "Tom", "Daniel": "Dan"}
STREETS = ["Geary Blvd", "Mission St", "Judah St", "Divisadero St", "Clement St", "Fillmore St",
           "Church St", "Haight St", "Polk St", "Balboa St"]
SF_ZIPS = ["94110", "94114", "94115", "94117", "94121", "94123", "94127", "94131", "94133"]
# Condition -> a medication for it. Chosen so filler patients never trigger conflict rules.
SAFE_TREATMENTS = {
    "Hypothyroidism": ("Levothyroxine", "50 mcg once daily"),
    "Gastroesophageal reflux disease": ("Omeprazole", "20 mg once daily"),
    "Essential hypertension": ("Amlodipine", "5 mg once daily"),
    "Asthma": ("Albuterol", "90 mcg inhaler, 2 puffs as needed"),
    "Hyperlipidemia": ("Atorvastatin", "10 mg once daily"),
    "Osteoarthritis of knee": ("Acetaminophen", "500 mg as needed"),
    "Seasonal allergic rhinitis": ("Loratadine", "10 mg once daily"),
}
HARMLESS_ALLERGIES = [("Latex", "Rash"), ("Shellfish", "Hives"), ("Peanuts", "Hives"), ("Bee stings", "Swelling")]


def filler_patients(rng: random.Random, count: int = 18) -> list[list[dict]]:
    people = []
    names = zip(rng.sample(FILLER_FIRST_NAMES, count), rng.sample(FILLER_LAST_NAMES, count))
    phones = rng.sample(range(100), count)
    for ((given, gender), family), phone in zip(names, phones):
        date = f"{rng.randint(2015, 2026)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        problems = rng.sample(sorted(SAFE_TREATMENTS), rng.randint(1, 2))
        base = {
            "given": given, "family": family, "gender": gender,
            "birthDate": f"{rng.randint(1940, 2006)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "phone": f"628-555-01{phone:02d}",
            "line": f"{rng.randint(10, 3999)} {rng.choice(STREETS)}",
            "postalCode": rng.choice(SF_ZIPS),
            "conditions": [condition(p, date) for p in problems],
            "medications": [med(*SAFE_TREATMENTS[p], date) for p in problems],
        }
        if rng.random() < 0.3:
            substance, reaction = rng.choice(HARMLESS_ALLERGIES)
            base["allergies"] = [allergy(substance, reaction, "low", date)]

        records = []
        for i, hospital in enumerate(rng.sample(sorted(HOSPITALS), rng.choice([1, 2, 2]))):
            record = dict(base, hospital=hospital)
            if i > 0:  # the second hospital's copy is a little different, as in real life
                variation = rng.choice(["nickname", "moved", "no_phone", "same"])
                if variation == "nickname" and given in FILLER_NICKNAMES:
                    record["given"] = FILLER_NICKNAMES[given]
                elif variation == "moved":
                    record["line"] = f"{rng.randint(10, 3999)} {rng.choice(STREETS)}"
                    record["postalCode"] = rng.choice([z for z in SF_ZIPS if z != base["postalCode"]])
                elif variation == "no_phone":
                    record.pop("phone")
            records.append(record)
        people.append(records)
    return people


def build_bundles(seed: int = 2026) -> dict[str, dict]:
    rng = random.Random(seed)
    entries: dict[str, list[dict]] = {
        h: [_entry({"resourceType": "Organization", "id": f"{h}-org", "name": name})]
        for h, (name, _) in HOSPITALS.items()
    }
    counters = {h: 0 for h in HOSPITALS}

    def next_id(hospital: str, kind: str) -> str:
        counters[hospital] += 1
        return f"{hospital}-{kind}-{counters[hospital]:03d}"

    for person in DEMO_PATIENTS + filler_patients(rng):
        for rec in person:
            h = rec["hospital"]
            pid = next_id(h, "pt")
            mrn = f"{HOSPITALS[h][1]}-{rng.randint(100000, 999999)}"
            subject = {"reference": f"Patient/{pid}"}
            entries[h].append(_entry(_patient(rec, pid, mrn, h)))
            for a in rec.get("allergies", []):
                entries[h].append(_entry({
                    "resourceType": "AllergyIntolerance", "id": next_id(h, "al"), "patient": subject,
                    "code": {"text": a["text"]}, "criticality": a["criticality"],
                    "reaction": [{"manifestation": [{"text": a["reaction"]}]}],
                    "recordedDate": a["date"],
                }))
            for c in rec.get("conditions", []):
                entries[h].append(_entry({
                    "resourceType": "Condition", "id": next_id(h, "cd"), "subject": subject,
                    "clinicalStatus": {"coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                    "code": {"text": c["text"]}, "onsetDateTime": c["date"],
                }))
            for m in rec.get("medications", []):
                entries[h].append(_entry({
                    "resourceType": "MedicationRequest", "id": next_id(h, "rx"), "status": "active",
                    "intent": "order", "subject": subject,
                    "medicationCodeableConcept": {"text": m["name"]},
                    "dosageInstruction": [{"text": m["dosage"]}], "authoredOn": m["date"],
                }))
    return {h: {"resourceType": "Bundle", "id": h, "type": "collection", "entry": e} for h, e in entries.items()}


def _patient(rec: dict, pid: str, mrn: str, hospital: str) -> dict:
    resource = {
        "resourceType": "Patient", "id": pid,
        "identifier": [{"system": f"urn:hospital:{hospital}:mrn", "value": mrn}],
        "name": [{"family": rec["family"], "given": [rec["given"]]}],
        "gender": rec["gender"], "birthDate": rec["birthDate"],
        "address": [{"line": [rec["line"]], "city": rec.get("city", "San Francisco"), "state": "CA",
                     "postalCode": rec["postalCode"]}],
    }
    if rec.get("phone"):
        resource["telecom"] = [{"system": "phone", "value": rec["phone"]}]
    return resource


def _entry(resource: dict) -> dict:
    return {"fullUrl": f"{resource['resourceType']}/{resource['id']}", "resource": resource}


def write_seed(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for hospital, bundle in build_bundles().items():
        (data_dir / f"{hospital}.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")


def ensure_seed_data(data_dir: Path = DATA_DIR) -> None:
    if not any(data_dir.glob("*.json")):
        write_seed(data_dir)


if __name__ == "__main__":
    write_seed()
    print(f"Wrote {len(HOSPITALS)} hospital bundles to {DATA_DIR}")
