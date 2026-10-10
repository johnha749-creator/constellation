import { medicationsFromGraph } from "./medications";

async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json();
}

const postJson = (path, body) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const fetchHospitals = () => request("/api/hospitals");
export const fetchPatients = () => request("/api/patients");
export const fetchConstellation = (id) => request(`/api/patients/${encodeURIComponent(id)}/constellation`);
// Returns { list, preview }. Until the backend route exists, FastAPI answers 404 "Not Found",
// and the list is computed in the browser instead (preview: true).
export async function fetchMedications(id, graph) {
  const res = await fetch(`/api/patients/${encodeURIComponent(id)}/medications`);
  if (res.ok) return { list: await res.json(), preview: false };
  const body = await res.json().catch(() => ({}));
  if (res.status === 404 && body.detail === "Not Found") return { list: medicationsFromGraph(graph), preview: true };
  throw new Error(`${res.status} ${res.statusText} for medications`);
}

export const resetDemo =() => postJson("/api/reload", {});
export const reviewMatch =(recordA, recordB, samePerson) =>
  postJson("/api/matches/review", { record_a: recordA, record_b: recordB, same_person: samePerson });
