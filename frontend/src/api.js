import { medicationsFromGraph } from "./medications";
import { statsFromPatients } from "./stats";

/** The backend answered 401: nobody is signed in, or the session timed out. */
export class SignedOutError extends Error {}

// The hosted demo on GitHub Pages has no backend. Its build (VITE_STATIC=1) reads JSON exported by
// backend/app/static_export.py instead, as a read-only visitor. "Connect hospital" switches to the
// exported state with Polaris Urgent Care connected; "Reset demo" switches back.
export const STATIC_DEMO = import.meta.env.VITE_STATIC === "1";
let staticState = "base";
const STATIC_SESSION = {
  user: { username: "visitor", name: "Demo visitor", role: "Physician, read-only", role_id: "physician",
          permissions: ["view_clinical", "connect_hospitals"] },
  idle_timeout_minutes: 15,
  matching: "standard",
};

async function staticGet(path, state = staticState) {
  if (path === "/api/me") return STATIC_SESSION;
  const name = path.replace(/^\/api\//, "").split("?")[0];
  const folder = name === "rubric" ? "" : `${state}/`; // the rubric is the same in every state
  const res = await fetch(`${import.meta.env.BASE_URL}demo/${folder}${name}.json`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json();
}

async function request(path, options) {
  if (STATIC_DEMO) {
    if (options?.method === "POST") throw new Error("The hosted demo is read-only. Run it locally to do this.");
    return staticGet(path);
  }
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
  if (STATIC_DEMO) return { data: await staticGet(path), preview: false };
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

/** The backend refused an uploaded bundle; `problems` lists why, one sentence each. */
export class BundleRejectedError extends Error {
  constructor(message, problems = []) {
    super(message);
    this.problems = problems;
  }
}

/** Upload a hospital's FHIR bundle, as the file's text. The backend checks it before using any of it. */
export async function connectHospital(bundleText) {
  if (STATIC_DEMO) return connectStatic(bundleText);
  const res = await fetch("/api/hospitals", { method: "POST", headers: { "Content-Type": "application/json" }, body: bundleText });
  if (res.status === 401) throw new SignedOutError("Not signed in");
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail ?? `${res.status} ${res.statusText}`;
    throw new BundleRejectedError(detail.message ?? String(detail), detail.problems ?? []);
  }
  return body;
}

// The hosted demo can only "connect" the sample hospital: its result was computed at build time.
async function connectStatic(bundleText) {
  let bundle;
  try {
    bundle = JSON.parse(bundleText);
  } catch {
    throw new BundleRejectedError("That file isn't valid JSON.");
  }
  if (bundle?.id !== "polaris") {
    throw new BundleRejectedError("The hosted demo can only connect the sample hospital.", [
      "Run Constellation locally (see the README) to upload your own FHIR bundle.",
    ]);
  }
  if (staticState === "polaris") {
    throw new BundleRejectedError("That bundle can't be connected.", ['A hospital with the id "polaris" is already connected.']);
  }
  const report = await staticGet("/api/report", "polaris");
  staticState = "polaris";
  return report;
}

export const fetchPatientAudit = (id) => request(`/api/patients/${encodeURIComponent(id)}/audit`);

// The reviewer is whoever is signed in; the backend takes it from the session.
export async function resetDemo() {
  if (!STATIC_DEMO) return postJson("/api/demo/reset");
  staticState = "base";
  return {};
}
export const reviewMatch = (recordA, recordB, samePerson) =>
  postJson("/api/matches/review", { record_a: recordA, record_b: recordB, same_person: samePerson });
