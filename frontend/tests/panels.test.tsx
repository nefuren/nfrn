import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlertsPanel } from "../src/panels/AlertsPanel";
import { LoginPanel } from "../src/panels/LoginPanel";
import { PortsPanel } from "../src/panels/PortsPanel";
import { RemotesList } from "../src/panels/RemotesList";
import { ScorePanel } from "../src/panels/ScorePanel";
import { VulnPanel } from "../src/panels/VulnPanel";
import type { AuditReport, SlowMessage } from "../src/lib/types";

// グラフ描画（canvas）は jsdom では行わない
vi.mock("../src/components/EChart", () => ({ EChart: () => <div data-testid="chart" /> }));

afterEach(cleanup);

const EVIL = '<img src=x onerror="alert(1)">';

function noHtmlInjected(container: HTMLElement) {
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
}

describe("AlertsPanel", () => {
  it("メッセージをテキストとして表示し、新しい順・レベル付き", () => {
    const { container } = render(
      <AlertsPanel
        alerts={[
          { id: 2, ts: "2026-11-23T09:00:05Z", level: "crit", kind: "bruteforce", message: EVIL, source_ip: "1.2.3.4" },
          { id: 1, ts: "2026-11-23T09:00:00Z", level: "warn", kind: "new_port", message: "新しい待ち受けポート", source_ip: null },
        ]}
      />,
    );
    noHtmlInjected(container);
    expect(container.textContent).toContain(EVIL);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("CRIT");
    expect(items[1]).toHaveTextContent("WARN");
  });

  it("空なら異常なしと出す", () => {
    render(<AlertsPanel alerts={[]} />);
    expect(screen.getByText(/異常なし/)).toBeInTheDocument();
  });
});

describe("PortsPanel", () => {
  const ports: SlowMessage["ports"] = [
    { proto: "tcp", address: "0.0.0.0", port: 3389, pid: 1, process: EVIL, exposed: true, risky: "RDP" },
    { proto: "tcp", address: "127.0.0.1", port: 8787, pid: 2, process: "python.exe", exposed: false, risky: null },
  ];

  it("外部公開と危険ポートを示し、プロセス名はテキスト", () => {
    const { container } = render(
      <PortsPanel ports={ports} firewall={{ available: true, profiles: { Domain: true, Private: false, Public: null } }} />,
    );
    noHtmlInjected(container);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("3389");
    expect(rows[0]).toHaveTextContent("RDP");
    expect(rows[0]).toHaveTextContent("公開");
    expect(rows[1]).toHaveTextContent("ローカル");
    expect(screen.getByText("Private").closest(".chip")).toHaveTextContent("OFF");
    expect(screen.getByText("Public").closest(".chip")).toHaveTextContent("?");
  });

  it("ファイアウォール未対応OSでは表示しない", () => {
    render(<PortsPanel ports={[]} firewall={{ available: false, profiles: {} }} />);
    expect(screen.queryByText("Domain")).toBeNull();
  });
});

describe("LoginPanel", () => {
  const base: SlowMessage["logins"] = {
    status: { state: "ok", message: "", source: "Windows セキュリティログ" },
    failures_per_minute: Array(60).fill(0),
    failures_1h: 3,
    failures_24h: 7,
    success_24h: 2,
    lockouts_24h: 1,
    recent: [{ ts: "2026-11-23T09:00:00Z", kind: "failure", user: EVIL, source_ip: "203.0.113.5", detail: "ネットワークログオン失敗" }],
  };

  it("集計と最近のイベントを表示する", () => {
    const { container } = render(<LoginPanel logins={base} />);
    noHtmlInjected(container);
    expect(container.textContent).toContain(EVIL);
    expect(screen.getByText("203.0.113.5")).toBeInTheDocument();
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("権限がないときは理由を表示する", () => {
    render(
      <LoginPanel
        logins={{ ...base, status: { state: "no_permission", message: "Event Log Readers グループへの追加が必要", source: "x" } }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Event Log Readers");
  });
});

describe("ScorePanel", () => {
  it("減点の内訳を表示する", () => {
    render(
      <ScorePanel score={{ value: 70, items: [{ label: "ファイアウォール無効：Public", points: -25 }], notes: ["メモ"] }} />,
    );
    expect(screen.getByText("ファイアウォール無効：Public")).toBeInTheDocument();
    expect(screen.getByText("-25")).toBeInTheDocument();
    expect(screen.getByText("メモ")).toBeInTheDocument();
  });
});

describe("VulnPanel", () => {
  const audit: AuditReport = {
    state: "done",
    last_run: "2026-11-23T09:00:00Z",
    targets: [{ name: "このアプリ (Python)", source: "pip", state: "unavailable", message: "ツールが見つかりません" }],
    findings: [
      { source: "npm", project: "frontend", package: "nanoid", version: "<3.3.8", vuln_id: "GHSA-mwcw", severity: "moderate", fix: "npm audit fix", title: EVIL, aliases: [] },
      { source: "pip", project: "backend", package: "requests", version: "2.19.0", vuln_id: "PYSEC-2018-28", severity: "critical", fix: "2.20.0", title: "", aliases: [] },
    ],
    counts: { critical: 1, moderate: 1 },
  };

  it("重大度の高い順に並べ、ツールが無い対象を知らせる", () => {
    const { container } = render(<VulnPanel audit={audit} />);
    noHtmlInjected(container);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("requests");
    expect(items[1]).toHaveTextContent("nanoid");
    expect(screen.getByText(/ツールが見つかりません/)).toBeInTheDocument();
  });

  it("実行前は待機中と出す", () => {
    render(<VulnPanel audit={{ state: "pending", last_run: null, targets: [], findings: [], counts: {} }} />);
    expect(screen.getByText(/待機中/)).toBeInTheDocument();
  });
});

describe("RemotesList", () => {
  it("通信先をテキストで表示する", () => {
    const { container } = render(
      <RemotesList remotes={[{ ip: "93.184.216.34", country: "US", count: 3, ports: [443], processes: [EVIL], private: false }]} />,
    );
    noHtmlInjected(container);
    expect(screen.getByText("93.184.216.34")).toBeInTheDocument();
    expect(screen.getByText("US")).toBeInTheDocument();
  });
});
