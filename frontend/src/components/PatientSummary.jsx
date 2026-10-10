import { SEVERITY_RANK } from "../labels";
import { summaryFromGraph } from "../summary";

function Section({ title, items, empty, hospitals, conflictsById, selectedNodeId, onSelectNode }) {
  return (
    <section className="summary-section">
      <h4>
        {title} <span className="tab-count">{items.length}</span>
      </h4>
      {items.length === 0 && <p className="muted small">{empty}</p>}
      {items.map((item) => {
        const issues = (item.conflict_ids ?? []).map((id) => conflictsById[id]).filter(Boolean);
        const worst = issues.sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity])[0]?.severity;
        return (
          <div key={item.name} className="summary-item">
            <div className="summary-head">
              <span className="summary-name">{item.name}</span>
              {worst && <span className={`badge ${worst}`}>{issues.length === 1 ? "1 conflict" : `${issues.length} conflicts`}</span>}
              {item.onlyAt && <span className="tag only">only at {hospitals[item.onlyAt]?.name ?? item.onlyAt}</span>}
              {item.unconfirmed && <span className="tag review">unconfirmed match</span>}
            </div>
            {item.sources.map((s) => (
              <button
                key={s.item_id}
                className={`med-source ${s.item_id === selectedNodeId ? "selected" : ""}`}
                onClick={() => onSelectNode(s.item_id)}
              >
                <span className="dot" style={{ background: hospitals[s.hospital]?.color }} />
                {!item.onlyAt && <span className="med-hospital">{hospitals[s.hospital]?.name ?? s.hospital}</span>}
                {s.detail && <span className="med-dosage">{s.detail}</span>}
                {s.date && <span className="muted">{s.date}</span>}
              </button>
            ))}
          </div>
        );
      })}
    </section>
  );
}

/** The combined chart: everything every hospital knows about this patient, in one place. */
export default function PatientSummary({ graph, medications, hospitals, selectedNodeId, onSelectNode, onShowConflicts }) {
  const summary = summaryFromGraph(graph, medications);
  const { conflicts } = graph;
  const conflictsById = Object.fromEntries(conflicts.map((c) => [c.id, c]));
  const high = conflicts.filter((c) => c.severity === "high").length;
  const shared = { hospitals, conflictsById, selectedNodeId, onSelectNode };

  return (
    <div className="summary">
      <p className="muted small">
        Combined from {graph.patient.record_count} records at {summary.hospitalCount}{" "}
        {summary.hospitalCount === 1 ? "hospital" : "hospitals"}.
        {summary.onlyOneHospital > 0 && (
          <>
            {" "}
            <strong className="only-count">
              {summary.onlyOneHospital} {summary.onlyOneHospital === 1 ? "item is" : "items are"} known to only one
              hospital
            </strong>
            , so no single chart had the full picture.
          </>
        )}
      </p>
      {conflicts.length > 0 && (
        <button className={`summary-alert ${high ? "high" : "moderate"}`} onClick={onShowConflicts}>
          ⚠ {conflicts.length} {conflicts.length === 1 ? "conflict" : "conflicts"}
          {high > 0 && `, ${high} high risk`}. Review them in the Conflicts tab →
        </button>
      )}
      {summary.hasUnconfirmed && (
        <p className="preview-note small">
          Items tagged “unconfirmed match” come from a record that may belong to someone else. Check the Record
          links tab.
        </p>
      )}
      <Section title="Allergies" items={summary.allergies} empty="No allergies recorded at any hospital." {...shared} />
      <Section title="Conditions" items={summary.conditions} empty="No conditions recorded." {...shared} />
      <Section
        title="Medications"
        items={medications ? summary.medications : []}
        empty={medications ? "No medications on record." : "Loading medications…"}
        {...shared}
      />
    </div>
  );
}
