/* Shared crosshair tooltip. Every chart in the app ships one -- an HTML chart
 * is interactive by default, and the desk reads exact MW off hover. */
import type { TooltipProps } from "recharts";

export interface Row {
  key: string;
  label: string;
  color?: string;
  format: (v: number) => string;
}

export function makeTooltip(title: (label: string) => string, rows: Row[]) {
  return function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
    if (!active || !payload?.length) return null;
    const point = payload[0].payload as Record<string, number | null>;

    return (
      <div className="tooltip">
        <div className="t-title">{title(String(label))}</div>
        {rows.map((r) => {
          const v = point[r.key];
          if (v == null) return null;
          return (
            <div className="t-row" key={r.key}>
              {r.color && <span className="dot" style={{ background: r.color }} aria-hidden="true" />}
              {r.label}
              <b>{r.format(v)}</b>
            </div>
          );
        })}
      </div>
    );
  };
}
