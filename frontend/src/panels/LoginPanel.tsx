import { useMemo } from "react";
import { EChart } from "../components/EChart";
import { axisBase, NEON, tooltipBase } from "../lib/colors";
import { formatTime } from "../lib/format";
import type { SlowMessage } from "../lib/types";

const KIND_LABEL = { failure: "失敗", success: "成功", lockout: "ロック" } as const;

export function LoginPanel({ logins }: { logins: SlowMessage["logins"] | undefined }) {
  const buckets = logins?.failures_per_minute;
  const option = useMemo(() => {
    const data = buckets ?? Array(60).fill(0);
    return {
      grid: { left: 28, right: 6, top: 8, bottom: 18 },
      tooltip: { ...tooltipBase, trigger: "axis", formatter: (p: { dataIndex: number; value: number }[]) =>
        `${60 - (p[0]?.dataIndex ?? 0)}分前: ${p[0]?.value ?? 0}回` },
      xAxis: {
        ...axisBase,
        type: "category",
        data: data.map((_, i) => i),
        axisLabel: { ...axisBase.axisLabel, interval: 14, formatter: (v: string) => (Number(v) === 59 ? "now" : `-${60 - Number(v)}m`) },
      },
      yAxis: { ...axisBase, type: "value", minInterval: 1 },
      series: [
        {
          type: "bar",
          data,
          barWidth: "70%",
          itemStyle: { color: NEON.magenta, shadowColor: NEON.magenta, shadowBlur: 6 },
          animationDurationUpdate: 300,
        },
      ],
    };
  }, [buckets]);

  const status = logins?.status;
  return (
    <div className="stack">
      <div className="stats">
        <Stat label="1時間の失敗" value={logins?.failures_1h} tone="magenta" />
        <Stat label="24時間の失敗" value={logins?.failures_24h} />
        <Stat label="24時間の成功" value={logins?.success_24h} tone="lime" />
        <Stat label="ロック" value={logins?.lockouts_24h} tone="orange" />
      </div>
      {status && status.state !== "ok" && status.state !== "pending" && (
        <p className="banner banner--warn" role="status">
          {status.message || "ログを取得できません"}
        </p>
      )}
      <EChart option={option} label="1分ごとのログイン失敗回数（直近60分）" className="chart--sm" />
      <ul className="evt-list">
        {logins?.recent.slice(0, 6).map((e, i) => (
          <li key={`${e.ts}-${i}`} className={`evt evt--${e.kind}`}>
            <span className="evt__time num">{formatTime(e.ts)}</span>
            <span className="evt__kind">{KIND_LABEL[e.kind]}</span>
            <span className="evt__user">{e.user || "—"}</span>
            <span className="evt__ip num">{e.source_ip ?? "—"}</span>
          </li>
        ))}
      </ul>
      {status?.source && <p className="foot">source: {status.source}</p>}
    </div>
  );
}

function Stat({ label, value, tone = "cyan" }: { label: string; value: number | undefined; tone?: string }) {
  return (
    <div className={`stat stat--${tone}`}>
      <span className="stat__v num">{value ?? "—"}</span>
      <span className="stat__k">{label}</span>
    </div>
  );
}
