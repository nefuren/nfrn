import { describe, expect, it } from "vitest";
import { buildGraph } from "../src/viz/graph";
import type { Remote } from "../src/lib/types";

const r = (ip: string, country: string, count = 1, priv = false): Remote => ({
  ip,
  country,
  count,
  ports: [443],
  processes: ["x.exe"],
  private: priv,
});

describe("buildGraph", () => {
  it("自分 → 国 → IP の2段でつなぐ", () => {
    const g = buildGraph([r("93.184.216.34", "US", 3), r("8.8.8.8", "US"), r("1.1.1.1", "AU")], new Set());
    const ids = g.nodes.map((n) => n.id);
    expect(ids).toContain("self");
    expect(ids).toContain("cc:US");
    expect(ids).toContain("cc:AU");
    expect(ids).toContain("ip:8.8.8.8");
    const links = g.links.map((l) => `${l.source}>${l.target}`);
    expect(links).toContain("self>cc:US");
    expect(links).toContain("cc:US>ip:93.184.216.34");
    expect(links).toContain("cc:AU>ip:1.1.1.1");
    const us = g.nodes.find((n) => n.id === "cc:US")!;
    expect(us.count).toBe(4);
  });

  it("LAN・不明・アラート対象で色分けする（アラートが最優先）", () => {
    const g = buildGraph(
      [r("192.168.1.1", "LAN", 1, true), r("203.0.113.5", "??"), r("45.33.32.156", "RU")],
      new Set(["45.33.32.156"]),
    );
    const tone = (id: string) => g.nodes.find((n) => n.id === id)!.tone;
    expect(tone("ip:192.168.1.1")).toBe("lan");
    expect(tone("ip:203.0.113.5")).toBe("unknown");
    expect(tone("ip:45.33.32.156")).toBe("alert");
    expect(tone("cc:RU")).toBe("alert"); // 配下にアラートがあれば国も強調
  });

  it("ノード数に上限をかける（多い順に残す）", () => {
    const many = Array.from({ length: 80 }, (_, i) => r(`10.0.${i}.1`, "LAN", i));
    const g = buildGraph(many, new Set(), 30);
    expect(g.nodes.filter((n) => n.kind === "ip")).toHaveLength(30);
    expect(g.nodes.some((n) => n.id === "ip:10.0.79.1")).toBe(true);
    expect(g.nodes.some((n) => n.id === "ip:10.0.0.1")).toBe(false);
  });

  it("通信先がなければ自分だけ", () => {
    const g = buildGraph([], new Set());
    expect(g.nodes.map((n) => n.id)).toEqual(["self"]);
    expect(g.links).toEqual([]);
  });
});
