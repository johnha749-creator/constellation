import { CONFLICT_TYPE_LABELS, SEVERITY_RANK } from "../labels";

/** "What is this patient actually taking?" One card per drug, listing every hospital that prescribed it. */
export default function MedicationList({ medications, conflicts, hospitals, selectedNodeId, onSelectNode, onSelectConflict }) {
  if (!medications) return <p className="muted">Loading medications…</p>;

  const { list, preview } = medications;
  const conflictsById = Object.fromEntries(conflicts.map((c) => [c.id, c]));
  const hospitalCount = new Set(list.flatMap((m) => m.sources.map((s) => s.hospital))).size;
  const withIssues = list.filter((m) => m.conflict_ids.length > 0).length;
  // Most dangerous drug first; otherwise keep the API's order.
  const worstRank = (med) => Math.max(0, ...med.conflict_ids.map((id) => SEVERITY_RANK[conflictsById[id]?.severity] ?? 0));
  const sorted = [...list].sort((a, b) => worstRank(b) - worstRank(a));

  return (
    <>
      <p className="muted small">
        {list.length} {list.length === 1 ? "medication" : "medications"} from {hospitalCount}{" "}
        {hospitalCount === 1 ? "hospital" : "hospitals"} · {withIssues} with issues
      </p>
      {preview && (
        <p className="preview-note small">
          Preview: built in the browser until the backend's <code>/medications</code> endpoint is ready.
        </p>
      )}
      {list.length === 0 && <p className="muted">No medications on record.</p>}
      {sorted.map((med) => {
        const issues = med.conflict_ids
          .map((id) => conflictsById[id])
          .filter(Boolean)
          .sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]);
        const worst = issues[0]?.severity ?? "ok";
        return (
          <div key={med.name} className={`card med-card ${worst}`}>
            <div className="med-head">
              <span className="med-name">{med.name}</span>
              {issues.length === 0 && <span className="badge ok">no issues</span>}
            </div>
            <ul className="med-sources">
              {med.sources.map((s) => (
                <li key={s.item_id}>
                  <button
                    className={`med-source ${s.item_id === selectedNodeId ? "selected" : ""}`}
                    onClick={() => onSelectNode(s.item_id)}
                  >
                    <span className="dot" style={{ background: hospitals[s.hospital]?.color }} />
                    <span className="med-hospital">{hospitals[s.hospital]?.name ?? s.hospital}</span>
                    <span className="med-dosage">{s.dosage}</span>
                    {s.date && <span className="muted">{s.date}</span>}
                  </button>
                </li>
              ))}
            </ul>
            {issues.length > 0 && (
              <div className="med-issues">
                {issues.map((c) => (
                  <button key={c.id} className={`issue ${c.severity}`} onClick={() => onSelectConflict(c.id)}>
                    <span className={`badge ${c.severity}`}>{c.severity}</span>
                    {CONFLICT_TYPE_LABELS[c.type] ?? c.type}: {c.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
