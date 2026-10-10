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


def test_nitrate_with_sildenafil_across_hospitals(index):
    cluster, conflicts = conflicts_for(index, "Anthony Russo", "1961-04-18")
    assert len(cluster.record_ids) == 2 and not cluster.needs_review  # "Tony", new address
    assert [(c.type, c.severity, c.cross_hospital, c.unconfirmed) for c in conflicts] == [
        ("interaction", "high", True, False)]
    assert conflicts[0].title == "Nitroglycerin + Sildenafil"


def test_statin_with_clarithromycin_across_hospitals(index):
    cluster, conflicts = conflicts_for(index, "Eleanor Whittaker", "1953-10-12")
    assert len(cluster.record_ids) == 2 and not cluster.needs_review  # surname and birth-date typos
    assert [(c.type, c.severity, c.cross_hospital, c.unconfirmed) for c in conflicts] == [
        ("interaction", "high", True, False)]
    assert "rhabdomyolysis" in conflicts[0].explanation


def test_filler_patients_have_no_conflicts(index):
    demo_ids = {f"{rec['given']} {rec['family']}" for person in DEMO_PATIENTS for rec in person}
    for summary in index.summaries():
        if summary["name"] not in demo_ids:
            assert sum(summary["conflicts"].values()) == 0, summary


def test_stats_add_up_to_the_patient_list(index):
    stats, summaries = index.stats(), index.summaries()
    assert stats["hospitals"] == 3
    assert stats["patients"] == len(summaries)
    assert stats["records"] == sum(s["record_count"] for s in summaries) == len(index.dataset.records)
    assert stats["needs_review"] == sum(s["needs_review"] for s in summaries) == 1  # Aisha
    for severity in ("high", "moderate", "low"):
        assert stats["conflicts"][severity] == sum(s["conflicts"][severity] for s in summaries)
    # Every demo conflict spans two hospitals.
    assert stats["cross_hospital_conflicts"] == sum(stats["conflicts"].values()) > 0


@pytest.fixture
def fresh_index(tmp_path):
    write_seed(tmp_path)
    return PatientIndex(tmp_path)


def test_confirming_a_possible_match_confirms_its_conflicts(fresh_index):
    a, b = fresh_index.find("Aisha Patel", "1990-07-22").record_ids
    patient_id = fresh_index.review_match(a, b, same_person=True)
    assert not fresh_index.clusters[patient_id].needs_review
    conflicts = fresh_index.conflicts[patient_id]
    assert conflicts and not any(c.unconfirmed for c in conflicts)


def test_rejecting_a_possible_match_splits_the_patient(fresh_index):
    a, b = fresh_index.find("Aisha Patel", "1990-07-22").record_ids
    fresh_index.review_match(a, b, same_person=False)
    for record_id in (a, b):
        cluster = fresh_index.cluster_of(record_id)
        assert cluster.record_ids == [record_id]
        assert fresh_index.conflicts[cluster.id] == []


def test_api_serves_a_constellation():
    client = TestClient(app)
    patients = client.get("/api/patients").json()
    assert patients[0]["conflicts"]["high"] > 0
    graph = client.get(f"/api/patients/{patients[0]['id']}/constellation").json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert all(link["source"] in node_ids and link["target"] in node_ids for link in graph["links"])
    assert client.get("/api/patients/nope/constellation").status_code == 404


def test_api_serves_stats():
    client = TestClient(app)
    stats = client.get("/api/stats").json()
    assert set(stats) == {"hospitals", "records", "patients", "needs_review", "conflicts",
                          "cross_hospital_conflicts"}
    assert set(stats["conflicts"]) == {"high", "moderate", "low"}
    assert stats["patients"] == len(client.get("/api/patients").json())


def test_api_match_review_round_trip():
    client = TestClient(app)
    aisha = next(p for p in client.get("/api/patients").json() if p["needs_review"])
    graph = client.get(f"/api/patients/{aisha['id']}/constellation").json()
    link = next(l for l in graph["links"] if l["kind"] == "match" and l["tier"] == "review")
    try:
        res = client.post("/api/matches/review", json={
            "record_a": link["source"], "record_b": link["target"], "same_person": True, "reviewer": "Dr. Lee"})
        patient_id = res.json()["patient_id"]
        graph = client.get(f"/api/patients/{patient_id}/constellation").json()
        confirmed = next(l for l in graph["links"] if l["kind"] == "match")
        assert (confirmed["tier"], confirmed["reviewed"]) == ("match", "same")
        history = client.get(f"/api/patients/{patient_id}/audit").json()
        assert history["verified"]
        assert (history["events"][0]["reviewer"], history["events"][0]["decision"]) == ("Dr. Lee", "same")
        bad = {"record_a": "nope", "record_b": link["target"], "same_person": True}
        assert client.post("/api/matches/review", json=bad).status_code == 404
        assert client.get("/api/patients/nope/audit").status_code == 404
    finally:
        client.post("/api/demo/reset", json={"reviewer": "test"})  # don't leak the review into other tests
    assert client.get("/api/audit").json()["events"][0]["action"] == "reset"
    assert any(p["needs_review"] for p in client.get("/api/patients").json())
