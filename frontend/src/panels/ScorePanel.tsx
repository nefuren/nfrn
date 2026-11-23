import { useMemo } from "react";
import { EChart } from "../components/EChart";
import { MONO, scoreColor } from "../lib/colors";
import type { Score } from "../lib/types";

export function ScorePanel({ score }: { score: Score | undefined }) {
  const value = score?.value ?? 0;
  const option = useMemo(() => {
    const color = scoreColor(value);
    return {
      series: [
        {
          type: "gauge",
          startAngle: 220,
          endAngle: -40,
          min: 0,
          max: 100,
          radius: "92%",
          center: ["50%", "60%"],
          progress: { show: true, width: 10, itemStyle: { color, shadowColor: color, shadowBlur: 14 } },
          axisLine: { lineStyle: { width: 10, color: [[1, "rgba(0, 240, 255, 0.1)"]] } },
          axisTick: { show: false },
          splitLine: { distance: -14, length: 4, lineStyle: { color: "rgba(0,240,255,0.35)", width: 1 } },
          axisLabel: { show: false },
          pointer: { show: false },
          anchor: { show: false },
          title: { show: false },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, "4%"],
            fontSize: 34,
            fontWeight: 700,
            fontFamily: MONO,
            color,
            formatter: "{value}",
          },
          data: [{ value: score ? value : 0 }],
          animationDurationUpdate: 600,
        },
      ],
    };
  }, [value, score]);

  return (
    <div className="score">
      <EChart option={option} label={`セキュリティスコア ${value} / 100`} className="score__gauge" />
      {score && score.items.length === 0 && <p className="ok-line">減点なし</p>}
      <ul className="score__items">
        {score?.items.map((item) => (
          <li key={item.label} className="score__item">
            <span className="score__label">{item.label}</span>
            <span className="score__points num">{item.points}</span>
          </li>
        ))}
        {score?.notes.map((n) => (
          <li key={n} className="score__note">
            {n}
          </li>
        ))}
      </ul>
    </div>
  );
}
