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
| Backend (Python, FastAPI) | Done, including the partner's `/medications` and `/api/stats` endpoints and two extra demo stories, blocking for scale, the audit trail, clinician sign-in with roles, masked contact details with access logging, encrypted (privacy-preserving) matching, the points rubric for matches, and "Connect hospital" (upload a FHIR bundle live). **95/95 tests pass.** |
| Synthetic data (3 hospitals, FHIR R4 JSON) | Generated in `backend/data/` |
| Frontend (React, Vite, D3) | Done and **checked in a browser**: the constellation forms, zooms to fit, conflicts highlight on click, the "Same person / Different people" review works, "Reset demo" works, and the Summary tab compiles each patient's chart. |
| Git / GitHub | Pushed to a **private** repo: https://github.com/johnha749-creator/constellation. Make it public before submitting to Devpost. |
| README | Done, with screenshots in `docs/`. **Add your team's names** (see the comment near the top). |
| Slides, pitch | Done: 7 slides with speaker notes at `/pitch.html`, with cited statistics on the problem and measured results for the fix. Add your names (see "The pitch deck"). |

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

Then open http://localhost:5173 and **sign in** with one of the demo accounts in
`backend/demo_users.json`. Vite forwards `/api/*` to the backend on port 8000.

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
| `seed.py` | Generates the synthetic hospitals and patients, plus the Polaris sample for "Connect hospital". **Edit demo stories here.** |
| `records.py` | Loads FHIR bundles into Python dataclasses (`parse_bundle` reads one bundle) |
| `connect.py` | Checks an uploaded hospital bundle as a whole before any of it is used, and lists the problems if it's unusable |
| `matching.py` | Record linkage, including blocking (see "Matching" below) |
| `audit.py` | The hash-chained audit log of match decisions and patient access (see "Audit trail" below) |
| `auth.py` | Sign-in: demo accounts, PBKDF2 password checks, sessions that end after 15 idle minutes |
| `privacy.py` | Masks phone, address, ZIP and MRN, and tracks who unmasked which patient and until when |
| `rubric.py` | The match rubric: every field's levels and points, the thresholds, and the rules that pick a level |
| `pprl.py` | Privacy-preserving matching on encrypted fingerprints (keyed hashes and keyed letter-pair hashes), scored with the same rubric |
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
| `components/DetailPanel.jsx` | Patient header, selected-star details, and four tabs: Summary, Conflicts, Medications, Record links |
| `components/PatientSummary.jsx`, `summary.js` | Summary tab: one combined chart (allergies, conditions, medications) with each item's hospitals, tagging items only one hospital knew about and items from an unconfirmed match |
| `components/ConnectHospital.jsx` | The "Connect hospital" dialog: upload a FHIR bundle (or the Polaris sample) and see what matched and any new conflicts |
| `components/MedicationList.jsx` | Medications tab: each drug, every hospital that prescribed it, and its issues |
| `pitch/Pitch.jsx`, `pitch/pitch.css` | The pitch deck at `/pitch.html` (see "The pitch deck" below) |
| `components/ReviewHistory.jsx` | Record links tab: this patient's access and review history, and the log's integrity check |
| `components/Login.jsx` | The sign-in screen. `App.jsx` shows it until someone signs in, and again after a timeout. |
| `components/StatsBar.jsx` | Header totals: patients, records, conflicts caught, matches to review |
| `medications.js`, `stats.js` | Build the medication list and the header totals in the browser until the backend's `/medications` and `/api/stats` endpoints exist |
| `labels.js` | Shared display labels and severity order |
| `api.js` | Fetch helpers |
| `styles.css` | Dark space theme |

### API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{ok: true}` (no sign-in needed) |
| POST | `/api/login` | Body `{username, password}`. Sets the session cookie. Returns `{user, idle_timeout_minutes, matching}` |
| POST | `/api/logout` | Ends the session |
| GET | `/api/me` | The signed-in user, or 401 |
| POST | `/api/patients/{id}/reveal` | Body `{reason}`. Unmasks this patient's contact details for this user for 15 minutes; logged |
| GET | `/api/hospitals` | `[{id, name}]` |
| POST | `/api/hospitals` | Body: a FHIR R4 Bundle (JSON, up to 5 MB). Connects a new hospital: checks the whole bundle (400 with `detail.problems` if it's unusable), scores only pairs that include a new record, logs it. Returns `{hospital, records, matched, needs_review, new_patients, pairs_compared, new_conflicts}`. Physicians only. In memory until a restart or reset. |
| GET | `/api/patients?q=` | Patient summaries, most urgent first |
| GET | `/api/stats` | Totals for the header |
| GET | `/api/patients/{id}/constellation` | `{patient, hospitals, nodes, links, conflicts}` |
| GET | `/api/patients/{id}/medications` | One row per drug across hospitals |
| GET | `/api/patients/{id}/audit` | This patient's decisions, newest first, plus `verified` / `first_bad_seq` |
| GET | `/api/audit?limit=` | The whole audit log, newest first, plus the integrity check |
| POST | `/api/matches/review` | Body `{record_a, record_b, same_person, note?}`. The signed-in clinician confirms or rejects a possible match; logged under their account. Returns `{patient_id}` |
| POST | `/api/demo/reset` | Undoes every decision by adding a reset entry to the log, and disconnects hospitals uploaded while running. The "Reset demo" button calls this. |

**Every route except `/api/health` and `/api/login` returns 401 unless someone is signed in.**
Opening a patient (`/constellation`) is logged as a view, and phone, address, ZIP and MRN in it are
masked unless that user has unmasked them.
| POST | `/api/reload` | Re-reads `backend/data/*.json` and the audit log from disk. Keeps decisions. |
| GET | `/api/rubric` | The match rubric: `{start, link_at, review_at, fields: [{field, levels: [{level, points}]}]}` |

Each `match` link in a constellation also carries `points` (the rubric total) and `breakdown`
(`[{field, level, values, points}]`, with values masked like everything else).

### Matching

Every pair of records is scored with **one fixed points rubric** (`rubric.py`). Judges may ask
about it.

- **Fields compared:** first name, last name, date of birth, sex, phone and ZIP.
- **Levels and points:** each field lands on exactly one named level, worth fixed points, for
  example "Nickname of the same name" +5.6, "Day and month swapped" +6.9, "Different" −5.1. The
  full table is in the README, in the app ("How scoring works" in the Record links tab), and at
  `GET /api/rubric`.
- **The decision:** start at **−10**, add each field's points.
  - **+4.2 or more** (about 95%): same person.
  - **0 to +4.2:** a clinician decides.
  - **below 0:** different people.
- **Where the points come from:** Fellegi–Sunter weights. Full agreement is worth `log2(m/u)`,
  disagreement `log2((1-m)/(1-u))`, and each partial level is a fixed fraction between them.
- **Spelling:** "Close spelling" means the names share at least 75% of their letter pairs
  (Dice ≥ 0.75), and "Similar spelling" at least 50%. One letter off a short name such as Maria
  vs Mario only reaches "similar", by design.
- **Consistency, all checked by `tests/test_rubric.py`:**
  - every documented case lands on its level;
  - more agreement never scores lower;
  - A vs B scores exactly like B vs A;
  - standard and encrypted matching give identical levels and points on every candidate pair of
    3,000 synthetic records.
- **In the app:** every record-link card shows its breakdown table (start, each field, total).
- **Why not looser thresholds?** They link a few more true pairs, but merge more wrong ones
  (99.78% precision instead of 99.98%). A wrong merge is worse than a trip to human review.
- **Unconfirmed conflicts:** a conflict that only exists because of a "review" link is marked
  `unconfirmed`, so we never claim certainty we don't have.
- **Human in the loop:** a "review" link shows **Same person / Different people** buttons.
  "Same person" turns the link into a confirmed match, so its conflicts become confirmed.
  "Different people" splits the records into two patients. Decisions go into the audit log and
  survive a restart; "Reset demo" undoes them by adding a reset entry.
- **Blocking (scalability):** two records are only compared if they share a birth date, a phone
  number, or a sound-alike surname (Soundex) plus birth year. On the demo data that's 22
  comparisons instead of 990, with no real link missed (a test checks this). Benchmark: 20,000
  records in about 1.3 s with 5,686× fewer comparisons (99.53% recall, 99.98% precision), and
  100,000 in about 86 s with 7,283× fewer (99.48% recall, 99.63% precision). Encrypted matching
  gives identical accuracy. Pair scores are cached, so a review relinks without
  re-scoring, and conflicts are only re-checked for patients whose links changed.

### Audit trail

- **Where it lives:** `backend/audit/reviews.jsonl`, one JSON entry per line, ignored by git.
  Tests write to a temporary file instead (see `tests/conftest.py`).
- **What each entry holds:** `seq`, `at` (UTC), `action` (`review`, `reset`, `view` or `reveal`),
  `reviewer` (display name) and `username` of the signed-in clinician, `prev_hash` and `hash`.
  Reviews add the two record ids, `decision`, `previous`, the `score` at the time and an optional
  `note`. Views and reveals add the patient's record ids, and reveals add the stated `reason`.
- **Append-only and hash-chained:** if an entry is edited or deleted, `verify()` reports it, the
  app shows a red warning, and that entry and everything after it are **ignored**, so a forged
  decision can't change a patient.
- **Clean history before presenting:** stop the backend, delete `backend/audit/reviews.jsonl`,
  and start it again. Clicking "Reset demo" undoes decisions but keeps them in the history,
  which is the point of an audit trail.

### Sign-in and privacy

- **Demo accounts:** `backend/demo_users.json` has four with their passwords: two physicians
  (`dr.lee`, `demo`), a nurse (`nurse.ruiz`) and a registration clerk (`reg.kim`). They're
  demo-only; the file says so.
- **Roles** (`ROLES` in `auth.py`, enforced by the backend):
  - **Physician:** everything, including **Connect hospital**.
  - **Nurse:** clinical data and "Show…", but no match decisions and no "Reset demo". Review
    cards say a physician or registration clerk must decide.
  - **Registration clerk:** identity only. The patient list is alphabetical with no severity
    badges, only the Record links tab shows, the sky shows just the record stars, and
    `/medications` returns 403. They can decide matches and use "Show…".
- **Sessions:** in memory, so **restarting the backend signs everyone out**. A session also ends
  after **15 minutes without activity**; the app then shows the sign-in screen with a message.
- **Masked contact details:** phone, address, ZIP and MRN show as `•••-•••-••42`, `941••` and so
  on, even inside match explanations. **Show…** in the right panel asks for a reason (logged),
  then shows them to that clinician for 15 minutes. Other clinicians still see them masked.
- **Encrypted matching:** start the backend with `CONSTELLATION_MATCHING=private` (PowerShell:
  `$env:CONSTELLATION_MATCHING="private"`). Records are then linked on fingerprints only, and the
  header shows "🔒 encrypted matching". It uses the same rubric with exact fingerprint
  equivalents, so every level, point and decision is identical to standard matching; only the
  breakdown hides the compared values. The default stays standard matching, so the breakdown can
  show values once they're unmasked.
- **Production settings** (documented, not needed for the demo): `CONSTELLATION_HTTPS=1` marks
  cookies Secure, and `CONSTELLATION_LINKAGE_KEY` sets the hospitals' shared fingerprint key.

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

**A fourth hospital for the live demo:** `frontend/public/samples/polaris-urgent-care.json`
(**Polaris Urgent Care**) isn't loaded at startup. "Connect hospital" → "Try the sample" adds it.
It has three visits:
- **Kenji Murphy**, who moved and whose phone is written differently, still links automatically.
  His asthma is known to Lyra and Orion, and Polaris prescribes propranolol for migraines:
  **1 high** (it can trigger an asthma attack) and **1 moderate** (it blunts his albuterol). Before
  Polaris connects he has no conflicts.
- **"Bill" Santos** links to William Santos by nickname. Nothing dangerous.
- **Priya Raman** is new, so she becomes patient number 26.

"Reset demo" disconnects it again. `python -m app.seed` regenerates the file.

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
   - item labels can still overlap on busy patients like Maria; drag a star to tidy up live
5. **Stretch goal** (only if time is left): RxNorm codes instead of matching drug names as text.
6. **Slides and pitch.** Leave at least an hour.
7. **Submit on Devpost.** The paste-ready text (tagline, story, tags, gallery list) is in
   [DEVPOST.md](DEVPOST.md). Fill in the `[brackets]` first.

## The pitch deck

The slides are a page in the frontend: with `npm run dev` running, open
**http://localhost:5173/pitch.html**. Seven slides, about 3 minutes plus the demo:

| # | Slide | What's on it |
|---|---|---|
| 1 | Title | The live 3D network |
| 2 | The problem, in numbers | Eight cited statistics (sources on the slide): 31% of adults use 2+ hospitals; match rates as low as 50% between organizations; 8–12% duplicate records; hospital data error rates up to 26.9%; 27–54% of patients with medication-history errors at admission; 1 in 167 Americans in the ER for medication harm each year; 7,613 wrong-patient events; up to $20M a year lost to bad data per provider |
| 3 | Why it still happens | Maria's three records; 35% of doctors share records only by fax or mail (ONC, 2019); 43% of hospitals routinely integrate outside records (ONC, 2023) |
| 4 | How we fix it | Read, Match, Catch, and the rubric thresholds |
| 5 | Live demo | Maria's constellation and the demo steps. **Switch to the app here.** |
| 6 | The fix, in numbers | 99.98% precision, 99.53% recall, 7,283× fewer comparisons, 86 s for 100,000 records, identical encrypted matching, 7 HIPAA safeguards, 95 tests |
| 7 | Close | What's next, the repo link, questions |

Every outside number has its source on the slide; if a judge asks, the sources are Bourgeois et
al. (Arch Intern Med 2010), Pew Charitable Trusts (2018), the AHIMA Journal, Tam et al. (CMAJ
2005), Budnitz et al. (JAMA 2021), ECRI Institute (2016), ONC's 2019 physician interoperability
brief, and ONC Data Brief 71 (2023 data). The 26.9% and $20M figures come from a HealthLeaders
article (January 2025) that reports them as upper bounds across studies without naming the
studies, so the slide says "at worst"; don't present them as averages.

- **Keys:** → or Space for next, ← for back, **F** for full screen, **N** for speaker notes (a
  short script for every slide). The controls in the bottom-right corner do the same.
- **Doesn't need the backend:** the title and closing slides show the live 3D network, and slide
  5 shows Maria's real constellation, all drawn from `frontend/src/pitch/snapshot.json`.
  Regenerate that file after changing the demo data, from `backend/`: `python -m app.snapshot`.
- **Add your names:** set `TEAM` at the top of `frontend/src/pitch/Pitch.jsx`. It appears on the
  title slide.
- **The demo:** slide 5 is where you switch to the app (http://localhost:5173) and run the demo
  below, then come back for slide 6. Click "Reset demo" in the app before you present.
- **A link stays on its slide:** `pitch.html#5` opens slide 5, and reloading keeps your place.

## The 2-minute demo

**Right before you present:** sign in (sessions end after 15 idle minutes) and click "Reset demo"
(it also disconnects Polaris from your last run-through).

1. **Problem (20 s):** "Hospitals can share records now, but a clinician gets a pile of
   documents from 3 systems. The same patient is spelled 3 ways, and nobody reads the pile."
2. **Open "All patients · 3D"** (top right of the sky): "Here's the whole network: three
   hospitals, every patient between them. The red ones have something dangerous."
3. **Click Maria Gonzalez's red star** (or pick her in the list). The view flies into her
   constellation: three hospitals, then gold "same person" lines, then a pulsing red line.
4. **The Summary tab opens first:** "One chart from three hospitals. Ten of these facts were
   known to only one hospital." Point at **Penicillin, only at Orion General Hospital**.
5. **Click the red line:** "Penicillin allergy at Orion, amoxicillin ordered at Lyra. Lyra never
   saw the allergy." This is the moment to land.
6. **Show the record links:** "M." vs "Maria", Gonzales vs Gonzalez, and why we're 96–100% sure.
7. **Click the other Maria Gonzalez:** "Same name, different person. We didn't merge them."
   Naive name matching would have.
8. **Aisha:** "When we're not sure, we say so." Point to the "needs review" link and the
   unconfirmed conflicts. Then open the **Record links** tab (it has an amber dot) and click
   **Same person**: the link turns gold and the conflicts become confirmed. "A human stays in
   control."
9. **Connect a hospital (20 s):** click **Connect hospital**, then **Try the sample: Polaris
   Urgent Care**. "A fourth hospital joins. Two of its three records matched patients we already
   knew, and only 4 pairs had to be compared. And there's a new danger: Kenji's asthma is on file
   at Lyra and Orion, and Polaris just prescribed propranolol, which can trigger an asthma
   attack." Click the conflict to open Kenji, now with a third star.
10. **Privacy (optional, 15 s):** point at the masked phone numbers in the match explanation.
   Click **Show…**, pick a reason, and show the new "Unmasked contact details. Reason: ..." line
   in the history. "HIPAA doesn't even require this for treatment. We hide it anyway, and every
   access is logged." Optionally sign in as the registration clerk to show that their view has no
   allergies, medications or conflicts at all.
11. **Close:** "Built on FHIR, the real standard hospitals use, so it could sit on top of TEFCA
   or Epic's network."

## Likely judge questions

- **"Isn't this just Epic Care Everywhere?"** Epic moves the documents. We work on what happens
  after they arrive: matching identities across systems and catching contradictions between
  them.
- **"HIPAA?" / "Why not real patient data?"** Real records are protected health information, and
  a hackathon isn't a permitted use, so everything is synthetic, which is how health IT is demoed
  and tested. We built in the Security Rule's technical safeguards (45 CFR 164.312): unique
  sign-in, role-based access, automatic logoff, audit controls and integrity checking. A real
  deployment would run inside the hospital or an HIE under a Business Associate Agreement;
  sharing records between providers for treatment is a permitted disclosure. We don't claim
  "HIPAA compliant": that also takes policies, agreements and a risk assessment.
- **"Isn't hiding contact details just HIPAA's minimum necessary rule?"** Careful: minimum
  necessary does *not* apply to sharing for treatment (45 CFR 164.502(b)(2)). Our masking goes
  beyond what the law requires, as privacy by design.
- **"Does the matcher have to see names?"** No. With encrypted matching it only sees
  fingerprints: keyed hashes of each value and of each name's letter pairs, with a secret the
  hospitals share. It reaches exactly the same scores as matching on real names (99.53% recall,
  99.98% precision on 20,000 synthetic records), and the tests check that.
- **"How do you decide two records are the same person?"** A fixed points rubric. Each field
  lands on one named level worth fixed points, for example a nickname is +5.6 and a day/month
  swap is +6.9. Start at −10, and +4.2 or more links them. Open any record link to see its
  breakdown, or "How scoring works" for the whole table.
- **"Why not machine learning for matching?"** Fellegi–Sunter is explainable. We can tell a
  nurse exactly why two records were linked, and in healthcare that matters more than a black
  box. The m/u weights could later be learned from data, for example with the EM algorithm.
- **"Are the drug rules real?"** They're a small hand-made demo set. A real product would
  license a drug database such as First Databank or Medi-Span and use RxNorm codes.

## Gotchas

- **Signed out unexpectedly?** Sessions end after 15 idle minutes and whenever the backend
  restarts. Sign in again; passwords are in `backend/demo_users.json`.
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
