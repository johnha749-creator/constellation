// Builds the same response as GET /api/patients/{id}/medications (see TASKS.md) from the
// constellation graph, so the Medications tab works before that backend endpoint exists.
export function medicationsFromGraph(graph) {
  const byName = new Map();
  for (const node of graph.nodes) {
    if (node.kind !== "medication") continue;
    const key = node.label.toLowerCase();
    if (!byName.has(key)) byName.set(key, { name: node.label, drug: null, sources: [], conflict_ids: [] });
    const details = Object.fromEntries(node.details);
    byName.get(key).sources.push({
      hospital: node.hospital,
      dosage: details.Details ?? "",
      date: details.Date ?? null,
      item_id: node.id,
    });
  }
  for (const med of byName.values()) {
    const itemIds = new Set(med.sources.map((s) => s.item_id));
    med.conflict_ids = graph.conflicts.filter((c) => c.item_ids.some((id) => itemIds.has(id))).map((c) => c.id);
  }
  return [...byName.values()].sort(
    (a, b) => (b.conflict_ids.length > 0) - (a.conflict_ids.length > 0) || a.name.localeCompare(b.name),
  );
}
