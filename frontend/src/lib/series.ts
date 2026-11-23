import type { TickMessage } from "./types";

export interface Sample {
  ts: string;
  t: number; // epoch ms
  cpu: number;
  mem: number;
  rx: number;
  tx: number;
}

export const SERIES_LENGTH = 120; // 2分ぶん

export function appendSample(series: Sample[], tick: TickMessage, max = SERIES_LENGTH): Sample[] {
  if (series.length && series[series.length - 1]!.ts === tick.ts) return series;
  const next = series.concat({
    ts: tick.ts,
    t: Date.parse(tick.ts),
    cpu: tick.system.cpu,
    mem: tick.system.mem,
    rx: tick.net.rx_bps,
    tx: tick.net.tx_bps,
  });
  return next.length > max ? next.slice(next.length - max) : next;
}
