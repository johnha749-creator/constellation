/** Everything logged about this patient: who opened the record, who unmasked contact details and
 *  why, and match decisions. From the tamper-evident audit log. */
export default function ReviewHistory({ audit }) {
  if (!audit) return null;
  const { verified, first_bad_seq: firstBad, total_events: total } = audit;
  const entries = collapseViews(audit.events);

  return (
    <section className="history">
      <h4 className="history-title">Access and review history</h4>
      <p className={`integrity ${verified ? "ok" : "broken"}`}>
        {!verified
          ? `Warning: the log was altered at entry #${firstBad}. That entry and everything after it are being ignored.`
          : `Tamper-evident log: all ${total} ${total === 1 ? "entry" : "entries"} verified`}
      </p>
      {entries.length === 0 && <p className="muted small">Nothing recorded about this patient yet.</p>}
      <ol className="history-list">
        {entries.map((e) => (
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

// Every page load logs a view, so back-to-back views by the same person become one line.
function collapseViews(events) {
  const out = [];
  for (const e of events) {
    const last = out[out.length - 1];
    if (e.action === "view" && last?.action === "view" && last.username === e.username) {
      last.count += 1;
      last.firstAt = e.at; // events are newest first
    } else {
      out.push({ ...e, count: 1 });
    }
  }
  return out;
}

function describe(e) {
  if (e.action === "view") return e.count > 1 ? `Opened this patient's records (${e.count} times).` : "Opened this patient's records.";
  if (e.action === "reveal") return `Unmasked contact details. Reason: ${e.reason}`;
  if (e.action === "reset") return "Reset the demo. Match decisions above no longer apply.";
  if (e.action === "connect") return `Connected ${e.hospital}, which added a record for this patient.`;
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
