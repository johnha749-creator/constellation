// Builds the same response as GET /api/stats (see TASKS.md) from the patient list, so the
// header works before that backend endpoint exists. Only the backend can tell which conflicts
// span hospitals, so that number is null here.
export function statsFromPatients(patients, hospitals) {
  const sum = (pick) => patients.reduce((total, p) => total + pick(p), 0);
  return {
    hospitals: hospitals.length,
    records: sum((p) => p.record_count),
    patients: patients.length,
    needs_review: sum((p) => (p.needs_review ? 1 : 0)),
    conflicts: {
      high: sum((p) => p.conflicts.high),
      moderate: sum((p) => p.conflicts.moderate),
      low: sum((p) => p.conflicts.low),
    },
    cross_hospital_conflicts: null,
  };
}
