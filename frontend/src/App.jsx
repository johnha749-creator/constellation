import { useEffect, useMemo, useState } from "react";
import { fetchConstellation, fetchHospitals, fetchPatients } from "./api";
import PatientList from "./components/PatientList";
import Constellation from "./components/Constellation";
import DetailPanel from "./components/DetailPanel";

const HOSPITAL_PALETTE = ["#7cc6fe", "#f4a7ff", "#9ef0c4", "#ffd29d", "#a5b4fc"];

export default function App() {
  const [hospitals, setHospitals] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [graph, setGraph] = useState(null);
  const [selectedConflictId, setSelectedConflictId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([fetchHospitals(), fetchPatients()])
      .then(([hospitalList, patientList]) => {
        setHospitals(hospitalList);
        setPatients(patientList);
        if (patientList.length) setSelectedId(patientList[0].id); // most urgent patient first
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setGraph(null);
    setSelectedConflictId(null);
    setSelectedNodeId(null);
    fetchConstellation(selectedId)
      .then((g) => !cancelled && setGraph(g))
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const hospitalInfo = useMemo(
    () =>
      Object.fromEntries(
        hospitals.map((h, i) => [h.id, { ...h, color: HOSPITAL_PALETTE[i % HOSPITAL_PALETTE.length] }]),
      ),
    [hospitals],
  );

  const selectConflict = (id) => {
    setSelectedConflictId(id);
    setSelectedNodeId(null);
  };
  const selectNode = (id) => {
    setSelectedNodeId(id);
    setSelectedConflictId(null);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">✦</span> Constellation
        </div>
        <div className="tagline">Connecting the scattered records of one patient, and the conflicts between them</div>
        <div className="disclaimer">Synthetic data only. Not for clinical use.</div>
      </header>

      {error && (
        <div className="error">
          Could not reach the API ({error}). Is the backend running on port 8000?
        </div>
      )}

      <main className="layout">
        <PatientList
          patients={patients}
          hospitals={hospitalInfo}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <section className="sky">
          {graph ? (
            <Constellation
              graph={graph}
              hospitals={hospitalInfo}
              selectedConflictId={selectedConflictId}
              selectedNodeId={selectedNodeId}
              onSelectConflict={selectConflict}
              onSelectNode={selectNode}
            />
          ) : (
            <div className="loading">Charting the sky…</div>
          )}
        </section>
        <DetailPanel
          graph={graph}
          hospitals={hospitalInfo}
          selectedConflictId={selectedConflictId}
          selectedNodeId={selectedNodeId}
          onSelectConflict={selectConflict}
        />
      </main>
    </div>
  );
}
