# Team plan: who builds what

We split the work **by folder**, so we never edit the same files and every push and pull
merges cleanly. Read [HANDOFF.md](HANDOFF.md) first for how the project works and how to run it.

| Person | Owns | Never touches |
|---|---|---|
| **Partner** | everything in `backend/` (Python) | `frontend/`, `README.md`, `HANDOFF.md`, `TASKS.md` |
| **Owner** (repo owner) | everything in `frontend/` (React), plus `README.md`, `HANDOFF.md`, `TASKS.md` | `backend/` |

If you need something changed in the other person's folder, ask them in chat instead of editing it.

## Partner: backend track (about 1.5 hours)

Do these in order. Push after each one.

### 1. Medication list endpoint (the main task)

`GET /api/patients/{id}/medications` answers "what is this patient actually taking, across
every hospital?"

- Put the logic in a new file, `backend/app/reconcile.py`, and the route in `backend/app/main.py`.
- **Group** the patient's medications by drug. Use `ClinicalItem.drug`, which is the normalized
  drug name; fall back to the lowercased text when it's `None`.
- Return one row per drug, listing every hospital that prescribed it.
- `conflict_ids`: the ids of conflicts in `index.conflicts[cluster_id]` whose `item_ids` include
  one of this drug's items.
- **Sort** drugs that have conflicts first, then alphabetically.
- Return **404** for an unknown patient, the same way the constellation route does.
- **Tests** go in `backend/tests/`. Check, for example, that Robert Chen's atorvastatin has two
  sources and one conflict, and that his amlodipine has none.

### 2. Stats endpoint (quick)

`GET /api/stats` returns totals for the header. Compute them from `index.clusters` and
`index.conflicts`.

### 3. Two more demo stories

Add them to `DEMO_PATIENTS` in `backend/app/seed.py`. Ideas:

- **Nitroglycerin + sildenafil:** a heart clinic prescribes nitroglycerin, and urgent care
  prescribes sildenafil. Together they can cause a dangerous drop in blood pressure.
- **Simvastatin + clarithromycin:** a statin plus an antibiotic that blocks its breakdown,
  which risks muscle damage.

Both rules already exist in `backend/app/knowledge.py`. Give each story at least 2 hospitals and
a realistic data-quality problem (a nickname, a typo, someone who moved).

After editing, regenerate the data with `python -m app.seed`, run `pytest`, and push. The
`test_filler_patients_have_no_conflicts` test reads `DEMO_PATIENTS`, so new stories are excluded
from it automatically.

## Owner: frontend track (about 1.5 hours)

1. **Medications tab:** give the right panel three tabs, Conflicts | Medications | Record links.
   Build it against fake data that matches the shape below, then switch to the real endpoint
   once the partner pushes task 1. Clicking a drug's conflict jumps to that conflict.
2. **Stats line** in the header, for example "23 patients · 41 records · 11 conflicts caught
   across hospitals".
3. **README.md** for the judges: the problem, screenshots, how to run it, and how it works.

## The API contract (agreed now, so nobody waits)

### `GET /api/patients/{id}/medications`

Returns a list. Drugs with conflicts come first. This is Robert Chen's real data:

```json
[
  {
    "name": "Atorvastatin",
    "drug": "atorvastatin",
    "sources": [
      { "hospital": "orion", "dosage": "20 mg once daily", "date": "2019-09-12", "item_id": "orion-rx-016" },
      { "hospital": "lyra",  "dosage": "40 mg once daily", "date": "2025-06-03", "item_id": "lyra-rx-015" }
    ],
    "conflict_ids": ["k1"]
  },
  {
    "name": "Amlodipine",
    "drug": "amlodipine",
    "sources": [
      { "hospital": "lyra", "dosage": "5 mg once daily", "date": "2025-06-03", "item_id": "lyra-rx-016" }
    ],
    "conflict_ids": []
  }
]
```

- `name`: how the drug is written in the records.
- `drug`: the normalized drug name, or `null` if it isn't in the knowledge base.
- `hospital`: a hospital id; the names come from `/api/hospitals`.
- `conflict_ids`: the same ids as in the constellation response's `conflicts` list. An empty
  list means no problems.

### `GET /api/stats`

These are the current real numbers:

```json
{
  "hospitals": 3,
  "records": 41,
  "patients": 23,
  "needs_review": 1,
  "conflicts": { "high": 6, "moderate": 4, "low": 1 },
  "cross_hospital_conflicts": 11
}
```

If you need to change either shape, tell the other person **before** you push.

## Git routine

- **Start:** `git pull`
- **Push** small commits every 30–45 minutes:
  ```bash
  git pull --rebase
  git push
  ```
- **After pulling backend changes, restart your backend.** `--reload` is unreliable on Windows.
- **Run `pytest`** (backend) or `npm run build` (frontend) before you push. Don't push red.
