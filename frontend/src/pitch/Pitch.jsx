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

// --- slides

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

function Problem() {
  const records = [
    { hospital: "orion", name: "Maria Gonzalez", fact: "Allergy: Penicillin", detail: "anaphylaxis, high criticality", tone: "allergy" },
    { hospital: "lyra", name: "Maria Gonzales", fact: "Ordered: Amoxicillin 875 mg", detail: "ER visit, 2026-09-28", tone: "med" },
    { hospital: "vega", name: "M. Gonzalez", fact: "Ordered: Enalapril 5 mg", detail: "a 2nd blood-pressure drug of the same kind", tone: "med" },
  ];
  return (
    <>
      <div className="kicker">The problem</div>
      <h2>One patient. Three hospitals. Three different records.</h2>
      <div className="record-row">
        {records.map((r) => (
          <div key={r.hospital} className="record-card" style={{ borderColor: color(r.hospital) }}>
            <div className="record-hospital" style={{ color: color(r.hospital) }}>{hospitals[r.hospital].name}</div>
            <div className="record-name">{r.name}</div>
            <div className="record-dob">born 1958-03-14</div>
            <div className={`record-fact ${r.tone}`}>{r.fact}</div>
            <div className="record-detail">{r.detail}</div>
          </div>
        ))}
      </div>
      <p className="punchline">
        Amoxicillin <em>is</em> a penicillin. The records moved between hospitals, but{" "}
        <span className="danger">nobody connected the dots.</span>
      </p>
    </>
  );
}

function Gap() {
  return (
    <>
      <div className="kicker">Why it's still unsolved</div>
      <h2>Moving records is solved. Making sense of them isn't.</h2>
      <div className="two-col">
        <div className="panel-card">
          <div className="panel-label ok">Already exists</div>
          <p>National networks like <strong>TEFCA</strong>, <strong>Epic's network</strong> and{" "}
            <strong>CommonWell</strong> already send records between hospitals.</p>
          <p className="muted">They deliver a pile of documents from different systems.</p>
        </div>
        <div className="panel-card">
          <div className="panel-label danger">Still unsolved</div>
          <ol className="big-list">
            <li><strong>Who is who?</strong> The same person is spelled, typed and dated differently in every system.</li>
            <li><strong>What's dangerous?</strong> Contradictions between hospitals that nobody cross-checks.</li>
          </ol>
        </div>
      </div>
    </>
  );
}

function Solution() {
  const steps = [
    ["Read", "Each hospital's records in FHIR R4, the standard format hospitals already exchange."],
    ["Match", "Link the records that belong to the same person, and explain why, in plain English."],
    ["Catch", "Flag allergies, dangerous drug pairs, duplicates and dose mismatches, with the hospital each fact came from."],
  ];
  return (
    <>
      <div className="kicker">Our solution</div>
      <h2>Constellation connects the dots.</h2>
      <div className="steps">
        {steps.map(([name, text], i) => (
          <div key={name} className="step">
            <div className="step-number">{i + 1}</div>
            <div className="step-name">{name}</div>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <p className="muted center">Then a clinician confirms anything uncertain, and every decision is audited.</p>
    </>
  );
}

function MariaConstellation() {
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
        <div className="kicker">Why "Constellation"</div>
        <h2>Every patient becomes a constellation.</h2>
        <ul className="legend-list">
          <li><span className="sym star">✦</span><span>Each hospital's record is a star, with its allergies, drugs and conditions around it.</span></li>
          <li><span className="sym gold" /><span>Gold lines: the <strong>same person</strong>, 96–100% sure.</span></li>
          <li><span className="sym red" /><span>Red lines: a <strong>conflict</strong>. Here, the penicillin allergy at Orion vs amoxicillin from Lyra.</span></li>
        </ul>
      </div>
    </div>
  );
}

function Demo() {
  return (
    <>
      <div className="kicker">Live demo</div>
      <h2 className="huge">Let's look at the sky.</h2>
      <ol className="demo-steps">
        <li>The whole network in 3D: red stars are in danger</li>
        <li>Maria: three spellings, one chart, and an allergy only one hospital knew</li>
        <li>The <em>other</em> Maria Gonzalez: same name, kept separate</li>
        <li>Aisha: an uncertain match, and a clinician decides</li>
        <li>A fourth hospital connects live, and a new danger appears</li>
      </ol>
    </>
  );
}

function Matching() {
  const examples = [
    // [one record, the other, rubric level, points]: the same numbers as rubric.py
    ["Jim", "James", "nickname", "+5.6"],
    ["O'Brien", "OBrien", "same once punctuation is ignored", "+6.6"],
    ["1947-11-02", "1947-02-11", "day and month swapped", "+6.9"],
    ["Patel", "Patel-Khan", "one contains the other", "+5.5"],
    ["Whittaker", "Whitaker", "close spelling", "+4.9"],
  ];
  return (
    <>
      <div className="kicker">Matching</div>
      <h2>Who is who? Explainable, not a black box.</h2>
      <div className="two-col wide-left">
        <table className="match-table">
          <tbody>
            {examples.map(([a, b, why, points]) => (
              <tr key={why}>
                <td>{a}</td>
                <td className="eq">≈</td>
                <td>{b}</td>
                <td className="muted">{why}</td>
                <td className="pts">{points}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div>
          <p>One fixed <strong>points rubric</strong>: every field lands on a named level worth set points. Start at −10, add them up:</p>
          <div className="threshold">
            <div className="t-different">below 0<span>different people</span></div>
            <div className="t-review">0 to +4.2<span>a clinician decides</span></div>
            <div className="t-same">+4.2 or more<span>same person</span></div>
          </div>
          <p className="muted">The two Maria Gonzalezes score −6.9: kept apart. Encrypted matching scores every pair identically.</p>
        </div>
      </div>
    </>
  );
}

function Trust() {
  const chain = [
    ["#1", "Dr. Lee", "same person", "9f2c…"],
    ["#2", "Dr. Ruiz", "different", "41ab…"],
    ["#3", "Dr. Lee", "reset", "c07e…"],
  ];
  return (
    <>
      <div className="kicker">Trust</div>
      <h2>A clinician stays in control, and every decision is on the record.</h2>
      <div className="two-col">
        <div className="panel-card review-mock">
          <div className="muted small">Possible match, needs review · scored 85%</div>
          <div>Aisha <strong>Patel</strong> ↔ Aisha <strong>Patel-Khan</strong></div>
          <ul className="muted small">
            <li>One last name contains the other: married name?</li>
            <li>Birth date differs by one digit: likely a typo</li>
          </ul>
          <div className="mock-buttons"><span className="mock-confirm">Same person</span><span>Different people</span></div>
        </div>
        <div>
          <div className="chain">
            {chain.map(([seq, who, what, hash], i) => (
              <div key={seq} className="chain-entry">
                <div className="chain-box"><strong>{seq}</strong> {who} · {what}<span className="hash">sha256 {hash}</span></div>
                {i < chain.length - 1 && <div className="chain-link">↓ includes the hash of the entry above</div>}
              </div>
            ))}
          </div>
          <p className="small">Edit or remove an earlier entry and the chain breaks: the app <span className="danger">flags it and ignores it</span>.</p>
        </div>
      </div>
    </>
  );
}

function Privacy() {
  const safeguards = [
    ["Synthetic patients only", "Real records are protected health information. We never touched any."],
    ["Every clinician signs in", "Their own account, and automatic logoff after 15 idle minutes."],
    ["Each role sees what its job needs", "Registration fixes identity mix-ups but never sees medications or diagnoses. Nurses can't merge records."],
    ["Every access is logged", "Contact details stay masked until there's a reason, and who opened what, and why, is in the tamper-evident log."],
  ];
  return (
    <>
      <div className="kicker">Privacy and HIPAA</div>
      <h2>Privacy by design, not as an afterthought.</h2>
      <div className="two-col wide-left">
        <div className="next-grid">
          {safeguards.map(([title, text]) => (
            <div key={title} className="panel-card">
              <div className="next-title">{title}</div>
              <p className="small">{text}</p>
            </div>
          ))}
        </div>
        <div className="panel-card">
          <div className="panel-label ok">Encrypted matching</div>
          <p>Hospitals share <strong>encrypted fingerprints</strong>, never names or birth dates, and we still link the records.</p>
          <div className="big-numbers single">
            <div><strong>Identical</strong><span>scores to matching on real names</span></div>
          </div>
          <p className="muted small">Keyed letter-pair hashes, scored with the same rubric: 99.5% recall and 99.98% precision on 20,000 synthetic records, the same as plain names. Deployed inside a hospital or an HIE under a Business Associate Agreement.</p>
        </div>
      </div>
    </>
  );
}

function Scale() {
  return (
    <>
      <div className="kicker">Scale</div>
      <h2>Built for a whole network, not just a demo.</h2>
      <div className="big-numbers">
        <div><strong>100,000</strong><span>patient records</span></div>
        <div><strong>&lt; 90 s</strong><span>to link them all</span></div>
        <div><strong>7,283×</strong><span>fewer comparisons</span></div>
        <div><strong>99.6%</strong><span>of automatic links correct</span></div>
      </div>
      <p className="center">
        <strong>Blocking:</strong> only compare records that share a birth date, a phone number, or a sound-alike surname plus birth year.
        Comparing every pair would take <strong>over 100 hours</strong>.
      </p>
      <p className="muted center small">Measured with our benchmark on synthetic patients with realistic mistakes (python -m app.benchmark).</p>
    </>
  );
}

function Next() {
  const items = [
    ["Real drug knowledge", "RxNorm drug codes and a licensed interaction database instead of our demo rules."],
    ["Plug into the networks", "Read records over FHIR APIs from TEFCA and Epic instead of files."],
    ["Hospital sign-on", "Use the hospital's single sign-on with two-factor login, and keep a copy of the audit log off-site."],
    ["Millions of records", "Spread scoring across CPU cores, and match new records as they arrive."],
  ];
  return (
    <>
      <div className="kicker">What's next</div>
      <h2>From hackathon to hospital.</h2>
      <div className="next-grid">
        {items.map(([title, text]) => (
          <div key={title} className="panel-card">
            <div className="next-title">{title}</div>
            <p>{text}</p>
          </div>
        ))}
      </div>
    </>
  );
}

function Close() {
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
    notes: "Hi, we're [names]. This is Constellation. Hospitals can already send each other patient records, but nobody connects the dots, and that's where patients get hurt.",
  },
  {
    id: "problem", Body: Problem,
    notes: "Meet Maria. Orion knows she's deathly allergic to penicillin. Lyra's ER spells her name differently and orders amoxicillin, which is a penicillin. A third clinic adds a second blood-pressure drug. Every record is correct on its own. Together they're dangerous.",
  },
  {
    id: "gap", Body: Gap,
    notes: "Moving the records already exists: TEFCA, Epic and CommonWell do that. What's missing is making sense of them: knowing these three records are one person, and catching contradictions between them.",
  },
  {
    id: "solution", Body: Solution,
    notes: "Constellation does three things. It reads records in FHIR, the format hospitals already use. It matches records to people and explains why. And it catches the conflicts, saying which hospital each fact came from.",
  },
  {
    id: "constellation", Body: MariaConstellation, className: "full-bleed",
    notes: "Here's Maria as a constellation. Each star is one hospital's record. Gold lines mean same person. The red line is the danger: penicillin allergy at Orion, amoxicillin from Lyra. One glance, and a clinician sees it.",
  },
  {
    id: "demo", Body: Demo,
    notes: "Switch to the app now (localhost:5173). Open 'All patients · 3D', click Maria's red star, point at 'Penicillin, only at Orion' in the Summary tab, then click the red line. Then the other Maria Gonzalez, then Aisha: open Record links and click Same person. Then Connect hospital, Try the sample: Kenji's new asthma conflict. Press Reset demo beforehand.",
  },
  {
    id: "matching", Body: Matching,
    notes: "Matching is the hard part, so we made it a fixed rubric. Every field lands on a named level worth set points: a nickname is plus 5.6, a swapped day and month plus 6.9. Start at minus 10; plus 4.2 links the records, below zero keeps them apart, and in between a human decides. Same evidence, same score, every time, and the app shows the breakdown for every link.",
  },
  {
    id: "trust", Body: Trust,
    notes: "In healthcare, a human has to stay in control. A clinician confirms uncertain matches, and every decision goes into a tamper-evident log. Each entry includes the hash of the one before it, so if anyone edits history, the chain breaks and we ignore it.",
  },
  {
    id: "privacy", Body: Privacy,
    notes: "We never used real patient data. Instead we built in the technical safeguards from HIPAA's Security Rule: every clinician signs in and is logged out when idle, each role only sees what its job needs, and every access is logged. We even hide contact details until there's a reason, which HIPAA doesn't require for treatment. And the matcher doesn't need names: hospitals share encrypted fingerprints, and the rubric gives exactly the same scores.",
  },
  {
    id: "scale", Body: Scale,
    notes: "And it scales. Comparing every pair of 100,000 records would take over 100 hours. With blocking, we link them in about a minute and a half. 99.6% of the automatic links are correct and 99.5% of the true links are found, measured on synthetic data with realistic mistakes, and anything uncertain goes to a human.",
  },
  {
    id: "next", Body: Next,
    notes: "Next: real drug data with RxNorm, reading records live from TEFCA and Epic over FHIR, signed-in clinicians, and spreading the work across machines.",
  },
  {
    id: "close", Body: Close, className: "full-bleed",
    notes: "Constellation: connect the dots before they cause harm. Thank you, and we'd love your questions.",
  },
];
