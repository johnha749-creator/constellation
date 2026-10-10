import json

from fastapi.testclient import TestClient

from app.auth import Accounts
from app.main import USERS_PATH, app
from app.privacy import Disclosures, mask_mrn, mask_phone, mask_zip

from conftest import demo_account


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


# --- sign-in

def test_everything_but_health_and_login_needs_sign_in():
    anonymous = TestClient(app)
    assert anonymous.get("/api/health").status_code == 200
    for path in ("/api/patients", "/api/stats", "/api/audit", "/api/me"):
        assert anonymous.get(path).status_code == 401, path


def test_wrong_password_is_rejected():
    account = demo_account()
    response = TestClient(app).post("/api/login", json={"username": account["username"], "password": "nope"})
    assert response.status_code == 401
    unknown = TestClient(app).post("/api/login", json={"username": "nobody", "password": "nope"})
    assert unknown.status_code == 401


def test_sign_in_and_out():
    account = demo_account(1)
    client = TestClient(app)
    response = client.post("/api/login", json={"username": account["username"], "password": account["password"]})
    assert response.json()["user"]["name"] == account["name"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/me").json()["user"]["username"] == account["username"]
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_sessions_end_after_being_idle():
    clock = FakeClock()
    accounts = Accounts(USERS_PATH, idle_timeout=15 * 60, clock=clock)
    account = demo_account()
    token, _ = accounts.login(account["username"], account["password"])
    clock.now = 14 * 60
    assert accounts.user_for(token) is not None  # activity restarts the timer...
    clock.now = 28 * 60
    assert accounts.user_for(token) is not None
    clock.now = 44 * 60
    assert accounts.user_for(token) is None  # ...but 16 idle minutes ends the session
    assert accounts.user_for(token) is None


def test_passwords_are_not_kept_in_plain_text():
    accounts = Accounts(USERS_PATH)
    passwords = {a["password"] for a in json.loads(USERS_PATH.read_text(encoding="utf-8"))["accounts"]}
    stored = {value for _, salt, digest in accounts._users.values() for value in (salt, digest)}
    assert not any(p.encode() in stored for p in passwords)


# --- masked contact details and access logging

def test_masks():
    assert mask_phone("415-555-0142") == "•••-•••-••42"
    assert mask_mrn("OR-100231") == "OR-••••31"
    assert mask_zip("94112") == "941••"


def aisha(client):
    patient = next(p for p in client.get("/api/patients").json() if p["name"].startswith("Aisha"))
    return patient["id"]


def test_contact_details_are_masked_until_a_reason_is_given(client):
    patient_id = aisha(client)
    masked = client.get(f"/api/patients/{patient_id}/constellation")
    text = masked.text
    assert masked.json()["contact_details_visible"] is False
    # Aisha's phones, ZIPs and street appear nowhere, not even in the match explanations.
    for raw in ("510-555-0129", "415-555-0175", "94704", "94118", "Shattuck"):
        assert raw not in text, raw
    assert "•••-•••-••29" in text

    assert client.post(f"/api/patients/{patient_id}/reveal", json={"reason": ""}).status_code == 422
    assert client.post(f"/api/patients/{patient_id}/reveal",
                       json={"reason": "Treatment: confirming identity"}).status_code == 200
    revealed = client.get(f"/api/patients/{patient_id}/constellation")
    assert revealed.json()["contact_details_visible"] is True
    assert "510-555-0129" in revealed.text

    # Another clinician still sees the masked version.
    other = demo_account(1)
    colleague = TestClient(app)
    colleague.post("/api/login", json={"username": other["username"], "password": other["password"]})
    assert "510-555-0129" not in colleague.get(f"/api/patients/{patient_id}/constellation").text


def test_views_and_reveals_are_logged_with_who_and_why(client):
    patient_id = aisha(client)
    client.get(f"/api/patients/{patient_id}/constellation")
    client.post(f"/api/patients/{patient_id}/reveal", json={"reason": "Treatment: calling the patient"})
    events = client.get(f"/api/patients/{patient_id}/audit").json()["events"]
    reveal, view = events[0], events[1]
    assert (reveal["action"], reveal["reason"], reveal["username"]) == (
        "reveal", "Treatment: calling the patient", demo_account()["username"])
    assert view["action"] == "view"


def test_reveal_expires():
    clock = FakeClock()
    grants = Disclosures(minutes=15, clock=clock)
    grants.grant("dr.lee", ["a", "b"])
    assert grants.allowed("dr.lee", ["a", "b"])
    assert not grants.allowed("nurse.ruiz", ["a"])
    clock.now = 16 * 60
    assert not grants.allowed("dr.lee", ["a"])


# --- role-based access

def signed_in_as(username):
    account = next(a for a in json.loads(USERS_PATH.read_text(encoding="utf-8"))["accounts"]
                   if a["username"] == username)
    client = TestClient(app)
    assert client.post("/api/login", json={"username": username, "password": account["password"]}).status_code == 200
    return client


def test_every_demo_account_has_a_known_role():
    accounts = json.loads(USERS_PATH.read_text(encoding="utf-8"))["accounts"]
    assert {a["role"] for a in accounts} == {"physician", "nurse", "registration"}


def test_registration_sees_identity_but_no_clinical_data():
    clerk = signed_in_as("reg.kim")
    assert clerk.get("/api/me").json()["user"]["role"] == "Registration clerk"
    patients = clerk.get("/api/patients").json()
    assert all(p["conflicts"] is None for p in patients)
    assert [p["name"] for p in patients] == sorted(p["name"] for p in patients)  # order mustn't hint either
    maria = next(p for p in patients if p["name"] == "Maria Gonzalez" and p["birth_date"] == "1958-03-14")
    graph = clerk.get(f"/api/patients/{maria['id']}/constellation").json()
    assert graph["clinical_visible"] is False and graph["conflicts"] == []
    assert {n["kind"] for n in graph["nodes"]} == {"record"}
    assert "Penicillin" not in str(graph) and "Amoxicillin" not in str(graph)
    assert any(link["kind"] == "match" for link in graph["links"])  # but can work on identity
    assert clerk.get(f"/api/patients/{maria['id']}/medications").status_code == 403


def test_nurses_see_clinical_data_but_cannot_decide_matches():
    nurse = signed_in_as("nurse.ruiz")
    aisha = next(p for p in nurse.get("/api/patients").json() if p["needs_review"])
    assert aisha["conflicts"]["high"] == 2
    graph = nurse.get(f"/api/patients/{aisha['id']}/constellation").json()
    link = next(l for l in graph["links"] if l["kind"] == "match")
    decision = {"record_a": link["source"], "record_b": link["target"], "same_person": True}
    response = nurse.post("/api/matches/review", json=decision)
    assert response.status_code == 403 and "Registered nurse" in response.json()["detail"]
    assert nurse.post("/api/demo/reset").status_code == 403
    assert nurse.post(f"/api/patients/{aisha['id']}/reveal", json={"reason": "Calling the patient"}).status_code == 200


def test_registration_can_decide_matches():
    clerk = signed_in_as("reg.kim")
    aisha = next(p for p in clerk.get("/api/patients").json() if p["needs_review"])
    graph = clerk.get(f"/api/patients/{aisha['id']}/constellation").json()
    link = next(l for l in graph["links"] if l["kind"] == "match")
    try:
        decision = {"record_a": link["source"], "record_b": link["target"], "same_person": True}
        assert clerk.post("/api/matches/review", json=decision).status_code == 200
    finally:
        clerk.post("/api/demo/reset")
