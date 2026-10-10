"""Constellation API: links patient records across hospitals and flags conflicts.

Run from the backend folder:  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .constellation import PatientIndex
from .reconcile import medication_list
from .seed import DATA_DIR, ensure_seed_data

ensure_seed_data(DATA_DIR)
index = PatientIndex(DATA_DIR)

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


@app.post("/api/matches/review")
def review_match(review: MatchReview) -> dict:
    """A clinician confirms or rejects a possible match between two records."""
    patient_id = index.review_match(review.record_a, review.record_b, review.same_person)
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Unknown record")
    return {"patient_id": patient_id}


@app.post("/api/reload")
def reload() -> dict:
    """Re-read the JSON files in backend/data after you edit them, without restarting.
    Also clears match reviews, which resets the demo."""
    global index
    index = PatientIndex(DATA_DIR)
    return {"patients": len(index.clusters)}
