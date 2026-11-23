import { describe, expect, it } from "vitest";
import { appendSample, type Sample } from "../src/lib/series";
import type { TickMessage } from "../src/lib/types";

function tick(ts: string, cpu: number): TickMessage {
  return {
    type: "tick",
    ts,
    system: { cpu, cpu_per_core: [], mem: 10, mem_used: 0, mem_total: 0, swap: 0, uptime: 0, processes: 0 },
    net: { rx_bps: 100, tx_bps: 50, rx_total: 0, tx_total: 0 },
    remotes: [],
    connections_total: 0,
    score: { value: 100, items: [], notes: [] },
  };
}

describe("appendSample", () => {
  it("tick を時系列に追加し、上限を超えたら古いものを捨てる", () => {
    let s: Sample[] = [];
    for (let i = 0; i < 5; i++) s = appendSample(s, tick(`2026-11-23T00:00:0${i}Z`, i), 3);
    expect(s.map((x) => x.cpu)).toEqual([2, 3, 4]);
    expect(s[2]).toMatchObject({ mem: 10, rx: 100, tx: 50 });
  });

  it("同じ ts の tick は二重に追加しない", () => {
    const t = tick("2026-11-23T00:00:00Z", 1);
    const s = appendSample(appendSample([], t, 10), t, 10);
    expect(s).toHaveLength(1);
  });
});
