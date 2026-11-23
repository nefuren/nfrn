// canvas（ECharts / D3）は CSS 変数を読めないので同じ値をここにも持つ
export const NEON = {
  cyan: "#00f0ff",
  magenta: "#ff2bd6",
  lime: "#a6ff00",
  orange: "#ff8a00",
  text: "#d8f6ff",
  muted: "#6f8aa0",
  grid: "rgba(0, 240, 255, 0.08)",
  bg: "#05060a",
} as const;

export const MONO = '"JetBrains Mono", Consolas, monospace';

export function scoreColor(v: number): string {
  return v >= 80 ? NEON.lime : v >= 50 ? NEON.orange : NEON.magenta;
}

/** ツールチップは richText（canvas 描画）にして HTML を一切生成しない */
export const tooltipBase = {
  renderMode: "richText",
  backgroundColor: "rgba(5, 6, 10, 0.92)",
  borderColor: NEON.cyan,
  borderWidth: 1,
  textStyle: { color: NEON.text, fontFamily: MONO, fontSize: 11 },
} as const;

export const axisBase = {
  axisLine: { lineStyle: { color: "rgba(0, 240, 255, 0.25)" } },
  axisTick: { show: false },
  axisLabel: { color: NEON.muted, fontFamily: MONO, fontSize: 10 },
  splitLine: { lineStyle: { color: NEON.grid } },
} as const;
