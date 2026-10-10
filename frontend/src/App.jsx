import { useEffect, useMemo, useState } from "react";
import { fetchConstellation, fetchHospitals, fetchMedications, fetchPatients, resetDemo, reviewMatch } from "./api";
import PatientList from "./components/PatientList";
import Constellation from "./components/Constellation";
import DetailPanel from "./components/DetailPanel";

const HOSPITAL_PALETTE = ["#7cc6fe", "#f4a7ff", "#9ef0c4", "#ffd29d", "#a5b4fc"];

export default function App() {
  const [hospitals, setHospitals] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [graph, setGraph] = useState(null);
  const [medications, setMedications] = useState(null); // { list, preview }
  const [selectedConflictId, setSelectedConflictId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0); // bumped when a review changes the data

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
  }, [selectedId, version]);

  useEffect(() => {
    setMedications(null);
    if (!graph) return;
    let cancelled = false;
    fetchMedications(graph.patient.id, graph)
      .then((m) => !cancelled && setMedications(m))
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [graph]);

  // A clinician decides whether two records are the same person; the constellation re-forms.
  const decideMatch = async (recordA, recordB, samePerson) => {
    try {
      const { patient_id } = await reviewMatch(recordA, recordB, samePerson);
      setPatients(await fetchPatients());
      setSelectedId(patient_id);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e.message);
    }
  };

  // Undo every match review so the demo can be run again from the start.
  const reset = async () => {
    try {
      await resetDemo();
      const list = await fetchPatients();
      setPatients(list);
      if (!list.some((p) => p.id === selectedId)) setSelectedId(list[0]?.id ?? null);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e.message);
    }
  };

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
        <button className="reset" onClick={reset} title="Undo match reviews and start the demo over">
          Reset demo
        </button>
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
          medications={medications}
          hospitals={hospitalInfo}
          selectedConflictId={selectedConflictId}
          selectedNodeId={selectedNodeId}
          onSelectConflict={selectConflict}
          onSelectNode={selectNode}
          onDecideMatch={decideMatch}
        />
      </main>
    </div>
  );
}
