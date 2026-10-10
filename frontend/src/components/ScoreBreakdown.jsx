/** Points with a sign and a real minus: +5.6, −4.3, 0.0. */
export function formatPoints(points) {
  if (points > 0) return `+${points.toFixed(1)}`;
  if (points < 0) return `−${Math.abs(points).toFixed(1)}`;
  return "0.0";
}

function band(points, rubric) {
  if (points >= rubric.link_at) return "Same person";
  if (points >= rubric.review_at) return "A clinician decides";
  return "Different people";
}

/** How one pair of records was scored: the starting points, each field's level, and the total. */
export function ScoreBreakdown({ link, rubric }) {
  if (!rubric) return null;
  return (
    <table className="rubric-table">
      <tbody>
        <tr className="start">
          <td>Start</td>
          <td className="muted">Most record pairs are different people</td>
          <td className="pts">{formatPoints(rubric.start)}</td>
        </tr>
        {link.breakdown.map((row) => (
          <tr key={row.field}>
            <td>{row.field}</td>
            <td>
              {row.level}
              {row.values && <span className="muted"> · {row.values}</span>}
            </td>
            <td className={`pts ${row.points > 0 ? "plus" : row.points < 0 ? "minus" : ""}`}>{formatPoints(row.points)}</td>
          </tr>
        ))}
        <tr className="total">
          <td>Total</td>
          <td>{band(link.points, rubric)}</td>
          <td className="pts">{formatPoints(link.points)}</td>
        </tr>
      </tbody>
    </table>
  );
}

/** The whole rubric: every field's levels and points, the same for every pair of records. */
export function HowScoringWorks({ rubric }) {
  if (!rubric) return null;
  return (
    <details className="how-scoring">
      <summary>How scoring works</summary>
      <p className="small muted">
        Every pair of records starts at {formatPoints(rubric.start)}. Each field adds the points for the one level it
        lands on. A total of {formatPoints(rubric.link_at)} or more links the records as the same person,{" "}
        {formatPoints(rubric.review_at)} to {formatPoints(rubric.link_at)} goes to a clinician, and below{" "}
        {formatPoints(rubric.review_at)} keeps them apart. Encrypted matching uses exactly the same table.
      </p>
      {rubric.fields.map((field) => (
        <table key={field.field} className="rubric-table compact">
          <thead>
            <tr>
              <th colSpan={2}>{field.field}</th>
            </tr>
          </thead>
          <tbody>
            {field.levels.map((level) => (
              <tr key={level.level}>
                <td>{level.level}</td>
                <td className={`pts ${level.points > 0 ? "plus" : level.points < 0 ? "minus" : ""}`}>
                  {formatPoints(level.points)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </details>
  );
}
