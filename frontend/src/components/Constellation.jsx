import { useEffect, useRef } from "react";
import * as d3 from "d3";

const ITEM_COLOR = { allergy: "#ffb454", medication: "#6cc7ff", condition: "#b79cff" };
const SEVERITY_COLOR = { high: "#ff4d6d", moderate: "#ff9f43", low: "#ffd166" };
const RADIUS = { record: 13, allergy: 5, medication: 5, condition: 5 };
const STAR = d3.symbol().type(d3.symbolStar).size(420);

// Animation timeline (ms): each hospital's stars appear in turn, then the links form.
const PER_HOSPITAL = 450;
const FADE = 700;

/**
 * Draws one patient as a constellation: each hospital's record is a star surrounded by its
 * allergies, medications and conditions; gold lines link records that are the same person,
 * and red glowing lines connect items that conflict.
 */
export default function Constellation({
  graph,
  hospitals,
  selectedConflictId,
  selectedNodeId,
  onSelectConflict,
  onSelectNode,
  legend = true,
}) {
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  // Keep the latest callbacks without rebuilding the simulation when they change.
  const handlers = useRef({});
  handlers.current = { onSelectConflict, onSelectNode };

  useEffect(() => {
    const svgEl = svgRef.current;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    const defs = svg.append("defs");
    addGlow(defs, "glow", 2.5);
    addGlow(defs, "glow-strong", 6);
    const starfield = svg.append("g");

    const sky = svg.append("g");
    const zoom = d3.zoom().scaleExtent([0.3, 3]).on("zoom", (e) => sky.attr("transform", e.transform));
    svg
      .call(zoom)
      .on("dblclick.zoom", null)
      .on("click", () => {
        handlers.current.onSelectNode(null);
        handlers.current.onSelectConflict(null);
      });

    // Each hospital gets its own patch of sky, spaced around a circle. The positions are
    // recomputed whenever the container changes size (see the ResizeObserver below).
    const anchors = new Map(graph.hospitals.map((h, i) => [h.id, { ...h, index: i, x: 0, y: 0 }]));
    const layout = (width, height) => {
      const ringRadius = anchors.size > 1 ? Math.min(width, height) * 0.28 : 0;
      for (const a of anchors.values()) {
        const angle = -Math.PI / 2 + (a.index * 2 * Math.PI) / anchors.size;
        a.x = width / 2 + ringRadius * Math.cos(angle);
        a.y = height / 2 + ringRadius * Math.sin(angle);
      }
      starfield.selectAll("*").remove();
      drawStarfield(starfield, width, height);
    };
    const { clientWidth: width, clientHeight: height } = svgEl.parentElement; // layout size
    layout(width, height);
    const colorOf = (hospitalId) => hospitals[hospitalId]?.color ?? "#ffffff";

    const nodes = graph.nodes.map((d) => {
      const a = anchors.get(d.hospital);
      return { ...d, x: a.x + (Math.random() - 0.5) * 60, y: a.y + (Math.random() - 0.5) * 60 };
    });
    const links = graph.links.map((d) => ({ ...d }));

    const sim = d3
      .forceSimulation(nodes)
      .alphaDecay(0.04) // settle in about 3 seconds
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance((l) => (l.kind === "has" ? 60 : 200))
          .strength((l) => (l.kind === "has" ? 0.7 : l.kind === "match" ? 0.03 : 0.01)),
      )
      .force("charge", d3.forceManyBody().strength((d) => (d.kind === "record" ? -300 : -90)))
      .force("collide", d3.forceCollide((d) => RADIUS[d.kind] + 12))
      .force("x", d3.forceX((d) => anchors.get(d.hospital).x).strength((d) => (d.kind === "record" ? 0.3 : 0.05)))
      .force("y", d3.forceY((d) => anchors.get(d.hospital).y).strength((d) => (d.kind === "record" ? 0.3 : 0.05)));

    const byKind = (kind) => links.filter((l) => l.kind === kind);
    const hasLines = sky.append("g").selectAll("line").data(byKind("has")).join("line").attr("class", "link has");
    const matchLines = sky
      .append("g")
      .selectAll("line")
      .data(byKind("match"))
      .join("line")
      .attr("class", (d) => `link match ${d.tier}`);
    const matchLabels = sky
      .append("g")
      .selectAll("text")
      .data(byKind("match"))
      .join("text")
      .attr("class", (d) => `match-label ${d.tier}`)
      .attr("text-anchor", "middle")
      .text((d) =>
        d.reviewed === "same"
          ? "✓ confirmed"
          : `${Math.round(d.probability * 100)}%${d.tier === "review" ? " · review" : ""}`,
      );

    const conflicts = sky
      .append("g")
      .selectAll("g")
      .data(byKind("conflict"))
      .join("g")
      .attr("class", "conflict-link")
      .on("click", (e, d) => {
        e.stopPropagation();
        handlers.current.onSelectConflict(d.conflict_id);
      });
    conflicts
      .append("line")
      .attr("class", "link conflict")
      .attr("stroke", (d) => SEVERITY_COLOR[d.severity])
      .attr("filter", "url(#glow)");
    conflicts.append("line").attr("class", "hit"); // wide invisible line, easier to click
    const conflictLines = conflicts.selectAll("line");

    const tooltip = d3.select(tooltipRef.current);
    const nodeGroups = sky
      .append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", (d) => `node ${d.kind}`)
      .on("click", (e, d) => {
        e.stopPropagation();
        handlers.current.onSelectNode(d.id);
      })
      .on("mouseenter", (e, d) => tooltip.style("opacity", 1).text(`${d.label} · ${d.sublabel}`))
      .on("mousemove", (e) => {
        const [x, y] = d3.pointer(e, svgEl);
        tooltip.style("left", `${x + 14}px`).style("top", `${y + 14}px`);
      })
      .on("mouseleave", () => tooltip.style("opacity", 0))
      .call(drag(sim));

    nodeGroups
      .append("circle")
      .attr("class", "halo")
      .attr("r", (d) => RADIUS[d.kind] * 2.4)
      .attr("fill", (d) => (d.kind === "record" ? colorOf(d.hospital) : ITEM_COLOR[d.kind]));
    nodeGroups
      .filter((d) => d.kind === "record")
      .append("path")
      .attr("class", "core")
      .attr("d", STAR)
      .attr("fill", "#fff")
      .attr("stroke", (d) => colorOf(d.hospital))
      .attr("stroke-width", 2)
      .attr("filter", "url(#glow)");
    nodeGroups
      .filter((d) => d.kind !== "record")
      .append("circle")
      .attr("class", "core")
      .attr("r", (d) => RADIUS[d.kind])
      .attr("fill", (d) => ITEM_COLOR[d.kind])
      .attr("filter", "url(#glow)");
    // Each record star is labelled with the patient's name as that hospital spells it,
    // plus the hospital's name in its color.
    const recordLabels = nodeGroups
      .filter((d) => d.kind === "record")
      .append("text")
      .attr("class", "record-label")
      .attr("text-anchor", "middle");
    recordLabels.append("tspan").attr("x", 0).attr("dy", 30).text((d) => d.label);
    recordLabels
      .append("tspan")
      .attr("class", "record-hospital")
      .attr("x", 0)
      .attr("dy", 14)
      .attr("fill", (d) => colorOf(d.hospital))
      .text((d) => hospitals[d.hospital]?.name ?? d.hospital);
    const itemLabels = nodeGroups
      .filter((d) => d.kind !== "record")
      .append("text")
      .attr("class", "item-label")
      .attr("dy", 4)
      .text((d) => d.label);
    const recordOf = new Map(nodes.filter((d) => d.kind === "record").map((d) => [d.id, d]));
    const isLeftOfRecord = (d) => d.x < recordOf.get(d.record).x;

    // The constellation forms: stars hospital by hospital, then matches, then conflicts.
    const delayOf = (hospitalId) => anchors.get(hospitalId).index * PER_HOSPITAL;
    const formed = graph.hospitals.length * PER_HOSPITAL + FADE;
    nodeGroups
      .attr("opacity", 0)
      .transition()
      .delay((d) => delayOf(d.hospital) + (d.kind === "record" ? 0 : 150 + Math.random() * 300))
      .duration(FADE)
      .attr("opacity", 1);
    hasLines
      .attr("opacity", 0)
      .transition()
      .delay((d) => delayOf(d.source.hospital) + 300)
      .duration(FADE)
      .attr("opacity", 1);
    for (const selection of [matchLines, matchLabels]) {
      selection.attr("opacity", 0).transition().delay(formed).duration(900).attr("opacity", 1);
    }
    conflicts
      .attr("opacity", 0)
      .transition()
      .delay(formed + 900)
      .duration(600)
      .attr("opacity", 1)
      .on("end", function () {
        d3.select(this).classed("pulse", true);
      });

    sim.on("tick", () => {
      for (const selection of [hasLines, matchLines, conflictLines]) {
        selection
          .attr("x1", (d) => d.source.x)
          .attr("y1", (d) => d.source.y)
          .attr("x2", (d) => d.target.x)
          .attr("y2", (d) => d.target.y);
      }
      matchLabels
        .attr("x", (d) => (d.source.x + d.target.x) / 2)
        .attr("y", (d) => (d.source.y + d.target.y) / 2 - 6);
      nodeGroups.attr("transform", (d) => `translate(${d.x},${d.y})`);
      // Put each item's label on the side facing away from its record star.
      itemLabels
        .attr("text-anchor", (d) => (isLeftOfRecord(d) ? "end" : "start"))
        .attr("dx", (d) => (isLeftOfRecord(d) ? -9 : 9));
    });

    // Once the layout settles, zoom out (never in) so every star and label is on screen.
    // Only once per layout, so dragging a star doesn't yank the view around.
    let size = { width, height };
    let fitted = false;
    sim.on("end", () => {
      const box = sky.node().getBBox();
      if (fitted || !box.width || !box.height || !size.width || !size.height) return;
      fitted = true;
      const pad = 30;
      const scale = Math.min(1, (size.width - 2 * pad) / box.width, (size.height - 2 * pad) / box.height);
      const x = size.width / 2 - scale * (box.x + box.width / 2);
      const y = size.height / 2 - scale * (box.y + box.height / 2);
      svg.transition().duration(700).call(zoom.transform, d3.zoomIdentity.translate(x, y).scale(scale));
    });

    // Follow the container's size: the first measurement can be 0 (hidden pane, layout not
    // settled), and the window can be resized or moved to a projector mid-demo.
    const observer = new ResizeObserver(([entry]) => {
      const { width: w, height: h } = entry.contentRect;
      if (!w || !h || (w === size.width && h === size.height)) return;
      size = { width: w, height: h };
      fitted = false;
      layout(w, h);
      sim.force("x").x((d) => anchors.get(d.hospital).x);
      sim.force("y").y((d) => anchors.get(d.hospital).y);
      sim.alpha(0.6).restart();
    });
    observer.observe(svgEl.parentElement);

    return () => {
      sim.stop();
      observer.disconnect();
    };
  }, [graph, hospitals]);

  // Highlight the selected conflict (and its two stars) without rebuilding the scene.
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const selected = graph.links.find((l) => l.kind === "conflict" && l.conflict_id === selectedConflictId);
    const focus = new Set(selected ? [selected.source, selected.target] : []);
    if (selectedNodeId) focus.add(selectedNodeId);
    svg
      .selectAll(".conflict-link")
      .classed("selected", (d) => d.conflict_id === selectedConflictId)
      .classed("dimmed", (d) => selected != null && d.conflict_id !== selectedConflictId)
      .select(".link")
      .attr("filter", (d) => (d.conflict_id === selectedConflictId ? "url(#glow-strong)" : "url(#glow)"));
    svg.selectAll(".node").classed("selected", (d) => focus.has(d.id));
  }, [graph, selectedConflictId, selectedNodeId]);

  return (
    <div className="constellation">
      <svg ref={svgRef} className="constellation-svg" />
      <div ref={tooltipRef} className="tooltip" />
      {legend && <Legend />}
    </div>
  );
}

function Legend() {
  return (
    <div className="legend">
      <div><span className="legend-star">✦</span> Hospital record</div>
      <div><span className="legend-dot" style={{ background: ITEM_COLOR.allergy }} /> Allergy</div>
      <div><span className="legend-dot" style={{ background: ITEM_COLOR.medication }} /> Medication</div>
      <div><span className="legend-dot" style={{ background: ITEM_COLOR.condition }} /> Condition</div>
      <div><span className="legend-line match" /> Same person</div>
      <div><span className="legend-line review" /> Possible match</div>
      <div><span className="legend-line conflict" /> Conflict (click it)</div>
    </div>
  );
}

function addGlow(defs, id, blur) {
  const filter = defs
    .append("filter")
    .attr("id", id)
    .attr("x", "-100%")
    .attr("y", "-100%")
    .attr("width", "300%")
    .attr("height", "300%");
  filter.append("feGaussianBlur").attr("stdDeviation", blur).attr("result", "blur");
  const merge = filter.append("feMerge");
  merge.append("feMergeNode").attr("in", "blur");
  merge.append("feMergeNode").attr("in", "SourceGraphic");
}

function drawStarfield(group, width, height) {
  const random = d3.randomLcg(42);
  const stars = d3.range(220).map(() => ({
    x: random() * width,
    y: random() * height,
    r: random() * 1.1 + 0.2,
    delay: random() * 5,
  }));
  group
    .selectAll("circle")
    .data(stars)
    .join("circle")
    .attr("class", "bg-star")
    .attr("cx", (d) => d.x)
    .attr("cy", (d) => d.y)
    .attr("r", (d) => d.r)
    .style("animation-delay", (d) => `${d.delay}s`);
}

function drag(sim) {
  return d3
    .drag()
    .on("start", (e, d) => {
      if (!e.active) sim.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on("drag", (e, d) => {
      d.fx = e.x;
      d.fy = e.y;
    })
    .on("end", (e, d) => {
      if (!e.active) sim.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    });
}
