async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json();
}

export const fetchHospitals = () => getJson("/api/hospitals");
export const fetchPatients = () => getJson("/api/patients");
export const fetchConstellation = (id) => getJson(`/api/patients/${encodeURIComponent(id)}/constellation`);
