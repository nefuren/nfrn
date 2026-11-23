import { useMemo } from "react";
import { EChart } from "../components/EChart";
import { axisBase, NEON, tooltipBase } from "../lib/colors";
import { formatBytes, formatBytesPerSec } from "../lib/format";
import type { Sample } from "../lib/series";
import type { TickMessage } from "../lib/types";

export function TrafficPanel({ tick, series }: { tick: TickMessage | null; series: Sample[] }) {
  const option = useMemo(
    () => ({
      grid: { left: 64, right: 10, top: 10, bottom: 22 },
      tooltip: { ...tooltipBase, trigger: "axis", valueFormatter: (v: number) => formatBytesPerSec(v) },
      xAxis: {
        ...axisBase,
        type: "time",
        axisLabel: { ...axisBase.axisLabel, formatter: "{HH}:{mm}:{ss}", hideOverlap: true },
        splitLine: { show: false },
      },
      yAxis: {
        ...axisBase,
        type: "value",
        axisLabel: { ...axisBase.axisLabel, formatter: (v: number) => formatBytesPerSec(v) },
        splitNumber: 3,
      },
      series: [
        area("受信", NEON.cyan, series.map((s) => [s.t, s.rx])),
        area("送信", NEON.magenta, series.map((s) => [s.t, s.tx])),
      ],
    }),
    [series],
  );

  const net = tick?.net;
  return (
    <div className="traffic">
      <div className="traffic__stats">
        <div className="stat stat--cyan">
          <span className="stat__v num">{net ? formatBytesPerSec(net.rx_bps) : "—"}</span>
          <span className="stat__k">▼ 受信 · 累計 {net ? formatBytes(net.rx_total) : "—"}</span>
        </div>
        <div className="stat stat--magenta">
          <span className="stat__v num">{net ? formatBytesPerSec(net.tx_bps) : "—"}</span>
          <span className="stat__k">▲ 送信 · 累計 {net ? formatBytes(net.tx_total) : "—"}</span>
        </div>
        <div className="stat stat--orange">
          <span className="stat__v num">{tick?.connections_total ?? "—"}</span>
          <span className="stat__k">確立中の接続</span>
        </div>
      </div>
      <EChart option={option} label="通信量の推移（直近2分）" className="traffic__chart" />
    </div>
  );
}

function area(name: string, color: string, data: number[][]) {
  return {
    name,
    type: "line",
    data,
    showSymbol: false,
    smooth: 0.3,
    lineStyle: { color, width: 1.6, shadowColor: color, shadowBlur: 10 },
    areaStyle: {
      color: {
        type: "linear",
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: `${color}55` },
          { offset: 1, color: `${color}00` },
        ],
      },
    },
    animation: false,
  };
}
