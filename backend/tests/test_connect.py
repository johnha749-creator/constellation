import copy

import pytest
from fastapi.testclient import TestClient

from app.audit import AuditLog
from app.connect import BundleError
from app.constellation import PatientIndex
from app.seed import build_sample_bundle, write_seed

from conftest import demo_account


@pytest.fixture
def index(tmp_path):
    data_dir = tmp_path / "data"
    write_seed(data_dir)
    return PatientIndex(data_dir, AuditLog())


@pytest.fixture(scope="module")
def sample():
    return build_sample_bundle()


def kenji(index):
    return index.find("Kenji Murphy", next(r.birth_date for r in index.dataset.records.values()
                                           if r.display_name == "Kenji Murphy"))


def test_connecting_polaris_links_records_and_finds_new_conflicts(index, sample):
    assert index.conflicts[kenji(index).id] == []
    report = index.connect_hospital(copy.deepcopy(sample), reviewer="Test")

    assert report["hospital"] == {"id": "polaris", "name": "Polaris Urgent Care"}
    assert (report["records"], report["matched"], report["new_patients"], report["needs_review"]) == (3, 2, 1, 0)
    # Kenji moved and Polaris writes his phone differently, but he's still linked automatically.
    cluster = kenji(index)
    assert {index.dataset.records[r].hospital_id for r in cluster.record_ids} == {"lyra", "orion", "polaris"}
    titles = {c.title: c.severity for c in index.conflicts[cluster.id]}
    assert titles == {"Propranolol with Asthma": "high", "Albuterol + Propranolol": "moderate"}
    assert [c["patient"] for c in report["new_conflicts"]] == ["Kenji Murphy", "Kenji Murphy"]
    # "Bill" is William Santos's nickname.
    born = next(r.birth_date for r in index.dataset.records.values() if r.display_name == "William Santos")
    assert index.find("Bill Santos", born).id == index.find("William Santos", born).id
    assert index.stats()["hospitals"] == 4 and index.stats()["patients"] == 26


def test_only_pairs_with_a_new_record_are_scored(index, sample):
    before = dict(index.scored)
    report = index.connect_hospital(copy.deepcopy(sample))
    assert 0 < report["pairs_compared"] < 10
    assert all(index.scored[pair] is result for pair, result in before.items())


def test_encrypted_matching_gives_the_same_report(tmp_path, sample):
    data_dir = tmp_path / "data"
    write_seed(data_dir)
    plain = PatientIndex(data_dir, AuditLog()).connect_hospital(copy.deepcopy(sample))
    private = PatientIndex(data_dir, AuditLog(), matching="private").connect_hospital(copy.deepcopy(sample))
    assert plain == private


def test_connecting_is_logged_and_shows_in_the_patients_history(index, sample):
    index.connect_hospital(copy.deepcopy(sample), reviewer="Dr. Test", username="dr.test")
    event = index.audit.events[-1]
    assert (event["action"], event["hospital"], event["username"]) == ("connect", "Polaris Urgent Care", "dr.test")
    assert index.audit.verify() is None
    history = index.audit_for(kenji(index).id)["events"]
    assert history[0]["action"] == "connect" and history[0]["hospital"] == "Polaris Urgent Care"


def broken(change):
    bundle = build_sample_bundle()
    change(bundle)
    return bundle


def resources(bundle, kind):
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == kind]


@pytest.mark.parametrize("bundle, problem", [
    ({"resourceType": "Patient"}, "isn't a FHIR Bundle"),
    ([1, 2, 3], "isn't a FHIR Bundle"),
    (broken(lambda b: b.update(id="orion")), "already connected"),
    (broken(lambda b: b.update(id="Not An Id!")), "lowercase letters"),
    (broken(lambda b: b.update(entry=[])), "no entries"),
    (broken(lambda b: resources(b, "Patient")[0].update(id="orion-pt-001")), "already used"),
    (broken(lambda b: resources(b, "MedicationRequest")[0].update(subject={"reference": "Patient/nobody"})),
     "must point at a Patient"),
    (broken(lambda b: resources(b, "Patient")[0].update(birthDate="10/12/1953")), "YYYY-MM-DD"),
    (broken(lambda b: resources(b, "Condition")[0].update(code={})), "no text"),
    (broken(lambda b: b.update(entry=[e for e in b["entry"] if e["resource"]["resourceType"] != "Organization"])),
     "exactly one Organization"),
    (broken(lambda b: b["entry"].append({"resource": "oops"})), "has no resource"),
])
def test_bad_bundles_are_rejected_and_change_nothing(index, bundle, problem):
    stats, events = index.stats(), len(index.audit.events)
    with pytest.raises(BundleError) as error:
        index.connect_hospital(bundle)
    assert any(problem in p for p in error.value.problems), error.value.problems
    assert index.stats() == stats and len(index.audit.events) == events
    assert "polaris" not in index.dataset.hospitals


def test_api_connects_a_hospital_and_reset_disconnects_it(client, sample):
    import json

    response = client.post("/api/hospitals", content=json.dumps(sample))
    try:
        assert response.status_code == 200, response.text
        assert response.json()["new_conflicts"][0]["title"] == "Propranolol with Asthma"
        assert len(client.get("/api/hospitals").json()) == 4
        again = client.post("/api/hospitals", content=json.dumps(sample))
        assert again.status_code == 400 and "already connected" in again.json()["detail"]["problems"][0]
    finally:
        client.post("/api/demo/reset")
    assert len(client.get("/api/hospitals").json()) == 3


def test_api_rejects_bad_json_and_roles_without_permission(client):
    response = client.post("/api/hospitals", content=b"{not json")
    assert response.status_code == 400 and response.json()["detail"]["message"] == "That file isn't valid JSON."

    from app.main import app

    nurse = demo_account(1)
    other = TestClient(app)
    other.post("/api/login", json={"username": nurse["username"], "password": nurse["password"]})
    assert other.post("/api/hospitals", content=b"{}").status_code == 403
