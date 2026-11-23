import { BarChart, GaugeChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([LineChart, BarChart, GaugeChart, GridComponent, TooltipComponent, CanvasRenderer]);

export type ChartOption = echarts.EChartsCoreOption;

interface Props {
  option: ChartOption;
  label: string;
  className?: string;
}

/** ECharts を canvas で描く薄いラッパー。外部文字列を option に入れないこと（数値のみ）。 */
export function EChart({ option, label, className = "" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const c = echarts.init(el, undefined, { renderer: "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { lazyUpdate: true });
  }, [option]);

  return <div ref={ref} className={`echart ${className}`} role="img" aria-label={label} />;
}
