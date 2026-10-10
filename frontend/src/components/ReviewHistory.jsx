/** Every decision made about this patient's records, from the tamper-evident audit log. */
export default function ReviewHistory({ audit }) {
  if (!audit) return null;
  const { events, verified, first_bad_seq: firstBad, total_events: total } = audit;

  return (
    <section className="history">
      <h4 className="history-title">Review history</h4>
      <p className={`integrity ${verified ? "ok" : "broken"}`}>
        {!verified
          ? `Warning: the log was altered at entry #${firstBad}. That entry and everything after it are being ignored.`
          : total === 0
            ? "Tamper-evident log: no decisions recorded yet"
            : `Tamper-evident log: all ${total} ${total === 1 ? "entry" : "entries"} verified`}
      </p>
      {events.length === 0 && <p className="muted small">No decisions about this patient yet.</p>}
      <ol className="history-list">
        {events.map((e) => (
          <li key={e.seq} className={`history-item ${e.action}`}>
            <div className="history-meta">
              <span>#{e.seq}</span>
              <time dateTime={e.at}>{formatTime(e.at)}</time>
              <span className="history-reviewer">{e.reviewer}</span>
            </div>
            <div>{describe(e)}</div>
            {e.note && <div className="muted small">“{e.note}”</div>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function describe(e) {
  if (e.action === "reset") return "Reset the demo. Decisions above no longer apply.";
  const [a, b] = e.records.map((r) => r.hospital ?? r.id);
  const verdict = e.decision === "same" ? "the same person" : "different people";
  const changed = e.previous ? ` (changed from ${e.previous === "same" ? "same person" : "different people"})` : "";
  return `Marked the ${a} and ${b} records as ${verdict}, scored ${Math.round(e.score * 100)}%${changed}.`;
}

function formatTime(iso) {
  const date = new Date(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  return date.toLocaleString([], sameDay ? { hour: "numeric", minute: "2-digit" } : { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
