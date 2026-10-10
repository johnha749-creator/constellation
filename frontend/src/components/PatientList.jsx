import { useMemo, useState } from "react";

export default function PatientList({ patients, hospitals, selectedId, onSelect }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter((p) => p.name.toLowerCase().includes(q) || (p.birth_date ?? "").includes(q));
  }, [patients, query]);

  return (
    <aside className="sidebar">
      <input
        className="search"
        type="search"
        placeholder="Search name or date of birth"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="count">{filtered.length} patients</div>
      <ul className="patient-list">
        {filtered.map((p) => (
          <li key={p.id}>
            <button
              className={`patient ${p.id === selectedId ? "selected" : ""}`}
              onClick={() => onSelect(p.id)}
            >
              <div className="patient-name">{p.name}</div>
              <div className="patient-meta">
                <span>{p.birth_date}</span>
                <span className="dots">
                  {p.hospitals.map((h) => (
                    <span
                      key={h}
                      className="dot"
                      title={hospitals[h]?.name}
                      style={{ background: hospitals[h]?.color }}
                    />
                  ))}
                </span>
              </div>
              <div className="badges">
                {p.conflicts.high > 0 && <span className="badge high">{p.conflicts.high} high</span>}
                {p.conflicts.moderate > 0 && <span className="badge moderate">{p.conflicts.moderate} moderate</span>}
                {p.conflicts.low > 0 && <span className="badge low">{p.conflicts.low} low</span>}
                {p.needs_review && <span className="badge review">match needs review</span>}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
