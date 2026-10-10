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
export const resetDemo = () => postJson("/api/reload", {});
export const reviewMatch =(recordA, recordB, samePerson) =>
  postJson("/api/matches/review", { record_a: recordA, record_b: recordB, same_person: samePerson });
