"""Turn a Synthea CSV export into three messy hospital bundles with a known answer key.

    python -m app.synthea_import --synthea path/to/synthea/csv

Synthea (https://github.com/synthetichealth/synthea) generates realistic made-up patients.
Each one has a single clean record holding every visit, allergy, medication and condition.
Real hospitals never see that, so this script:

  1. assigns every Synthea provider organization to one of our three hospitals, and gives
     each hospital only what was recorded at its own visits;
  2. registers the patient separately at each hospital, with the mistakes front desks make:
     nicknames, maiden names, typos, mistyped birth dates, old addresses, missing phones;
  3. adds look-alike relatives who share a household (a parent or child with the same name,
     a twin, a spouse) and must NOT be merged with the patient;
  4. hides dangerous drug combinations across hospitals: half on the patient's record at
     one hospital, the other half at another, written the way Synthea writes drug names;
  5. writes FHIR R4 bundles in the same shape as backend/data, plus truth/answer_key.json,
     which says which records are really the same person and where the conflicts are hidden.

`python -m app.evaluate` then scores the matcher and the conflict checker against that key.
Unlike app.benchmark, neither the people nor their medications were written by us.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .seed import HOSPITALS

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "eval" / "synthea"

# How often a record at a patient's second or third hospital carries each mistake.
RATES = {
    "nickname": 0.35,         # of patients whose first name has a common nickname
    "first_initial": 0.04,
    "middle_name": 0.10,      # of patients with a middle name: "Jayne" becomes "Jayne Mira"
    "first_name_typo": 0.04,
    "maiden_name": 0.50,      # of patients with a maiden name on file
    "last_name_typo": 0.07,
    "birth_date_typo": 0.05,
    "moved": 0.20,            # new address; half of them also have a new phone
    "no_phone": 0.20,
}

# Deliberately wider than the matcher's own nickname list, so this is not an open-book test.
NICKNAMES = {
    "William": ["Bill", "Will", "Liam"], "Robert": ["Bob", "Rob", "Bobby"], "James": ["Jim", "Jimmy"],
    "John": ["Jack", "Johnny"], "Michael": ["Mike", "Mick"], "Richard": ["Rick", "Dick", "Rich"],
    "Charles": ["Charlie", "Chuck"], "Thomas": ["Tom", "Tommy"], "Joseph": ["Joe", "Joey"],
    "Christopher": ["Chris"], "Daniel": ["Dan", "Danny"], "Matthew": ["Matt"], "Anthony": ["Tony"],
    "Edward": ["Ed", "Ted", "Eddie"], "Steven": ["Steve"], "Andrew": ["Andy", "Drew"], "Kenneth": ["Ken"],
    "Joshua": ["Josh"], "Benjamin": ["Ben"], "Samuel": ["Sam"], "Alexander": ["Alex"], "Nicholas": ["Nick"],
    "Timothy": ["Tim"], "Patrick": ["Pat"], "Gregory": ["Greg"], "Raymond": ["Ray"], "Lawrence": ["Larry"],
    "Francisco": ["Paco", "Frank"], "José": ["Pepe"], "Jose": ["Pepe"], "Guillermo": ["Memo", "Bill"],
    "Eduardo": ["Lalo", "Eddie"], "Roberto": ["Beto"], "Alejandro": ["Alex"], "Ignacio": ["Nacho"],
    "Elizabeth": ["Liz", "Beth", "Betty"], "Margaret": ["Maggie", "Meg", "Peggy"],
    "Katherine": ["Kate", "Katie", "Kathy"], "Catherine": ["Cathy", "Kate"], "Jennifer": ["Jen", "Jenny"],
    "Patricia": ["Pat", "Trish", "Patty"], "Barbara": ["Barb"], "Susan": ["Sue", "Susie"],
    "Jessica": ["Jess"], "Rebecca": ["Becky", "Becca"], "Deborah": ["Deb", "Debbie"],
    "Christina": ["Tina", "Chris"], "Victoria": ["Vicky", "Tori"], "Samantha": ["Sam"],
    "Alexandra": ["Alex", "Sandra"], "Abigail": ["Abby"], "Dorothy": ["Dot", "Dottie"],
    "Stephanie": ["Steph"], "Kimberly": ["Kim"], "Cynthia": ["Cindy"], "Pamela": ["Pam"],
    "María": ["Mari"], "Maria": ["Mari"], "Guadalupe": ["Lupe"], "Dolores": ["Lola"],
    "Teresa": ["Tere", "Terry"], "Isabel": ["Isa", "Chabela"], "Mercedes": ["Meche"],
}



def _allergy(text: str, reaction: str) -> dict:
    return {"kind": "allergy", "text": text, "reaction": reaction, "criticality": "high", "date": "2019-05-01"}


def _medication(text: str, date: str = "2026-09-15") -> dict:
    return {"kind": "medication", "text": text, "dosage": _strength(text), "date": date}


# Dangerous combinations to hide: (what it is, the half at the home hospital, the half elsewhere).
# The last two use brand names, as real charts often do.
PLANTED = [
    ("penicillin allergy, then amoxicillin",
     lambda: _allergy("Penicillin V", "Anaphylaxis"), lambda: _medication("Amoxicillin 500 MG Oral Tablet")),
    ("sulfa antibiotic allergy, then the same antibiotic",
     lambda: _allergy("Sulfamethoxazole / Trimethoprim", "Hives"),
     lambda: _medication("Sulfamethoxazole 800 MG / Trimethoprim 160 MG Oral Tablet")),
    ("aspirin allergy, then ibuprofen",
     lambda: _allergy("Aspirin", "Wheezing"), lambda: _medication("Ibuprofen 400 MG Oral Tablet [Ibu]")),
    ("warfarin, then naproxen",
     lambda: _medication("Warfarin Sodium 5 MG Oral Tablet", "2021-03-10"),
     lambda: _medication("Naproxen sodium 220 MG Oral Tablet")),
    ("warfarin, then clopidogrel",
     lambda: _medication("Warfarin Sodium 5 MG Oral Tablet", "2021-03-10"),
     lambda: _medication("Clopidogrel 75 MG Oral Tablet")),
    ("nitroglycerin, then sildenafil",
     lambda: _medication("Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray", "2022-06-01"),
     lambda: _medication("sildenafil 50 MG Oral Tablet")),
    ("simvastatin, then clarithromycin",
     lambda: _medication("Simvastatin 20 MG Oral Tablet", "2018-11-20"),
     lambda: _medication("Clarithromycin 500 MG Oral Tablet")),
    ("sertraline, then tramadol",
     lambda: _medication("sertraline 100 MG Oral Tablet", "2023-02-14"),
     lambda: _medication("tramadol hydrochloride 50 MG Oral Tablet")),
    ("warfarin under its brand name Coumadin, then naproxen",
     lambda: _medication("Coumadin 5 MG Oral Tablet", "2021-03-10"),
     lambda: _medication("Naproxen sodium 220 MG Oral Tablet")),
    ("aspirin allergy, then ibuprofen under its brand name Advil",
     lambda: _allergy("Aspirin", "Wheezing"), lambda: _medication("Advil 200 MG Oral Tablet")),
]

STREETS = ["Main Street", "Elm Street", "Washington Street", "Maple Avenue", "Pleasant Street",
           "Summer Street", "School Street", "Park Avenue", "Highland Avenue", "Union Street"]
AREA_CODES = ["339", "351", "413", "508", "617", "774", "781", "857", "978"]
# Each hospital's system has its own conventions. These apply to every record it holds.
PHONE_STYLES = {"orion": "{}-{}-{}", "lyra": "({}) {}-{}", "vega": "{}.{}.{}"}
UPPERCASE_NAMES = {"vega"}
_NEIGHBOURS = {  # keys next to each other on a keyboard
    "a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh", "h": "gj", "i": "uo",
    "j": "hk", "k": "jl", "l": "k", "m": "n", "n": "bm", "o": "ip", "p": "o", "q": "w", "r": "et",
    "s": "ad", "t": "ry", "u": "yi", "v": "cb", "w": "qe", "x": "zc", "y": "tu", "z": "x",
}


@dataclass
class Person:
    """One real (made-up) person, before any hospital has typed them in."""

    id: str
    kind: str  # "synthea" | "namesake" | "twin" | "spouse"
    relative_of: str | None
    given: str
    middle: str
    family: str
    maiden: str
    gender: str
    birth_date: str
    line: str
    city: str
    state: str
    postal_code: str
    phone: str
    visits: dict[str, int]  # hospital id -> number of visits there
    items: dict[str, list[dict]]  # hospital id -> allergies, medications and conditions recorded there

    @property
    def home(self) -> str:
        """The hospital the person uses most. Its record is the careful, up-to-date one."""
        return max(self.visits, key=lambda h: (self.visits[h], h))


def hospital_of(organization_id: str) -> str:
    """Each Synthea provider organization belongs to one of our hospitals, always the same one."""
    ids = sorted(HOSPITALS)
    return ids[zlib.crc32(organization_id.encode()) % len(ids)]


def read_people(synthea_dir: Path, phones: Iterator[str]) -> list[Person]:
    hospital_of_visit: dict[str, str] = {}
    visits: dict[str, Counter] = defaultdict(Counter)
    for row in _rows(synthea_dir, "encounters"):
        hospital = hospital_of(row["ORGANIZATION"])
        hospital_of_visit[row["Id"]] = hospital
        visits[row["PATIENT"]][hospital] += 1

    # patient -> hospital -> (kind, text) -> item. Keyed so a repeat prescription counts once.
    items: dict[str, dict[str, dict[tuple, dict]]] = defaultdict(lambda: defaultdict(dict))

    def add(row: dict, item: dict) -> None:
        hospital = hospital_of_visit.get(row["ENCOUNTER"])
        if hospital and not row["STOP"]:  # still current
            items[row["PATIENT"]][hospital][(item["kind"], item["text"].lower())] = item

    for row in _rows(synthea_dir, "allergies"):
        if row["DESCRIPTION"].startswith("Allergic disposition"):  # "has allergies", no substance named
            continue
        add(row, {"kind": "allergy", "text": _plain(row["DESCRIPTION"]), "reaction": _plain(row["DESCRIPTION1"]),
                  "criticality": "high" if row["SEVERITY1"] == "SEVERE" else "low", "date": row["START"][:10]})
    for row in _rows(synthea_dir, "medications"):
        add(row, {"kind": "medication", "text": row["DESCRIPTION"], "dosage": _strength(row["DESCRIPTION"]),
                  "date": row["START"][:10]})
    for row in _rows(synthea_dir, "conditions"):
        if row["DESCRIPTION"].endswith("(disorder)"):  # skip social findings such as "Full-time employment"
            add(row, {"kind": "condition", "text": _plain(row["DESCRIPTION"]), "date": row["START"][:10]})

    people = []
    for row in _rows(synthea_dir, "patients"):
        if not visits[row["Id"]]:
            continue
        people.append(Person(
            id=f"p{len(people) + 1:03d}", kind="synthea", relative_of=None,
            given=_name(row["FIRST"]), middle=_name(row["MIDDLE"]), family=_name(row["LAST"]),
            maiden=_name(row["MAIDEN"]), gender={"M": "male", "F": "female"}[row["GENDER"]],
            birth_date=row["BIRTHDATE"], line=row["ADDRESS"], city=row["CITY"], state=row["STATE"],
            postal_code="" if row["ZIP"] == "00000" else row["ZIP"],  # 00000 is Synthea's "unknown"
            phone=next(phones), visits=dict(visits[row["Id"]]),
            items={h: list(found.values()) for h, found in items[row["Id"]].items()},
        ))
    return people


def make_relatives(people: list[Person], count_each: int, rng: random.Random) -> list[Person]:
    """Different people who look alike on paper: same household, phone and surname."""
    names = {g: sorted({p.given for p in people if p.gender == g}) for g in ("male", "female")}
    adults = [p for p in people if p.birth_date < "1996"]
    relatives = []
    for kind in ("namesake", "twin", "spouse"):
        for base in rng.sample(adults, min(count_each, len(adults))):
            given, gender, birth_date, family = base.given, base.gender, base.birth_date, base.family
            if kind == "namesake":  # a parent or child with the same first and last name
                year = int(base.birth_date[:4])
                gap = rng.randint(22, 35)
                year = year - gap if year - gap >= 1925 else year + gap
                birth_date = f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
                if rng.random() < 0.5:
                    family = f"{family} {'Jr' if year > int(base.birth_date[:4]) else 'Sr'}"
            else:
                if kind == "spouse":
                    gender = "female" if base.gender == "male" else "male"
                    year = int(base.birth_date[:4]) + rng.randint(-6, 6)
                    birth_date = f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
                else:  # a twin: same birth date, any gender
                    gender = rng.choice(["male", "female"])
                given = rng.choice([n for n in names[gender] if n != base.given] or ["Jordan"])
            hospitals = rng.sample(sorted(base.visits), min(len(base.visits), rng.choice([1, 2])))
            donor = rng.choice(people)  # their own, unrelated medical history
            relatives.append(Person(
                id=f"{base.id}-{kind}", kind=kind, relative_of=base.id, given=given, middle="", family=family,
                maiden="", gender=gender, birth_date=birth_date, line=base.line, city=base.city,
                state=base.state, postal_code=base.postal_code, phone=base.phone,
                visits={h: 2 if i == 0 else 1 for i, h in enumerate(hospitals)},
                items={hospitals[0]: [dict(item) for item in donor.items.get(donor.home, [])]},
            ))
    return relatives


def plant_conflicts(people: list[Person], count: int, rng: random.Random) -> list[dict]:
    """Hide `count` dangerous combinations, each split between two of one patient's hospitals."""
    eligible = [p for p in people if p.kind == "synthea" and len(p.visits) > 1]
    planted = []
    for n, person in enumerate(rng.sample(eligible, min(count, len(eligible)))):
        what, at_home, elsewhere = PLANTED[n % len(PLANTED)]
        away = rng.choice(sorted(h for h in person.visits if h != person.home))
        person.items.setdefault(person.home, []).append({**at_home(), "planted": n})
        person.items.setdefault(away, []).append({**elsewhere(), "planted": n})
        planted.append({"person": person.id, "what": what, "items": []})  # item ids are filled in later
    return planted


class Registrar:
    """Types a person into one hospital's system, mistakes included."""

    def __init__(self, rng: random.Random, phones: Iterator[str], towns: list[tuple[str, str]],
                 rates: dict[str, float]):
        self.rng, self.phones, self.towns, self.rates = rng, phones, towns, rates

    def register(self, person: Person, hospital: str) -> tuple[dict, list[str]]:
        """The patient fields as this hospital has them, and the names of the mistakes made."""
        rng, mistakes = self.rng, []
        rec = {"given": person.given, "family": person.family, "gender": person.gender,
               "birthDate": person.birth_date, "line": person.line, "city": person.city,
               "state": person.state, "postalCode": person.postal_code, "phone": person.phone}
        if hospital != person.home:
            self._first_name(person, rec, mistakes)
            self._last_name(person, rec, mistakes)
            if self._roll("birth_date_typo"):
                rec["birthDate"], mistake = _mistype_date(person.birth_date, rng)
                mistakes.append(mistake)
            if self._roll("moved"):
                rec["line"] = f"{rng.randint(10, 999)} {rng.choice(STREETS)}"
                rec["city"], rec["postalCode"] = rng.choice(self.towns)
                mistakes.append("moved")
                if rng.random() < 0.5:
                    rec["phone"] = next(self.phones)
                    mistakes.append("new_phone")
            if "new_phone" not in mistakes and self._roll("no_phone"):
                rec["phone"] = None
                mistakes.append("no_phone")
        # House style, applied to every record at this hospital. Not counted as a mistake.
        if hospital in UPPERCASE_NAMES:
            rec["given"], rec["family"] = rec["given"].upper(), rec["family"].upper()
        if rec["phone"]:
            rec["phone"] = PHONE_STYLES.get(hospital, "{}-{}-{}").format(*rec["phone"].split("-"))
        return rec, mistakes

    def _roll(self, mistake: str) -> bool:
        return self.rng.random() < self.rates[mistake]

    def _first_name(self, person: Person, rec: dict, mistakes: list[str]) -> None:
        if person.given in NICKNAMES and self._roll("nickname"):
            rec["given"] = self.rng.choice(NICKNAMES[person.given])
            mistakes.append("nickname")
        elif self._roll("first_initial"):
            rec["given"] = f"{person.given[0]}."
            mistakes.append("first_initial")
        elif person.middle and self._roll("middle_name"):
            rec["given"] = f"{person.given} {person.middle}"
            mistakes.append("middle_name")
        elif self._roll("first_name_typo") and (typo := _typo(person.given, self.rng)) != person.given:
            rec["given"] = typo
            mistakes.append("first_name_typo")

    def _last_name(self, person: Person, rec: dict, mistakes: list[str]) -> None:
        if person.maiden and self._roll("maiden_name"):
            if self.rng.random() < 0.3:
                rec["family"] = f"{person.maiden}-{person.family}"
                mistakes.append("hyphenated_name")
            else:
                rec["family"] = person.maiden
                mistakes.append("maiden_name")
        elif self._roll("last_name_typo") and (typo := _typo(person.family, self.rng)) != person.family:
            rec["family"] = typo
            mistakes.append("last_name_typo")


def build_bundles(people: list[Person], registrar: Registrar,
                  planted: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """The FHIR bundle for each hospital, and for each record: whose it is and what's wrong with it."""
    rng = registrar.rng
    bundles, records = {}, {}
    for hospital, (name, prefix) in HOSPITALS.items():
        entries = [_entry({"resourceType": "Organization", "id": f"{hospital}-org", "name": name})]
        counter = 0

        def next_id(kind: str) -> str:
            nonlocal counter
            counter += 1
            return f"{hospital}-{kind}-{counter:04d}"

        patients = [p for p in people if hospital in p.visits]
        rng.shuffle(patients)  # so record numbers don't line up from one hospital to the next
        for person in patients:
            rec, mistakes = registrar.register(person, hospital)
            pid = next_id("pt")
            records[pid] = {"person": person.id, "home": hospital == person.home, "mistakes": mistakes}
            entries.append(_entry(_patient(rec, pid, f"{prefix}-{rng.randint(100000, 999999)}", hospital)))
            subject = {"reference": f"Patient/{pid}"}
            for item in person.items.get(hospital, []):
                resource = _item(item, next_id, subject)
                if "planted" in item:
                    planted[item["planted"]]["items"].append(resource["id"])
                entries.append(_entry(resource))
        bundles[hospital] = {"resourceType": "Bundle", "id": hospital, "type": "collection", "entry": entries}
    return bundles, records


def generate(synthea_dir: Path, out_dir: Path = DEFAULT_OUT, seed: int = 2026, relatives: int = 10,
             conflicts: int = 20, rates: dict[str, float] | None = None) -> dict:
    """Write hospitals/*.json and truth/answer_key.json under out_dir. Returns the answer key."""
    rng = random.Random(seed)
    # 555-0100 to 555-0199 is the range reserved for made-up phone numbers.
    numbers = [f"{area}-555-01{n:02d}" for area in AREA_CODES for n in range(100)]
    rng.shuffle(numbers)
    phones = iter(numbers)
    people = read_people(synthea_dir, phones)
    towns = sorted({(p.city, p.postal_code) for p in people if p.postal_code})
    people += make_relatives(people, relatives, rng)
    planted = plant_conflicts(people, conflicts, rng)
    bundles, records = build_bundles(people, Registrar(rng, phones, towns, {**RATES, **(rates or {})}), planted)
    truth = {
        "source": "Synthea sample patients, split across three hospitals by app.synthea_import",
        "seed": seed,
        "people": {p.id: {"kind": p.kind, "relative_of": p.relative_of} for p in people},
        "records": records,
        "planted_conflicts": planted,
    }
    (out_dir / "hospitals").mkdir(parents=True, exist_ok=True)
    (out_dir / "truth").mkdir(parents=True, exist_ok=True)
    for hospital, bundle in bundles.items():
        (out_dir / "hospitals" / f"{hospital}.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    (out_dir / "truth" / "answer_key.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return truth


# --- FHIR resources, in the same shape app.seed writes and app.records reads

def _entry(resource: dict) -> dict:
    return {"fullUrl": f"{resource['resourceType']}/{resource['id']}", "resource": resource}


def _patient(rec: dict, pid: str, mrn: str, hospital: str) -> dict:
    address = {"line": [rec["line"]], "city": rec["city"], "state": rec["state"]}
    if rec["postalCode"]:
        address["postalCode"] = rec["postalCode"]
    resource = {
        "resourceType": "Patient", "id": pid,
        "identifier": [{"system": f"urn:hospital:{hospital}:mrn", "value": mrn}],
        "name": [{"family": rec["family"], "given": rec["given"].split()}],
        "gender": rec["gender"], "birthDate": rec["birthDate"], "address": [address],
    }
    if rec["phone"]:
        resource["telecom"] = [{"system": "phone", "value": rec["phone"]}]
    return resource


def _item(item: dict, next_id, subject: dict) -> dict:
    if item["kind"] == "allergy":
        resource = {"resourceType": "AllergyIntolerance", "id": next_id("al"), "patient": subject,
                    "code": {"text": item["text"]}, "criticality": item["criticality"],
                    "recordedDate": item["date"]}
        if item["reaction"]:
            resource["reaction"] = [{"manifestation": [{"text": item["reaction"]}]}]
        return resource
    if item["kind"] == "condition":
        return {"resourceType": "Condition", "id": next_id("cd"), "subject": subject,
                "clinicalStatus": {"coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "code": {"text": item["text"]}, "onsetDateTime": item["date"]}
    return {"resourceType": "MedicationRequest", "id": next_id("rx"), "status": "active", "intent": "order",
            "subject": subject, "medicationCodeableConcept": {"text": item["text"]},
            "dosageInstruction": [{"text": item["dosage"]}] if item["dosage"] else [],
            "authoredOn": item["date"]}


# --- reading Synthea

def _rows(synthea_dir: Path, table: str) -> Iterator[dict]:
    with open(synthea_dir / f"{table}.csv", newline="", encoding="utf-8") as file:
        yield from csv.DictReader(file)


def _name(text: str) -> str:
    """Synthea tags every name with a number ("Guillermo498") so no real person is named."""
    return re.sub(r"\d", "", text).strip()


def _plain(text: str) -> str:
    """Drop SNOMED's trailing category tags: "Eggs (edible) (substance)" -> "Eggs"."""
    return re.sub(r"(\s*\([a-z ]+\))+$", "", text).strip()


def _strength(description: str) -> str:
    """"Simvastatin 20 MG Oral Tablet" -> "20 mg". Synthea's CSV has no dosing directions."""
    match = re.search(r"(\d+(?:\.\d+)?) MG(?![/A-Za-z])", description)
    return f"{match.group(1)} mg" if match else ""


# --- mistakes

def _typo(name: str, rng: random.Random) -> str:
    if len(name) < 4:
        return name
    i = rng.randrange(1, len(name) - 1)
    kind = rng.choice(["drop", "double", "swap", "replace"])
    if kind == "drop":
        return name[:i] + name[i + 1:]
    if kind == "double":
        return name[:i] + name[i] + name[i:]
    if kind == "swap" and name[i] != name[i + 1]:
        return name[:i] + name[i + 1] + name[i] + name[i + 2:]
    return name[:i] + rng.choice(_NEIGHBOURS.get(name[i].lower(), "e")) + name[i + 1:]


def _mistype_date(date: str, rng: random.Random) -> tuple[str, str]:
    """A wrong but still valid date, and the name of the mistake."""
    year, month, day = date.split("-")
    kind = rng.choice(["swap", "transpose", "digit"])
    if kind == "swap" and int(day) <= 12 and day != month:
        return f"{year}-{day}-{month}", "birth_date_day_month_swapped"
    transposed = f"{year[:2]}{year[3]}{year[2]}"
    if kind == "transpose" and transposed < year:  # an earlier year, so never in the future
        return f"{transposed}-{month}-{day}", "birth_date_digits_transposed"
    days = [d for d in range(1, 29) if d != int(day) and f"{d:02d}"[0] == day[0]]
    if days:
        return f"{year}-{month}-{rng.choice(days):02d}", "birth_date_one_digit_off"
    return f"{int(year) - 1}-{month}-{day}", "birth_date_one_digit_off"  # day 30 or 31


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--synthea", type=Path, required=True, help="folder holding Synthea's CSV files")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--relatives", type=int, default=10, help="look-alike relatives of each kind")
    parser.add_argument("--conflicts", type=int, default=20, help="dangerous combinations to hide")
    args = parser.parse_args()
    key = generate(args.synthea, args.out, args.seed, args.relatives, args.conflicts)
    per_person = Counter(r["person"] for r in key["records"].values())
    kinds = Counter(p["kind"] for p in key["people"].values())
    print(f"People:   {len(key['people'])} ({kinds['synthea']} from Synthea, "
          f"{len(key['people']) - kinds['synthea']} look-alike relatives)")
    print(f"Records:  {len(key['records'])} across {len(HOSPITALS)} hospitals "
          f"({sum(n > 1 for n in per_person.values())} people are at more than one)")
    print(f"Hidden:   {len(key['planted_conflicts'])} dangerous combinations, each split between two hospitals")
    print(f"Wrote {args.out}")
