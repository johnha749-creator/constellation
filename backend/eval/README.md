# Accuracy check on patients we didn't write

`app.benchmark` measures the matcher on people and mistakes we generated ourselves. This folder
holds a second, independent check: patients from [Synthea](https://github.com/synthetichealth/synthea),
the open-source synthetic patient generator, with their real-style drug names.

- `synthea/hospitals/*.json`: 280 records at three hospitals, in the same FHIR format as `backend/data`
- `synthea/truth/answer_key.json`: which records are really the same person, the mistakes in each
  record, and where the hidden conflicts are
- `synthea/REPORT.md`: the current results

## Run it

From `backend/`:

```bash
python -m app.evaluate
```

To rebuild the dataset, download the 100-patient CSV sample from
https://synthea.mitre.org/downloads, unzip it, and run:

```bash
python -m app.synthea_import --synthea path/to/csv
python -m app.evaluate --report eval/synthea/REPORT.md
```

## How the dataset is made

`app.synthea_import` takes each Synthea patient's single clean record and:

1. splits it across three hospitals by where each visit happened;
2. registers the patient separately at each hospital with front-desk mistakes: nicknames,
   maiden names, typos, mistyped birth dates, old addresses, missing phones;
3. adds 30 look-alike relatives who share a household with a patient (a parent or child with
   the same name, a twin, a spouse) and must not be merged with them;
4. hides 20 dangerous drug combinations, half at one hospital and half at another.

## What the first run found, and what we changed

The first run showed the matcher merging relatives. A shared phone, ZIP and surname outweighed a
different first name or birth date, so every twin and every same-name parent and child was linked
automatically. `app.benchmark` has no relatives in it, so it could not show this.

The matcher now caps the score of any pair whose first name or birth date flatly disagrees
(`RELATIVE_CAP` in `app/matching.py`). Those pairs go to a clinician for review. Same dataset,
before and after:

| | Before | After |
|---|---|---|
| True links found automatically | 175 of 179 | 175 of 179 |
| Wrong links made | 59 | 0 |
| Patients put back together exactly | 78 of 105 | 102 of 105 |
| Twin and same-name relative pairs merged | 57 of 57 | 0 (all sent to review) |
| False alarms shown as confirmed conflicts | 6 | 0 |
| Links in the review queue | 10 | 57 |

The larger review queue is the cost: a person now decides the cases a twin could explain.
`python -m app.benchmark --records 20000` gives the same numbers as before the change.

## Known gaps

- **Married name plus a move.** The 3 links still missed are women registered under a maiden
  name at one hospital who have since moved, with a new or missing phone number. Only the first
  name and birth date agree, which is not enough to link safely.
- **Brand names.** The 4 hidden conflicts that were missed were written as "Coumadin" and "Advil".
  The drug list matches generic names as text. RxNorm codes would fix this.
- **Drug coverage.** The drug list recognizes about 56% of Synthea's medication orders. The rest
  (epinephrine, hydrochlorothiazide, antihistamines and others) can't take part in any rule yet.
- **A mistyped birth year plus a new phone** can slip past blocking, because none of the three
  blocking keys then match. A fourth key (surname sound plus birth month and day) would catch it
  for 12 to 16% more comparisons.
- **Relatives are invented, not from Synthea**, and there are far more of them here than in a
  real population. They are a stress test, so the review-queue size is a worst case.
