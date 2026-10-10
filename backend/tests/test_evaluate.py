import csv
import json

import pytest

from app.evaluate import evaluate, render
from app.matching import compare_records
from app.records import PatientRecord, load_dataset
from app.synthea_import import RATES, generate, hospital_of

NO_MISTAKES = dict.fromkeys(RATES, 0.0)


def _organizations() -> dict[str, str]:
    """One made-up Synthea organization id for each of our hospitals."""
    found = {}
    for n in range(1000):
        found.setdefault(hospital_of(f"org-{n}"), f"org-{n}")
    return found


ORG = _organizations()


def _write(folder, table, rows):
    with open(folder / f"{table}.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def synthea(tmp_path):
    """A three-patient Synthea export, with only the columns the importer reads."""
    folder = tmp_path / "synthea"
    folder.mkdir()

    def patient(pid, first, last, born, gender, maiden="", middle=""):
        return {"Id": pid, "BIRTHDATE": born, "FIRST": first, "MIDDLE": middle, "LAST": last, "MAIDEN": maiden,
                "GENDER": gender, "ADDRESS": "12 Main Street", "CITY": "Salem", "STATE": "Massachusetts",
                "ZIP": "01970"}

    def visit(vid, pid, hospital):
        return {"Id": vid, "PATIENT": pid, "ORGANIZATION": ORG[hospital]}

    _write(folder, "patients", [
        patient("uuid-ann", "Ann123", "Reed456", "1960-05-17", "F", maiden="Stone789"),
        patient("uuid-bob", "Robert11", "Hale22", "1975-02-03", "M", middle="Lee33"),
        patient("uuid-cy", "Cyrus5", "Vale6", "1988-11-30", "M"),
    ])
    _write(folder, "encounters", [
        visit("v1", "uuid-ann", "orion"), visit("v2", "uuid-ann", "orion"), visit("v3", "uuid-ann", "lyra"),
        visit("v4", "uuid-bob", "lyra"), visit("v5", "uuid-bob", "lyra"), visit("v6", "uuid-bob", "vega"),
        visit("v7", "uuid-cy", "vega"),
    ])
    _write(folder, "allergies", [
        {"START": "2019-06-02", "STOP": "", "PATIENT": "uuid-ann", "ENCOUNTER": "v1",
         "DESCRIPTION": "Penicillin V", "DESCRIPTION1": "Anaphylaxis (disorder)", "SEVERITY1": "SEVERE"},
        {"START": "2019-06-02", "STOP": "", "PATIENT": "uuid-ann", "ENCOUNTER": "v1",
         "DESCRIPTION": "Allergic disposition (finding)", "DESCRIPTION1": "", "SEVERITY1": ""},
    ])
    _write(folder, "medications", [
        {"START": "2026-09-28T10:00:00Z", "STOP": "", "PATIENT": "uuid-ann", "ENCOUNTER": "v3",
         "DESCRIPTION": "Amoxicillin 500 MG Oral Tablet"},
        {"START": "2020-01-01T10:00:00Z", "STOP": "2020-02-01T10:00:00Z", "PATIENT": "uuid-bob", "ENCOUNTER": "v4",
         "DESCRIPTION": "Ibuprofen 400 MG Oral Tablet [Ibu]"},
    ])
    _write(folder, "conditions", [
        {"START": "2012-04-10", "STOP": "", "PATIENT": "uuid-bob", "ENCOUNTER": "v6",
         "DESCRIPTION": "Essential hypertension (disorder)"},
        {"START": "2012-04-10", "STOP": "", "PATIENT": "uuid-bob", "ENCOUNTER": "v6",
         "DESCRIPTION": "Full-time employment (finding)"},
    ])
    return folder


def test_each_hospital_only_gets_what_happened_there(synthea, tmp_path):
    generate(synthea, tmp_path / "out", relatives=0, conflicts=0, rates=NO_MISTAKES)
    dataset = load_dataset(tmp_path / "out" / "hospitals")
    assert len(dataset.records) == 5  # Ann and Robert at two hospitals each, Cyrus at one
    at = {(item.hospital_id, item.text) for item in dataset.items}
    assert at == {("orion", "Penicillin V"), ("lyra", "Amoxicillin 500 MG Oral Tablet"),
                  ("vega", "Essential hypertension")}  # no stopped drug, no social finding, no vague allergy
    assert {r.given.title() for r in dataset.records.values()} == {"Ann", "Robert", "Cyrus"}  # numbers stripped


def test_nothing_in_the_bundles_gives_the_answer_away(synthea, tmp_path):
    truth = generate(synthea, tmp_path / "out", relatives=1, conflicts=1)
    text = "".join(path.read_text(encoding="utf-8") for path in (tmp_path / "out" / "hospitals").glob("*.json"))
    assert "uuid-" not in text and "planted" not in text
    assert not any(person in text for person in truth["people"])


def test_same_seed_gives_the_same_dataset(synthea, tmp_path):
    for name in ("a", "b"):
        generate(synthea, tmp_path / name, seed=7)
    for part in ("hospitals/orion.json", "hospitals/lyra.json", "hospitals/vega.json", "truth/answer_key.json"):
        assert (tmp_path / "a" / part).read_text() == (tmp_path / "b" / part).read_text()


def test_clean_records_score_perfectly(synthea, tmp_path):
    generate(synthea, tmp_path / "out", relatives=0, conflicts=0, rates=NO_MISTAKES)
    results = evaluate(tmp_path / "out")
    matching, conflicts = results["matching"], results["conflicts"]
    assert matching["true_links"] == 2
    assert matching["auto"] == {"found": 2, "wrong": 0}
    assert matching["people_whole"] == matching["people_at_several"] == 2
    # Ann's allergy is at Orion and her amoxicillin at Lyra: only linking the records reveals it.
    assert conflicts["cross_hospital"]["high"] == {"total": 1, "confirmed": 1, "review": 0, "missed": 0}
    assert conflicts["false_alarms"] == {}
    assert "Accuracy check" in render(results)


def test_hidden_conflicts_are_counted_and_misses_explained(synthea, tmp_path):
    truth = generate(synthea, tmp_path / "out", relatives=0, conflicts=2, rates=NO_MISTAKES)
    assert [len(hidden["items"]) for hidden in truth["planted_conflicts"]] == [2, 2]
    planted = evaluate(tmp_path / "out")["conflicts"]["planted"]
    assert planted["total"] == 2 and planted["confirmed"] == 2


def test_relatives_are_separate_people_in_the_answer_key(synthea, tmp_path):
    truth = generate(synthea, tmp_path / "out", relatives=1, conflicts=0)
    relatives = {pid: p for pid, p in truth["people"].items() if p["relative_of"]}
    assert {p["kind"] for p in relatives.values()} == {"namesake", "twin", "spouse"}
    matching = evaluate(tmp_path / "out")["matching"]
    assert matching["auto"]["wrong"] == 0  # a relative is never merged into the patient automatically
    assert sum(sum(counts.values()) for counts in matching["by_relative"].values()) > 0


def _record(given, family, birth_date, gender="male", rid="x"):
    return PatientRecord(rid, "h", None, given, family, birth_date, gender, "617-555-0142", "01970", None)


def test_twins_at_the_same_address_need_review():
    result = compare_records(_record("Grady", "McLaughlin", "1973-11-12"),
                             _record("Raphael", "McLaughlin", "1973-11-12"))
    assert result.tier == "review"
    assert any("relative" in reason for reason in result.reasons)


def test_parent_and_child_with_the_same_name_need_review():
    result = compare_records(_record("Mario", "VonRueden", "1966-09-08"),
                             _record("Mario", "VonRueden", "1990-01-14"))
    assert result.tier == "review"


def test_a_typo_in_the_birth_date_is_still_linked_automatically():
    result = compare_records(_record("Mario", "VonRueden", "1966-09-08"),
                             _record("Mario", "VonRueden", "1966-09-03"))
    assert result.tier == "match" and result.caution is None
