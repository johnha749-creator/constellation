import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import Constellation from "../components/Constellation";
import { withHospitalColors } from "../labels";
import snapshot from "./snapshot.json"; // regenerate with `python -m app.snapshot` in backend/

const Galaxy3D = lazy(() => import("../components/Galaxy3D"));

// Shown on the title slide. Fill in before presenting.
const TEAM = "";
const REPO = "github.com/johnha749-creator/constellation";

const hospitals = withHospitalColors(snapshot.hospitals);
const { stats } = snapshot;
const color = (id) => hospitals[id].color;

/**
 * The pitch deck: open /pitch.html while `npm run dev` is running.
 * → / Space: next · ←: back · F: full screen · N: speaker notes
 */
export default function Pitch() {
  const [index, setIndex] = useState(() => {
    const n = Number(window.location.hash.slice(1));
    return Number.isInteger(n) && n >= 1 && n <= SLIDES.length ? n - 1 : 0;
  });
  const [showNotes, setShowNotes] = useState(false);
  const go = useCallback((delta) => setIndex((i) => Math.min(SLIDES.length - 1, Math.max(0, i + delta))), []);

  useEffect(() => {
    window.history.replaceState(null, "", `#${index + 1}`); // a reload stays on this slide
  }, [index]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.("input, textarea")) return;
      if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) go(1);
      else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) go(-1);
      else if (e.key === "Home") setIndex(0);
      else if (e.key === "End") setIndex(SLIDES.length - 1);
      else if (e.key.toLowerCase() === "f") toggleFullscreen();
      else if (e.key.toLowerCase() === "n") setShowNotes((s) => !s);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const slide = SLIDES[index];
  // Buttons lose focus after a click, so Space/Enter keep meaning "next slide".
  const click = (action) => (e) => {
    e.currentTarget.blur();
    action();
  };

  return (
    <div className="deck">
      <div className="frame">
        <Starfield />
        <section key={slide.id} className={`slide ${slide.className ?? ""}`}>
          <slide.Body />
        </section>
      </div>
      <nav className="deck-nav" aria-label="Slides">
        <button onClick={click(() => go(-1))} disabled={index === 0} aria-label="Previous slide">‹</button>
        <span>{index + 1} / {SLIDES.length}</span>
        <button onClick={click(() => go(1))} disabled={index === SLIDES.length - 1} aria-label="Next slide">›</button>
        <button onClick={click(() => setShowNotes((s) => !s))}>Notes (N)</button>
        <button onClick={click(toggleFullscreen)}>Full screen (F)</button>
      </nav>
      {showNotes && (
        <aside className="deck-notes">
          <strong>Say:</strong> {slide.notes}
        </aside>
      )}
    </div>
  );
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.();
}

function Starfield() {
  const stars = [];
  let seed = 11;
  const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 140; i++) {
    stars.push(<circle key={i} className="bg-star" cx={random() * 160} cy={random() * 90} r={random() * 0.18 + 0.04}
                       style={{ animationDelay: `${random() * 5}s` }} />);
  }
  return <svg className="deck-stars" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">{stars}</svg>;
}

// --- slides (7). Every outside number is cited on its slide; every number about Constellation
// comes from our tests and benchmark (see README.md).

function Title() {
  return (
    <>
      <div className="slide-galaxy">
        <Suspense fallback={null}>
          <Galaxy3D patients={snapshot.patients} hospitals={hospitals} selectedId={null} onSelect={() => {}} legend={false} />
        </Suspense>
      </div>
      <div className="title-text">
        <div className="kicker">Hyphen-Hacks 2026 · Crafting Constellations</div>
        <h1><span className="brand-mark">✦</span> Constellation</h1>
        <p className="lede">Hospitals can already share patient records.<br />Nobody connects the dots.</p>
        {TEAM && <p className="team">{TEAM}</p>}
      </div>
      <div className="title-stats">
        {stats.patients} patients · {stats.records} records · {stats.hospitals} hospitals ·{" "}
        <span className="danger">{stats.cross_hospital_conflicts} conflicts caught across hospitals</span>
      </div>
    </>
  );
}

const PROBLEM_STATS = [
  ["31%", <>of adults used <strong>2+ hospitals</strong>, and they made <strong>56.5%</strong> of all acute-care visits</>,
    "Bourgeois et al., Arch Intern Med 2010 (3.7M Massachusetts adults)"],
  ["50%", <>worst-case <strong>match rate</strong> when patient records are shared between organizations</>,
    "Pew Charitable Trusts 2018, citing ONC-funded research"],
  ["8–12%", <>of a hospital's patient records are <strong>duplicates</strong> of the same person</>,
    "AHIMA Journal"],
  ["27–54%", <>of patients admitted to hospital have <strong>an error in their medication history</strong></>,
    "Tam et al., CMAJ 2005, systematic review"],
  ["1 in 167", <>Americans goes to the ER for <strong>medication harm</strong> every year; 38.6% are admitted</>,
    "Budnitz et al., JAMA 2021"],
  ["7,613", <><strong>wrong-patient</strong> events reported by 181 organizations; 9% caused harm or death</>,
    "ECRI Institute, 2016"],
];

function Problem() {
  return (
    <>
      <div className="kicker">The problem, in numbers</div>
      <h2>Patients are scattered across hospitals. Their records don't add up.</h2>
      <div className="fact-grid">
        {PROBLEM_STATS.map(([number, text, source]) => (
          <div key={source} className="fact">
            <div className="fact-number">{number}</div>
            <div className="fact-text">{text}</div>
            <div className="fact-source">{source}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function WhyItHappens() {
  const records = [
    { hospital: "orion", name: "Maria Gonzalez", fact: "Allergy: Penicillin", detail: "anaphylaxis", tone: "allergy" },
    { hospital: "lyra", name: "Maria Gonzales", fact: "Ordered: Amoxicillin", detail: "ER visit, last month", tone: "med" },
    { hospital: "vega", name: "M. Gonzalez", fact: "Ordered: Enalapril", detail: "a 2nd drug of the same kind", tone: "med" },
  ];
  return (
    <>
      <div className="kicker">Why it still happens</div>
      <h2>Records move. Nobody connects them.</h2>
      <div className="record-row compact">
        {records.map((r) => (
          <div key={r.hospital} className="record-card" style={{ borderColor: color(r.hospital) }}>
            <div className="record-hospital" style={{ color: color(r.hospital) }}>{hospitals[r.hospital].name}</div>
            <div className="record-name">{r.name}</div>
            <div className={`record-fact ${r.tone}`}>{r.fact}</div>
            <div className="record-detail">{r.detail}</div>
          </div>
        ))}
      </div>
      <div className="two-col why-row">
        <p className="punchline">
          Three spellings, one woman. Amoxicillin <em>is</em> a penicillin. Every record is correct on its own;{" "}
          <span className="danger">together they're dangerous.</span>
        </p>
        <div className="fact inline">
          <div className="fact-number">43%</div>
          <div className="fact-text">of U.S. hospitals <strong>routinely</strong> send, receive, find <em>and</em> integrate
            outside records. The networks exist (TEFCA, Epic, CommonWell); making sense of what arrives doesn't.</div>
          <div className="fact-source">ONC Data Brief 71: non-federal acute care hospitals, 2023</div>
        </div>
      </div>
    </>
  );
}

function Fix() {
  const steps = [
    ["Read", "Every hospital's records in FHIR R4, the format they already exchange. A new hospital can connect live."],
    ["Match", "One fixed points rubric over 6 fields. Nickname +5.6, swapped day and month +6.9, typo in a surname +4.9."],
    ["Catch", "5 kinds of conflict across the combined chart: allergy, interaction, duplicate drug, drug vs diagnosis, dose."],
  ];
  return (
    <>
      <div className="kicker">How we fix it</div>
      <h2>Read. Match. Catch.</h2>
      <div className="steps">
        {steps.map(([name, text], i) => (
          <div key={name} className="step">
            <div className="step-number">{i + 1}</div>
            <div className="step-name">{name}</div>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <div className="threshold">
        <div className="t-different">below 0<span>different people</span></div>
        <div className="t-review">0 to +4.2<span>a clinician decides</span></div>
        <div className="t-same">+4.2 or more<span>same person</span></div>
      </div>
      <p className="muted center small">
        Every pair starts at −10 points. The two different Maria Gonzalezes score −6.9 and stay apart. Every link
        shows its breakdown, and every decision goes into a tamper-evident log.
      </p>
    </>
  );
}

function Demo() {
  const [conflictId, setConflictId] = useState("k1"); // the penicillin conflict
  const [nodeId, setNodeId] = useState(null);
  return (
    <div className="split">
      <div className="split-visual">
        <Constellation
          graph={snapshot.maria}
          hospitals={hospitals}
          selectedConflictId={conflictId}
          selectedNodeId={nodeId}
          onSelectConflict={(id) => {
            setConflictId(id);
            setNodeId(null);
          }}
          onSelectNode={(id) => {
            setNodeId(id);
            setConflictId(null);
          }}
          legend={false}
        />
      </div>
      <div className="split-text">
        <div className="kicker">Live demo</div>
        <h2>Every patient becomes a constellation.</h2>
        <ul className="legend-list">
          <li><span className="sym gold" /><span>Gold: the <strong>same person</strong>, 96–100% sure</span></li>
          <li><span className="sym red" /><span>Red: a <strong>conflict</strong> between hospitals</span></li>
        </ul>
        <ol className="demo-steps">
          <li>All patients in 3D: red stars are in danger</li>
          <li>Maria: 10 of her 10 facts were known to only one hospital</li>
          <li>The <em>other</em> Maria Gonzalez stays separate</li>
          <li>Aisha: unsure, so a clinician decides</li>
          <li>A 4th hospital connects live: a new danger</li>
        </ol>
      </div>
    </div>
  );
}

function Results() {
  return (
    <>
      <div className="kicker">The fix, in numbers</div>
      <h2>Measured, not promised.</h2>
      <div className="big-numbers">
        <div><strong>99.98%</strong><span>of automatic links are correct (20,000 records)</span></div>
        <div><strong>99.53%</strong><span>of true matches found (20,000 records)</span></div>
        <div><strong>7,283×</strong><span>fewer comparisons: 5 billion → 686,541 (100,000 records)</span></div>
        <div><strong>86 s</strong><span>to link 100,000 records, instead of 100+ hours</span></div>
      </div>
      <div className="result-row">
        <div><strong>100%</strong> the same decisions when hospitals share only <em>encrypted</em> fingerprints</div>
        <div><strong>{stats.cross_hospital_conflicts}</strong> conflicts caught across hospitals in our demo, {stats.conflicts.high} high risk</div>
        <div><strong>7</strong> HIPAA Security Rule safeguards built in: sign-in, roles, logoff, audit log…</div>
        <div><strong>95</strong> automated tests</div>
      </div>
      <p className="muted center small">
        Benchmarked on synthetic patients with realistic mistakes: typos, nicknames, swapped dates, moves
        (python -m app.benchmark).
      </p>
    </>
  );
}

function Close() {
  const next = [
    ["Real drug data", "RxNorm codes and a licensed interaction database"],
    ["Plug into the networks", "read live from TEFCA and Epic over FHIR APIs"],
    ["Hospital-grade", "single sign-on, an off-site audit copy, millions of records"],
  ];
  return (
    <>
      <div className="slide-galaxy dim">
        <Suspense fallback={null}>
          <Galaxy3D patients={snapshot.patients} hospitals={hospitals} selectedId={null} onSelect={() => {}} legend={false} />
        </Suspense>
      </div>
      <div className="close-text">
        <h1><span className="brand-mark">✦</span> Constellation</h1>
        <p className="lede">Connect the dots before they cause harm.</p>
        <div className="close-next">
          {next.map(([title, text]) => (
            <div key={title}><strong>{title}</strong><span>{text}</span></div>
          ))}
        </div>
        <p className="repo">{REPO}</p>
        <p className="thanks">Thank you. Questions?</p>
        <p className="muted small">All patients and hospitals are synthetic. Not for clinical use.</p>
      </div>
    </>
  );
}

const SLIDES = [
  {
    id: "title", Body: Title, className: "full-bleed title-slide",
    notes: "Hi, we're [names], and this is Constellation. Hospitals can already send each other patient records. But nobody connects the dots, and that's where patients get hurt.",
  },
  {
    id: "problem", Body: Problem,
    notes: "The numbers. About a third of adults use more than one hospital, and they make over half of all visits. When records cross organizations, matching can be as bad as 50%. Up to 12% of a hospital's records are duplicates. At admission, a quarter to a half of patients have an error in their medication history. 1 in 167 Americans ends up in the ER from medication harm every year. And ECRI collected over 7,600 wrong-patient events, 9% of them harmful.",
  },
  {
    id: "why", Body: WhyItHappens,
    notes: "Here's how it happens. Maria's penicillin allergy is at Orion. Lyra's ER spells her name differently and orders amoxicillin, which is a penicillin. Every record is correct; together they're dangerous. The networks to move records exist, but only 43% of hospitals routinely integrate what they receive. Moving records is solved. Making sense of them isn't.",
  },
  {
    id: "fix", Body: Fix,
    notes: "Constellation does three things. It reads FHIR, the format hospitals already use. It matches records with one fixed rubric: every field earns set points, start at minus 10, plus 4.2 links, and anything in between goes to a clinician. Same evidence, same score, every time. Then it catches five kinds of conflict across the combined chart, naming the hospital behind each side.",
  },
  {
    id: "demo", Body: Demo, className: "full-bleed",
    notes: "This is Maria as a constellation: each star is one hospital's record, gold lines are the same person, the red line is the penicillin conflict. Now switch to the app (localhost:5173, Reset demo beforehand): 3D view, Maria's red star, the Summary tab ('Penicillin, only at Orion'), the red line, the other Maria Gonzalez, Aisha's review, then Connect hospital → Try the sample → Kenji.",
  },
  {
    id: "results", Body: Results,
    notes: "Does it work? On 20,000 synthetic records with realistic mistakes, 99.98% of automatic links are correct and 99.5% of true matches are found; the rest go to a human. Blocking cuts 5 billion comparisons to under 700,000, so 100,000 records link in under 90 seconds. Hospitals can share encrypted fingerprints instead of names and get exactly the same decisions. We built in seven HIPAA Security Rule safeguards, and 95 automated tests back all of this.",
  },
  {
    id: "close", Body: Close, className: "full-bleed",
    notes: "Next: real drug data with RxNorm, reading live from TEFCA and Epic, and hospital-grade sign-on and scale. Constellation: connect the dots before they cause harm. Thank you, and we'd love your questions.",
  },
];

