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

When someone is treated at more than one hospital, every hospital keeps its own chart. That's
common: in a study of 3.7 million Massachusetts adults, **31%** used two or more hospitals, and
they made **56.5%** of all acute-care visits.

National networks like TEFCA, Epic's network and CommonWell can now *move* those charts between
hospitals. But two things still go wrong:

1. **The same person looks different in every system.** "Jim OBrien" at one hospital is
   "James O'Brien" at another, with the birth date typed day-first. When records are shared
   between organizations, match rates can be as low as **50%**.
2. **Nobody cross-checks the pile.** One hospital records a penicillin allergy. Another hospital's
   ER, without seeing it, orders amoxicillin, which *is* a penicillin. Every record is correct on
   its own. Together they're dangerous.

The harm is real: **27–54%** of patients have an error in the medication history taken when
they're admitted, and **1 in 167** Americans goes to the ER for medication harm every year. Yet
only **43%** of U.S. hospitals routinely send, receive, find *and* integrate outside records.
Moving records is mostly solved. Making sense of them isn't.

We wanted to build the piece that connects the dots. With the theme "Crafting Constellations",
the picture was almost literal: each hospital's record is a star, and the patient is the
constellation.

*Sources: Bourgeois et al., Arch Intern Med 2010; Pew Charitable Trusts, 2018; Tam et al., CMAJ
2005; Budnitz et al., JAMA 2021; ONC Data Brief 71 (2023 data).*

## What it does

Constellation reads each hospital's records in **FHIR R4**, the standard format hospitals
exchange, and then:

- **Works out which records belong to the same person**, despite nicknames, typos, swapped
  dates, married names and moves, and shows the score for every field.
- **Puts a clinician in charge of uncertain matches.** A possible match is flagged "needs review",
  and conflicts that depend on it are labelled *unconfirmed*.
- **Compiles one chart per patient**, tagging what only one hospital knew. For our demo patient
  Maria, all 10 of her allergies, conditions and medications were known to just one hospital,
  including her penicillin allergy.
- **Catches conflicts across hospitals:** allergy vs drug, dangerous drug pairs, duplicate drugs,
  a drug that worsens a diagnosis, and dose mismatches. Each is ranked and explained, naming the
  hospital behind each side.
- **Connects a new hospital live.** Upload its FHIR bundle and Constellation matches it against
  every patient. In our demo, Polaris Urgent Care joins and Constellation immediately flags that
  Kenji Murphy, whose asthma is on file at two other hospitals, was just prescribed propranolol,
  which can trigger an asthma attack.
- **Draws it all as a sky:** gold lines join records of the same person, red lines join facts that
  conflict, and a 3D view shows every patient between the hospitals that hold their records.

## How we built it

**Stack.** A Python + FastAPI backend reads synthetic FHIR R4 bundles from three made-up
hospitals. The frontend is React + Vite, with D3 for each patient's constellation and three.js for
the 3D network. 95 pytest tests cover the logic.

**Matching with one fixed rubric.** We used **Fellegi–Sunter** record linkage, the standard
statistics for this problem. Each field (first name, last name, birth date, sex, phone, ZIP) has
two rates: $m$, how often it agrees when two records *are* the same person, and $u$, how often it
agrees by chance when they *aren't*. Agreement is worth $\log_2 \frac{m}{u}$ points and
disagreement $\log_2 \frac{1-m}{1-u}$ (a negative number). Partial evidence, such as a nickname,
a typo or a swapped day and month, is a named level that counts as a fixed fraction $a$ of
agreement:

$$\text{points}(\text{level}) = a \log_2 \frac{m}{u} + (1 - a) \log_2 \frac{1-m}{1-u}$$

rounded to one decimal, so the same evidence always earns the same points. A pair starts from the
odds that two random records are the same person, about 1 in 1,000:

$$S = \underbrace{-10}_{\approx\, \log_2 \frac{1}{1000}} + \sum_{\text{fields}} \text{points}, \qquad P(\text{same person}) = \frac{1}{1 + 2^{-S}}$$

If $S \ge 4.2$ (about 95%) the records are linked automatically; if $0 \le S < 4.2$ a clinician
decides; below 0 they stay apart. Our two different women named Maria Gonzalez score

$$-10 + \underbrace{5.6}_{\text{first}} + \underbrace{6.6}_{\text{last}} + \underbrace{1.0}_{\text{sex}} - \underbrace{5.1}_{\text{birth date}} - \underbrace{2.3}_{\text{phone}} - \underbrace{2.7}_{\text{ZIP}} = -6.9$$

so they're never merged. To spot typos, names are split into letter pairs ("maria" becomes
`_m ma ar ri ia a_`) and compared with the Dice coefficient:

$$\text{Dice}(A, B) = \frac{2\,|A \cap B|}{|A| + |B|}$$

A Dice score of 0.75 or more counts as "close spelling, likely a typo".

**Scaling with blocking.** Comparing every pair of $n$ records takes $\binom{n}{2}$ comparisons:
about $5 \times 10^9$ for $n = 100{,}000$, or 100+ hours. We only compare records that share a
birth date, a phone number, or a sound-alike surname (Soundex) plus birth year. That's 686,541
comparisons, **7,283× fewer**, while keeping 99.97% of the true links. 100,000 records link in 86
seconds. On 20,000 synthetic records with realistic mistakes, **99.98%** of automatic links are
correct and **99.53%** of true matches are found; the rest go to a human.

**Privacy-preserving matching.** In encrypted mode, hospitals send keyed hashes,
$\text{HMAC-SHA256}_k(\cdot)$, of each whole value and of each letter pair. Dice only needs the
sizes of the sets and their overlap, so $|A \cap B|$ can be counted on hashes. The matcher never
sees a name or a birth date, yet makes exactly the same decisions.

**A tamper-evident audit log.** Every match decision and every time someone opens a patient is
appended to a hash chain, where each entry includes the hash of the one before:

$$h_i = \text{SHA-256}(e_i \,\|\, h_{i-1}), \qquad h_0 = 0$$

Editing or deleting an old entry breaks the chain, and the app then ignores everything from that
point on.

**Privacy and HIPAA.** All patients are synthetic. We built in seven technical safeguards from
HIPAA's Security Rule, including personal sign-in (salted PBKDF2), roles (a registration clerk can
fix identity mix-ups but never sees diagnoses or medications), automatic logoff after 15 idle
minutes, audit controls and integrity checks. We also go further than the rule requires: contact
details stay masked until a clinician gives a reason, which is logged.

## Challenges we ran into

- **Two people, one name.** Our demo has two different women named Maria Gonzalez. Matching on
  names alone merges them, putting one woman's allergy in the other's chart. The rubric keeps them
  apart because their birth date, phone and ZIP all disagree.
- **Making the scoring consistent.** Our first matcher used a sliding similarity score
  (Jaro–Winkler), so two equally bad typos could earn different points. Our encrypted matcher used
  Bloom filters, whose hash collisions made it disagree with the plain matcher on 0.07% of fields.
  We replaced both with named levels and exact letter-pair hashes. Now the two matchers agree on
  every pair we test.
- **Precision vs recall.** Looser spelling rules found more true matches (99.72% instead of
  99.53%), but also made more wrong merges (99.78% precision instead of 99.98%). In healthcare a
  wrong merge is worse than asking a human, so we kept the stricter rules.
- **Getting HIPAA right.** We first claimed HIPAA's "minimum necessary" rule required masking
  contact details. Then we read the regulation: that rule doesn't apply to sharing for treatment
  (45 CFR §164.502(b)(2)). We corrected our docs, mapped each feature to the specific Security
  Rule section it implements, and don't call the prototype "HIPAA compliant".
- **A log that actually protects.** Our first audit log detected a forged entry but still applied
  the forged decision. Now only the trusted part of the chain is ever replayed.
- **One we haven't solved yet.** A father and son with the same name who share a home phone score
  $+15.2$ and would be linked automatically. The rubric adds fields up as if they were
  independent, but families share phones and ZIP codes. Capping any pair with a clearly different
  birth date at "needs review" is our next fix.

## What we learned

- **Log-odds make evidence add up.** Once every field is a $\log_2$ likelihood ratio, combining
  evidence is just addition, and every decision can be explained line by line.
- **In healthcare, being unsure is a feature.** The safest answer to an uncertain match is to ask
  a clinician, not to guess.
- **FHIR**, the format real hospital systems exchange, and how much of a patient's record it can
  carry.
- **What HIPAA actually says**, section by section, including what it doesn't require.
- **Privacy has trade-offs.** Bloom filters protect better against frequency analysis but give up
  exactness; we chose exactness and documented the risk.

## What's next for Constellation

- RxNorm drug codes and a licensed interaction database instead of our small demo rules
- Reading live from FHIR servers on TEFCA and Epic, with hospital single sign-on
- Household-aware matching to fix the father-and-son case
- Hardening the encrypted fingerprints against frequency analysis

*All patients and hospitals are synthetic. This is a hackathon prototype, not a medical device.*
