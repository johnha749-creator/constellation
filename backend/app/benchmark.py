"""Benchmark record linkage at scale, on synthetic patients with known answers.

    python -m app.benchmark                   # 20,000 records
    python -m app.benchmark --records 50000

Each fake person gets 1-3 records at different hospitals, with the mistakes real records have:
nicknames, misspelled or married surnames, swapped or mistyped birth dates, moves, missing
phones. Because we know who is really who, we can measure how many true links are found
(recall) and how many found links are right (precision).
"""
from __future__ import annotations

import argparse
import random
import time
from collections import defaultdict
from itertools import combinations

from .matching import candidate_pairs, cluster_records, score_pairs
from .records import PatientRecord

FIRST_NAMES = [
    ("James", "male"), ("Robert", "male"), ("William", "male"), ("Michael", "male"), ("Thomas", "male"),
    ("Daniel", "male"), ("David", "male"), ("Joseph", "male"), ("Carlos", "male"), ("Wei", "male"),
    ("Arjun", "male"), ("Omar", "male"), ("Kenji", "male"), ("Liam", "male"), ("Noah", "male"),
    ("Mateo", "male"), ("Samuel", "male"), ("Andre", "male"), ("Felix", "male"), ("Hugo", "male"),
    ("Elizabeth", "female"), ("Katherine", "female"), ("Margaret", "female"), ("Jennifer", "female"),
    ("Maria", "female"), ("Aisha", "female"), ("Mei", "female"), ("Priya", "female"), ("Fatima", "female"),
    ("Olivia", "female"), ("Sofia", "female"), ("Grace", "female"), ("Nadia", "female"), ("Chloe", "female"),
    ("Hana", "female"), ("Ines", "female"), ("Leah", "female"), ("Ruth", "female"), ("Zoe", "female"),
    ("Amara", "female"),
]
NICKNAMES = {"James": "Jim", "Robert": "Bob", "William": "Bill", "Michael": "Mike", "Thomas": "Tom",
             "Daniel": "Dan", "Elizabeth": "Liz", "Katherine": "Kate", "Margaret": "Peggy", "Jennifer": "Jen"}
# 25 x 10 x 15 = 3,750 made-up surnames, from common ("Albergson") to rare.
SURNAME_PARTS = (
    ["Al", "Bar", "Cal", "Dal", "Er", "Fen", "Gar", "Hal", "Is", "Jor", "Kel", "Lin", "Mor", "Nor", "Ost",
     "Par", "Quin", "Ros", "Sal", "Tor", "Ul", "Var", "Wes", "Yar", "Zel"],
    ["a", "e", "i", "o", "an", "en", "in", "on", "ar", "er"],
    ["berg", "by", "dale", "ford", "gate", "ham", "ley", "man", "more", "ton", "ski", "son", "stein",
     "well", "wood"],
)
HOSPITALS = ["orion", "lyra", "vega", "sirius", "altair"]


def make_population(n_records: int, seed: int = 7) -> tuple[list[PatientRecord], dict[str, int]]:
    """Synthetic records plus the truth: record id -> person number."""
    rng = random.Random(seed)
    surnames = [a + b + c for a in SURNAME_PARTS[0] for b in SURNAME_PARTS[1] for c in SURNAME_PARTS[2]]
    rng.shuffle(surnames)
    weights = [1 / (rank + 1) ** 0.8 for rank in range(len(surnames))]  # a few names are very common
    zips = [f"94{n:03d}" for n in range(100, 160)]
    records: list[PatientRecord] = []
    person_of: dict[str, int] = {}
    person = 0
    while len(records) < n_records:
        person += 1
        given, gender = rng.choice(FIRST_NAMES)
        family = rng.choices(surnames, weights)[0]
        dob = f"{rng.randint(1930, 2010)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        phone = f"{rng.randint(200, 999)}-555-{rng.randint(0, 9999):04d}"
        zip_code = rng.choice(zips)
        copies = rng.choices([1, 2, 3], [50, 35, 15])[0]
        for i, hospital in enumerate(rng.sample(HOSPITALS, copies)):
            g, f, d, p, z = given, family, dob, phone, zip_code
            if i > 0:  # later copies pick up the usual mistakes
                if given in NICKNAMES and rng.random() < 0.15:
                    g = NICKNAMES[given]
                if rng.random() < 0.10:
                    f = _misspell(f, rng)
                if gender == "female" and rng.random() < 0.03:
                    f = f"{family}-{rng.choices(surnames, weights)[0]}"  # married name
                if rng.random() < 0.05:
                    d = _mistype_date(d, rng)
                if rng.random() < 0.15:  # moved
                    z = rng.choice(zips)
                    if rng.random() < 0.5:
                        p = f"{rng.randint(200, 999)}-555-{rng.randint(0, 9999):04d}"
                if rng.random() < 0.10:
                    p = None
            record = PatientRecord(f"r{len(records)}", hospital, None, g, f, d, gender, p, z, None)
            records.append(record)
            person_of[record.id] = person
    return records, person_of


def _misspell(name: str, rng: random.Random) -> str:
    i = rng.randrange(1, len(name) - 1)
    kind = rng.choice(["drop", "double", "swap"])
    if kind == "drop":
        return name[:i] + name[i + 1:]
    if kind == "double":
        return name[:i] + name[i] + name[i:]
    return name[:i] + name[i + 1] + name[i] + name[i + 2:]


def _mistype_date(date: str, rng: random.Random) -> str:
    year, month, day = date.split("-")
    if int(day) <= 12 and rng.random() < 0.5:
        return f"{year}-{day}-{month}"  # day and month swapped
    return f"{year}-{month}-{day[0]}{(int(day[1]) + rng.randint(1, 8)) % 10}"  # one digit off


def run(n_records: int) -> None:
    records, person_of = make_population(n_records)
    by_id = {r.id: r for r in records}
    n = len(records)

    start = time.perf_counter()
    pairs = candidate_pairs(records)
    blocked = time.perf_counter()
    scored = score_pairs(by_id, pairs)
    compared = time.perf_counter()
    clusters = cluster_records(records, scored=scored)
    done = time.perf_counter()

    # Truth: every pair of records that belongs to one person.
    members: dict[int, list[str]] = defaultdict(list)
    for rid, p in person_of.items():
        members[p].append(rid)
    true_pairs = {tuple(sorted(pair)) for ids in members.values() for pair in combinations(ids, 2)}

    # Linked automatically = same confirmed group (score >= 95%). Review = 50-95%, a human decides.
    auto, review = set(), set()
    for cluster in clusters:
        for a, b in combinations(sorted(cluster.record_ids), 2):
            (auto if cluster.confirmed(a, b) else review).add((a, b))
    found_true = auto & true_pairs
    all_pairs = n * (n - 1) // 2
    per_comparison = (compared - blocked) / max(len(pairs), 1)

    print(f"Records:                 {n:,} ({len(members):,} real people)")
    print(f"Comparing every pair:    {all_pairs:,} comparisons, about "
          f"{_duration(all_pairs * per_comparison)} at this machine's speed")
    print(f"With blocking:           {len(pairs):,} comparisons ({all_pairs / max(len(pairs), 1):,.0f}x fewer)")
    print(f"Time:                    {done - start:.1f} s total "
          f"(blocking {blocked - start:.1f} s, scoring {compared - blocked:.1f} s, "
          f"clustering {done - compared:.1f} s)")
    print(f"True links kept by blocking: {len(true_pairs & pairs) / len(true_pairs):.2%}")
    print(f"Linked automatically:    recall {len(found_true) / len(true_pairs):.2%}, "
          f"precision {len(found_true) / max(len(auto), 1):.2%}")
    print(f"Sent to human review:    {len(review):,} pairs "
          f"({len(review & true_pairs):,} really the same person)")


def _duration(seconds: float) -> str:
    if seconds < 120:
        return f"{seconds:.0f} seconds"
    if seconds < 7200:
        return f"{seconds / 60:.0f} minutes"
    return f"{seconds / 3600:.1f} hours"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--records", type=int, default=20_000)
    run(parser.parse_args().records)
