import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { NetworkMap } from "../src/viz/NetworkMap";

afterEach(cleanup);

it("ラベルはテキストとして描かれ、外部文字列が HTML として解釈されない", () => {
  const evil = '<img src=x onerror="alert(1)">';
  const { container } = render(
    <NetworkMap
      hostname={evil}
      remotes={[{ ip: "93.184.216.34", country: "US", count: 2, ports: [443], processes: [evil], private: false }]}
      alertIps={[]}
    />,
  );
  const svg = container.querySelector("svg");
  expect(svg).not.toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("foreignObject")).toBeNull();
  const labels = Array.from(container.querySelectorAll("text")).map((t) => t.textContent);
  expect(labels).toContain("US");
  expect(labels).toContain(evil); // 自ホスト名もただの文字列
});

it("短い間隔で更新が続いても、消えた通信先のノードは確実に取り除かれる", async () => {
  const a = { ip: "93.184.216.34", country: "US", count: 1, ports: [443], processes: ["a"], private: false };
  const b = { ip: "1.1.1.1", country: "AU", count: 1, ports: [443], processes: ["b"], private: false };
  const { container, rerender } = render(<NetworkMap remotes={[a, b]} alertIps={[]} />);
  const labels = () => Array.from(container.querySelectorAll("g.nm-node text.nm-label")).map((t) => t.textContent);
  expect(labels()).toContain("1.1.1.1");
  // フェードアウト(600ms)より短い間隔で、更新が途切れずに届き続ける状況
  for (let i = 0; i < 12; i++) {
    rerender(<NetworkMap remotes={[{ ...a, count: i + 1 }]} alertIps={[]} />);
    await new Promise((r) => setTimeout(r, 150));
  }
  expect(labels()).not.toContain("1.1.1.1");
  expect(labels()).not.toContain("AU");
  expect(labels()).toContain("93.184.216.34");
});
