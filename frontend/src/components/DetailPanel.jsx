import { useEffect, useRef, useState } from "react";
import { CONFLICT_TYPE_LABELS } from "../labels";
import MedicationList from "./MedicationList";
import ReviewHistory from "./ReviewHistory";

const KIND_LABELS = { record: "Patient record", allergy: "Allergy", medication: "Medication", condition: "Condition" };

const MATCH_HEADINGS = {
  same: "Confirmed same person by a clinician",
  match: "Same person",
  review: "Possible match, needs review",
};

export default function DetailPanel({
  graph,
  medications,
  audit,
  reviewer,
  onReviewerChange,
  hospitals,
  selectedConflictId,
  selectedNodeId,
  onSelectConflict,
  onSelectNode,
  onDecideMatch,
}) {
  const [tab, setTab] = useState("conflicts");
  const panelRef = useRef(null);

  // Selecting a conflict (in the sky or from a medication) shows its card.
  useEffect(() => {
    if (selectedConflictId) setTab("conflicts");
  }, [selectedConflictId]);
  useEffect(() => {
    panelRef.current?.querySelector(".conflict-card.selected")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedConflictId, tab]);

  if (!graph) return <aside className="panel" />;

  const { patient, conflicts } = graph;
  const node = graph.nodes.find((n) => n.id === selectedNodeId);
  const nodesById = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const matches = graph.links.filter((l) => l.kind === "match");
  const tabs = [
    ["conflicts", "Conflicts", conflicts.length],
    ["medications", "Medications", medications?.list.length ?? "…"],
    ["links", "Record links", matches.length, patient.needs_review],
  ];

  return (
    <aside className="panel" ref={panelRef}>
      <div className="patient-header">
        <h2>{patient.name}</h2>
        <div className="muted">
          Born {patient.birth_date} · {patient.gender} · {patient.record_count} records at{" "}
          {patient.hospitals.length} {patient.hospitals.length === 1 ? "hospital" : "hospitals"}
        </div>
      </div>

      {node && (
        <section className="card node-card" style={{ borderColor: hospitals[node.hospital]?.color }}>
          <div className="card-kicker">{KIND_LABELS[node.kind]}</div>
          <h3>{node.label}</h3>
          <dl>
            {node.details.map(([label, value]) => (
              <div key={label} className="detail-row">
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <div className="tabs" role="tablist">
        {tabs.map(([id, label, count, needsReview]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label} <span className="tab-count">{count}</span>
            {needsReview && <span className="review-dot" title="A possible match needs review" />}
          </button>
        ))}
      </div>

      {tab === "conflicts" && (
        <>
          {conflicts.length === 0 && <p className="muted">No conflicts found across these records.</p>}
          {conflicts.map((c) => (
            <button
              key={c.id}
              className={`card conflict-card ${c.severity} ${c.id === selectedConflictId ? "selected" : ""}`}
              onClick={() => onSelectConflict(c.id === selectedConflictId ? null : c.id)}
            >
              <div className="card-kicker">
                <span className={`badge ${c.severity}`}>{c.severity}</span> {CONFLICT_TYPE_LABELS[c.type] ?? c.type}
                {c.cross_hospital && <span className="tag">across hospitals</span>}
                {c.unconfirmed && <span className="tag review">unconfirmed match</span>}
              </div>
              <div className="conflict-title">{c.title}</div>
              <p>{c.explanation}</p>
              <div className="muted small">
                {c.item_ids.map((id) => nodesById[id]?.label).join(" ↔ ")} · {c.hospitals.join(" ↔ ")}
              </div>
            </button>
          ))}
        </>
      )}

      {tab === "medications" && (
        <MedicationList
          medications={medications}
          conflicts={conflicts}
          hospitals={hospitals}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
          onSelectConflict={onSelectConflict}
        />
      )}

      {tab === "links" && (
        <>
          <label className="reviewer">
            <span className="muted small">Reviewing as</span>
            <input
              value={reviewer}
              onChange={(e) => onReviewerChange(e.target.value)}
              placeholder="Your name, e.g. Dr. Lee"
              maxLength={80}
            />
          </label>
          {matches.length === 0 && <p className="muted">Only one record found for this patient.</p>}
          {matches.map((m) => (
            <div key={`${m.source}-${m.target}`} className={`card match-card ${m.tier}`}>
              <div className="card-kicker">
                {MATCH_HEADINGS[m.reviewed ?? m.tier]} · scored {(m.probability * 100).toFixed(1)}%
              </div>
              <div className="small">
                {hospitals[nodesById[m.source]?.hospital]?.name} ↔ {hospitals[nodesById[m.target]?.hospital]?.name}
              </div>
              {m.agrees_on.length > 0 && <div className="small muted">Agrees on: {m.agrees_on.join(", ")}</div>}
              <ul className="reasons">
                {m.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              {m.tier === "review" && (
                <div className="review-actions">
                  <button className="btn confirm" onClick={() => onDecideMatch(m.source, m.target, true)}>
                    Same person
                  </button>
                  <button className="btn reject" onClick={() => onDecideMatch(m.source, m.target, false)}>
                    Different people
                  </button>
                </div>
              )}
            </div>
          ))}
          <ReviewHistory audit={audit} />
        </>
      )}
    </aside>
  );
}
