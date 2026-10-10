/** Header totals: the whole network at a glance. */
export default function StatsBar({ stats }) {
  if (!stats) return <div className="stats" />;

  const { data, preview } = stats;
  const { high, moderate, low } = data.conflicts;
  const acrossHospitals = data.cross_hospital_conflicts != null;

  return (
    <div className="stats">
      <Stat value={data.patients} label="patients" />
      <Stat value={data.records} label={`records from ${data.hospitals} hospitals`} />
      <Stat
        value={acrossHospitals ? data.cross_hospital_conflicts : high + moderate + low}
        label={acrossHospitals ? "conflicts caught across hospitals" : "conflicts caught"}
        tone="conflict"
        extra={high > 0 ? `${high} high` : null}
      />
      {data.needs_review > 0 && (
        <Stat
          value={data.needs_review}
          label={data.needs_review === 1 ? "match to review" : "matches to review"}
          tone="review"
        />
      )}
      {preview && (
        <span className="stats-preview" title="Computed in the browser until the backend's /api/stats endpoint is ready">
          preview
        </span>
      )}
    </div>
  );
}

function Stat({ value, label, tone, extra }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {extra && <span className="badge high">{extra}</span>}
    </div>
  );
}
