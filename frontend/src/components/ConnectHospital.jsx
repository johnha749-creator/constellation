import { useEffect, useRef, useState } from "react";
import { BundleRejectedError, connectHospital, SignedOutError } from "../api";

const SAMPLE_URL = `${import.meta.env.BASE_URL}samples/polaris-urgent-care.json`;
const MAX_BYTES = 5 * 1024 * 1024;

/** Upload a new hospital's FHIR bundle. Constellation matches its records against every patient
 *  and reports what changed, including any new conflicts its data creates. */
export default function ConnectHospital({ onClose, onConnected, onOpenPatient, onSignedOut }) {
  const [state, setState] = useState({ status: "idle" }); // idle | uploading | done | failed
  const [dragging, setDragging] = useState(false);
  const dialogRef = useRef(null);

  useEffect(() => {
    dialogRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const upload = async (getText, label) => {
    setState({ status: "uploading", label });
    try {
      const report = await connectHospital(await getText());
      setState({ status: "done", report });
      onConnected(report);
    } catch (e) {
      if (e instanceof SignedOutError) return onSignedOut();
      setState({
        status: "failed",
        message: e instanceof BundleRejectedError ? e.message : `Upload failed (${e.message}).`,
        problems: e.problems ?? [],
      });
    }
  };

  const uploadFile = (file) => {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setState({ status: "failed", message: "That file is too big: the limit is 5 MB.", problems: [] });
      return;
    }
    upload(() => file.text(), file.name);
  };

  const uploadSample = () =>
    upload(async () => {
      const res = await fetch(SAMPLE_URL);
      if (!res.ok) throw new Error(`couldn't load the sample: ${res.status}`);
      return res.text();
    }, "polaris-urgent-care.json");

  const busy = state.status === "uploading";
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="connect-title" tabIndex={-1} ref={dialogRef}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 id="connect-title">Connect a hospital</h3>
        <p className="muted small">
          Upload the hospital's records as a <strong>FHIR R4 Bundle</strong> (JSON). Constellation checks the whole
          file first, matches every record against the patients it already knows using the same rubric, and checks the
          combined records for conflicts. The upload is logged.
        </p>

        {state.status !== "done" && (
          <>
            <label
              className={`drop-zone ${dragging ? "dragging" : ""} ${busy ? "busy" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                uploadFile(e.dataTransfer.files[0]);
              }}
            >
              <input
                type="file"
                accept=".json,application/json,application/fhir+json"
                disabled={busy}
                onChange={(e) => {
                  uploadFile(e.target.files[0]);
                  e.target.value = ""; // so choosing the same file again (after fixing it) uploads again
                }}
              />
              {busy ? `Matching ${state.label}…` : "Drop a FHIR bundle here, or click to choose a file"}
            </label>
            <div className="modal-row">
              <button className="btn confirm" onClick={uploadSample} disabled={busy}>
                Try the sample: Polaris Urgent Care
              </button>
              <a className="small" href={SAMPLE_URL} download>
                Download the sample
              </a>
            </div>
          </>
        )}

        {state.status === "failed" && (
          <div className="upload-error" role="alert">
            <strong>{state.message}</strong>
            {state.problems.length > 0 && (
              <ul>
                {state.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
            <div className="muted small">Nothing was added.</div>
          </div>
        )}

        {state.status === "done" && <Report report={state.report} onOpenPatient={onOpenPatient} />}
      </div>
    </div>
  );
}

function Report({ report, onOpenPatient }) {
  const { hospital, records, matched, new_patients: newPatients, needs_review: review, new_conflicts: conflicts } = report;
  return (
    <div className="connect-report">
      <div className="connect-done">✓ {hospital.name} is connected</div>
      <p className="small">
        {records} {records === 1 ? "record" : "records"}: {matched} matched {matched === 1 ? "a patient" : "patients"}{" "}
        we already knew{review > 0 && ` (${review} need${review === 1 ? "s" : ""} review)`}, and {newPatients}{" "}
        {newPatients === 1 ? "is a new patient" : "are new patients"}. Only the {report.pairs_compared} record pairs
        that include a new record were scored.
      </p>
      {conflicts === null ? null : conflicts.length === 0 ? (
        <p className="muted small">No new conflicts.</p>
      ) : (
        <>
          <div className="connect-alert">
            ⚠ {conflicts.length} new {conflicts.length === 1 ? "conflict" : "conflicts"} found:
          </div>
          {conflicts.map((c) => (
            <button key={`${c.patient_id}-${c.title}`} className={`issue ${c.severity}`} onClick={() => onOpenPatient(c.patient_id)}>
              <span className={`badge ${c.severity}`}>{c.severity}</span>
              <span>
                <strong>{c.patient}</strong>: {c.title}{" "}
                {c.cross_hospital && <span className="tag">across hospitals</span>}{" "}
                {c.unconfirmed && <span className="tag review">unconfirmed match</span>}
              </span>
              <span className="open-arrow">Open →</span>
            </button>
          ))}
        </>
      )}
    </div>
  );
}
