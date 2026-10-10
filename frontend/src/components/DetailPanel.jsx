const TYPE_LABELS = {
  allergy: "Allergy",
  duplicate_therapy: "Duplicate therapy",
  interaction: "Drug interaction",
  condition: "Drug vs condition",
  dose_mismatch: "Dose mismatch",
};

export default function DetailPanel({ graph, hospitals, selectedConflictId, selectedNodeId, onSelectConflict }) {
  if (!graph) return <aside className="panel" />;

  const { patient, conflicts } = graph;
  const node = graph.nodes.find((n) => n.id === selectedNodeId);
  const nodesById = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const matches = graph.links.filter((l) => l.kind === "match");

  return (
    <aside className="panel">
      <div className="patient-header">
        <h2>{patient.name}</h2>
        <div className="muted">
          Born {patient.birth_date} · {patient.gender} · {patient.record_count} records at{" "}
          {patient.hospitals.length} {patient.hospitals.length === 1 ? "hospital" : "hospitals"}
        </div>
      </div>

      {node && (
        <section className="card node-card" style={{ borderColor: hospitals[node.hospital]?.color }}>
          <div className="card-kicker">{node.kind === "record" ? "Patient record" : node.kind}</div>
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

      <h3 className="section-title">
        Conflicts <span className="muted">({conflicts.length})</span>
      </h3>
      {conflicts.length === 0 && <p className="muted">No conflicts found across these records.</p>}
      {conflicts.map((c) => (
        <button
          key={c.id}
          className={`card conflict-card ${c.severity} ${c.id === selectedConflictId ? "selected" : ""}`}
          onClick={() => onSelectConflict(c.id === selectedConflictId ? null : c.id)}
        >
          <div className="card-kicker">
            <span className={`badge ${c.severity}`}>{c.severity}</span> {TYPE_LABELS[c.type] ?? c.type}
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

      <h3 className="section-title">
        Record links <span className="muted">({matches.length})</span>
      </h3>
      {matches.length === 0 && <p className="muted">Only one record found for this patient.</p>}
      {matches.map((m) => (
        <div key={`${m.source}-${m.target}`} className={`card match-card ${m.tier}`}>
          <div className="card-kicker">
            {m.tier === "match" ? "Same person" : "Possible match, needs review"} ·{" "}
            {(m.probability * 100).toFixed(1)}%
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
        </div>
      ))}
    </aside>
  );
}
