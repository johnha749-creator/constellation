import os
import tempfile
from pathlib import Path

# Point the API's audit log at a throwaway file before app.main is imported, so tests never
# write into the real backend/audit/reviews.jsonl.
os.environ["CONSTELLATION_AUDIT_LOG"] = str(Path(tempfile.mkdtemp()) / "reviews.jsonl")
