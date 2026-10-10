import { medicationsFromGraph } from "./medications";
import { statsFromPatients } from "./stats";

/** The backend answered 401: nobody is signed in, or the session timed out. */
export class SignedOutError extends Error {}

async function request(path, options) {
  const res = await fetch(path, options);
  if (res.status === 401) throw new SignedOutError("Not signed in");
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json();
}

const postJson = (path, body) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });

// For endpoints the backend may not have yet (see TASKS.md): until the route exists, FastAPI
// answers 404 "Not Found", so we build the same response in the browser instead.
// Returns { data, preview }.
async function fetchOrPreview(path, buildPreview) {
  const res = await fetch(path);
  if (res.ok) return { data: await res.json(), preview: false };
  if (res.status === 401) throw new SignedOutError("Not signed in");
  const body = await res.json().catch(() => ({}));
  if (res.status === 404 && body.detail === "Not Found") return { data: buildPreview(), preview: true };
  throw new Error(`${res.status} ${res.statusText} for ${path}`);
}

export async function login(username, password) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (res.status === 401) throw new Error("Wrong username or password.");
  if (!res.ok) throw new Error(`Could not sign in (${res.status} ${res.statusText}). Is the backend running?`);
  return res.json();
}

export const logout = () => postJson("/api/logout");
export const fetchMe = () => request("/api/me");

export const fetchHospitals = () => request("/api/hospitals");
export const fetchRubric = () => request("/api/rubric");
export const fetchPatients = () => request("/api/patients");
export const fetchConstellation = (id) => request(`/api/patients/${encodeURIComponent(id)}/constellation`);
export const revealContactDetails = (id, reason) =>
  postJson(`/api/patients/${encodeURIComponent(id)}/reveal`, { reason });

export async function fetchMedications(id, graph) {
  const { data, preview } = await fetchOrPreview(`/api/patients/${encodeURIComponent(id)}/medications`, () =>
    medicationsFromGraph(graph),
  );
  return { list: data, preview };
}

export const fetchStats = (patients, hospitals) =>
  fetchOrPreview("/api/stats", () => statsFromPatients(patients, hospitals));

export const fetchPatientAudit = (id) => request(`/api/patients/${encodeURIComponent(id)}/audit`);

// The reviewer is whoever is signed in; the backend takes it from the session.
export const resetDemo = () => postJson("/api/demo/reset");
export const reviewMatch = (recordA, recordB, samePerson) =>
  postJson("/api/matches/review", { record_a: recordA, record_b: recordB, same_person: samePerson });
