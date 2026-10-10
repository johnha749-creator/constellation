import pytest

from app.constellation import PatientIndex
from app.reconcile import medication_list
from app.records import ClinicalItem
from app.seed import write_seed


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    write_seed(data_dir)
    return PatientIndex(data_dir)


def medications_for(index, name, birth_date):
    cluster = index.find(name, birth_date)
    assert cluster is not None, f"{name} not found"
    return medication_list(index.items_of(cluster), index.conflicts[cluster.id])


def test_same_drug_at_two_hospitals_is_one_row(index):
    atorvastatin, amlodipine = medications_for(index, "Robert Chen", "1972-05-05")
    assert (atorvastatin["name"], atorvastatin["drug"]) == ("Atorvastatin", "atorvastatin")
    assert [(s["hospital"], s["dosage"], s["date"]) for s in atorvastatin["sources"]] == [
        ("orion", "20 mg once daily", "2019-09-12"),
        ("lyra", "40 mg once daily", "2025-06-03"),
    ]
    assert len(atorvastatin["conflict_ids"]) == 1  # the dose mismatch
    assert (amlodipine["name"], amlodipine["conflict_ids"]) == ("Amlodipine", [])
    assert [s["hospital"] for s in amlodipine["sources"]] == ["lyra"]


def test_drugs_with_conflicts_come_first_then_alphabetical(index):
    rows = medications_for(index, "Maria Gonzalez", "1958-03-14")
    assert [row["name"] for row in rows] == ["Amoxicillin", "Enalapril", "Ibuprofen", "Lisinopril", "Metformin"]
    assert [bool(row["conflict_ids"]) for row in rows] == [True, True, True, True, False]


def test_conflict_ids_point_at_the_patients_conflicts(index):
    cluster = index.find("Maria Gonzalez", "1958-03-14")
    conflicts = {c.id: c for c in index.conflicts[cluster.id]}
    rows = medication_list(index.items_of(cluster), list(conflicts.values()))
    for row in rows:
        item_ids = {s["item_id"] for s in row["sources"]}
        assert all(item_ids & set(conflicts[cid].item_ids) for cid in row["conflict_ids"])
    # Every one of Maria's conflicts involves a medication, so each shows up on some drug.
    assert {cid for row in rows for cid in row["conflict_ids"]} == set(conflicts)
    amoxicillin = next(row for row in rows if row["drug"] == "amoxicillin")
    assert conflicts[amoxicillin["conflict_ids"][0]].type == "allergy"


def test_unknown_drugs_are_grouped_by_their_text():
    def item(item_id, hospital, kind, text):
        return ClinicalItem(item_id, f"{hospital}-pt", hospital, kind, text, "once daily", "2026-01-01")

    rows = medication_list([
        item("a", "orion", "medication", "Vitamin D3"),
        item("b", "lyra", "medication", "vitamin d3"),
        item("c", "lyra", "condition", "Vitamin D deficiency"),
    ], [])
    assert len(rows) == 1
    assert (rows[0]["drug"], rows[0]["conflict_ids"]) == (None, [])
    assert [s["item_id"] for s in rows[0]["sources"]] == ["a", "b"]


def test_api_serves_medications(client):
    bob = next(p for p in client.get("/api/patients", params={"q": "chen"}).json())
    rows = client.get(f"/api/patients/{bob['id']}/medications").json()
    assert [row["drug"] for row in rows] == ["atorvastatin", "amlodipine"]
    assert set(rows[0]) == {"name", "drug", "sources", "conflict_ids"}
    assert set(rows[0]["sources"][0]) == {"hospital", "dosage", "date", "item_id"}
    # The ids are the same ones the constellation response uses.
    graph = client.get(f"/api/patients/{bob['id']}/constellation").json()
    assert rows[0]["conflict_ids"] == [c["id"] for c in graph["conflicts"]]
    assert {s["item_id"] for row in rows for s in row["sources"]} <= {n["id"] for n in graph["nodes"]}
    assert client.get("/api/patients/nope/medications").status_code == 404
