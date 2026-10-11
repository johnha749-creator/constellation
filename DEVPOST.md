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

## About the project (paste everything below this line into the story field)

Devpost renders Markdown, with LaTeX math between `$...$` and `$$...$$`.

---

## Inspiration

Many patients get care at more than one hospital: in one study, **31%** of adults used two or
more. Hospitals can now send records to each other, but two problems remain:

- **The same person looks different in each system**, like "Jim OBrien" and "James O'Brien".
  Between organizations, records are matched correctly as little as **50%** of the time.
- **Nobody checks the records against each other.** One hospital knows a patient is allergic to
  penicillin; another orders amoxicillin, which *is* a penicillin.

Every year, **1 in 167** Americans goes to the ER because of medication harm. We wanted to connect
the dots, and the theme "Crafting Constellations" fit perfectly: each hospital's record is a star,
and the patient is the constellation.

*Sources: Bourgeois et al., 2010; Pew Charitable Trusts, 2018; Budnitz et al., JAMA 2021.*

## What it does

Constellation reads records from several hospitals, works out which ones belong to the same
person, and flags dangerous conflicts between them, like an allergy at one hospital and a matching
drug at another. Uncertain matches go to a clinician to decide. Each patient is drawn as a
constellation: gold lines link records of the same person, and red lines show conflicts.

## How we built it

**Backend:** Python and FastAPI, reading made-up patient records in FHIR, the format hospitals
use. **Frontend:** React, D3 for each patient's constellation, and three.js for a 3D view of every
patient.

**Matching:** each field (name, birth date, phone, ZIP and so on) earns points when it agrees and
loses points when it doesn't. Every pair starts at −10:

$$\text{score} = -10 + \sum \text{field points}$$

Above +4.2, the records are linked. Between 0 and +4.2, a clinician decides. Below 0, they're
different people. Two different women named Maria Gonzalez share a name but not a birth date,
phone or ZIP, so they score −6.9 and stay apart.

**Scale:** we only compare records that share something, like a birth date. For 100,000 records
that's **7,283× fewer** comparisons, and it finishes in 86 seconds.

**Privacy:** sign-in, roles, a tamper-evident log of who did what, and an option to match records
on encrypted fingerprints instead of names.

## Challenges we ran into

- **Two people, one name.** Matching on names alone would merge the two Marias and put one
  woman's allergy in the other's chart.
- **Consistency.** Our first scoring gave slightly different points for similar typos, so we
  switched to a fixed points table. Now the same evidence always gets the same score.
- **Safety vs. catching everything.** Looser rules found a few more matches but also made more
  wrong ones. We chose to send uncertain cases to a person instead.
- **HIPAA.** We misread one rule at first and had to correct our claims. We learned to cite
  exactly what the law requires.

## What we learned

- How hospitals match patient records, and why it's still hard.
- How to turn evidence into a score you can explain line by line.
- What HIPAA actually requires.
- In healthcare, saying "I'm not sure" is safer than guessing.

## What's next

Real drug databases, connecting to real hospital networks, and fixing a case we found: a father
and son with the same name and phone number.

*All patients are made up. This is a prototype, not a medical device.*
