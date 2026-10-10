from itertools import combinations

from app.matching import (blocking_keys, candidate_pairs, cluster_records, compare_records,
                          jaro_winkler, score_pairs, soundex)
from app.records import PatientRecord, load_dataset
from app.seed import write_seed


def record(given, family, birth_date, gender="female", phone=None, postal_code=None, rid="x"):
    return PatientRecord(rid, "h", None, given, family, birth_date, gender, phone, postal_code, None)


def test_jaro_winkler_known_value():
    assert round(jaro_winkler("martha", "marhta"), 3) == 0.961


def test_nickname_and_punctuation_still_match():
    a = record("James", "O'Brien", "1947-11-02", "male", "415-555-0117", "94116")
    b = record("Jim", "OBrien", "1947-11-02", "male", None, "94116")
    result = compare_records(a, b)
    assert result.tier == "match"
    assert any("nickname" in r for r in result.reasons)


def test_same_name_different_person_is_not_merged():
    a = record("Maria", "Gonzalez", "1958-03-14", phone="415-555-0142", postal_code="94112")
    b = record("Maria", "Gonzalez", "1985-09-30", phone="415-555-0198", postal_code="94103")
    assert compare_records(a, b).tier == "non-match"


def test_swapped_day_and_month_is_explained():
    a = record("James", "O'Brien", "1947-11-02", "male", "415-555-0117", "94116")
    b = record("James", "O Brien", "1947-02-11", "male", "415-555-0163", "94116")
    result = compare_records(a, b)
    assert result.tier == "match"
    assert any("swapped" in r for r in result.reasons)


def test_married_name_with_typo_needs_review():
    a = record("Aisha", "Patel", "1990-07-22", phone="415-555-0175", postal_code="94118")
    b = record("Aisha", "Patel-Khan", "1990-07-27", phone="510-555-0129", postal_code="94704")
    assert compare_records(a, b).tier == "review"


def test_soundex_known_values():
    assert [soundex(n) for n in ("Robert", "Rupert", "Tymczak", "Pfister", "Whittaker", "Whitaker")] == [
        "R163", "R163", "T522", "P236", "W326", "W326"]


def test_blocking_keeps_hard_matches_together():
    # Each pair below gets past at least one blocking key despite its mistake.
    pairs = [
        (record("James", "O'Brien", "1947-11-02"), record("James", "O Brien", "1947-02-11")),  # swapped DOB
        (record("Aisha", "Patel", "1990-07-22"), record("Aisha", "Patel-Khan", "1990-07-27")),  # married name + typo
        (record("Eleanor", "Whittaker", "1953-10-12", phone="415-555-0136"),
         record("Eleanor", "Whitaker", "1953-10-21", phone="415.555.0136")),  # spelling + transposed digits
    ]
    for a, b in pairs:
        assert blocking_keys(a) & blocking_keys(b), (a.family, b.family)


def test_blocking_finds_every_match_that_comparing_all_pairs_finds(tmp_path):
    write_seed(tmp_path)
    records = list(load_dataset(tmp_path).records.values())
    by_id = {r.id: r for r in records}
    everything = score_pairs(by_id, [tuple(sorted((a.id, b.id))) for a, b in combinations(records, 2)])
    blocked = candidate_pairs(records)
    assert set(everything) <= blocked  # no real link is missed
    assert len(blocked) * 10 < len(records) * (len(records) - 1) // 2  # but far fewer comparisons
    partition = lambda clusters: sorted(sorted(c.record_ids) for c in clusters)
    assert partition(cluster_records(records)) == partition(cluster_records(records, scored=everything))
