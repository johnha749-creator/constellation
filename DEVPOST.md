# Devpost submission (paste-ready)

Copy each part into the matching field on https://hyphen-hacks26.devpost.com/. Replace the
`[brackets]` first. Everything else is accurate as of the latest commit.

---

## Project name

Constellation

## Elevator pitch (the one-line tagline, 200 characters max)

Hospitals can already share patient records. Constellation connects the dots: it links one
patient's records across hospitals and flags dangerous conflicts before they cause harm.

## Built with (the tags field)

python, fastapi, react, vite, d3.js, three.js, fhir, pytest, javascript, css

## Try it out (links)

- GitHub: https://github.com/johnha749-creator/constellation (make the repo **public** first)

## Image gallery (upload these from `docs/`)

1. `conflict.jpg`: Maria's constellation, with the red penicillin-vs-amoxicillin line
2. `galaxy.jpg`: every patient in 3D between the three hospitals
3. `medications.jpg`: what Maria is actually taking, across hospitals
4. `review.jpg`: an uncertain match waiting for a clinician

Add a screenshot of the **Summary** tab too: open Maria Gonzalez and capture the panel showing
"Penicillin, only at Orion General Hospital".

---

## About the project (the story field; Devpost renders this Markdown)

## Inspiration

[Optional: one or two sentences about why this matters to you. A real reason beats a statistic.]

When someone is treated at several hospitals, each one keeps its own chart. National networks
such as TEFCA, Epic's network and CommonWell can now send those charts between hospitals, so
*moving* the data is mostly solved. Two problems are left over. The same person looks different
in every system ("Jim OBrien" in one, "James O'Brien" with a day-first birth date in another), and
nobody cross-checks the pile. One hospital records a penicillin allergy, and another hospital's
ER, without seeing it, orders amoxicillin, which is a penicillin.

Every record is correct on its own. Together they're dangerous. We wanted to build the piece that
connects the dots, so the theme "Crafting Constellations" fit almost literally.

## What it does

Constellation reads each hospital's records in **FHIR R4**, the standard format hospitals use, and
then:

- **Works out which records belong to the same person**, despite nicknames, typos, swapped
  dates, married names and moves. Every link shows its score, field by field.
- **Puts a clinician in charge of uncertain matches.** A possible match is flagged "needs review",
  and a clinician clicks **Same person** or **Different people**. Conflicts that depend on an
  unconfirmed match are labelled *unconfirmed*, so we never claim more certainty than we have.
- **Compiles one chart per patient:** allergies, conditions and medications from every hospital,
  each tagged with where it came from. For our demo patient Maria, every one of her 10 items is
  known to just one hospital, including her penicillin allergy.
- **Catches conflicts across hospitals:** allergy vs drug, duplicate drugs, dangerous drug pairs,
  a drug that worsens a diagnosis, and the same drug at different doses. Each one is ranked high,
  moderate or low and explained in plain English, naming the hospital behind each side.
- **Connects a new hospital live.** Upload its FHIR bundle and Constellation checks the whole
  file, matches its records against every patient, and reports new dangers. In our demo, Polaris
  Urgent Care joins and Constellation immediately flags that Kenji Murphy, whose asthma is on file
  at two other hospitals, was just prescribed propranolol, which can trigger an asthma attack.
- **Draws every patient as a constellation.** Each hospital record is a star, the patient's
  allergies, medications and conditions orbit it, gold lines join records of the same person,
  and red lines join facts that conflict. A 3D view shows the whole network: hospitals are suns,
  and every patient floats between the hospitals that hold their records, glowing red when
  something is wrong.

## How we built it

- **Backend:** Python and FastAPI, reading synthetic FHIR R4 bundles for three made-up hospitals.
- **Matching:** a fixed points rubric based on **Fellegi–Sunter** record linkage, the standard
  statistical method. Each field (name, birth date, sex, phone, ZIP) lands on one named level,
  such as "nickname" or "day and month swapped", worth a fixed number of points. A pair starts
  at −10 points: +4.2 or more links automatically, and 0 to +4.2 goes to a clinician.
- **Scale:** comparing every pair of 100,000 records would take 5 billion comparisons. **Blocking**
  only compares records that share a birth date, a phone number, or a similar-sounding last name
  plus birth year. That's 7,283× fewer comparisons, while keeping 99.97% of the real links.
- **Privacy:** clinicians sign in, and roles decide what they see. A registration clerk can fix
  identity mix-ups but never sees diagnoses or medications. Contact details stay masked until a
  clinician gives a reason, which is logged. Matching can also run on **encrypted fingerprints**
  (keyed hashes of names, split into letter pairs), and it gives exactly the same decisions as
  plain matching.
- **Audit trail:** every decision and every access goes into an append-only, **hash-chained** log.
  Editing or deleting an old entry breaks the chain, and the app then ignores everything from
  that point on.
- **Frontend:** React and Vite, D3 for each patient's constellation, and three.js for the 3D view.
- **Tests:** 95 pytest tests, including checks that the encrypted and plain matchers agree on
  every candidate pair of 3,000 synthetic records.

## Challenges we ran into

- **Two people, one name.** Our demo has two different women named Maria Gonzalez. Naive name
  matching merges them, which would put one woman's allergy in the other's chart. The rubric keeps
  them apart: same name, but a different birth date, phone and ZIP.
- **Making scoring consistent.** Our first matcher used a sliding similarity score, so two similar
  typos could earn different points, and the encrypted matcher disagreed with the plain one on
  0.07% of fields. We replaced both with one rubric of named levels and fixed points. Now the two
  matchers agree on every pair we test.
- **Precision vs recall.** Looser spelling rules found slightly more true matches, but also made
  more wrong merges. In healthcare a wrong merge is worse than asking a human, so we chose the
  stricter rules.
- **Getting HIPAA right.** At first we claimed that masking contact details was required by HIPAA's
  "minimum necessary" rule. Then we found that rule doesn't apply to sharing for treatment, so we
  corrected our docs. We map each feature to the specific Security Rule safeguard it implements
  and don't call the prototype "HIPAA compliant".
- **A tamper-evident log that actually protects.** Our first version detected a forged entry but
  still applied the forged decision. Now only the trusted part of the chain is ever replayed.

## Accomplishments that we're proud of

- Every match is explainable: the app shows exactly which fields earned which points.
- **20,000 records** linked in about a second, with **99.53% recall and 99.98% precision** on
  synthetic data with realistic mistakes.
- Encrypted matching with **exactly the same results** as plain matching.
- The constellation itself: you can spot a dangerous patient at a glance.

## What we learned

- How record linkage works in real health systems, and why it's still unsolved.
- FHIR, the format real hospital systems exchange.
- What HIPAA actually requires, section by section, and what it doesn't.
- How hash chains make a log tamper-evident.

## What's next for Constellation

- Real drug coding (RxNorm) and a licensed drug-interaction database instead of our small demo
  rules.
- Connecting to real FHIR servers, and hospital single sign-on with two-factor authentication.
- Matching new records as they arrive, spread across machines.
- Hardening the encrypted fingerprints against frequency analysis.

*All patients and hospitals are synthetic. This is a hackathon prototype, not a medical device.*
