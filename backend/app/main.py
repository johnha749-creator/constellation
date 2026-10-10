"""Constellation API: links patient records across hospitals and flags conflicts.

Run from the backend folder:  uvicorn app.main:app --port 8000

Every route except /api/health and /api/login needs a signed-in clinician (see auth.py).
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .audit import AuditLog
from .auth import COOKIE, Accounts, User
from .constellation import PatientIndex
from .privacy import REVEAL_MINUTES, Disclosures
from .reconcile import medication_list
from .seed import DATA_DIR, ensure_seed_data

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Every match decision and patient access is appended here and replayed on startup.
# Tests point it at a temporary file instead.
AUDIT_PATH = Path(os.environ.get("CONSTELLATION_AUDIT_LOG", BACKEND_DIR / "audit" / "reviews.jsonl"))
USERS_PATH = Path(os.environ.get("CONSTELLATION_USERS", BACKEND_DIR / "demo_users.json"))
# Session cookies must only travel over HTTPS in a real deployment. Local development is plain
# HTTP, so this is opt-in here.
SECURE_COOKIES = os.environ.get("CONSTELLATION_HTTPS") == "1"

ensure_seed_data(DATA_DIR)
index = PatientIndex(DATA_DIR, AuditLog(AUDIT_PATH))
accounts = Accounts(USERS_PATH)
disclosures = Disclosures()

app = FastAPI(title="Constellation API")

PUBLIC_PATHS = {"/api/health", "/api/login", "/api/logout"}


@app.middleware("http")
async def require_sign_in(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path not in PUBLIC_PATHS:
        user = accounts.user_for(request.cookies.get(COOKIE))
        if user is None:
            return JSONResponse({"detail": "Not signed in"}, status_code=401)
        request.state.user = user
    return await call_next(request)


def signed_in(request: Request) -> User:
    return request.state.user


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


class Login(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(body: Login, response: Response) -> dict:
    session = accounts.login(body.username.strip(), body.password)
    if session is None:
        raise HTTPException(status_code=401, detail="Wrong username or password")
    token, user = session
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=SECURE_COOKIES, path="/")
    return {"user": user.as_dict(), "idle_timeout_minutes": accounts.idle_timeout / 60}


@app.post("/api/logout")
def logout(request: Request, response: Response) -> dict:
    accounts.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request) -> dict:
    return {"user": signed_in(request).as_dict(), "idle_timeout_minutes": accounts.idle_timeout / 60}


@app.get("/api/hospitals")
def hospitals() -> list[dict]:
    return [{"id": h.id, "name": h.name} for h in index.dataset.hospitals.values()]


@app.get("/api/stats")
def stats() -> dict:
    return index.stats()


@app.get("/api/patients")
def patients(q: str | None = None) -> list[dict]:
    return index.summaries(q)


@app.get("/api/patients/{cluster_id}/constellation")
def constellation(cluster_id: str, request: Request) -> dict:
    """Opening a patient is logged. Contact details stay masked unless this clinician revealed them."""
    user = signed_in(request)
    cluster = index.clusters.get(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    index.log_access(cluster_id, "view", reviewer=user.name, username=user.username)
    return index.constellation(cluster_id, reveal=disclosures.allowed(user.username, cluster.record_ids))


class Reveal(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@app.post("/api/patients/{cluster_id}/reveal")
def reveal(cluster_id: str, body: Reveal, request: Request) -> dict:
    """Break the glass: show this patient's contact details to this clinician for a while,
    after they state why. The reason is logged."""
    user = signed_in(request)
    cluster = index.clusters.get(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    index.log_access(cluster_id, "reveal", reviewer=user.name, username=user.username, reason=body.reason.strip())
    disclosures.grant(user.username, cluster.record_ids)
    return {"visible_for_minutes": REVEAL_MINUTES}


@app.get("/api/patients/{cluster_id}/medications")
def medications(cluster_id: str) -> list[dict]:
    """What the patient is actually taking, across every hospital."""
    cluster = index.clusters.get(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    return medication_list(index.items_of(cluster), index.conflicts[cluster.id])


class MatchReview(BaseModel):
    record_a: str
    record_b: str
    same_person: bool
    note: str | None = Field(None, max_length=500)


@app.post("/api/matches/review")
def review_match(review: MatchReview, request: Request) -> dict:
    """The signed-in clinician confirms or rejects a possible match between two records. Logged."""
    user = signed_in(request)
    patient_id = index.review_match(review.record_a, review.record_b, review.same_person,
                                    reviewer=user.name, username=user.username, note=review.note)
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Unknown record")
    return {"patient_id": patient_id}


@app.post("/api/demo/reset")
def reset_demo(request: Request) -> dict:
    """Undo every match decision so the demo can run again. The audit log keeps them."""
    user = signed_in(request)
    index.reset_reviews(user.name, user.username)
    return {"patients": len(index.clusters)}


@app.get("/api/audit")
def audit_log(limit: int = 100) -> dict:
    """Every logged decision and access, newest first, and whether the hash chain is intact."""
    return index.audit_log(limit)


@app.get("/api/patients/{cluster_id}/audit")
def patient_audit(cluster_id: str) -> dict:
    """Everything logged about this patient's records, newest first."""
    history = index.audit_for(cluster_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    return history


@app.post("/api/reload")
def reload() -> dict:
    """Re-read backend/data/*.json and the audit log from disk, without restarting.
    Match decisions are kept: they are replayed from the log."""
    global index
    index = PatientIndex(DATA_DIR, AuditLog(AUDIT_PATH))
    return {"patients": len(index.clusters)}
