import pytest
from fastapi.testclient import TestClient

from app.constellation import PatientIndex
from app.main import app
from app.seed import DEMO_PATIENTS, write_seed


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    write_seed(data_dir)
    return PatientIndex(data_dir)


def conflicts_for(index, name, birth_date):
    cluster = index.find(name, birth_date)
    assert cluster is not None, f"{name} not found"
    return cluster, index.conflicts[cluster.id]


def test_maria_records_from_three_hospitals_are_linked(index):
    cluster, _ = conflicts_for(index, "Maria Gonzalez", "1958-03-14")
    assert len(cluster.record_ids) == 3


def test_same_name_stranger_stays_separate(index):
    cluster, conflicts = conflicts_for(index, "Maria Gonzalez", "1985-09-30")
    assert len(cluster.record_ids) == 1
    assert conflicts == []


def test_penicillin_allergy_vs_amoxicillin_across_hospitals(index):
    _, conflicts = conflicts_for(index, "Maria Gonzalez", "1958-03-14")
    top = conflicts[0]
    assert (top.type, top.severity, top.cross_hospital) == ("allergy", "high", True)
    assert "Amoxicillin" in top.title


def test_blood_thinner_problems(index):
    _, conflicts = conflicts_for(index, "James O'Brien", "1947-11-02")
    kinds = {(c.type, c.severity) for c in conflicts}
    assert ("duplicate_therapy", "high") in kinds  # warfarin + apixaban
    assert ("interaction", "high") in kinds  # anticoagulant + naproxen


def test_conflicts_behind_an_unreviewed_match_are_marked_unconfirmed(index):
    cluster, conflicts = conflicts_for(index, "Aisha Patel", "1990-07-22")
    assert cluster.needs_review
    assert conflicts and all(c.unconfirmed for c in conflicts)


def test_dose_mismatch_is_low_severity(index):
    _, conflicts = conflicts_for(index, "Robert Chen", "1972-05-05")
    assert [(c.type, c.severity) for c in conflicts] == [("dose_mismatch", "low")]


def test_filler_patients_have_no_conflicts(index):
    demo_ids = {f"{rec['given']} {rec['family']}" for person in DEMO_PATIENTS for rec in person}
    for summary in index.summaries():
        if summary["name"] not in demo_ids:
            assert sum(summary["conflicts"].values()) == 0, summary


def test_api_serves_a_constellation():
    client = TestClient(app)
    patients = client.get("/api/patients").json()
    assert patients[0]["conflicts"]["high"] > 0
    graph = client.get(f"/api/patients/{patients[0]['id']}/constellation").json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert all(link["source"] in node_ids and link["target"] in node_ids for link in graph["links"])
    assert client.get("/api/patients/nope/constellation").status_code == 404
