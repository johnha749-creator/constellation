# Constellation: handoff

Read this first if you're picking up the project (teammate, new machine, or a new Claude session).

## The hackathon

- **Event:** Hyphen-Hacks 2026 (LWHS), **Sat Oct 10, 9 AM to 9 PM**, 755 Ocean Ave, San Francisco
- **Theme:** "Crafting Constellations"
- **Submit:** a GitHub repo on Devpost: https://hyphen-hacks26.devpost.com/
- **Judges:** from Cisco, Microsoft, Apple and Google. Judging criteria were still "TBD" on Devpost; check whether they were announced at kickoff.
- **Prizes:** about $500 / $300 / $200 for 1st / 2nd / 3rd

## The idea

> Hospitals can already share records, but nobody connects the dots. Constellation turns a
> patient's scattered records into one constellation and flags dangerous conflicts before
> they cause harm.

Sharing data between hospitals **already exists** (TEFCA, Epic Care Everywhere / Epic Nexus,
CommonWell, Carequality). So we don't build the plumbing. We build the layer on top, which is
still unsolved:

1. **Patient matching:** the same person shows up differently at each hospital (nicknames,
   typos, swapped birth dates, married names). We link the records and explain why.
2. **Conflict detection:** for example, a penicillin allergy recorded at Hospital A while
   Hospital B prescribes amoxicillin. We flag it and say which hospital each fact came from.

**How it fits the theme:** each hospital's records are stars. We draw the lines: gold for
"same person", red and glowing for "these two facts conflict".

## Status

| Part | State |
|---|---|
| Backend (Python, FastAPI) | Done, including the partner's `/medications` and `/api/stats` endpoints and two extra demo stories, blocking for scale, and the audit trail. **34/34 tests pass.** |
| Synthetic data (3 hospitals, FHIR R4 JSON) | Generated in `backend/data/` |
| Frontend (React, Vite, D3) | Done and **checked in a browser**: the constellation forms, zooms to fit, conflicts highlight on click, the "Same person / Different people" review works, and "Reset demo" works. |
| Git / GitHub | Pushed to a **private** repo: https://github.com/johnha749-creator/constellation. Make it public before submitting to Devpost. |
| README | Done, with screenshots in `docs/`. **Add your team's names** (see the comment near the top). |
| Slides, pitch | Done: 11 slides with speaker notes at `/pitch.html`. Add your names (see "The pitch deck"). |

## Run it

You need Python 3.11+ and Node 20+. The project was built with Python 3.14 and Node 26.

**Backend** (terminal 1):

```bash
cd backend
py -m venv .venv                 # macOS/Linux: python3 -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. Vite forwards `/api/*` to the backend on port 8000.

**Tests:** run `pytest` from inside `backend/`, with the virtual environment active.

> **Windows gotchas:**
> - `python` can open the Microsoft Store instead of running Python. Use `py` instead, as shown above.
> - `--reload` sometimes says "Reloading..." and then keeps running the **old** code. If a new
>   API route returns 404, stop the backend (Ctrl+C) and start it again.
> - The frontend dev server can miss quick edits in the same way. If the page doesn't match
>   the code, stop `npm run dev` and start it again. If it then says port 5173 is in use, an
>   old Vite `node.exe` is still running; end it in Task Manager.

## How it works

```
backend/data/*.json         one FHIR R4 Bundle per hospital (Patient, AllergyIntolerance,
        │                   MedicationRequest, Condition)
        ▼
records.py                  parse bundles into PatientRecord / ClinicalItem objects
        ▼
matching.py                 score every pair of records, then group them into "clusters"
        │                   (one cluster = one real person)
        ▼
conflicts.py + knowledge.py check each person's combined items against the rule list
        ▼
constellation.py            build the graph JSON: nodes, links, conflicts
        ▼
main.py (FastAPI)  ──/api──▶  React app: PatientList │ Constellation (D3) │ DetailPanel
```

### Backend files (`backend/app/`)

| File | What it does |
|---|---|
| `main.py` | API routes (listed below) |
| `seed.py` | Generates the synthetic hospitals and patients. **Edit demo stories here.** |
| `records.py` | Loads FHIR bundles into Python dataclasses |
| `matching.py` | Record linkage, including blocking (see "Matching" below) |
| `audit.py` | The hash-chained audit log of match decisions (see "Audit trail" below) |
| `reconcile.py` | One row per drug across hospitals, for the Medications tab |
| `benchmark.py` | `python -m app.benchmark`: speed and accuracy of matching on synthetic patients |
| `snapshot.py` | `python -m app.snapshot`: saves the demo data the pitch deck draws from |
| `knowledge.py` | Small hand-made drug list: drug classes, allergy groups, interactions, duplicate therapy, condition rules. **Add rules here.** |
| `conflicts.py` | Applies the rules to one patient and writes the explanations |
| `constellation.py` | `PatientIndex`: loads everything once, then serves patient summaries and graphs |

### Frontend files (`frontend/src/`)

| File | What it does |
|---|---|
| `App.jsx` | Layout and state: selected patient, conflict and star |
| `components/Constellation.jsx` | The D3 force graph: starfield, glow, the "forming" animation, zoom and drag, click to select |
| `components/Galaxy3D.jsx` | The "All patients · 3D" view (three.js): hospital suns, a star per patient colored by its worst conflict, orbit and zoom, click a star to open it. Loaded only when opened. |
| `components/PatientList.jsx` | Search and patient list with severity badges |
| `components/DetailPanel.jsx` | Patient header, selected-star details, and three tabs: Conflicts, Medications, Record links |
| `components/MedicationList.jsx` | Medications tab: each drug, every hospital that prescribed it, and its issues |
| `pitch/Pitch.jsx`, `pitch/pitch.css` | The pitch deck at `/pitch.html` (see "The pitch deck" below) |
| `components/ReviewHistory.jsx` | Record links tab: this patient's audit history and the log's integrity check |
| `components/StatsBar.jsx` | Header totals: patients, records, conflicts caught, matches to review |
| `medications.js`, `stats.js` | Build the medication list and the header totals in the browser until the backend's `/medications` and `/api/stats` endpoints exist |
| `labels.js` | Shared display labels and severity order |
| `api.js` | Fetch helpers |
| `styles.css` | Dark space theme |

### API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{ok: true}` |
| GET | `/api/hospitals` | `[{id, name}]` |
| GET | `/api/patients?q=` | Patient summaries, most urgent first |
| GET | `/api/stats` | Totals for the header |
| GET | `/api/patients/{id}/constellation` | `{patient, hospitals, nodes, links, conflicts}` |
| GET | `/api/patients/{id}/medications` | One row per drug across hospitals |
| GET | `/api/patients/{id}/audit` | This patient's decisions, newest first, plus `verified` / `first_bad_seq` |
| GET | `/api/audit?limit=` | The whole audit log, newest first, plus the integrity check |
| POST | `/api/matches/review` | Body `{record_a, record_b, same_person, reviewer, note?}`. A clinician confirms or rejects a possible match; logged. Returns `{patient_id}` |
| POST | `/api/demo/reset` | Body `{reviewer}`. Undoes every decision by adding a reset entry to the log. The "Reset demo" button calls this. |
| POST | `/api/reload` | Re-reads `backend/data/*.json` and the audit log from disk. Keeps decisions. |

### Matching

This is a Fellegi–Sunter style scorer, a standard method for record linkage. Judges may ask about it.

- **Fields compared:** first name, last name, date of birth (DOB), sex, phone and ZIP. Each field
  adds evidence for or against a match. The weight is `log2(m/u)` when the field agrees and
  `log2((1-m)/(1-u))` when it disagrees. Partial agreement is interpolated between the two.
- **Smart comparisons:**
  - nicknames: Jim = James
  - an initial only: "M." vs "Maria"
  - punctuation: O'Brien = OBrien = O Brien
  - hyphenated or married names: Patel ⊂ Patel-Khan
  - Jaro-Winkler string similarity for misspellings
  - DOB with day and month swapped, one wrong digit, or two digits transposed
- **Turning evidence into a decision:** start from prior odds of 1 in 1000, add up the weights,
  and convert to a probability.
  - **≥ 95%:** match
  - **≥ 50%:** possible match that needs human review
  - **below 50%:** different people
- **Unconfirmed conflicts:** a conflict that only exists because of a "review" link is marked
  `unconfirmed`, so we never claim certainty we don't have.
- **Human in the loop:** a "review" link shows **Same person / Different people** buttons.
  "Same person" turns the link into a confirmed match, so its conflicts become confirmed.
  "Different people" splits the records into two patients. Decisions go into the audit log and
  survive a restart; "Reset demo" undoes them by adding a reset entry.
- **Blocking (scalability):** two records are only compared if they share a birth date, a phone
  number, or a sound-alike surname (Soundex) plus birth year. On the demo data that's 22
  comparisons instead of 990, with no real link missed (a test checks this). Benchmark: 20,000
  records in 2.5 s with 5,686× fewer comparisons, and 100,000 in 58 s with 7,283× fewer;
  recall and precision stay around 99.7%. Pair scores are cached, so a review relinks without
  re-scoring, and conflicts are only re-checked for patients whose links changed.

### Audit trail

- **Where it lives:** `backend/audit/reviews.jsonl`, one JSON entry per line, ignored by git.
  Tests write to a temporary file instead (see `tests/conftest.py`).
- **What each entry holds:** `seq`, `at` (UTC), `action` (`review` or `reset`), `reviewer`,
  the two record ids, `decision`, `previous`, the `score` at the time, an optional `note`,
  `prev_hash` and `hash`.
- **Append-only and hash-chained:** if an entry is edited or deleted, `verify()` reports it, the
  app shows a red warning, and that entry and everything after it are **ignored**, so a forged
  decision can't change a patient.
- **Clean history before presenting:** stop the backend, delete `backend/audit/reviews.jsonl`,
  and start it again. Clicking "Reset demo" undoes decisions but keeps them in the history,
  which is the point of an audit trail.

### Conflict types

`allergy` (a drug or its class vs a recorded allergy) · `duplicate_therapy` (two drugs from the
same class) · `interaction` (drug + drug) · `condition` (drug vs diagnosis) · `dose_mismatch`
(same drug, different dose at different hospitals).

Severity is high, moderate or low. Each conflict records which hospital each side came from.

## Demo data

The hospitals are fictional and named after stars: **Orion General Hospital**, **Lyra Medical
Center** and **Vega Community Clinic**. The filler patients are random but seeded, so the data
is the same on every machine. The 7 hand-written stories:

| Patient | What it shows |
|---|---|
| **Maria Gonzalez** (1958) | ⭐ **Flagship.** Orion has a penicillin allergy (anaphylaxis) and kidney disease. Lyra's ER ordered amoxicillin and ibuprofen. Vega added a second ACE inhibitor. Spelling differs (Gonzales) and Vega has only "M." **1 high + 4 moderate conflicts.** |
| **Maria Gonzalez** (1985) | Same name, **different person**. Correctly kept separate. Great Q&A moment. |
| **James O'Brien** (1947) | "Jim OBrien" at Lyra, and a day/month-swapped DOB at Vega. Warfarin + apixaban + naproxen: **3 high-severity bleeding risks.** |
| **Aisha Patel / Patel-Khan** (1990) | Married name, moved, new phone, and a DOB typo, so the match is **"needs review" (about 85%)**. Sulfa allergy vs Bactrim, and sertraline + tramadol (serotonin syndrome). Both conflicts are marked *unconfirmed*. |
| **Robert "Bob" Chen** (1972) | Atorvastatin 20 mg at one hospital vs 40 mg at the other: **low-severity** dose mismatch |
| **Anthony "Tony" Russo** (1961) | Nickname, and he moved. Orion's heart clinic prescribed nitroglycerin; Vega's urgent care added sildenafil. **High:** severe blood-pressure drop |
| **Eleanor Whittaker / Whitaker** (1953) | Dropped letter in the surname and two birth-date digits transposed, still matched. Simvastatin + clarithromycin. **High:** muscle damage |

The other 18 patients are filler, and a test checks that they produce **zero** conflicts.

- **Regenerate the data:** run `python -m app.seed` from `backend/`. This overwrites the JSON in
  `backend/data/`.
- **Hand edits:** you can edit those JSON files directly, then call `POST /api/reload`.

## Next steps (in order)

1. **Share the GitHub repo.** It's already pushed (private). Add your partner as a
   collaborator (repo Settings → Collaborators), and make the repo public before submitting
   to Devpost so the judges can see it.
2. **Add your names to README.md** (there's a comment near the top for this).
3. **Rehearse the demo below** on the laptop and screen you'll present on. Use "Reset demo"
   between run-throughs.
4. **Optional polish:**
   - a medication-reconciliation summary ("what this patient is actually taking")
   - uploading a new hospital's FHIR bundle live during the demo
   - item labels can still overlap on busy patients like Maria; drag a star to tidy up live
5. **Stretch goals** (only if time is left):
   - [Synthea](https://github.com/synthetichealth/synthea) generated patients
   - RxNorm codes instead of matching drug names as text
   - blocking, so matching scales to large datasets
6. **Slides and pitch.** Leave at least an hour.

## The pitch deck

The slides are a page in the frontend: with `npm run dev` running, open
**http://localhost:5173/pitch.html**.

- **Keys:** → or Space for next, ← for back, **F** for full screen, **N** for speaker notes (a
  short script for every slide). The controls in the bottom-right corner do the same.
- **Doesn't need the backend:** the title and closing slides show the live 3D network, and slide
  5 shows Maria's real constellation, all drawn from `frontend/src/pitch/snapshot.json`.
  Regenerate that file after changing the demo data, from `backend/`: `python -m app.snapshot`.
- **Add your names:** set `TEAM` at the top of `frontend/src/pitch/Pitch.jsx`. It appears on the
  title slide.
- **The demo:** slide 6 is where you switch to the app (http://localhost:5173) and run the demo
  below. Click "Reset demo" in the app before you present.
- **A link stays on its slide:** `pitch.html#5` opens slide 5, and reloading keeps your place.

## The 2-minute demo

1. **Problem (20 s):** "Hospitals can share records now, but a clinician gets a pile of
   documents from 3 systems. The same patient is spelled 3 ways, and nobody reads the pile."
2. **Open "All patients · 3D"** (top right of the sky): "Here's the whole network: three
   hospitals, every patient between them. The red ones have something dangerous."
3. **Click Maria Gonzalez's red star** (or pick her in the list). The view flies into her
   constellation: three hospitals, then gold "same person" lines, then a pulsing red line.
4. **Click the red line:** "Penicillin allergy at Orion, amoxicillin ordered at Lyra." This is
   the moment to land.
5. **Show the record links:** "M." vs "Maria", Gonzales vs Gonzalez, and why we're 96–100% sure.
6. **Click the other Maria Gonzalez:** "Same name, different person. We didn't merge them."
   Naive name matching would have.
7. **Aisha:** "When we're not sure, we say so." Point to the "needs review" link and the
   unconfirmed conflicts. Then open the **Record links** tab (it has an amber dot) and click
   **Same person**: the link turns gold and the conflicts become confirmed. "A human stays in
   control."
8. **Close:** "Built on FHIR, the real standard hospitals use, so it could sit on top of TEFCA
   or Epic's network."

## Likely judge questions

- **"Isn't this just Epic Care Everywhere?"** Epic moves the documents. We work on what happens
  after they arrive: matching identities across systems and catching contradictions between
  them.
- **"HIPAA?"** All the data is synthetic. A real deployment would run inside the hospital
  network or under a Business Associate Agreement, and exchange data through TEFCA rather than
  copying it.
- **"Why not machine learning for matching?"** Fellegi–Sunter is explainable. We can tell a
  nurse exactly why two records were linked, and in healthcare that matters more than a black
  box. The m/u weights could later be learned from data, for example with the EM algorithm.
- **"Are the drug rules real?"** They're a small hand-made demo set. A real product would
  license a drug database such as First Databank or Medi-Span and use RxNorm codes.

## Gotchas

- **Not clinical advice.** The drug list in `knowledge.py` is for the demo only. The app header
  says "Synthetic data only. Not for clinical use."
- **Which patient opens first:** the list is sorted by number of high-severity conflicts, so
  **James** is selected on load, not Maria. Click Maria for the demo, or change the sort in
  `constellation.py` (`summaries`).
- **Test warning:** pytest prints a Starlette deprecation warning about `httpx`. It's harmless.
- **`.claude/launch.json`** only lets Claude Code's preview pane start the servers. Ignore it
  otherwise.
- **Loose versions:** `requirements.txt` doesn't pin versions. The frontend uses React 19.3,
  Vite 8.3 and D3 7.9 (see `package-lock.json`).
