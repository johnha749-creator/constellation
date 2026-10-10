"""Score the matcher and the conflict checker against a dataset with a known answer key.

    python -m app.evaluate                                  # backend/eval/synthea
    python -m app.evaluate path/to/dataset --report REPORT.md

The dataset folder holds hospitals/*.json (FHIR bundles, read exactly as the app reads
backend/data) and truth/answer_key.json (which records are really the same person).
`python -m app.synthea_import` builds one from Synthea patients.

Matching is scored on pairs of records. Conflict detection is scored on the conflicts that
no single hospital could see: both halves are only on the same chart once records are linked.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from .conflicts import Conflict, find_conflicts
from .matching import cluster_records, compare_records
from .records import ClinicalItem, Dataset, load_dataset
from .synthea_import import DEFAULT_OUT

SEVERITIES = ("high", "moderate", "low")


def evaluate(dataset_dir: Path = DEFAULT_OUT) -> dict:
    truth = json.loads((dataset_dir / "truth" / "answer_key.json").read_text(encoding="utf-8"))
    dataset = load_dataset(dataset_dir / "hospitals")
    clusters = cluster_records(list(dataset.records.values()))
    person_of = {rid: info["person"] for rid, info in truth["records"].items()}
    members: dict[str, list[str]] = defaultdict(list)  # person -> their record ids
    for rid in dataset.records:
        members[person_of[rid]].append(rid)
    kinds = Counter(p["kind"] for p in truth["people"].values())
    return {
        "dataset": {
            "source": truth.get("source"),
            "people": len(members),
            "relatives": len(members) - kinds.get("synthea", len(members)),
            "records": len(dataset.records),
            "hospitals": len(dataset.hospitals),
            "people_at_several": sum(len(ids) > 1 for ids in members.values()),
        },
        "matching": score_matching(dataset, clusters, truth, members),
        "conflicts": score_conflicts(dataset, clusters, truth, members),
    }


def score_matching(dataset: Dataset, clusters: list, truth: dict, members: dict[str, list[str]]) -> dict:
    records = dataset.records
    true_pairs = _pairs(members.values())

    # Linked automatically = same confirmed group (score >= 95%). Review = 50-95%, a human decides.
    auto, review, group_of = set(), set(), {}
    for cluster in clusters:
        group_of.update(cluster.confirmed_group)
        for a, b in combinations(sorted(cluster.record_ids), 2):
            (auto if cluster.confirmed(a, b) else review).add((a, b))
    review_links = [e for c in clusters for e in c.edges if e.result.tier == "review"]

    # The obvious alternative: link records whose name and birth date are identical.
    exact_groups: dict[tuple, list[str]] = defaultdict(list)
    for r in records.values():
        exact_groups[(_letters(r.given), _letters(r.family), r.birth_date)].append(r.id)
    exact = _pairs(exact_groups.values())

    group_members: dict[str, set[str]] = defaultdict(set)
    for rid, group in group_of.items():
        group_members[group].add(rid)
    several = [ids for ids in members.values() if len(ids) > 1]

    by_mistake: dict[str, Counter] = defaultdict(Counter)
    for a, b in true_pairs:
        info = truth["records"]
        outcome = "auto" if (a, b) in auto else "review" if (a, b) in review else "missed"
        for mistake in sorted({*info[a]["mistakes"], *info[b]["mistakes"]}) or ["none"]:
            by_mistake[mistake][outcome] += 1

    # Relatives are different people: every record of theirs must stay apart from the patient's.
    by_relative: dict[str, Counter] = defaultdict(Counter)
    for pid, person in truth["people"].items():
        for a in members.get(pid, []) if person["relative_of"] else []:
            for b in members.get(person["relative_of"], []):
                pair = (a, b) if a < b else (b, a)
                outcome = "merged" if pair in auto else "review" if pair in review else "apart"
                by_relative[person["kind"]][outcome] += 1

    def describe(pair: tuple[str, str]) -> dict:
        result = compare_records(records[pair[0]], records[pair[1]])
        return {"records": [_label(dataset, rid) for rid in pair], "score": round(result.probability, 4),
                "mistakes": sorted({m for rid in pair for m in truth["records"][rid]["mistakes"]}),
                "reasons": result.reasons}

    return {
        "true_links": len(true_pairs),
        "exact": {"found": len(exact & true_pairs), "wrong": len(exact - true_pairs)},
        "auto": {"found": len(auto & true_pairs), "wrong": len(auto - true_pairs)},
        "with_review": {"found": len((auto | review) & true_pairs)},
        "review_queue": {"links": len(review_links),
                         "same_person": sum(_same(truth, e.a, e.b) for e in review_links)},
        "people_at_several": len(several),
        "people_whole": sum(group_members[group_of[ids[0]]] == set(ids) for ids in several),
        "by_mistake": {m: dict(c) for m, c in sorted(by_mistake.items(), key=lambda kv: -sum(kv[1].values()))},
        "by_relative": {k: dict(c) for k, c in by_relative.items()},
        "missed_examples": [describe(p) for p in sorted(true_pairs - auto - review)[:6]],
        "wrong_examples": sorted((describe(p) for p in auto - true_pairs), key=lambda e: -e["score"])[:6],
    }


def score_conflicts(dataset: Dataset, clusters: list, truth: dict, members: dict[str, list[str]]) -> dict:
    person_of = {rid: info["person"] for rid, info in truth["records"].items()}
    cluster_of = {rid: cluster.id for cluster in clusters for rid in cluster.record_ids}
    items_by_record: dict[str, list[ClinicalItem]] = defaultdict(list)
    for item in dataset.items:
        items_by_record[item.record_id].append(item)
    item_by_id = {item.id: item for item in dataset.items}

    def key(conflict: Conflict) -> tuple:
        """The same problem gets the same key whichever copies of the two facts were paired."""
        sides = (item_by_id[i] for i in conflict.item_ids)
        return conflict.type, frozenset(item.drug or item.text.lower() for item in sides)

    def always(a: str, b: str) -> bool:
        return True

    # What a perfect matcher would let us see, and which of it needs records to be linked.
    exist: dict[tuple, dict] = {}
    for person, rids in members.items():
        alone = {key(c) for rid in rids for c in find_conflicts(items_by_record[rid], dataset.hospitals, always)}
        combined = find_conflicts([i for rid in rids for i in items_by_record[rid]], dataset.hospitals, always)
        for conflict in combined:
            exist[(person, key(conflict))] = {"severity": conflict.severity,
                                              "needs_linking": key(conflict) not in alone}

    # What the app actually shows, using its own links.
    shown: dict[tuple, str] = {}
    false_alarms: Counter = Counter()
    for cluster in clusters:
        items = [i for rid in cluster.record_ids for i in items_by_record[rid]]
        for conflict in find_conflicts(items, dataset.hospitals, cluster.confirmed):
            person_a, person_b = (person_of[item_by_id[i].record_id] for i in conflict.item_ids)
            if person_a != person_b:  # two different people's facts on one chart
                false_alarms["review" if conflict.unconfirmed else "confirmed"] += 1
            elif not conflict.unconfirmed:
                shown[(person_a, key(conflict))] = "confirmed"
            else:
                shown.setdefault((person_a, key(conflict)), "review")

    cross = {s: Counter() for s in SEVERITIES}
    for k, found in exist.items():
        if found["needs_linking"]:
            cross[found["severity"]][shown.get(k, "missed")] += 1

    # The combinations app.synthea_import hid on purpose: were they shown, and if not, why not?
    planted: Counter = Counter()
    planted_missed = []
    for hidden in truth.get("planted_conflicts", []):
        a, b = (item_by_id[i] for i in hidden["items"])
        sides = frozenset(item.drug or item.text.lower() for item in (a, b))
        found = {status for (person, (_, pair)), status in shown.items()
                 if person == hidden["person"] and pair == sides}
        outcome = "confirmed" if "confirmed" in found else "review" if found else "missed"
        planted[outcome] += 1
        if outcome == "missed":
            unknown_drugs = [i.text for i in (a, b) if i.kind == "medication" and not i.drug]
            if unknown_drugs:
                why = f'the drug list does not know "{unknown_drugs[0]}"'
            elif cluster_of[a.record_id] != cluster_of[b.record_id]:
                why = "the two records were never linked"
            else:
                why = "no rule covers this pair"
            planted_missed.append({"what": hidden["what"], "why": why})

    medications = [i for i in dataset.items if i.kind == "medication"]
    unknown = Counter(_drug_name(i.text) for i in medications if not i.drug)
    return {
        "all": len(exist),
        "within_one_hospital": sum(not f["needs_linking"] for f in exist.values()),
        "cross_hospital": {s: {"total": sum(c.values()), "confirmed": c["confirmed"],
                               "review": c["review"], "missed": c["missed"]} for s, c in cross.items()},
        "false_alarms": dict(false_alarms),
        "planted": {"total": sum(planted.values()), **{k: planted[k] for k in ("confirmed", "review", "missed")}},
        "planted_missed": planted_missed,
        "medication_orders": len(medications),
        "recognized": sum(1 for i in medications if i.drug),
        "unrecognized": unknown.most_common(12),
    }


def render(results: dict) -> str:
    """The results as Markdown: readable in a terminal, and ready to paste into a README."""
    d, m, c = results["dataset"], results["matching"], results["conflicts"]
    total = m["true_links"]

    def share(n: int, of: int) -> str:
        return f"{n / of:.1%} ({n} of {of})" if of else "n/a"

    out = [
        "# Accuracy check on Synthea patients",
        "",
        f"{d['records']} records at {d['hospitals']} hospitals, for {d['people']} people: "
        f"{d['people'] - d['relatives']} Synthea patients and {d['relatives']} look-alike relatives "
        f"sharing their households. {d['people_at_several']} people have records at more than one "
        f"hospital, which makes {total} true links to find.",
        "",
        "## Matching",
        "",
        "| Method | True links found | Wrong links made |",
        "|---|---|---|",
        f"| Identical name and birth date | {share(m['exact']['found'], total)} | {m['exact']['wrong']} |",
        f"| Constellation, linked automatically | {share(m['auto']['found'], total)} | {m['auto']['wrong']} |",
        f"| Constellation, counting links sent to review | {share(m['with_review']['found'], total)} | |",
        "",
        f"- Patients put back together exactly, with nobody else's records mixed in: "
        f"{share(m['people_whole'], m['people_at_several'])}.",
        f"- Review queue: {m['review_queue']['links']} links for a clinician to decide, "
        f"{m['review_queue']['same_person']} of them really the same person.",
        "",
        "### By mistake in the record",
        "",
        "| Mistake | Links | Linked automatically | Sent to review | Missed |",
        "|---|---|---|---|---|",
    ]
    for mistake, counts in m["by_mistake"].items():
        n = sum(counts.values())
        out.append(f"| {mistake.replace('_', ' ')} | {n} | {counts.get('auto', 0)} | "
                   f"{counts.get('review', 0)} | {counts.get('missed', 0)} |")
    if m["by_relative"]:
        out += ["", "### Look-alike relatives (different people who must stay apart)", "",
                "| Relative | Record pairs | Kept apart | Sent to review | Wrongly merged |", "|---|---|---|---|---|"]
        for kind, counts in m["by_relative"].items():
            out.append(f"| {kind} | {sum(counts.values())} | {counts.get('apart', 0)} | "
                       f"{counts.get('review', 0)} | {counts.get('merged', 0)} |")
    for title, examples in (("Wrong links", m["wrong_examples"]), ("Missed links", m["missed_examples"])):
        if examples:
            out += ["", f"### {title}: examples", ""]
            for e in examples:
                why = "; ".join(e["reasons"]) or "no differences noted"
                out.append(f"- {e['records'][0]} / {e['records'][1]}: scored {e['score']:.0%}. {why}.")

    out += [
        "",
        "## Conflict detection",
        "",
        f"With perfect matching, the rules find {c['all']} conflicts. {c['within_one_hospital']} sit inside "
        "one hospital's record. The rest are only visible once records from different hospitals are linked:",
        "",
        "| Severity | Cross-hospital conflicts | Shown | Shown as unconfirmed | Missed |",
        "|---|---|---|---|---|",
    ]
    for severity in SEVERITIES:
        row = c["cross_hospital"][severity]
        out.append(f"| {severity} | {row['total']} | {row['confirmed']} | {row['review']} | {row['missed']} |")
    alarms = c["false_alarms"]
    hidden = c["planted"]
    if hidden["total"]:
        out += ["", "### Dangerous combinations hidden on purpose", "",
                f"We hid {hidden['total']} high-severity combinations, half on a patient's record at one hospital "
                f"and half at another. Constellation showed {hidden['confirmed']}, showed {hidden['review']} "
                f"as unconfirmed, and missed {hidden['missed']}."]
        misses = Counter((miss["what"], miss["why"]) for miss in c["planted_missed"])
        out += [f"- Missed {n}: {what}, because {why}." for (what, why), n in misses.items()]
    out += [
        "",
        "### Other checks",
        "",
        f"- False alarms from mixing two people's records: {alarms.get('confirmed', 0)} shown as confirmed, "
        f"{alarms.get('review', 0)} shown as unconfirmed.",
        f"- Medication orders the drug list recognizes: {share(c['recognized'], c['medication_orders'])}.",
    ]
    if c["unrecognized"]:
        out.append("- Most common drugs it does not know: "
                   + ", ".join(f"{name} ({n})" for name, n in c["unrecognized"]) + ".")
    return "\n".join(out) + "\n"


def _pairs(groups) -> set[tuple[str, str]]:
    return {pair for ids in groups for pair in combinations(sorted(ids), 2)}


def _same(truth: dict, a: str, b: str) -> bool:
    return truth["records"][a]["person"] == truth["records"][b]["person"]


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _label(dataset: Dataset, record_id: str) -> str:
    r = dataset.records[record_id]
    return f"{r.display_name}, born {r.birth_date} ({dataset.hospitals[r.hospital_id].name})"


def _drug_name(text: str) -> str:
    """"24 HR metoprolol succinate 100 MG Extended Release Oral Tablet" -> "metoprolol succinate"."""
    name = re.sub(r"^\{\s*\d+ \(", "", text)  # a pack: "{28 (norethindrone 0.35 MG ..."
    name = re.sub(r"^(NDA\d+ )?(\d+(\.\d+)? (HR|ACTUAT|ML) )*", "", name)
    return " ".join(re.split(r" \d", name, maxsplit=1)[0].lower().split()) or text.lower()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dataset", type=Path, nargs="?", default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, help="also write the results to this Markdown file")
    args = parser.parse_args()
    report = render(evaluate(args.dataset))
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # names may have accents
    print(report)
