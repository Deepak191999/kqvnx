/* Presentation helpers. Energy desks read MW and GWh, not raw floats. */

export const mw = (v: number | null | undefined, digits = 0): string =>
  v == null ? "--" : `${v.toLocaleString("en-GB", { maximumFractionDigits: digits })}`;

export const gwh = (mwh: number | null | undefined, digits = 1): string =>
  mwh == null ? "--" : (mwh / 1000).toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const pct = (v: number | null | undefined, digits = 1): string =>
  v == null ? "--" : `${v.toFixed(digits)}%`;

export const signed = (v: number | null | undefined, digits = 0): string =>
  v == null ? "--" : `${v > 0 ? "+" : ""}${mw(v, digits)}`;

/** Hour label for the x-axis; the delivery day is already in the chart title. */
export const hourLabel = (iso: string): string => iso.slice(11, 16);

export const dayLabel = (iso: string): string =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

export const stampLabel = (iso: string): string =>
  `${iso.slice(8, 10)} ${new Date(iso).toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" })} ${iso.slice(11, 16)}`;

/** Inclusive list of ISO dates between two bounds. */
export const dateRange = (from: string, to: string): string[] => {
  const out: string[] = [];
  const cur = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  while (cur <= end) {
    out.push(cur.toISOString().slice(0, 10));
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return out;
};
