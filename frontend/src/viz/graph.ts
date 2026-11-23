import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import type { Remote } from "../lib/types";

export type Tone = "self" | "public" | "lan" | "unknown" | "alert";

export interface GraphNode extends SimulationNodeDatum {
  id: string;
  kind: "self" | "country" | "ip";
  label: string;
  count: number;
  tone: Tone;
  remote?: Remote;
}

export interface GraphLink extends SimulationLinkDatum<GraphNode> {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  count: number;
  tone: Tone;
}

export const MAX_IP_NODES = 40;

function ipTone(r: Remote, alertIps: Set<string>): Tone {
  if (alertIps.has(r.ip)) return "alert";
  if (r.private || r.country === "LAN" || r.country === "LOCAL") return "lan";
  if (r.country === "??") return "unknown";
  return "public";
}

/** 自分 → 国 → IP の木構造を作る。force シミュレーションの入力にそのまま使う。 */
export function buildGraph(remotes: Remote[], alertIps: Set<string>, maxIp = MAX_IP_NODES) {
  const top = [...remotes].sort((a, b) => b.count - a.count).slice(0, maxIp);
  const nodes: GraphNode[] = [{ id: "self", kind: "self", label: "THIS PC", count: 0, tone: "self" }];
  const links: GraphLink[] = [];
  const countries = new Map<string, GraphNode>();

  for (const r of top) {
    const cc = r.country || "??";
    const tone = ipTone(r, alertIps);
    let country = countries.get(cc);
    if (!country) {
      country = {
        id: `cc:${cc}`,
        kind: "country",
        label: cc,
        count: 0,
        tone: cc === "LAN" || cc === "LOCAL" ? "lan" : cc === "??" ? "unknown" : "public",
      };
      countries.set(cc, country);
      nodes.push(country);
      links.push({ id: `self>${country.id}`, source: "self", target: country.id, count: 0, tone: country.tone });
    }
    country.count += r.count;
    if (tone === "alert") country.tone = "alert";
    const id = `ip:${r.ip}`;
    nodes.push({ id, kind: "ip", label: r.ip, count: r.count, tone, remote: r });
    links.push({ id: `${country.id}>${id}`, source: country.id, target: id, count: r.count, tone });
  }

  for (const l of links) {
    if (l.source === "self") {
      const c = countries.get(String(l.target).slice(3))!;
      l.count = c.count;
      l.tone = c.tone;
    }
  }
  return { nodes, links };
}
