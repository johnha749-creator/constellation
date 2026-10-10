import dataclasses

import pytest

from app import pprl
from app.constellation import PatientIndex
from app.matching import candidate_pairs, cluster_records, score_pairs
from app.records import PatientRecord, load_dataset
from app.seed import write_seed


def record(given, family, birth_date, phone=None, postal_code=None, rid="x"):
    return PatientRecord(rid, "h", "MRN-1", given, family, birth_date, "female", phone, postal_code, "1 Main St")


def test_fingerprints_reveal_nothing_readable():
    encoded = pprl.encode(record("Aisha", "Patel-Khan", "1990-07-27", "510-555-0129", "94704"))
    # Bloom filters are opaque bit sets (ints); every text field must be a keyed hash.
    text = " ".join(str(v) for v in dataclasses.asdict(encoded).values() if isinstance(v, (str, frozenset)))
    for secret in ("aisha", "patel", "khan", "1990-07-27", "19900727", "510-555-0129", "5105550129",
                   "94704", "main st", "mrn"):
        assert secret not in text.lower(), secret


def test_fingerprints_depend_on_the_shared_key():
    r = record("Maria", "Gonzalez", "1958-03-14")
    assert pprl.encode(r, b"key-1") == pprl.encode(r, b"key-1")
    assert pprl.encode(r, b"key-1").last != pprl.encode(r, b"key-2").last  # useless without the key


def test_hard_cases_still_link_on_fingerprints():
    cases = [  # (a, b, expected tier)
        (record("James", "O'Brien", "1947-11-02", "415-555-0117", "94116"),
         record("Jim", "OBrien", "1947-11-02", None, "94116"), "match"),  # nickname, punctuation
        (record("James", "O'Brien", "1947-11-02", "415-555-0117", "94116"),
         record("James", "O Brien", "1947-02-11", "415-555-0163", "94116"), "match"),  # swapped date
        (record("Aisha", "Patel", "1990-07-22", "415-555-0175", "94118"),
         record("Aisha", "Patel-Khan", "1990-07-27", "510-555-0129", "94704"), "review"),  # married + typo
        (record("Maria", "Gonzalez", "1958-03-14", "415-555-0142", "94112"),
         record("Maria", "Gonzalez", "1985-09-30", "415-555-0198", "94103"), "non-match"),  # same name only
    ]
    for a, b, tier in cases:
        assert pprl.compare_encoded(pprl.encode(a), pprl.encode(b)).tier == tier, (a.family, b.family)


@pytest.fixture
def data_dir(tmp_path):
    write_seed(tmp_path)
    return tmp_path


def test_finds_the_same_patients_as_plain_matching(data_dir):
    records = list(load_dataset(data_dir).records.values())
    plain = score_pairs({r.id: r for r in records}, candidate_pairs(records))
    encoded, private = pprl.link_privately(records)
    assert pprl.candidate_pairs(encoded.values()) == candidate_pairs(records)  # hashed blocking works
    assert set(private) == set(plain)
    partition = lambda clusters: sorted(sorted(c.record_ids) for c in clusters)
    assert partition(cluster_records(records, scored=plain)) == partition(
        cluster_records(list(encoded.values()), scored=private, compare=pprl.compare_encoded))


def test_the_app_can_run_on_fingerprints(data_dir):
    index = PatientIndex(data_dir, matching="private")
    aisha = index.find("Aisha Patel", "1990-07-22")
    assert aisha.needs_review
    a, b = aisha.record_ids
    patient_id = index.review_match(a, b, same_person=True)
    assert not any(c.unconfirmed for c in index.conflicts[patient_id])
    graph = index.constellation(patient_id)
    assert graph["conflicts"]  # still caught: the clinical facts stay at the hospitals, only identity is hidden
