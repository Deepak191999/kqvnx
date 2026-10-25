/* Small presentational building blocks shared by both views. */
import type { ReactNode } from "react";

export function Card({
  title,
  note,
  children,
  aside,
}: {
  title?: string;
  note?: ReactNode;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section className="card">
      {title && (
        <header style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
          <div>
            <h2>{title}</h2>
            {note && <div className="note">{note}</div>}
          </div>
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function Tile({
  label,
  value,
  unit,
  caption,
  accent,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  caption?: ReactNode;
  accent?: boolean;
  tone?: "pos" | "neg";
}) {
  return (
    <div className={`tile${accent ? " accent" : ""}`}>
      <div className="label">{label}</div>
      <div className={`value${tone ? ` delta-${tone}` : ""}`}>
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {caption && <div className="caption">{caption}</div>}
    </div>
  );
}

/** Legend is always rendered for multi-series charts: identity is never colour alone. */
export function Legend({ items }: { items: { color: string; label: string; area?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span className="legend-item" key={it.label}>
          <span
            className={`swatch${it.area ? " area" : ""}`}
            style={{ background: it.color }}
            aria-hidden="true"
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return <div className="state">Loading {what}…</div>;
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state error">
      <strong>Could not load data.</strong>
      <div style={{ marginTop: 6, fontSize: 13 }}>{message}</div>
    </div>
  );
}
