"""The match rubric must be consistent: the same evidence always earns the same level and points,
in either order, in either matching mode."""
import pytest
from fastapi.testclient import TestClient

from app import pprl
from app.benchmark import make_population
from app.matching import candidate_pairs, compare_records
from app.records import PatientRecord, load_dataset
from app.rubric import LINK_AT, PRIOR, REVIEW_AT, RUBRIC, as_table
from app.main import app
from app.seed import write_seed

from conftest import demo_account


def record(given, family, birth_date, phone=None, postal_code=None, gender="female", rid="x"):
    return PatientRecord(rid, "h", None, given, family, birth_date, gender, phone, postal_code, None)


BASE = record("Maria", "Gonzalez", "1958-03-14", "415-555-0142", "94112", rid="a")

# (field, value in BASE's place, expected level): one documented case per rubric level.
CASES = [
    ("first_name", "Maria", "same"),
    ("first_name", "M.", "initial"),
    ("first_name", "Mariah", "close"),
    ("first_name", "Mario", "similar"),  # one letter off a short name shares fewer letter pairs
    ("first_name", "Marta", "similar"),
    ("first_name", "Olivia", "different"),
    ("first_name", "", "missing"),
    ("last_name", "Gonzales", "close"),
    ("last_name", "Gonzalez-Ruiz", "contains"),
    ("last_name", "Gonzaga", "similar"),
    ("last_name", "Okafor", "different"),
    ("birth_date", "1958-14-03", "swapped"),
    ("birth_date", "1958-03-15", "digit"),
    ("birth_date", "1958-03-27", "year_month"),
    ("birth_date", "1985-09-30", "different"),
    ("phone", "(415) 555-0142", "same"),
    ("phone", None, "missing"),
    ("postal_code", "94110", "different"),
]
FIELD_ATTR = {"first_name": "given", "last_name": "family", "birth_date": "birth_date",
              "phone": "phone", "postal_code": "postal_code"}


def with_field(field, value):
    values = dict(BASE.__dict__, id="b")
    values[FIELD_ATTR[field]] = value
    return PatientRecord(**values)


@pytest.mark.parametrize("field,value,level", CASES)
def test_each_case_lands_on_its_documented_level(field, value, level):
    other = with_field(field, value)
    plain = {f.field: f.level for f in compare_records(BASE, other).fields}
    private = {f.field: f.level for f in pprl.compare_encoded(pprl.encode(BASE), pprl.encode(other)).fields}
    assert plain[field] == private[field] == level


def test_nicknames_count_as_the_same_name():
    a, b = record("James", "O'Brien", "1947-11-02"), record("Jim", "OBrien", "1947-11-02")
    levels = {f.field: f.level for f in compare_records(a, b).fields}
    assert (levels["first_name"], levels["last_name"]) == ("nickname", "same")


def test_more_agreement_never_scores_lower():
    for rule in RUBRIC.values():
        points = [rule.points(level.key) for level in rule.levels]  # listed from most to least agreement
        assert points == sorted(points, reverse=True), rule.label
        assert rule.points("same") > 0 > rule.points("different")


def test_thresholds_match_the_stated_probabilities():
    assert PRIOR == -10.0 and REVIEW_AT == 0.0
    assert 0.94 < 1 / (1 + 2 ** -LINK_AT) < 0.95  # +4.2 points is "about 95%"


def test_the_published_table_is_what_the_code_adds_up():
    table = as_table()
    for entry, rule in zip(table["fields"], RUBRIC.values()):
        published = [level["points"] for level in entry["levels"][:-1]]
        assert published == [rule.points(level.key) for level in rule.levels]
        assert entry["levels"][-1] == {"level": "Missing in one record", "points": 0.0}


@pytest.fixture(scope="module")
def populations(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    write_seed(data_dir)
    return [list(load_dataset(data_dir).records.values()), make_population(3000)[0]]


def test_order_never_matters(populations):
    for records in populations:
        by_id = {r.id: r for r in records}
        for a, b in candidate_pairs(records):
            forward, backward = compare_records(by_id[a], by_id[b]), compare_records(by_id[b], by_id[a])
            assert [f.level for f in forward.fields] == [f.level for f in backward.fields]
            assert forward.points == backward.points


def test_encrypted_matching_reaches_exactly_the_same_scores(populations):
    for records in populations:
        by_id = {r.id: r for r in records}
        encoded = {r.id: pprl.encode(r) for r in records}
        for a, b in candidate_pairs(records):
            plain = compare_records(by_id[a], by_id[b])
            private = pprl.compare_encoded(encoded[a], encoded[b])
            assert [f.level for f in plain.fields] == [f.level for f in private.fields], (a, b)
            assert (plain.points, plain.tier) == (private.points, private.tier)


def test_the_breakdown_adds_up_to_the_total():
    result = compare_records(BASE, record("M.", "Gonzales", "1958-03-14", None, "94122", rid="b"))
    assert round(PRIOR + sum(row["points"] for row in result.breakdown()), 1) == result.points
    assert result.tier == ("match" if result.points >= LINK_AT else "review" if result.points >= REVIEW_AT else "non-match")


def test_the_api_serves_the_rubric_and_each_links_breakdown():
    # Signed in as an account that hasn't unmasked anything (other tests unmask as dr.lee).
    account = demo_account(2)
    client = TestClient(app)
    client.post("/api/login", json={"username": account["username"], "password": account["password"]})
    assert client.get("/api/rubric").json() == as_table()
    aisha = next(p for p in client.get("/api/patients").json() if p["needs_review"])
    link = next(l for l in client.get(f"/api/patients/{aisha['id']}/constellation").json()["links"]
                if l["kind"] == "match")
    assert round(PRIOR + sum(row["points"] for row in link["breakdown"]), 1) == link["points"]
    phone = next(row for row in link["breakdown"] if row["field"] == "Phone")
    assert phone["level"] == "Different" and "510-555-0129" not in phone["values"]  # masked
