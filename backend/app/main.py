"""Constellation API: links patient records across hospitals and flags conflicts.

Run from the backend folder:  uvicorn app.main:app --port 8000
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .audit import AuditLog
from .constellation import PatientIndex
from .reconcile import medication_list
from .seed import DATA_DIR, ensure_seed_data

# Clinicians' decisions are appended here and replayed on startup. Tests point it elsewhere.
AUDIT_PATH = Path(os.environ.get("CONSTELLATION_AUDIT_LOG",
                                 Path(__file__).resolve().parent.parent / "audit" / "reviews.jsonl"))

ensure_seed_data(DATA_DIR)
index = PatientIndex(DATA_DIR, AuditLog(AUDIT_PATH))

app = FastAPI(title="Constellation API")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


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
def constellation(cluster_id: str) -> dict:
    graph = index.constellation(cluster_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    return graph


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
    reviewer: str = Field("Unknown reviewer", min_length=1, max_length=80)
    note: str | None = Field(None, max_length=500)


@app.post("/api/matches/review")
def review_match(review: MatchReview) -> dict:
    """A clinician confirms or rejects a possible match between two records. Logged."""
    patient_id = index.review_match(review.record_a, review.record_b, review.same_person,
                                    reviewer=review.reviewer, note=review.note)
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Unknown record")
    return {"patient_id": patient_id}


class DemoReset(BaseModel):
    reviewer: str = Field("Unknown reviewer", min_length=1, max_length=80)


@app.post("/api/demo/reset")
def reset_demo(reset: DemoReset) -> dict:
    """Undo every match decision so the demo can run again. The audit log keeps them."""
    index.reset_reviews(reset.reviewer)
    return {"patients": len(index.clusters)}


@app.get("/api/audit")
def audit_log(limit: int = 100) -> dict:
    """Every logged decision, newest first, and whether the hash chain is intact."""
    return index.audit_log(limit)


@app.get("/api/patients/{cluster_id}/audit")
def patient_audit(cluster_id: str) -> dict:
    """Decisions about this patient's records, newest first."""
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
