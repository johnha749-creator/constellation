"""Export the demo as static JSON for the hosted, read-only version on GitHub Pages.

    python -m app.static_export ../frontend/public/demo

GitHub Pages can't run this Python backend, so the frontend's static build (VITE_STATIC=1) reads
these files instead of calling the API. Two states are exported: the three demo hospitals, and the
same after Polaris Urgent Care connects, so "Connect hospital" still works in the hosted demo.
Contact details are masked, as a signed-in physician first sees them. The GitHub Actions workflow
generates these files on every deploy; they aren't committed.
"""
import json
import sys
from pathlib import Path

from . import rubric
from .audit import AuditLog
from .constellation import PatientIndex
from .reconcile import medication_list
from .seed import DATA_DIR, build_sample_bundle


def export_state(index: PatientIndex, out: Path) -> None:
    """Every GET the frontend makes, as one file per response."""
    _write(out / "hospitals.json", [{"id": h.id, "name": h.name} for h in index.dataset.hospitals.values()])
    _write(out / "patients.json", index.summaries())
    _write(out / "stats.json", index.stats())
    for cluster_id, cluster in index.clusters.items():
        folder = out / "patients" / cluster_id
        _write(folder / "constellation.json", index.constellation(cluster_id))
        _write(folder / "medications.json", medication_list(index.items_of(cluster), index.conflicts[cluster_id]))
        _write(folder / "audit.json", index.audit_for(cluster_id))


def main(out_dir: str) -> None:
    out = Path(out_dir)
    index = PatientIndex(DATA_DIR, AuditLog())  # an in-memory log: the demo's starting state
    _write(out / "rubric.json", rubric.as_table())
    export_state(index, out / "base")
    report = index.connect_hospital(build_sample_bundle(), reviewer="Demo visitor")
    export_state(index, out / "polaris")
    _write(out / "polaris" / "report.json", report)
    print(f"Exported {len(index.clusters)} patients (with Polaris) to {out}")


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo"))
