import { medicationsFromGraph } from "./medications";
import { statsFromPatients } from "./stats";

async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json();
}

const postJson = (path, body) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// For endpoints the backend may not have yet (see TASKS.md): until the route exists, FastAPI
// answers 404 "Not Found", so we build the same response in the browser instead.
// Returns { data, preview }.
async function fetchOrPreview(path, buildPreview) {
  const res = await fetch(path);
  if (res.ok) return { data: await res.json(), preview: false };
  const body = await res.json().catch(() => ({}));
  if (res.status === 404 && body.detail === "Not Found") return { data: buildPreview(), preview: true };
  throw new Error(`${res.status} ${res.statusText} for ${path}`);
}

export const fetchHospitals = () => request("/api/hospitals");
export const fetchPatients = () => request("/api/patients");
export const fetchConstellation = (id) => request(`/api/patients/${encodeURIComponent(id)}/constellation`);

export async function fetchMedications(id, graph) {
  const { data, preview } = await fetchOrPreview(`/api/patients/${encodeURIComponent(id)}/medications`, () =>
    medicationsFromGraph(graph),
  );
  return { list: data, preview };
}

export const fetchStats = (patients, hospitals) =>
  fetchOrPreview("/api/stats", () => statsFromPatients(patients, hospitals));

export const fetchPatientAudit = (id) => request(`/api/patients/${encodeURIComponent(id)}/audit`);

export const resetDemo = (reviewer) => postJson("/api/demo/reset", { reviewer });
export const reviewMatch = (recordA, recordB, samePerson, reviewer) =>
  postJson("/api/matches/review", { record_a: recordA, record_b: recordB, same_person: samePerson, reviewer });
