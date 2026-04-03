/**
 * GenealogyMap — D3.js force-directed graph.
 *
 * Data contract:
 *   nodes: [{ id, name, depth_level, underground_score, lastfm_listeners,
 *              formation_year, country, image_url, tags, genres }]
 *   edges: [{ source, target, strength, confidence, source_type,
 *              musicbrainz_type }]
 */
import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";

// ─── Visual constants ────────────────────────────────────────────────────────

const DEPTH_RADII   = [44, 32, 24, 18, 14];
const BG            = "#0A0B0F";
const SURFACE       = "#14161E";
const BORDER        = "#2A2D3A";
const TEXT_PRIMARY  = "#F0F0F5";
const TEXT_MUTED    = "#4B4F63";
const COL_PURPLE    = "#7C5CFC";
const COL_TEAL      = "#3AAFB9";
const COL_GREEN     = "#10B981";
const COL_AMBER     = "#F59E0B";

// underground_score 0 → purple (mainstream), 1 → green (deep underground)
const colorScale = d3
  .scaleLinear()
  .domain([0, 0.35, 0.70, 1.0])
  .range([COL_PURPLE, "#5B8FC4", COL_TEAL, COL_GREEN])
  .interpolate(d3.interpolateRgb.gamma(2.2));

// ─── Helpers ─────────────────────────────────────────────────────────────────

function nodeRadius(depth, score) {
  const base  = DEPTH_RADII[Math.min(depth ?? 0, 4)];
  const bonus = (score ?? 0) > 0.7 ? 1.2 : 1.0;
  return Math.round(base * bonus);
}

function nodeColor(score) {
  return colorScale(Math.min(1, Math.max(0, score ?? 0)));
}

function edgeColor(sourceType) {
  if (sourceType === "musicbrainz")          return COL_PURPLE;
  if (sourceType === "lastfm_similar")       return COL_TEAL;
  if (sourceType === "matrix_similarity")    return COL_AMBER;
  if (sourceType === "embedding_similarity") return COL_TEAL;
  if (sourceType === "audio_similarity")     return "#E879F9"; // pink-violet
  if (sourceType === "lyric_similarity")     return "#FB923C"; // orange
  if (sourceType === "production_link")      return "#34D399"; // emerald
  if (sourceType === "fusion")               return "#94A3B8"; // slate
  return "#4B5069";
}

function edgeDash(sourceType) {
  if (sourceType === "musicbrainz")          return null;      // solid
  if (sourceType === "lastfm_similar")       return "8,5";     // dashed
  if (sourceType === "matrix_similarity")    return "5,3,2,3"; // dash-dot
  if (sourceType === "embedding_similarity") return "3,6";     // dotted
  if (sourceType === "audio_similarity")     return "6,4";     // dashed
  if (sourceType === "lyric_similarity")     return "4,4";     // even dash
  if (sourceType === "production_link")      return "8,3,2,3"; // dash-dot
  if (sourceType === "fusion")               return "2,4";     // fine dots
  return "3,6";
}

function edgeRelationLabel(edge) {
  if (
    edge.source_type     === "musicbrainz" &&
    edge.musicbrainz_type === "influenced by"
  ) return "influenced by";
  if (edge.source_type === "musicbrainz") return "connected";
  if (edge.source_type === "matrix_similarity") return "suggested connection";
  if (edge.source_type === "embedding_similarity") return "vector proximity";
  if (edge.source_type === "audio_similarity") return "sonic similarity";
  if (edge.source_type === "lyric_similarity") return "lyrical kinship";
  if (edge.source_type === "production_link") return "shared production";
  if (edge.source_type === "fusion") return "multi-signal match";
  return "from the same scene";
}

function linkDistance(edge) {
  const depthLevel = edge.source?.depth_level ?? 0;
  const base = [130, 150, 175, 200][Math.min(depthLevel, 3)];
  return base + (1 - (edge.strength ?? 0.5)) * 40;
}

function truncate(str, max = 18) {
  if (!str) return "?";
  return str.length > max ? str.slice(0, max - 1) + "…" : str;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function GenealogyMap({
  data,
  onNodeSelect,
  selectedNode,
  filters = {},
}) {
  const containerRef    = useRef(null);
  const svgRef          = useRef(null);
  const simRef          = useRef(null);
  const zoomRef         = useRef(null);
  const tooltipRef      = useRef(null);
  const onSelectRef     = useRef(onNodeSelect);

  // Keep callback ref fresh without restarting simulation
  useEffect(() => { onSelectRef.current = onNodeSelect; }, [onNodeSelect]);

  // ── Zoom controls ──────────────────────────────────────────────────────────
  const zoomIn = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current)
      .transition().duration(280)
      .call(zoomRef.current.scaleBy, 1.45);
  }, []);

  const zoomOut = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current)
      .transition().duration(280)
      .call(zoomRef.current.scaleBy, 1 / 1.45);
  }, []);

  const resetZoom = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current)
      .transition().duration(380)
      .call(zoomRef.current.transform, d3.zoomIdentity);
  }, []);

  // ── Tooltip helpers ────────────────────────────────────────────────────────
  const showTooltip = useCallback((html, x, y) => {
    const el = tooltipRef.current;
    if (!el) return;
    el.innerHTML   = html;
    el.style.left  = `${x + 14}px`;
    el.style.top   = `${y - 10}px`;
    el.style.opacity = "1";
    el.style.pointerEvents = "none";
  }, []);

  const hideTooltip = useCallback(() => {
    const el = tooltipRef.current;
    if (el) el.style.opacity = "0";
  }, []);

  // ── Main D3 build ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!svgRef.current || !containerRef.current || !data?.nodes?.length) return;

    const container = containerRef.current;
    let { clientWidth: W, clientHeight: H } = container;
    if (W < 1 || H < 1) { W = 800; H = 600; }

    const svg    = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    if (simRef.current) simRef.current.stop();

    // ── SVG defs ──────────────────────────────────────────────────────────
    const defs = svg.append("defs");

    // Glow filter — underground nodes
    const glow = defs.append("filter")
      .attr("id", "glow")
      .attr("x", "-60%").attr("y", "-60%")
      .attr("width", "220%").attr("height", "220%");
    glow.append("feGaussianBlur").attr("stdDeviation", "5").attr("result", "blur");
    const glowMerge = glow.append("feMerge");
    glowMerge.append("feMergeNode").attr("in", "blur");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Root glow — root artist node
    const rootGlow = defs.append("filter")
      .attr("id", "root-glow")
      .attr("x", "-80%").attr("y", "-80%")
      .attr("width", "260%").attr("height", "260%");
    rootGlow.append("feGaussianBlur").attr("stdDeviation", "10").attr("result", "blur");
    const rootMerge = rootGlow.append("feMerge");
    rootMerge.append("feMergeNode").attr("in", "blur");
    rootMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Arrow markers
    [
      { id: "arrow-mb",     color: COL_PURPLE  },
      { id: "arrow-lfm",    color: COL_TEAL    },
      { id: "arrow-matrix", color: COL_AMBER   },
      { id: "arrow-embed",  color: COL_TEAL    },
      { id: "arrow-audio",  color: "#E879F9"   },
      { id: "arrow-lyric",  color: "#FB923C"   },
      { id: "arrow-prod",   color: "#34D399"   },
      { id: "arrow-fusion", color: "#94A3B8"   },
      { id: "arrow-tag",    color: "#4B5069"   },
    ].forEach(({ id, color }) => {
      defs.append("marker")
        .attr("id", id)
        .attr("viewBox", "0 0 10 10")
        .attr("refX", 10).attr("refY", 5)
        .attr("markerWidth", 5).attr("markerHeight", 5)
        .attr("orient", "auto-start-reverse")
        .append("path")
        .attr("d", "M 0 0 L 10 5 L 0 10 z")
        .attr("fill", color).attr("opacity", 0.55);
    });

    // ── Clone data (simulation mutates x/y) ───────────────────────────────
    const isSparse = data.nodes.length <= 10;

    const nodes = data.nodes.map((n) => ({
      ...n,
      _r: nodeRadius(n.depth_level ?? 0, n.underground_score ?? 0),
    }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    const edges = data.edges
      .map((e) => ({
        ...e,
        source: nodeById.get(e.source) ?? e.source,
        target: nodeById.get(e.target) ?? e.target,
      }))
      .filter(
        (e) => typeof e.source === "object" && typeof e.target === "object"
      );

    // ── Simulation ────────────────────────────────────────────────────────
    const sim = d3.forceSimulation(nodes)
      .force(
        "link",
        d3.forceLink(edges)
          .id((d) => d.id)
          .distance((d) => linkDistance(d))
          .strength(0.65)
      )
      .force(
        "charge",
        d3.forceManyBody()
          .strength(isSparse ? -280 : -420)
          .distanceMax(550)
      )
      .force(
        "center",
        d3.forceCenter(W / 2, H / 2).strength(isSparse ? 0.5 : 0.25)
      )
      .force(
        "collide",
        d3.forceCollide()
          .radius((d) => d._r + 14)
          .strength(0.85)
      )
      .force("x", d3.forceX(W / 2).strength(isSparse ? 0.08 : 0.025))
      .force("y", d3.forceY(H / 2).strength(isSparse ? 0.08 : 0.025));

    simRef.current = sim;

    // ── Canvas group (zoom target) ─────────────────────────────────────────
    const canvas = svg.append("g").attr("class", "canvas");
    const edgeG  = canvas.append("g").attr("class", "edges");
    const nodeG  = canvas.append("g").attr("class", "nodes");

    // ── Edges ──────────────────────────────────────────────────────────────
    const edgeSel = edgeG
      .selectAll("g.edge")
      .data(edges, (e) => `${e.source.id}→${e.target.id}`)
      .join((enter) => {
        const g = enter.append("g").attr("class", "edge");

        // Visible line
        g.append("line")
          .attr("class", "edge-line")
          .attr("stroke",          (e) => edgeColor(e.source_type))
          .attr("stroke-dasharray",(e) => edgeDash(e.source_type) ?? null)
          .attr("stroke-width",    (e) => Math.max(0.8, (e.strength ?? 0.5) * 2.8))
          .attr("stroke-opacity",  (e) => 0.28 + (e.confidence ?? 0.5) * 0.45)
          .attr("marker-end",      (e) => {
            if (e.source_type === "musicbrainz")          return "url(#arrow-mb)";
            if (e.source_type === "lastfm_similar")       return "url(#arrow-lfm)";
            if (e.source_type === "matrix_similarity")    return "url(#arrow-matrix)";
            if (e.source_type === "embedding_similarity") return "url(#arrow-embed)";
            if (e.source_type === "audio_similarity")     return "url(#arrow-audio)";
            if (e.source_type === "lyric_similarity")     return "url(#arrow-lyric)";
            if (e.source_type === "production_link")      return "url(#arrow-prod)";
            if (e.source_type === "fusion")               return "url(#arrow-fusion)";
            return "url(#arrow-tag)";
          });

        // Invisible wide hit-target
        g.append("line")
          .attr("class", "edge-hit")
          .attr("stroke", "transparent")
          .attr("stroke-width", 18)
          .style("cursor", "crosshair")
          .on("mouseenter", (event, e) => {
            const [mx, my] = d3.pointer(event, container);
            showTooltip(
              `<div class="tt-edge">
                <p class="tt-title">${edgeRelationLabel(e)}</p>
                <p class="tt-sub">${Math.round((e.strength ?? 0) * 100)}% strength
                  &nbsp;·&nbsp; ${Math.round((e.confidence ?? 0) * 100)}% confidence</p>
                <p class="tt-source" style="color:${edgeColor(e.source_type)}">
                  ${e.source_type === "musicbrainz" ? "Documented · MusicBrainz"
                    : e.source_type === "matrix_similarity" ? "Suggested · Similarity Matrix"
                    : e.source_type === "embedding_similarity" ? "Vector proximity · Embedding"
                    : e.source_type === "audio_similarity" ? "Sonic match · Audio Analysis"
                    : e.source_type === "lyric_similarity" ? "Thematic match · Lyric Analysis"
                    : e.source_type === "production_link" ? "Shared credits · Production Network"
                    : e.source_type === "fusion" ? "Multi-signal · Fusion Engine"
                    : "Last.fm listener data"}
                </p>
              </div>`,
              mx, my
            );
            d3.select(event.currentTarget.previousSibling)
              .transition().duration(120)
              .attr("stroke-opacity", 1)
              .attr("stroke-width", (e2) => Math.max(1.5, (e2.strength ?? 0.5) * 4.5));
          })
          .on("mouseleave", (event) => {
            hideTooltip();
            d3.select(event.currentTarget.previousSibling)
              .transition().duration(160)
              .attr("stroke-opacity", (e2) => 0.28 + (e2.confidence ?? 0.5) * 0.45)
              .attr("stroke-width",   (e2) => Math.max(0.8, (e2.strength ?? 0.5) * 2.8));
          });

        g.style("opacity", 0)
          .transition().duration(500)
          .style("opacity", 1);

        return g;
      });

    // ── Nodes ──────────────────────────────────────────────────────────────
    function dragBehavior() {
      return d3.drag()
        .on("start", (event, d) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event) => {
          if (!event.active) sim.alphaTarget(0);
          // Node stays pinned; double-click to release
        });
    }

    const nodeSel = nodeG
      .selectAll("g.node")
      .data(nodes, (d) => d.id)
      .join((enter) => {
        const g = enter
          .append("g")
          .attr("class", "node")
          .style("cursor", "pointer")
          .call(dragBehavior())
          .on("click", (event, d) => {
            event.stopPropagation();
            onSelectRef.current?.(d);
          })
          .on("dblclick", (event, d) => {
            event.stopPropagation();
            d.fx = null;
            d.fy = null;
            sim.alphaTarget(0.2).restart();
            setTimeout(() => sim.alphaTarget(0), 250);
          })
          .on("mouseenter", (event, d) => {
            const [mx, my] = d3.pointer(event, container);
            const listenersStr = d.lastfm_listeners
              ? `${d.lastfm_listeners.toLocaleString()} Last.fm listeners`
              : "";
            showTooltip(
              `<div class="tt-node">
                <p class="tt-title">${d.name}</p>
                ${d.formation_year ? `<p class="tt-sub">${d.formation_year}${d.country ? " · " + d.country : ""}</p>` : ""}
                ${listenersStr ? `<p class="tt-sub tt-mono">${listenersStr}</p>` : ""}
                <p class="tt-score" style="color:${nodeColor(d.underground_score ?? 0)}">
                  ${Math.round((d.underground_score ?? 0) * 100)}% underground
                </p>
              </div>`,
              mx, my - d._r - 12
            );

            // Highlight connected edges
            edgeSel.selectAll("line.edge-line")
              .transition().duration(140)
              .attr("stroke-opacity", (e) => {
                const connected = e.source.id === d.id || e.target.id === d.id;
                return connected ? 1 : 0.04;
              })
              .attr("stroke-width", (e) => {
                const connected = e.source.id === d.id || e.target.id === d.id;
                return connected
                  ? Math.max(1.5, (e.strength ?? 0.5) * 4)
                  : Math.max(0.8, (e.strength ?? 0.5) * 2.8);
              });

            // Dim unrelated nodes
            nodeSel.transition().duration(140)
              .style("opacity", (n) => {
                if (n.id === d.id) return 1;
                const linked = edges.some(
                  (e) =>
                    (e.source.id === d.id && e.target.id === n.id) ||
                    (e.target.id === d.id && e.source.id === n.id)
                );
                return linked ? 1 : 0.18;
              });

            // Show label for hovered node
            d3.select(event.currentTarget)
              .select("text.node-label")
              .transition().duration(120)
              .attr("opacity", 1);
          })
          .on("mouseleave", (event) => {
            hideTooltip();
            edgeSel.selectAll("line.edge-line")
              .transition().duration(180)
              .attr("stroke-opacity", (e) => 0.28 + (e.confidence ?? 0.5) * 0.45)
              .attr("stroke-width",   (e) => Math.max(0.8, (e.strength ?? 0.5) * 2.8));
            nodeSel.transition().duration(180).style("opacity", 1);
            // Hide label if depth >= 2
            d3.select(event.currentTarget)
              .select("text.node-label")
              .transition().duration(120)
              .attr("opacity", (d) => d.depth_level <= 1 ? 1 : 0);
          });

        const col = (d) => nodeColor(d.underground_score ?? 0);

        // Outer pulse ring
        g.append("circle")
          .attr("class", "node-ring")
          .attr("r",             (d) => d._r + 5)
          .attr("fill",          "none")
          .attr("stroke",        col)
          .attr("stroke-width",  1.5)
          .attr("stroke-opacity",(d) => (d.underground_score ?? 0) > 0.7 ? 0.45 : 0.18);

        // Main filled circle
        g.append("circle")
          .attr("class", "node-circle")
          .attr("r",            (d) => d._r)
          .attr("fill",         (d) => `${nodeColor(d.underground_score ?? 0)}28`)
          .attr("stroke",       col)
          .attr("stroke-width", (d) => d.depth_level === 0 ? 2.5 : 1.8);

        // Artist image (with fallback on error)
        g.each(function (d) {
          if (!d.image_url) return;
          const safe    = d.id.replace(/[^a-zA-Z0-9]/g, "_");
          const clipId  = `clip-${safe}`;
          defs.append("clipPath")
            .attr("id", clipId)
            .append("circle")
            .attr("r", d._r - 2);
          d3.select(this)
            .append("image")
            .attr("href", d.image_url)
            .attr("x",  -(d._r - 2)).attr("y", -(d._r - 2))
            .attr("width",  (d._r - 2) * 2).attr("height", (d._r - 2) * 2)
            .attr("clip-path", `url(#${clipId})`)
            .attr("preserveAspectRatio", "xMidYMid slice")
            .on("error", function () { d3.select(this).remove(); });
        });

        // Fallback letter initial
        g.append("text")
          .attr("class", "node-initial")
          .attr("text-anchor",       "middle")
          .attr("dominant-baseline", "central")
          .attr("fill",        col)
          .attr("font-size",   (d) => Math.max(10, d._r * 0.52))
          .attr("font-weight", "600")
          .attr("font-family", "Inter, system-ui, sans-serif")
          .attr("pointer-events", "none")
          .style("display", (d) => d.image_url ? "none" : "block")
          .text((d) => (d.name ?? "?").charAt(0).toUpperCase());

        // Name label
        g.append("text")
          .attr("class", "node-label")
          .attr("text-anchor",  "middle")
          .attr("y",            (d) => d._r + 15)
          .attr("fill",         TEXT_PRIMARY)
          .attr("font-size",    (d) => d.depth_level === 0 ? 13 : d.depth_level === 1 ? 11 : 10)
          .attr("font-weight",  (d) => d.depth_level <= 1 ? "600" : "400")
          .attr("font-family",  "Inter, system-ui, sans-serif")
          .attr("pointer-events", "none")
          .attr("opacity",      (d) => d.depth_level <= 1 ? 1 : 0)
          .text((d) => truncate(d.name, 20));

        // Glow effects
        g.filter((d) => d.depth_level === 0)
          .select("circle.node-circle")
          .attr("filter", "url(#root-glow)");
        g.filter((d) => (d.underground_score ?? 0) > 0.7 && d.depth_level !== 0)
          .select("circle.node-circle")
          .attr("filter", "url(#glow)");

        // Animate in
        g.attr("transform", `translate(${W / 2},${H / 2})`)
          .style("opacity", 0)
          .transition()
          .duration(550)
          .delay((_, i) => i * 22)
          .style("opacity", 1);

        return g;
      });

    // ── Tick ──────────────────────────────────────────────────────────────
    sim.on("tick", () => {
      // Edge: line from source circle edge → target circle edge
      edgeSel.selectAll("line").each(function (e) {
        const dx   = e.target.x - e.source.x;
        const dy   = e.target.y - e.source.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) return;
        const srcR = e.source._r;
        const tgtR = e.target._r + 6; // small gap for arrowhead
        d3.select(this)
          .attr("x1", e.source.x + (dx / dist) * srcR)
          .attr("y1", e.source.y + (dy / dist) * srcR)
          .attr("x2", e.target.x - (dx / dist) * tgtR)
          .attr("y2", e.target.y - (dy / dist) * tgtR);
      });

      nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    // ── Zoom ──────────────────────────────────────────────────────────────
    const zoom = d3.zoom()
      .scaleExtent([0.08, 10])
      .on("zoom", (event) => {
        canvas.attr("transform", event.transform);
      });

    svg.call(zoom);
    svg.on("dblclick.zoom", () => {
      svg.transition().duration(380)
        .call(zoom.transform, d3.zoomIdentity);
    });
    svg.on("click", (event) => {
      if (event.target === svgRef.current) onSelectRef.current?.(null);
    });
    zoomRef.current = zoom;

    // ── ResizeObserver ────────────────────────────────────────────────────
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width < 10 || height < 10) return;
      sim
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("x",      d3.forceX(width / 2).strength(isSparse ? 0.08 : 0.025))
        .force("y",      d3.forceY(height / 2).strength(isSparse ? 0.08 : 0.025))
        .alpha(0.15)
        .restart();
    });
    ro.observe(container);

    return () => {
      sim.stop();
      ro.disconnect();
    };
  }, [data, showTooltip, hideTooltip]);

  // ── Selection highlight (no sim restart) ──────────────────────────────────
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("g.node circle.node-ring")
      .transition().duration(200)
      .attr("stroke-width", (d) =>
        selectedNode?.id === d.id ? 3 : 1.5
      )
      .attr("stroke-opacity", (d) => {
        if (!selectedNode)            return (d.underground_score ?? 0) > 0.7 ? 0.45 : 0.18;
        if (selectedNode.id === d.id) return 1;
        return (d.underground_score ?? 0) > 0.7 ? 0.25 : 0.08;
      });
    svg.selectAll("g.node circle.node-circle")
      .transition().duration(200)
      .attr("stroke-width", (d) =>
        selectedNode?.id === d.id
          ? d.depth_level === 0 ? 3 : 2.5
          : d.depth_level === 0 ? 2.5 : 1.8
      );
  }, [selectedNode]);

  // ── Filter visibility (no sim restart) ────────────────────────────────────
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);

    svg.selectAll("g.node").transition().duration(200).style("opacity", (d) => {
      if (filters.underground_only && (d.underground_score ?? 0) < 0.4) return 0.12;
      if (filters.geo && d.country && d.country.toLowerCase() !== filters.geo.toLowerCase()) return 0.12;
      if (filters.era) {
        const dec = Math.floor((d.formation_year ?? 0) / 10) * 10;
        if (String(dec) !== String(filters.era) && d.depth_level !== 0) return 0.12;
      }
      return 1;
    });

    svg.selectAll("g.edge").transition().duration(200).style("opacity", (e) => {
      if (filters.source_type && e.source_type !== filters.source_type) return 0.05;
      return 1;
    });
  }, [filters]);

  // ─── Render ──────────────────────────────────────────────────────────────
  const nodeCount  = data?.nodes?.length ?? 0;
  const isSparse   = nodeCount > 0 && nodeCount <= 10;
  const isEmpty    = nodeCount === 0;

  return (
    <div ref={containerRef} className="relative w-full h-full overflow-hidden" style={{ background: BG }}>

      {/* D3 canvas */}
      {!isEmpty && (
        <svg ref={svgRef} className="w-full h-full" style={{ display: "block" }} />
      )}

      {/* Empty state */}
      {isEmpty && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-8 animate-fade-in">
          <div
            className="w-14 h-14 rounded-2xl border flex items-center justify-center mb-5"
            style={{ background: SURFACE, borderColor: BORDER }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ color: TEXT_MUTED }}>
              <circle cx="12" cy="5"  r="3" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="5"  cy="19" r="3" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="19" cy="19" r="3" stroke="currentColor" strokeWidth="1.5" />
              <path d="M12 8v7M9.5 17.5L6.5 17M14.5 17.5L17.5 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <p className="text-sm font-medium" style={{ color: TEXT_PRIMARY }}>No lineage data</p>
          <p className="text-xs mt-1.5 max-w-xs" style={{ color: TEXT_MUTED }}>
            Search for an artist to explore their connections and underground roots.
          </p>
        </div>
      )}

      {/* Sparse state note */}
      {isSparse && !isEmpty && (
        <div
          className="absolute bottom-5 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl border backdrop-blur-md animate-fade-in"
          style={{ background: `${SURFACE}E8`, borderColor: `${COL_TEAL}40` }}
        >
          <p className="text-xs text-center" style={{ color: COL_TEAL }}>
            {nodeCount} connections mapped — limited data available for this artist
          </p>
        </div>
      )}

      {/* Zoom controls */}
      <div className="absolute top-4 right-4 flex flex-col gap-1.5 z-10">
        {[
          { onClick: zoomIn,    title: "Zoom in",    icon: "M6 2v8M2 6h8", cx: "6 2v8M2 6h8" },
          { onClick: zoomOut,   title: "Zoom out",   icon: "M2 6h8" },
          { onClick: resetZoom, title: "Reset view", icon: "M2 2h3M2 2v3M10 10H7M10 10V7M2 10h3M2 10V7M10 2H7M10 2v3" },
        ].map(({ onClick, title, icon }) => (
          <button
            key={title}
            onClick={onClick}
            title={title}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150"
            style={{
              background: `${SURFACE}E8`,
              border: `1px solid ${BORDER}`,
              color: TEXT_MUTED,
              backdropFilter: "blur(8px)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = TEXT_PRIMARY;
              e.currentTarget.style.borderColor = `${COL_PURPLE}60`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = TEXT_MUTED;
              e.currentTarget.style.borderColor = BORDER;
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d={icon} stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        ))}
      </div>

      {/* Legend */}
      <div
        className="absolute bottom-4 left-4 rounded-xl p-3 space-y-3 z-10"
        style={{ background: `${SURFACE}E8`, border: `1px solid ${BORDER}`, backdropFilter: "blur(8px)" }}
      >
        <div>
          <p className="text-2xs uppercase tracking-wider font-medium mb-2" style={{ color: TEXT_MUTED }}>
            Connections
          </p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke={COL_PURPLE} strokeWidth="1.5" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Documented influence</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke={COL_TEAL} strokeWidth="1.5" strokeDasharray="5,3" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Scene connection</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke={COL_TEAL} strokeWidth="1.5" strokeDasharray="3,6" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Embedding proximity</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke="#E879F9" strokeWidth="1.5" strokeDasharray="6,4" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Sonic similarity</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke="#FB923C" strokeWidth="1.5" strokeDasharray="4,4" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Lyrical kinship</span>
            </div>
            <div className="flex items-center gap-2">
              <svg width="24" height="4" viewBox="0 0 24 4">
                <line x1="0" y1="2" x2="24" y2="2" stroke="#34D399" strokeWidth="1.5" strokeDasharray="8,3,2,3" />
              </svg>
              <span className="text-2xs" style={{ color: "#8B8FA3" }}>Shared production</span>
            </div>
          </div>
        </div>

        <div className="border-t pt-2.5" style={{ borderColor: BORDER }}>
          <p className="text-2xs uppercase tracking-wider font-medium mb-2" style={{ color: TEXT_MUTED }}>
            Nodes
          </p>
          <div className="flex items-center gap-1.5">
            {[COL_PURPLE, "#5B8FC4", COL_TEAL, COL_GREEN].map((c, i) => (
              <div
                key={i}
                className="rounded-full"
                style={{
                  width:  `${14 - i * 2}px`,
                  height: `${14 - i * 2}px`,
                  background: c,
                  opacity: 0.8,
                }}
              />
            ))}
            <span className="text-2xs ml-0.5" style={{ color: TEXT_MUTED }}>mainstream → underground</span>
          </div>
        </div>
      </div>

      {/* Tooltip (DOM-managed, not React state for perf) */}
      <div
        ref={tooltipRef}
        className="absolute z-50 rounded-xl pointer-events-none"
        style={{
          opacity: 0,
          transition: "opacity 0.1s ease",
          background: `${SURFACE}F5`,
          border: `1px solid ${BORDER}`,
          backdropFilter: "blur(12px)",
          padding: "10px 13px",
          boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
          maxWidth: "220px",
        }}
      />

      {/* Inline tooltip styles */}
      <style>{`
        .tt-title  { font-size:12px; font-weight:600; color:${TEXT_PRIMARY}; margin-bottom:3px; }
        .tt-sub    { font-size:11px; color:#8B8FA3; margin-top:2px; }
        .tt-mono   { font-family: "JetBrains Mono", monospace; }
        .tt-score  { font-size:11px; font-weight:500; margin-top:4px; }
        .tt-source { font-size:11px; font-weight:500; margin-top:3px; }
      `}</style>
    </div>
  );
}
