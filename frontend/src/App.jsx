import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  fetchConstellation,
  fetchHospitals,
  fetchMe,
  fetchMedications,
  fetchPatientAudit,
  fetchPatients,
  fetchStats,
  logout,
  resetDemo,
  revealContactDetails,
  reviewMatch,
  SignedOutError,
} from "./api";
import PatientList from "./components/PatientList";
import Constellation from "./components/Constellation";
import DetailPanel from "./components/DetailPanel";
import Login from "./components/Login";
import StatsBar from "./components/StatsBar";
import { REVIEW_MATCHES, VIEW_CLINICAL, withHospitalColors } from "./labels";
// three.js is large, so the 3D view is only downloaded when someone opens it.
const Galaxy3D = lazy(() => import("./components/Galaxy3D"));

const TIMED_OUT = "You were signed out after 15 minutes without activity. Sign in again to continue.";

/** Nothing is shown until a clinician signs in. Signing out unmounts the workspace, which
 *  clears every patient's data (including revealed contact details) from the page. */
export default function App() {
  const [session, setSession] = useState({ status: "checking" });

  useEffect(() => {
    fetchMe()
      .then((info) => setSession({ status: "signed-in", ...info }))
      .catch((e) =>
        setSession({ status: "signed-out", message: e instanceof SignedOutError ? null : `Could not reach the API (${e.message}).` }),
      );
  }, []);

  if (session.status === "checking") return <div className="loading">Checking your session…</div>;
  if (session.status === "signed-out") {
    return <Login message={session.message} onSignedIn={(info) => setSession({ status: "signed-in", ...info })} />;
  }
  return (
    <Workspace
      user={session.user}
      matching={session.matching}
      onSignedOut={(message) => setSession({ status: "signed-out", message })}
    />
  );
}

function Workspace({ user, matching, onSignedOut }) {
  // What this user's role allows. The backend enforces the same rules; this only hides controls.
  const can = (permission) => user.permissions?.includes(permission) ?? false;
  const [hospitals, setHospitals] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [graph, setGraph] = useState(null);
  const [medications, setMedications] = useState(null); // { list, preview }
  const [stats, setStats] = useState(null); // { data, preview }
  const [audit, setAudit] = useState(null); // this patient's access and review history
  const [view, setView] = useState("patient"); // "patient" (2D constellation) | "galaxy" (all patients, 3D)
  const [selectedConflictId, setSelectedConflictId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0); // bumped when a review or reveal changes what we see

  // A 401 anywhere means the session ended (usually the 15-minute idle timeout).
  const fail = (e) => (e instanceof SignedOutError ? onSignedOut(TIMED_OUT) : setError(e.message));

  useEffect(() => {
    Promise.all([fetchHospitals(), fetchPatients()])
      .then(([hospitalList, patientList]) => {
        setHospitals(hospitalList);
        setPatients(patientList);
        if (patientList.length) setSelectedId(patientList[0].id); // most urgent patient first
      })
      .catch(fail);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setGraph(null);
    setSelectedConflictId(null);
    setSelectedNodeId(null);
    fetchConstellation(selectedId)
      .then((g) => !cancelled && setGraph(g))
      .catch(fail);
    return () => {
      cancelled = true;
    };
  }, [selectedId, version]);

  useEffect(() => {
    setMedications(null);
    if (!graph || !can(VIEW_CLINICAL)) return;
    let cancelled = false;
    fetchMedications(graph.patient.id, graph)
      .then((m) => !cancelled && setMedications(m))
      .catch(fail);
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
      .catch(fail);
    return () => {
      cancelled = true;
    };
  }, [graph]);

  // Re-count whenever the patient list changes (after a review or a reset).
  useEffect(() => {
    if (!hospitals.length) return;
    let cancelled = false;
    fetchStats(patients, hospitals)
      .then((s) => !cancelled && setStats(s))
      .catch(fail);
    return () => {
      cancelled = true;
    };
  }, [patients, hospitals]);

  // A clinician decides whether two records are the same person; the constellation re-forms.
  const decideMatch = async (recordA, recordB, samePerson) => {
    try {
      const { patient_id } = await reviewMatch(recordA, recordB, samePerson);
      setPatients(await fetchPatients());
      setSelectedId(patient_id);
      setVersion((v) => v + 1);
    } catch (e) {
      fail(e);
    }
  };

  // "Break the glass": show this patient's contact details, after giving a reason that's logged.
  const revealContacts = async (reason) => {
    try {
      await revealContactDetails(selectedId, reason);
      setVersion((v) => v + 1);
    } catch (e) {
      fail(e);
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
      fail(e);
    }
  };

  const signOut = async () => {
    await logout().catch(() => {}); // signed out either way
    onSignedOut(null);
  };

  const hospitalInfo = useMemo(() => withHospitalColors(hospitals), [hospitals]);

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
          <div className="session">
            {matching === "private" && (
              <span className="badge private" title="Patients are linked on encrypted fingerprints, never names or birth dates">
                🔒 encrypted matching
              </span>
            )}
            <span className="session-user" title={`Signed in as ${user.username}`}>
              {user.name} · {user.role}
            </span>
            {can(REVIEW_MATCHES) && (
              <button className="reset" onClick={reset}>
                Reset demo
              </button>
            )}
            <button className="reset" onClick={signOut}>
              Sign out
            </button>
          </div>
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
          hospitals={hospitalInfo}
          selectedConflictId={selectedConflictId}
          selectedNodeId={selectedNodeId}
          onSelectConflict={selectConflict}
          onSelectNode={selectNode}
          onDecideMatch={decideMatch}
          onRevealContacts={revealContacts}
          can={can}
          roleLabel={user.role}
        />
      </main>
    </div>
  );
}
