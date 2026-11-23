import { useMemo } from "react";
import { EChart } from "../components/EChart";
import { axisBase, NEON, tooltipBase } from "../lib/colors";
import { formatBytes, formatPct, formatUptime } from "../lib/format";
import type { Sample } from "../lib/series";
import type { TickMessage } from "../lib/types";

export function SystemPanel({ tick, series }: { tick: TickMessage | null; series: Sample[] }) {
  const option = useMemo(
    () => ({
      grid: { left: 30, right: 6, top: 8, bottom: 6 },
      tooltip: { ...tooltipBase, trigger: "axis", valueFormatter: (v: number) => `${v.toFixed(1)}%` },
      xAxis: { ...axisBase, type: "time", show: false },
      yAxis: { ...axisBase, type: "value", min: 0, max: 100, splitNumber: 2 },
      series: [
        line("CPU", NEON.cyan, series.map((s) => [s.t, s.cpu])),
        line("MEM", NEON.lime, series.map((s) => [s.t, s.mem])),
      ],
    }),
    [series],
  );

  const sys = tick?.system;
  return (
    <div className="stack">
      <div className="stats">
        <div className="stat stat--cyan">
          <span className="stat__v num">{formatPct(sys?.cpu)}</span>
          <span className="stat__k">CPU</span>
        </div>
        <div className="stat stat--lime">
          <span className="stat__v num">{formatPct(sys?.mem)}</span>
          <span className="stat__k">
            MEM {sys ? `${formatBytes(sys.mem_used)} / ${formatBytes(sys.mem_total)}` : ""}
          </span>
        </div>
      </div>
      <EChart option={option} label="CPU とメモリ使用率の推移（直近2分）" className="chart--sm" />
      <div className="cores" aria-label="コアごとの CPU 使用率">
        {sys?.cpu_per_core.map((v, i) => (
          <span key={i} className="core" title={`core ${i}: ${v.toFixed(0)}%`}>
            <span className="core__fill" style={{ height: `${Math.min(100, Math.max(0, v))}%` }} />
          </span>
        ))}
      </div>
      <p className="foot num">
        UPTIME {formatUptime(sys?.uptime)} · PROC {sys?.processes ?? "—"} · SWAP {formatPct(sys?.swap)}
      </p>
    </div>
  );
}

function line(name: string, color: string, data: number[][]) {
  return {
    name,
    type: "line",
    data,
    showSymbol: false,
    smooth: true,
    lineStyle: { color, width: 1.5, shadowColor: color, shadowBlur: 8 },
    areaStyle: { color, opacity: 0.08 },
    animation: false,
  };
}
