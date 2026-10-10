// Compiles one chart from every hospital's records: allergies and conditions grouped by name, each
// listing the hospitals that recorded it. Items only one hospital knows about are the ones a
// clinician at any other hospital would never have seen.

/** Records that are only linked to the rest by a match still waiting for review. */
export function unconfirmedRecords(graph) {
  const records = graph.nodes.filter((n) => n.kind === "record").map((n) => n.id);
  const parent = Object.fromEntries(records.map((id) => [id, id]));
  const find = (id) => (parent[id] === id ? id : (parent[id] = find(parent[id])));
  for (const link of graph.links) {
    if (link.kind === "match" && link.tier === "match") parent[find(link.source)] = find(link.target);
  }
  const sizes = {};
  for (const id of records) sizes[find(id)] = (sizes[find(id)] ?? 0) + 1;
  // The biggest confirmed group is "the patient"; on a tie, the group of the first record.
  const main = records.map(find).reduce((best, root) => (sizes[root] > sizes[best] ? root : best), find(records[0]));
  return new Set(records.filter((id) => find(id) !== main));
}

function group(nodes, kind, unconfirmed, hospitalCount) {
  const byName = new Map();
  for (const node of nodes) {
    if (node.kind !== kind) continue;
    const key = node.label.toLowerCase();
    if (!byName.has(key)) byName.set(key, { name: node.label, sources: [] });
    const details = Object.fromEntries(node.details);
    byName.get(key).sources.push({
      hospital: node.hospital,
      detail: details.Details ?? "",
      date: details.Date ?? null,
      item_id: node.id,
    });
  }
  return [...byName.values()]
    .map((entry) => {
      const hospitals = new Set(entry.sources.map((s) => s.hospital));
      return {
        ...entry,
        onlyAt: hospitalCount > 1 && hospitals.size === 1 ? entry.sources[0].hospital : null,
        unconfirmed: entry.sources.every((s) => unconfirmed.has(nodeRecord(nodes, s.item_id))),
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

function nodeRecord(nodes, itemId) {
  return nodes.find((n) => n.id === itemId)?.record;
}

/** The combined chart for one patient's constellation graph. */
export function summaryFromGraph(graph, medications) {
  const unconfirmed = unconfirmedRecords(graph);
  const hospitalCount = graph.patient.hospitals.length;
  const allergies = group(graph.nodes, "allergy", unconfirmed, hospitalCount);
  const conditions = group(graph.nodes, "condition", unconfirmed, hospitalCount);
  const meds = (medications?.list ?? []).map((med) => {
    const hospitals = new Set(med.sources.map((s) => s.hospital));
    return {
      name: med.name,
      sources: med.sources.map((s) => ({ ...s, detail: s.dosage })),
      conflict_ids: med.conflict_ids,
      onlyAt: hospitalCount > 1 && hospitals.size === 1 ? med.sources[0].hospital : null,
      unconfirmed: med.sources.every((s) => unconfirmed.has(nodeRecord(graph.nodes, s.item_id))),
    };
  });
  const all = [...allergies, ...conditions, ...meds];
  return {
    allergies,
    conditions,
    medications: meds,
    hospitalCount,
    onlyOneHospital: all.filter((i) => i.onlyAt).length,
    hasUnconfirmed: unconfirmed.size > 0,
  };
}
