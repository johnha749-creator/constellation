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

// [number, short label, source]. "At worst" marks upper bounds, so nobody reads them as averages.
const PROBLEM_STATS = [
  ["31%", "of adults use 2+ hospitals", "Bourgeois et al., Arch Intern Med 2010"],
  ["50%", "match rate between organizations, at worst", "Pew Charitable Trusts, 2018"],
  ["8–12%", "of hospital records are duplicates", "AHIMA Journal"],
  ["26.9%", "hospital data error rate, at worst", "HealthLeaders, 2025"],
  ["27–54%", "of patients: medication-history errors at admission", "Tam et al., CMAJ 2005"],
  ["1 in 167", "Americans in the ER each year from medication harm", "Budnitz et al., JAMA 2021"],
  ["7,613", "wrong-patient events; 9% caused harm", "ECRI Institute, 2016"],
  ["$20M", "a year lost to bad data per provider, at worst", "HealthLeaders, 2025"],
];

function Fact({ number, text, source, className = "" }) {
  return (
    <div className={`fact ${className}`}>
      <div className="fact-number">{number}</div>
      <div className="fact-text">{text}</div>
      <div className="fact-source">{source}</div>
    </div>
  );
}

function Problem() {
  return (
    <>
      <div className="kicker">The problem, in numbers</div>
      <h2>Patients are scattered. Their records don't add up.</h2>
      <div className="fact-grid">
        {PROBLEM_STATS.map(([number, text, source]) => (
          <Fact key={text} number={number} text={text} source={source} />
        ))}
      </div>
    </>
  );
}

function WhyItHappens() {
  const records = [
    { hospital: "orion", name: "Maria Gonzalez", fact: "Allergy: Penicillin", tone: "allergy" },
    { hospital: "lyra", name: "Maria Gonzales", fact: "Ordered: Amoxicillin", tone: "med" },
    { hospital: "vega", name: "M. Gonzalez", fact: "Ordered: Enalapril", tone: "med" },
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
          </div>
        ))}
      </div>
      <p className="punchline center">
        Amoxicillin <em>is</em> a penicillin. Each record is right; <span className="danger">together they're dangerous.</span>
      </p>
      <div className="fact-pair">
        <Fact className="inline" number="35%" text="of doctors share records only by fax or mail" source="ONC, 2019" />
        <Fact className="inline" number="43%" text="of hospitals routinely integrate outside records" source="ONC, 2023" />
      </div>
    </>
  );
}

function Fix() {
  const steps = [
    ["Read", "Every hospital's records, in FHIR."],
    ["Match", "Fixed points per field. Same evidence, same score."],
    ["Catch", "5 kinds of conflict, with the hospital behind each."],
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
      <p className="muted center small">Start at −10. The two different Maria Gonzalezes score −6.9: kept apart.</p>
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
        <h2>Every patient is a constellation.</h2>
        <ul className="legend-list">
          <li><span className="sym gold" /><span>Gold: <strong>same person</strong></span></li>
          <li><span className="sym red" /><span>Red: <strong>conflict</strong></span></li>
        </ul>
        <ol className="demo-steps">
          <li>3D: red stars are in danger</li>
          <li>Maria: an allergy only Orion knew</li>
          <li>The other Maria: kept apart</li>
          <li>Aisha: a clinician decides</li>
          <li>New hospital, new danger</li>
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
        <div><strong>99.98%</strong><span>auto-links correct</span></div>
        <div><strong>99.53%</strong><span>true matches found</span></div>
        <div><strong>7,283×</strong><span>fewer comparisons at 100,000</span></div>
        <div><strong>86 s</strong><span>for 100,000 records</span></div>
      </div>
      <div className="result-row">
        <div><strong>100%</strong> same results, encrypted</div>
        <div><strong>{stats.cross_hospital_conflicts}</strong> conflicts caught in our demo</div>
        <div><strong>7</strong> HIPAA safeguards built in</div>
        <div><strong>95</strong> automated tests</div>
      </div>
      <p className="muted center small">Synthetic patients with realistic mistakes; 20,000 records unless noted.</p>
    </>
  );
}

function Close() {
  const next = [
    ["Real drug data", "RxNorm + an interaction database"],
    ["Live networks", "TEFCA and Epic over FHIR"],
    ["Hospital-grade", "single sign-on, millions of records"],
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
    notes: "A third of adults use more than one hospital. When records cross organizations, matching can be as bad as 50%. Up to 12% of a hospital's records are duplicates, and some studies find data errors in over a quarter of hospital records. A quarter to a half of patients arrive with medication-history errors, 1 in 167 Americans ends up in the ER from medication harm each year, and bad data can cost a provider up to 20 million dollars a year.",
  },
  {
    id: "why", Body: WhyItHappens,
    notes: "Here's how it happens. Maria's penicillin allergy is at Orion. Lyra's ER spells her name differently and orders amoxicillin, a penicillin. Each record is right; together they're dangerous. A third of doctors still share records only by fax or mail, and fewer than half of hospitals routinely integrate what they receive.",
  },
  {
    id: "fix", Body: Fix,
    notes: "Constellation reads FHIR, the format hospitals already use. It matches records with fixed points per field: start at minus 10, plus 4.2 links, and anything in between goes to a clinician. Same evidence, same score, every time. Then it catches five kinds of conflict, naming the hospital behind each side.",
  },
  {
    id: "demo", Body: Demo, className: "full-bleed",
    notes: "This is Maria: each star is one hospital's record, gold is the same person, red is the penicillin conflict. Now switch to the app (localhost:5173, Reset demo beforehand): 3D view, Maria's red star, the Summary tab, the red line, the other Maria Gonzalez, Aisha's review, then Connect hospital → Try the sample → Kenji.",
  },
  {
    id: "results", Body: Results,
    notes: "On 20,000 synthetic records with realistic mistakes, 99.98% of automatic links are correct and 99.5% of true matches are found; the rest go to a human. Blocking cuts 5 billion comparisons to under 700,000, so 100,000 records link in 86 seconds. Encrypted fingerprints give exactly the same decisions, and 95 tests back it up.",
  },
  {
    id: "close", Body: Close, className: "full-bleed",
    notes: "Next: real drug data, live feeds from TEFCA and Epic, and hospital-grade sign-on and scale. Constellation: connect the dots before they cause harm. Thank you!",
  },
];
