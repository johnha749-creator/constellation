"""Constellation API: links patient records across hospitals and flags conflicts.

Run from the backend folder:  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException

from .constellation import PatientIndex
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


@app.get("/api/patients")
def patients(q: str | None = None) -> list[dict]:
    return index.summaries(q)


@app.get("/api/patients/{cluster_id}/constellation")
def constellation(cluster_id: str) -> dict:
    graph = index.constellation(cluster_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Unknown patient")
    return graph


@app.post("/api/reload")
def reload() -> dict:
    """Re-read the JSON files in backend/data after you edit them, without restarting."""
    global index
    index = PatientIndex(DATA_DIR)
    return {"patients": len(index.clusters)}
