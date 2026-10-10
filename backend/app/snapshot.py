"""Save a frozen copy of the demo data for the pitch deck.

    python -m app.snapshot

Writes frontend/src/pitch/snapshot.json. The deck draws the real 3D view and Maria's
constellation from it, so the slides still work if the backend isn't running during the pitch.
Re-run after changing the demo data.
"""
import json
from pathlib import Path

from .constellation import PatientIndex
from .seed import DATA_DIR

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pitch" / "snapshot.json"


def main() -> None:
    index = PatientIndex(DATA_DIR)  # no audit log: the demo's starting state, before any reviews
    maria = index.find("Maria Gonzalez", "1958-03-14")
    snapshot = {
        "hospitals": [{"id": h.id, "name": h.name} for h in index.dataset.hospitals.values()],
        "patients": index.summaries(),
        "stats": index.stats(),
        "maria": index.constellation(maria.id),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
