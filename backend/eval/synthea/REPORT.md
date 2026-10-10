# Accuracy check on Synthea patients

280 records at 3 hospitals, for 138 people: 108 Synthea patients and 30 look-alike relatives sharing their households. 105 people have records at more than one hospital, which makes 179 true links to find.

## Matching

| Method | True links found | Wrong links made |
|---|---|---|
| Identical name and birth date | 64.2% (115 of 179) | 0 |
| Constellation, linked automatically | 97.8% (175 of 179) | 0 |
| Constellation, counting links sent to review | 98.3% (176 of 179) | |

- Patients put back together exactly, with nobody else's records mixed in: 97.1% (102 of 105).
- Review queue: 57 links for a clinician to decide, 1 of them really the same person.

### By mistake in the record

| Mistake | Links | Linked automatically | Sent to review | Missed |
|---|---|---|---|---|
| none | 73 | 73 | 0 | 0 |
| no phone | 34 | 33 | 0 | 1 |
| moved | 33 | 29 | 1 | 3 |
| new phone | 24 | 20 | 1 | 3 |
| middle name | 22 | 22 | 0 | 0 |
| maiden name | 14 | 11 | 0 | 3 |
| first initial | 12 | 11 | 1 | 0 |
| last name typo | 10 | 10 | 0 | 0 |
| nickname | 5 | 4 | 0 | 1 |
| first name typo | 3 | 3 | 0 | 0 |
| hyphenated name | 3 | 3 | 0 | 0 |
| birth date one digit off | 2 | 2 | 0 | 0 |
| birth date digits transposed | 1 | 1 | 0 | 0 |

### Look-alike relatives (different people who must stay apart)

| Relative | Record pairs | Kept apart | Sent to review | Wrongly merged |
|---|---|---|---|---|
| namesake | 30 | 0 | 30 | 0 |
| twin | 27 | 0 | 27 | 0 |
| spouse | 29 | 27 | 2 | 0 |

### Missed links: examples

- Sue Barrows, born 1969-04-25 (Lyra Medical Center) / SUSAN HEGMANN, born 1969-04-25 (Vega Community Clinic): scored 42%. 'Sue' and 'SUSAN' treated as the same name (nickname); Last names differ ('Barrows' vs 'HEGMANN'); Phone missing in one record; ZIP differs (02116 vs 01890).
- Merlene Thompson, born 1972-09-11 (Lyra Medical Center) / Merlene Kiehn, born 1972-09-11 (Orion General Hospital): scored 13%. Last names differ ('Thompson' vs 'Kiehn'); Phone differs ((978) 555-0109 vs 339-555-0176); ZIP differs (02457 vs 02139).
- Susan Barrows, born 1969-04-25 (Orion General Hospital) / SUSAN HEGMANN, born 1969-04-25 (Vega Community Clinic): scored 13%. Last names differ ('Barrows' vs 'HEGMANN'); Phone differs (339-555-0112 vs 508.555.0189); ZIP differs (02461 vs 01890).

## Conflict detection

With perfect matching, the rules find 49 conflicts. 27 sit inside one hospital's record. The rest are only visible once records from different hospitals are linked:

| Severity | Cross-hospital conflicts | Shown | Shown as unconfirmed | Missed |
|---|---|---|---|---|
| high | 15 | 15 | 0 | 0 |
| moderate | 4 | 4 | 0 | 0 |
| low | 3 | 3 | 0 | 0 |

### Dangerous combinations hidden on purpose

We hid 20 high-severity combinations, half on a patient's record at one hospital and half at another. Constellation showed 16, showed 0 as unconfirmed, and missed 4.
- Missed 2: warfarin under its brand name Coumadin, then naproxen, because the drug list does not know "Coumadin 5 MG Oral Tablet".
- Missed 2: aspirin allergy, then ibuprofen under its brand name Advil, because the drug list does not know "Advil 200 MG Oral Tablet".

### Other checks

- False alarms from mixing two people's records: 0 shown as confirmed, 5 shown as unconfirmed.
- Medication orders the drug list recognizes: 56.3% (202 of 359).
- Most common drugs it does not know: epinephrine (19), hydrochlorothiazide (14), ferrous sulfate (9), vitamin b12 (8), cetirizine hydrochloride (7), budesonide (6), ethinyl estradiol (6), norethindrone (6), alendronic acid (5), fexofenadine hydrochloride (5), insulin isophane human (5), loratadine (5).
