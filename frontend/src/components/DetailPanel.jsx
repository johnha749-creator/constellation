import { useEffect, useRef, useState } from "react";
import { STATIC_DEMO } from "../api";
import { CONFLICT_TYPE_LABELS, REVEAL_CONTACTS, REVIEW_MATCHES } from "../labels";
import MedicationList from "./MedicationList";
import PatientSummary from "./PatientSummary";
import ReviewHistory from "./ReviewHistory";
import { formatPoints, HowScoringWorks, ScoreBreakdown } from "./ScoreBreakdown";

const KIND_LABELS = { record: "Patient record", allergy: "Allergy", medication: "Medication", condition: "Condition" };

const REVEAL_REASONS = [
  "Treatment: confirming the patient's identity",
  "Treatment: contacting the patient",
  "Care coordination with another hospital",
];

/** Contact details stay hidden until the clinician says why they need them ("break the glass"). */
function ContactAccess({ visible, allowed, onReveal }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(REVEAL_REASONS[0]);
  const [other, setOther] = useState("");

  if (visible) {
    return (
      <div className="privacy-bar visible">
        Contact details are visible to you for 15 minutes. This access was logged.
      </div>
    );
  }
  const submit = (e) => {
    e.preventDefault();
    onReveal(reason === "other" ? other.trim() : reason);
  };
  return (
    <div className="privacy-bar">
      <div className="privacy-row">
        <span>Phone, address, ZIP and record numbers are hidden.</span>
        {!open && allowed && (
          <button className="btn small-btn" onClick={() => setOpen(true)}>
            Show…
          </button>
        )}
      </div>
      {open && (
        <form className="reveal-form" onSubmit={submit}>
          <label>
            Why do you need them? Your answer is logged.
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {REVEAL_REASONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
              <option value="other">Other…</option>
            </select>
          </label>
          {reason === "other" && (
            <input
              value={other}
              onChange={(e) => setOther(e.target.value)}
              placeholder="Describe the reason"
              minLength={3}
              maxLength={200}
              required
            />
          )}
          <div className="review-actions">
            <button type="submit" className="btn confirm">
              Show contact details
            </button>
            <button type="button" className="btn reject" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

const MATCH_HEADINGS = {
  same: "Confirmed same person by a clinician",
  match: "Same person",
  review: "Possible match, needs review",
};

export default function DetailPanel({
  graph,
  medications,
  audit,
  rubric,
  hospitals,
  selectedConflictId,
  selectedNodeId,
  onSelectConflict,
  onSelectNode,
  onDecideMatch,
  onRevealContacts,
  can,
  roleLabel,
}) {
  const [tab, setTab] = useState("summary");
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
  // Roles without clinical access (registration) only get the identity tab.
  const clinical = graph.clinical_visible !== false;
  const linksTab = ["links", "Record links", matches.length, patient.needs_review];
  const tabs = clinical
    ? [
        ["summary", "Summary", null],
        ["conflicts", "Conflicts", conflicts.length],
        ["medications", "Medications", medications?.list.length ?? "…"],
        linksTab,
      ]
    : [linksTab];
  const activeTab = clinical ? tab : "links";

  return (
    <aside className="panel" ref={panelRef}>
      <div className="patient-header">
        <h2>{patient.name}</h2>
        <div className="muted">
          Born {patient.birth_date} · {patient.gender} · {patient.record_count} records at{" "}
          {patient.hospitals.length} {patient.hospitals.length === 1 ? "hospital" : "hospitals"}
        </div>
      </div>

      <ContactAccess
        key={patient.id}
        visible={graph.contact_details_visible}
        allowed={can(REVEAL_CONTACTS)}
        onReveal={onRevealContacts}
      />

      {!clinical && (
        <div className="privacy-bar">
          Allergies, medications, diagnoses and conflicts are hidden for your role ({roleLabel}). You can
          still check and fix which records belong to this patient.
        </div>
      )}

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
            aria-selected={activeTab === id}
            className={`tab ${activeTab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label} {count !== null && <span className="tab-count">{count}</span>}
            {needsReview && <span className="review-dot" title="A possible match needs review" />}
          </button>
        ))}
      </div>

      {activeTab === "summary" && (
        <PatientSummary
          graph={graph}
          medications={medications}
          hospitals={hospitals}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
          onShowConflicts={() => setTab("conflicts")}
        />
      )}

      {activeTab === "conflicts" && (
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

      {activeTab === "medications" && (
        <MedicationList
          medications={medications}
          conflicts={conflicts}
          hospitals={hospitals}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
          onSelectConflict={onSelectConflict}
        />
      )}

      {activeTab === "links" && (
        <>
          {matches.length === 0 && <p className="muted">Only one record found for this patient.</p>}
          {matches.map((m) => (
            <div key={`${m.source}-${m.target}`} className={`card match-card ${m.tier}`}>
              <div className="card-kicker">
                {MATCH_HEADINGS[m.reviewed ?? m.tier]} · {formatPoints(m.points)} points (
                {Math.round(m.probability * 100)}%)
              </div>
              <div className="small">
                {hospitals[nodesById[m.source]?.hospital]?.name} ↔ {hospitals[nodesById[m.target]?.hospital]?.name}
              </div>
              <ScoreBreakdown link={m} rubric={rubric} />
              {m.tier === "review" && can(REVIEW_MATCHES) && (
                <div className="review-actions">
                  <button className="btn confirm" onClick={() => onDecideMatch(m.source, m.target, true)}>
                    Same person
                  </button>
                  <button className="btn reject" onClick={() => onDecideMatch(m.source, m.target, false)}>
                    Different people
                  </button>
                </div>
              )}
              {m.tier === "review" && !can(REVIEW_MATCHES) && (
                <p className="muted small">
                  {STATIC_DEMO
                    ? "In the hosted demo, reviews are off. Run Constellation locally to decide this match."
                    : "A physician or registration clerk needs to decide this match."}
                </p>
              )}
            </div>
          ))}
          <HowScoringWorks rubric={rubric} />
          <ReviewHistory audit={audit} />
        </>
      )}
    </aside>
  );
}
