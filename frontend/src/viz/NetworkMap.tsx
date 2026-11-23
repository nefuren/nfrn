import { easeCubicOut } from "d3-ease";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type ForceLink,
  type Simulation,
} from "d3-force";
import { select } from "d3-selection";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { NEON } from "../lib/colors";
import type { Remote } from "../lib/types";
import { buildGraph, type GraphLink, type GraphNode, type Tone } from "./graph";

// 注意: 外部由来の文字列（IP・国コード・ホスト名・プロセス名）は必ず .text() / React のテキストで描く。
// .html() は ESLint で禁止している。

export const TONE_COLOR: Record<Tone, string> = {
  self: NEON.cyan,
  public: NEON.cyan,
  lan: NEON.lime,
  unknown: NEON.orange,
  alert: NEON.magenta,
};

const SHOW_IP_LABELS_UNDER = 18;
const SWEEP_DEG_PER_SEC = 50;

function radius(d: GraphNode): number {
  if (d.kind === "self") return 27;
  if (d.kind === "country") return 9 + Math.sqrt(d.count) * 2.2;
  return 3 + Math.sqrt(d.count) * 1.6;
}

function endpoints(l: GraphLink): [GraphNode, GraphNode] | null {
  return typeof l.source === "object" && typeof l.target === "object" ? [l.source, l.target] : null;
}

interface Hover {
  x: number;
  y: number;
  node: GraphNode;
}

interface Props {
  remotes: Remote[];
  alertIps: string[];
  hostname?: string;
}

export function NetworkMap({ remotes, alertIps, hostname }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<Simulation<GraphNode, GraphLink> | null>(null);
  const nodesRef = useRef<Map<string, GraphNode>>(new Map());
  const linksRef = useRef<GraphLink[]>([]);
  const sizeRef = useRef({ w: 600, h: 400 });
  const [hover, setHover] = useState<Hover | null>(null);
  const reduced = useMemo(
    () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  // ---------- 初期化（1回だけ）: SVG の骨組み・シミュレーション・アニメーションループ ----------
  useEffect(() => {
    const wrap = wrapRef.current;
    const svgEl = svgRef.current;
    if (!wrap || !svgEl) return;
    const svg = select(svgEl);

    const defs = svg.append("defs");
    const glow = defs.append("filter").attr("id", "nm-glow").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
    glow.append("feGaussianBlur").attr("stdDeviation", 3).attr("result", "blur");
    const merge = glow.append("feMerge");
    merge.append("feMergeNode").attr("in", "blur");
    merge.append("feMergeNode").attr("in", "SourceGraphic");
    const grad = defs.append("linearGradient").attr("id", "nm-sweep").attr("x1", "0").attr("y1", "0").attr("x2", "1").attr("y2", "0");
    grad.append("stop").attr("offset", "0%").attr("stop-color", NEON.cyan).attr("stop-opacity", 0);
    grad.append("stop").attr("offset", "100%").attr("stop-color", NEON.cyan).attr("stop-opacity", 0.22);

    const rings = svg.append("g").attr("class", "nm-rings");
    for (const r of [70, 140, 210, 280, 350]) {
      rings.append("circle").attr("r", r);
    }
    rings.append("line").attr("x1", -360).attr("x2", 360).attr("y1", 0).attr("y2", 0);
    rings.append("line").attr("y1", -360).attr("y2", 360).attr("x1", 0).attr("x2", 0);
    const sweep = svg.append("g").attr("class", "nm-sweep");
    const R = 360;
    const a0 = (-40 * Math.PI) / 180;
    sweep
      .append("path")
      .attr("d", `M0,0 L${R * Math.cos(a0)},${R * Math.sin(a0)} A${R},${R} 0 0,1 ${R},0 Z`)
      .attr("fill", "url(#nm-sweep)");

    svg.append("g").attr("class", "nm-links").attr("filter", "url(#nm-glow)");
    // 粒はぼかしなし（毎フレーム動くので、フィルタをかけると重い）
    svg.append("g").attr("class", "nm-particles");
    svg.append("g").attr("class", "nm-nodes").attr("filter", "url(#nm-glow)");

    const draw = () => {
      svg
        .select(".nm-links")
        .selectAll<SVGLineElement, GraphLink>("line")
        .each(function (l) {
          const e = endpoints(l);
          if (!e) return;
          this.setAttribute("x1", String(e[0].x ?? 0));
          this.setAttribute("y1", String(e[0].y ?? 0));
          this.setAttribute("x2", String(e[1].x ?? 0));
          this.setAttribute("y2", String(e[1].y ?? 0));
        });
      svg
        .select(".nm-nodes")
        .selectAll<SVGGElement, GraphNode>("g.nm-node")
        .attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
      // IP のラベルは国ノードと反対側に出して重なりを避ける
      svg
        .select(".nm-nodes")
        .selectAll<SVGGElement, GraphNode>("g.nm-node--ip")
        .each(function (d) {
          const parent = nodesRef.current.get(`cc:${d.remote?.country || "??"}`);
          const right = (d.x ?? 0) >= (parent?.x ?? 0);
          const label = this.querySelector("text.nm-label");
          if (!label) return;
          label.setAttribute("text-anchor", right ? "start" : "end");
          label.setAttribute("x", String((radius(d) + 4) * (right ? 1 : -1)));
        });
    };

    const sim = forceSimulation<GraphNode>([])
      .force(
        "link",
        forceLink<GraphNode, GraphLink>([])
          .id((d) => d.id)
          .distance((l) => (endpoints(l)?.[0].kind === "self" ? 135 : 44))
          .strength(0.8),
      )
      .force(
        "charge",
        forceManyBody<GraphNode>().strength((d) => (d.kind === "self" ? -500 : d.kind === "country" ? -280 : -55)),
      )
      .force("collide", forceCollide<GraphNode>((d) => radius(d) + 7))
      .force("x", forceX<GraphNode>(0).strength(0.04))
      .force("y", forceY<GraphNode>(0).strength(0.07))
      .alphaDecay(0.03)
      .on("tick", draw);
    simRef.current = sim;

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const w = rect.width || 600;
      const h = rect.height || 400;
      sizeRef.current = { w, h };
      svg.attr("viewBox", `${-w / 2} ${-h / 2} ${w} ${h}`);
    };
    resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    ro?.observe(wrap);

    // 線の上を流れる光の粒 + レーダーの回転
    const phases = new Map<string, number>();
    let raf = 0;
    let last = typeof performance !== "undefined" ? performance.now() : 0;
    let angle = 0;
    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      angle = (angle + dt * SWEEP_DEG_PER_SEC) % 360;
      sweep.attr("transform", `rotate(${angle})`);

      const particles: { key: string; x: number; y: number; color: string }[] = [];
      for (const l of linksRef.current) {
        const e = endpoints(l);
        if (!e) continue;
        const n = l.count > 3 ? 2 : 1;
        for (let i = 0; i < n; i++) {
          const key = `${l.id}#${i}`;
          const speed = 0.25 + Math.min(l.count, 12) * 0.04;
          const p = ((phases.get(key) ?? Math.random()) + dt * speed) % 1;
          phases.set(key, p);
          const t = i % 2 === 0 ? p : 1 - p; // 偶数は外向き、奇数は内向き
          particles.push({
            key,
            x: (e[0].x ?? 0) + ((e[1].x ?? 0) - (e[0].x ?? 0)) * t,
            y: (e[0].y ?? 0) + ((e[1].y ?? 0) - (e[0].y ?? 0)) * t,
            color: TONE_COLOR[l.tone],
          });
        }
      }
      svg
        .select(".nm-particles")
        .selectAll<SVGCircleElement, (typeof particles)[number]>("circle")
        .data(particles, (d) => d.key)
        .join("circle")
        .attr("r", 2)
        .attr("fill", (d) => d.color)
        .attr("cx", (d) => d.x)
        .attr("cy", (d) => d.y);
      raf = requestAnimationFrame(loop);
    };
    if (!reduced && typeof requestAnimationFrame === "function") raf = requestAnimationFrame(loop);

    return () => {
      if (raf) cancelAnimationFrame(raf);
      sim.stop();
      ro?.disconnect();
      svg.selectAll("*").remove();
      simRef.current = null;
      nodesRef.current = new Map();
      linksRef.current = [];
    };
  }, [reduced]);

  // ---------- データ更新: 既存ノードの位置を保ったまま差分を反映 ----------
  useEffect(() => {
    const svgEl = svgRef.current;
    const sim = simRef.current;
    if (!svgEl || !sim) return;
    const svg = select(svgEl);
    const graph = buildGraph(remotes, new Set(alertIps));
    const prev = nodesRef.current;
    const next = new Map<string, GraphNode>();

    const nodes = graph.nodes.map((n) => {
      const old = prev.get(n.id);
      if (old) {
        old.label = n.label;
        old.count = n.count;
        old.tone = n.tone;
        old.remote = n.remote;
        next.set(n.id, old);
        return old;
      }
      const parentId = n.kind === "ip" ? `cc:${n.remote?.country || "??"}` : "self";
      const parent = next.get(parentId) ?? prev.get(parentId);
      const angle = Math.random() * Math.PI * 2;
      const dist = n.kind === "country" ? 120 : 30;
      n.x = (parent?.x ?? 0) + Math.cos(angle) * dist;
      n.y = (parent?.y ?? 0) + Math.sin(angle) * dist;
      if (n.kind === "self") {
        n.fx = 0;
        n.fy = 0;
      }
      next.set(n.id, n);
      return n;
    });
    const structureChanged = nodes.length !== prev.size || nodes.some((n) => !prev.has(n.id));
    nodesRef.current = next;

    sim.nodes(nodes);
    (sim.force("link") as ForceLink<GraphNode, GraphLink>).links(graph.links);
    linksRef.current = graph.links;

    // 線
    const linkSel = svg
      .select(".nm-links")
      .selectAll<SVGLineElement, GraphLink>("line:not(.nm-exiting)")
      .data(graph.links, (d) => d.id);
    linkSel.exit().classed("nm-exiting", true).transition().duration(600).attr("stroke-opacity", 0).remove();
    linkSel
      .enter()
      .append("line")
      .attr("stroke-opacity", 0)
      .call((s) => s.transition().duration(900).ease(easeCubicOut).attr("stroke-opacity", 0.6))
      .merge(linkSel)
      .attr("stroke", (d) => TONE_COLOR[d.tone])
      .attr("stroke-width", (d) => 0.8 + Math.log2(1 + d.count) * 0.7);

    // ノード
    const ipCount = nodes.filter((n) => n.kind === "ip").length;
    const nodeSel = svg
      .select(".nm-nodes")
      .selectAll<SVGGElement, GraphNode>("g.nm-node:not(.nm-exiting)")
      .data(nodes, (d) => d.id);
    nodeSel.exit().classed("nm-exiting", true).transition().duration(600).attr("opacity", 0).remove();
    const entered = nodeSel
      .enter()
      .append("g")
      .attr("class", (d) => `nm-node nm-node--${d.kind}`)
      .attr("opacity", 0)
      .attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    entered.filter((d) => d.kind === "self").append("circle").attr("class", "nm-halo").attr("r", 34);
    entered.append("circle").attr("class", "nm-dot");
    entered.append("text").attr("class", "nm-label");
    entered.filter((d) => d.kind === "self").append("text").attr("class", "nm-sub").attr("y", 46);
    entered.transition().duration(900).ease(easeCubicOut).attr("opacity", 1);

    const all = entered.merge(nodeSel);
    all.classed("nm-node--alert", (d) => d.tone === "alert");
    all
      .select<SVGCircleElement>("circle.nm-dot")
      .attr("r", radius)
      .attr("stroke", (d) => TONE_COLOR[d.tone])
      .attr("fill", (d) => (d.kind === "ip" ? TONE_COLOR[d.tone] : "rgba(5, 6, 10, 0.85)"));
    all
      .select<SVGTextElement>("text.nm-label")
      .attr("y", (d) => (d.kind === "ip" ? 3 : 4))
      .each(function (d) {
        if (d.kind !== "ip") {
          this.setAttribute("x", "0");
          this.setAttribute("text-anchor", "middle");
        }
      })
      .attr("fill", (d) => (d.kind === "self" ? NEON.cyan : TONE_COLOR[d.tone]))
      .attr("display", (d) => (d.kind !== "ip" || ipCount <= SHOW_IP_LABELS_UNDER || d.tone === "alert" ? null : "none"))
      .text((d) => d.label);
    all.select<SVGTextElement>("text.nm-sub").text(hostname ?? "");

    all
      .on("mouseenter", (_e, d) => {
        const { w, h } = sizeRef.current;
        setHover({ x: (d.x ?? 0) + w / 2, y: (d.y ?? 0) + h / 2, node: d });
      })
      .on("mouseleave", () => setHover(null));

    sim.alpha(structureChanged ? 0.6 : Math.max(sim.alpha(), 0.04)).restart();
  }, [remotes, alertIps, hostname]);

  const r = hover?.node.remote;
  return (
    <div className="nm" ref={wrapRef}>
      <svg ref={svgRef} className="nm__svg" role="img" aria-label="通信先のネットワーク図" />
      <ul className="nm__legend" aria-label="凡例">
        <li><i className="nm-swatch nm-swatch--public" />公開</li>
        <li><i className="nm-swatch nm-swatch--lan" />LAN</li>
        <li><i className="nm-swatch nm-swatch--unknown" />国不明</li>
        <li><i className="nm-swatch nm-swatch--alert" />アラート</li>
      </ul>
      {hover && hover.node.kind !== "self" && (
        <div className="nm__tip" style={{ left: hover.x, top: hover.y }} role="tooltip">
          <div className="nm__tip-title num">{hover.node.label}</div>
          {r ? (
            <>
              <div>国: {r.country} · 接続 {r.count}</div>
              <div className="num">ポート: {r.ports.join(", ")}</div>
              <div>プロセス: {r.processes.join(", ")}</div>
            </>
          ) : (
            <div>接続 {hover.node.count}</div>
          )}
        </div>
      )}
    </div>
  );
}
