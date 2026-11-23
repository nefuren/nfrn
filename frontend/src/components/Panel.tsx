import type { ReactNode } from "react";

export type Accent = "cyan" | "magenta" | "lime" | "orange";

interface Props {
  title: string;
  code?: string;
  accent?: Accent;
  className?: string;
  aside?: ReactNode;
  children?: ReactNode;
}

/** 光る枠線のパネル。title / code は固定文字列、children はテキストとして描く。 */
export function Panel({ title, code, accent = "cyan", className = "", aside, children }: Props) {
  return (
    <section className={`panel panel--${accent} ${className}`} aria-label={title}>
      <header className="panel__head">
        <h2 className="panel__title">
          {code && <span className="panel__code">{code}</span>}
          {title}
        </h2>
        {aside && <div className="panel__aside">{aside}</div>}
      </header>
      <div className="panel__body">{children}</div>
    </section>
  );
}

/** 段階3でグラフに置き換える仮の中身 */
export function Placeholder({ value, label, note }: { value: ReactNode; label: string; note?: string }) {
  return (
    <div className="placeholder">
      <div className="placeholder__value num">{value}</div>
      <div className="placeholder__label">{label}</div>
      {note && <div className="placeholder__note">{note}</div>}
    </div>
  );
}
