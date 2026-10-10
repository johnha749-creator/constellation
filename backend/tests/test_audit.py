import json

import pytest

from app.audit import AuditLog
from app.constellation import PatientIndex
from app.seed import write_seed


def review(log, a="r1", b="r2", same=True, previous=None):
    return log.record_review(a, b, same, reviewer="Dr. Lee", score=0.85, previous=previous)


def test_entries_survive_reopening_the_file(tmp_path):
    path = tmp_path / "reviews.jsonl"
    review(AuditLog(path))
    reopened = AuditLog(path)
    assert len(reopened.events) == 1
    event = reopened.events[0]
    assert (event["seq"], event["reviewer"], event["decision"], event["score"]) == (1, "Dr. Lee", "same", 0.85)
    assert reopened.current_reviews() == {frozenset(("r1", "r2")): True}


def test_latest_decision_wins_and_reset_clears_without_deleting():
    log = AuditLog()
    review(log, same=True)
    review(log, same=False, previous=True)
    assert log.current_reviews() == {frozenset(("r1", "r2")): False}
    log.record_reset("Dr. Lee")
    assert log.current_reviews() == {}
    assert [e["action"] for e in log.events] == ["review", "review", "reset"]
    assert log.events[1]["previous"] == "same"


def test_hash_chain_detects_an_edited_entry(tmp_path):
    path = tmp_path / "reviews.jsonl"
    log = AuditLog(path)
    review(log)
    review(log, a="r3", b="r4")
    review(log, a="r5", b="r6")
    assert AuditLog(path).verify() is None

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["decision"] = "different"  # someone quietly flips the second decision
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reopened = AuditLog(path)
    assert reopened.verify() == 2
    # The forged entry, and everything after it, is ignored rather than applied.
    assert reopened.current_reviews() == {frozenset(("r1", "r2")): True}


def test_hash_chain_detects_a_deleted_entry(tmp_path):
    path = tmp_path / "reviews.jsonl"
    log = AuditLog(path)
    for pair in (("r1", "r2"), ("r3", "r4"), ("r5", "r6")):
        review(log, *pair)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert AuditLog(path).verify() == 3


@pytest.fixture
def data_dir(tmp_path):
    write_seed(tmp_path / "data")
    return tmp_path / "data"


def test_decisions_survive_a_restart(data_dir, tmp_path):
    path = tmp_path / "reviews.jsonl"
    index = PatientIndex(data_dir, AuditLog(path))
    a, b = index.find("Aisha Patel", "1990-07-22").record_ids
    index.review_match(a, b, same_person=True, reviewer="Dr. Lee")

    restarted = PatientIndex(data_dir, AuditLog(path))
    cluster = restarted.cluster_of(a)
    assert not cluster.needs_review
    history = restarted.audit_for(cluster.id)
    assert history["verified"] and history["total_events"] == 1
    entry = history["events"][0]
    assert (entry["reviewer"], entry["decision"]) == ("Dr. Lee", "same")
    assert 0.5 < entry["score"] < 0.95  # it was a "needs review" score when decided
    assert {r["hospital"] for r in entry["records"]} == {"Orion General Hospital", "Lyra Medical Center"}


def test_reset_restores_the_original_links_but_keeps_history(data_dir):
    index = PatientIndex(data_dir)
    a, b = index.find("Aisha Patel", "1990-07-22").record_ids
    index.review_match(a, b, same_person=False, reviewer="Dr. Lee")
    assert index.cluster_of(a).id != index.cluster_of(b).id
    index.reset_reviews("Dr. Lee")
    cluster = index.cluster_of(a)
    assert cluster.id == index.cluster_of(b).id and cluster.needs_review
    assert [e["action"] for e in index.audit_for(cluster.id)["events"]] == ["reset", "review"]
