import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  fetchConstellation,
  fetchHospitals,
  fetchMedications,
  fetchPatientAudit,
  fetchPatients,
  fetchStats,
  resetDemo,
  reviewMatch,
} from "./api";
import PatientList from "./components/PatientList";
import Constellation from "./components/Constellation";
import DetailPanel from "./components/DetailPanel";
// three.js is large, so the 3D view is only downloaded when someone opens it.
const Galaxy3D = lazy(() => import("./components/Galaxy3D"));
import StatsBar from "./components/StatsBar";

const HOSPITAL_PALETTE = ["#7cc6fe", "#f4a7ff", "#9ef0c4", "#ffd29d", "#a5b4fc"];
const REVIEWER_KEY = "constellation.reviewer";

// Remembering the reviewer's name is a convenience only; storage can be blocked or empty.
function loadReviewer() {
  try {
    return localStorage.getItem(REVIEWER_KEY) || "";
  } catch {
    return "";
  }
}

function saveReviewer(name) {
  try {
    localStorage.setItem(REVIEWER_KEY, name);
  } catch {
    // not saved; the name still works for this visit
  }
}

export default function App() {
  const [hospitals, setHospitals] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [graph, setGraph] = useState(null);
  const [medications, setMedications] = useState(null); // { list, preview }
  const [stats, setStats] = useState(null); // { data, preview }
  const [audit, setAudit] = useState(null); // this patient's review history
  const [reviewer, setReviewer] = useState(loadReviewer);
  const [view, setView] = useState("patient"); // "patient" (2D constellation) | "galaxy" (all patients, 3D)
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

  useEffect(() => {
    setAudit(null);
    if (!graph) return;
    let cancelled = false;
    fetchPatientAudit(graph.patient.id)
      .then((a) => !cancelled && setAudit(a))
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [graph]);

  const changeReviewer = (name) => {
    setReviewer(name);
    saveReviewer(name);
  };
  const reviewerName = reviewer.trim() || "Unnamed reviewer";

  // Re-count whenever the patient list changes (after a review or a reset).
  useEffect(() => {
    if (!hospitals.length) return;
    let cancelled = false;
    fetchStats(patients, hospitals)
      .then((s) => !cancelled && setStats(s))
      .catch((e) => setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [patients, hospitals]);

  // A clinician decides whether two records are the same person; the constellation re-forms.
  const decideMatch = async (recordA, recordB, samePerson) => {
    try {
      const { patient_id } = await reviewMatch(recordA, recordB, samePerson, reviewerName);
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
      await resetDemo(reviewerName);
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

  // Clicking a star in the 3D view zooms into that patient's constellation.
  const openPatient = (id) => {
    setSelectedId(id);
    setView("patient");
  };

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
        <div className="brand-block">
          <div className="brand">
            <span className="brand-mark">✦</span> Constellation
          </div>
          <div className="tagline">Connecting a patient's scattered records, and the conflicts between them</div>
        </div>
        <StatsBar stats={stats} />
        <div className="topbar-side">
          <div className="disclaimer">Synthetic data only. Not for clinical use.</div>
          <button className="reset" onClick={reset}>
            Reset demo
          </button>
        </div>
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
          {view === "galaxy" ? (
            <Suspense fallback={<div className="loading">Lighting up the galaxy…</div>}>
              <Galaxy3D patients={patients} hospitals={hospitalInfo} selectedId={selectedId} onSelect={openPatient} />
            </Suspense>
          ) : graph ? (
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
          <div className="view-toggle" role="tablist" aria-label="View">
            <button role="tab" aria-selected={view === "patient"} className={view === "patient" ? "active" : ""} onClick={() => setView("patient")}>
              Patient constellation
            </button>
            <button role="tab" aria-selected={view === "galaxy"} className={view === "galaxy" ? "active" : ""} onClick={() => setView("galaxy")}>
              All patients · 3D
            </button>
          </div>
        </section>
        <DetailPanel
          graph={graph}
          medications={medications}
          audit={audit}
          reviewer={reviewer}
          onReviewerChange={changeReviewer}
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
