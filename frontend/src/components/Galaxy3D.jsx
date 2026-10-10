import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";

const SEVERITY_COLOR = { high: "#ff4d6d", moderate: "#ff9f43", low: "#ffd166", none: "#dfe6ff" };
const REVIEW_COLOR = "#f7b267";
const HOSPITAL_RING = 24; // distance of each hospital from the center
const VIEW_DIRECTION = new THREE.Vector3(0, 36, 56).normalize(); // looking down a little, so the hospital triangle reads

/**
 * The whole network in 3D. Hospitals are suns; each patient is a star placed between the
 * hospitals that hold its records, joined to them by faint beams. Color shows the patient's most
 * serious conflict. Click a star to open that patient's constellation.
 */
export default function Galaxy3D({ patients, hospitals, selectedId, onSelect, legend = true }) {
  const wrapRef = useRef(null);
  const tooltipRef = useRef(null);
  const sceneRef = useRef(null); // { stars: Map(id -> sprite), selectRing }
  const cameraState = useRef(null); // keep the viewpoint when the data refreshes
  const handlers = useRef({});
  handlers.current = { onSelect };
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const wrap = wrapRef.current;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setWebglFailed(true);
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    wrap.appendChild(renderer.domElement);
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.domElement.className = "galaxy-labels";
    wrap.appendChild(labelRenderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 3000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;
    controls.minDistance = 12;
    controls.maxDistance = 180;
    let needsFit = !cameraState.current;
    if (cameraState.current) {
      camera.position.copy(cameraState.current.position);
      controls.target.copy(cameraState.current.target);
      controls.autoRotate = cameraState.current.autoRotate;
    }
    controls.addEventListener("start", () => (controls.autoRotate = false)); // the viewer takes over

    const disposables = [];
    const track = (thing) => (disposables.push(thing), thing);
    const glow = track(makeGlowTexture());
    const ring = track(makeRingTexture());

    // A distant starfield.
    const starPositions = new Float32Array(1800 * 3);
    const random = mulberry32(7);
    for (let i = 0; i < 1800; i++) {
      const v = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
      v.multiplyScalar(400 + random() * 400);
      starPositions.set([v.x, v.y, v.z], i * 3);
    }
    const starGeometry = track(new THREE.BufferGeometry());
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const starMaterial = track(new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, transparent: true, opacity: 0.7 }));
    scene.add(new THREE.Points(starGeometry, starMaterial));

    // Hospitals: suns spaced around a ring.
    const hospitalList = Object.values(hospitals);
    const hospitalPos = new Map();
    hospitalList.forEach((h, i) => {
      const angle = (i / hospitalList.length) * Math.PI * 2 - Math.PI / 2;
      const position = new THREE.Vector3(Math.cos(angle) * HOSPITAL_RING, 0, Math.sin(angle) * HOSPITAL_RING);
      hospitalPos.set(h.id, position);
      const sun = new THREE.Sprite(track(glowMaterial(glow, h.color, 1)));
      sun.scale.setScalar(11);
      sun.position.copy(position);
      scene.add(sun);
      sun.add(label(h.name, "galaxy-hospital", h.color, -0.45));
    });

    // Patients: stars between their hospitals, beams to each one.
    const stars = new Map();
    const pulsing = [];
    const beamPositions = [];
    const beamColors = [];
    for (const p of patients) {
      const position = patientPosition(p, hospitalPos);
      const severity = worstSeverity(p);
      const star = new THREE.Sprite(track(glowMaterial(glow, SEVERITY_COLOR[severity], severity === "none" ? 0.75 : 1)));
      const size = 2.6 + p.record_count * 0.7 + (severity === "high" ? 1.2 : 0);
      star.scale.setScalar(size);
      star.position.copy(position);
      star.userData = { patient: p, size };
      scene.add(star);
      stars.set(p.id, star);
      if (severity === "high") pulsing.push(star);
      if (p.needs_review) {
        const halo = new THREE.Sprite(track(glowMaterial(ring, REVIEW_COLOR, 0.9)));
        halo.scale.setScalar(1.6); // relative to the star, since children inherit its scale
        star.add(halo);
      }
      if (severity !== "none" || p.needs_review) star.add(label(p.name, "galaxy-patient", null, 0.9));
      for (const h of p.hospitals) {
        const target = hospitalPos.get(h);
        if (!target) continue;
        const color = new THREE.Color(hospitals[h].color);
        beamPositions.push(position.x, position.y, position.z, target.x, target.y, target.z);
        beamColors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      }
    }
    const beamGeometry = track(new THREE.BufferGeometry());
    beamGeometry.setAttribute("position", new THREE.Float32BufferAttribute(beamPositions, 3));
    beamGeometry.setAttribute("color", new THREE.Float32BufferAttribute(beamColors, 3));
    const beamMaterial = track(
      new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false }),
    );
    scene.add(new THREE.LineSegments(beamGeometry, beamMaterial));

    // The selected patient gets a white ring.
    const selectRing = new THREE.Sprite(track(glowMaterial(ring, "#ffffff", 1)));
    selectRing.visible = false;
    scene.add(selectRing);
    sceneRef.current = { stars, selectRing };
    placeSelectRing(sceneRef.current, selectedIdRef.current);

    // Hover for details, click (without dragging) to open the patient.
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const tooltip = tooltipRef.current;
    let downAt = null;
    const pick = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      return raycaster.intersectObjects([...stars.values()], false)[0]?.object.userData.patient ?? null;
    };
    const onMove = (event) => {
      const p = pick(event);
      renderer.domElement.style.cursor = p ? "pointer" : "grab";
      if (!p) {
        tooltip.style.opacity = 0;
        return;
      }
      const rect = wrap.getBoundingClientRect();
      tooltip.textContent = describe(p, hospitals);
      tooltip.style.left = `${event.clientX - rect.left + 14}px`;
      tooltip.style.top = `${event.clientY - rect.top + 14}px`;
      tooltip.style.opacity = 1;
    };
    const onDown = (event) => (downAt = [event.clientX, event.clientY]);
    const onUp = (event) => {
      if (!downAt || Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1]) > 5) return;
      const p = pick(event);
      if (p) handlers.current.onSelect(p.id);
    };
    const onLeave = () => (tooltip.style.opacity = 0);
    const canvas = renderer.domElement;
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointerleave", onLeave);

    // Follow the container's size (it can be 0 while the page is hidden).
    const resize = () => {
      const { clientWidth: width, clientHeight: height } = wrap; // layout size
      if (!width || !height) return;
      renderer.setSize(width, height);
      labelRenderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (needsFit) {
        // Back the camera off until all the hospitals and their labels fit across the view.
        const halfWidth = Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect);
        const distance = Math.max(60, (HOSPITAL_RING + 14) / Math.tan(halfWidth));
        camera.position.copy(VIEW_DIRECTION).multiplyScalar(distance);
        needsFit = false;
      }
    };
    const observer = new ResizeObserver(resize);
    observer.observe(wrap);
    resize();

    const clock = new THREE.Clock();
    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      for (const star of pulsing) star.scale.setScalar(star.userData.size * (1 + 0.18 * Math.sin(t * 3)));
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      cameraState.current = { position: camera.position.clone(), target: controls.target.clone(), autoRotate: controls.autoRotate };
      observer.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointerleave", onLeave);
      controls.dispose();
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      canvas.remove();
      labelRenderer.domElement.remove();
      sceneRef.current = null;
    };
  }, [patients, hospitals]);

  // Move the white ring when the selection changes, without rebuilding the scene.
  useEffect(() => {
    if (sceneRef.current) placeSelectRing(sceneRef.current, selectedId);
  }, [selectedId]);

  if (webglFailed) {
    return <div className="loading">The 3D view needs WebGL, which this browser doesn't provide.</div>;
  }

  return (
    <div className="galaxy" ref={wrapRef}>
      <div ref={tooltipRef} className="tooltip" />
      {legend && (
        <div className="legend galaxy-legend">
          <div><span className="legend-dot" style={{ background: SEVERITY_COLOR.high }} /> High-severity conflict</div>
          <div><span className="legend-dot" style={{ background: SEVERITY_COLOR.moderate }} /> Moderate</div>
          <div><span className="legend-dot" style={{ background: SEVERITY_COLOR.low }} /> Low</div>
          <div><span className="legend-dot" style={{ background: SEVERITY_COLOR.none }} /> No conflicts</div>
          <div><span className="legend-ring" /> Match needs review</div>
          <div className="legend-note">Each star is a patient, placed between the hospitals that hold their records. Click one to open it.</div>
        </div>
      )}
    </div>
  );
}

function worstSeverity(p) {
  if (p.conflicts.high) return "high";
  if (p.conflicts.moderate) return "moderate";
  if (p.conflicts.low) return "low";
  return "none";
}

function describe(p, hospitals) {
  const where = p.hospitals.map((h) => hospitals[h]?.name ?? h).join(", ");
  const { high, moderate, low } = p.conflicts;
  const issues = high + moderate + low ? `${high} high, ${moderate} moderate, ${low} low` : "no conflicts";
  return `${p.name} (${p.birth_date}) · ${p.record_count} records at ${where} · ${issues}${p.needs_review ? " · match needs review" : ""}`;
}

// Where a patient's star goes: the middle of its hospitals, nudged by a stable per-patient
// offset so stars don't overlap. Single-hospital patients orbit their hospital's sun.
function patientPosition(p, hospitalPos) {
  const random = mulberry32(hash(p.id));
  const anchors = p.hospitals.map((h) => hospitalPos.get(h)).filter(Boolean);
  const center = new THREE.Vector3();
  anchors.forEach((a) => center.add(a));
  if (anchors.length) center.divideScalar(anchors.length);
  const direction = new THREE.Vector3(random() - 0.5, (random() - 0.5) * 1.4, random() - 0.5).normalize();
  const distance = anchors.length === 1 ? 6 + random() * 6 : 2 + random() * 5;
  return center.add(direction.multiplyScalar(distance));
}

function placeSelectRing({ stars, selectRing }, selectedId) {
  const star = stars.get(selectedId);
  selectRing.visible = !!star;
  if (star) {
    selectRing.position.copy(star.position);
    selectRing.scale.setScalar(star.userData.size * 1.15);
  }
}

function glowMaterial(texture, color, opacity) {
  return new THREE.SpriteMaterial({
    map: texture,
    color: new THREE.Color(color),
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
}

function label(text, className, color, offsetY) {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = text;
  if (color) el.style.color = color;
  const object = new CSS2DObject(el);
  object.position.set(0, offsetY, 0);
  return object;
}

function makeGlowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const g = canvas.getContext("2d");
  const gradient = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.12, "rgba(255,255,255,0.95)");
  gradient.addColorStop(0.35, "rgba(255,255,255,0.3)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gradient;
  g.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeRingTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const g = canvas.getContext("2d");
  g.strokeStyle = "rgba(255,255,255,0.9)";
  g.lineWidth = 5;
  g.beginPath();
  g.arc(64, 64, 52, 0, Math.PI * 2);
  g.stroke();
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// Small seeded random generator, so every patient lands in the same place on every load.
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(text) {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}
