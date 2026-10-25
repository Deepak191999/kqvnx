/* The buyer's working screen: what to assume about wind for a delivery day,
 * using only information that existed before the auction closed. */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, ErrorState, Legend, Loading, Tile } from "../components/primitives";
import { makeTooltip } from "../components/ChartTooltip";
import { api, type Meta } from "../lib/api";
import { dateRange, dayLabel, gwh, hourLabel, mw, pct, stampLabel } from "../lib/format";
import { useFetch } from "../lib/useFetch";

const C = {
  forecast: "var(--series-forecast)",
  calibrated: "var(--series-calibrated)",
  actual: "var(--series-actual)",
  band: "var(--band-fill)",
};

const DecisionTooltip = makeTooltip((l) => `Hour beginning ${l}`, [
  { key: "generation", label: "Forecast (published)", color: C.forecast, format: (v) => `${mw(v)} MW` },
  { key: "calibrated", label: "Forecast (calibrated)", color: C.calibrated, format: (v) => `${mw(v)} MW` },
  { key: "actual", label: "Actual outturn", color: C.actual, format: (v) => `${mw(v)} MW` },
  { key: "p10", label: "P10 (low wind)", format: (v) => `${mw(v)} MW` },
  { key: "p90", label: "P90 (high wind)", format: (v) => `${mw(v)} MW` },
]);

export function DecisionView({
  meta,
  date,
  onDateChange,
}: {
  meta: Meta;
  date: string;
  onDateChange: (d: string) => void;
}) {
  const { data, error, loading } = useFetch(() => api.decision(date), [date]);
  const days = dateRange(meta.delivery_date_from, meta.delivery_date_to);

  const picker = (
    <div className="controls">
      <div className="control">
        <label htmlFor="delivery-day">Delivery day</label>
        <select id="delivery-day" value={date} onChange={(e) => onDateChange(e.target.value)}>
          {days.map((d) => (
            <option key={d} value={d}>
              {new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", {
                weekday: "short",
                day: "numeric",
                month: "short",
                year: "numeric",
                timeZone: "UTC",
              })}
            </option>
          ))}
        </select>
      </div>
      {data && (
        <div className="control" style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Decision locked at <span className="mono">{stampLabel(data.gate_closure_utc)}</span> · using
          vintage <span className="mono">{stampLabel(data.vintage_used)}</span>
        </div>
      )}
    </div>
  );

  if (loading) return (<>{picker}<Loading what="the decision view" /></>);
  if (error || !data) return (<>{picker}<ErrorState message={error ?? "No data"} /></>);

  const { summary, calibration } = data;
  const chart = data.points.map((p) => ({ ...p, hour: hourLabel(p.start_time) }));
  const spread =
    summary.p10_mwh != null && summary.p90_mwh != null ? summary.p90_mwh - summary.p10_mwh : null;

  return (
    <>
      {picker}

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Tile
          label="Expected wind — as published"
          value={gwh(summary.expected_wind_mwh_raw)}
          unit="GWh"
          caption={`${mw(summary.expected_wind_mwh_raw / 24)} MW average`}
        />
        <Tile
          label="Expected wind — calibrated"
          value={gwh(summary.expected_wind_mwh_calibrated)}
          unit="GWh"
          caption="Bias-corrected on settled history"
          accent
        />
        <Tile
          label="Procurement adjustment"
          value={`${summary.adjustment_mwh > 0 ? "+" : ""}${gwh(summary.adjustment_mwh)}`}
          unit="GWh"
          caption="Extra thermal cover implied"
          tone={summary.adjustment_mwh < 0 ? "neg" : "pos"}
        />
        <Tile
          label="P10 – P90 range"
          value={spread == null ? "--" : gwh(spread)}
          unit="GWh"
          caption={
            summary.p10_mwh == null
              ? "Insufficient history"
              : `${gwh(summary.p10_mwh)} – ${gwh(summary.p90_mwh)} GWh`
          }
        />
      </div>

      {calibration && (
        <div className="callout">
          <strong>Why the two numbers differ.</strong> Across the {calibration.fitted_on_days} delivery
          days already settled, the published forecast overstated metered wind in{" "}
          {pct(calibration.over_forecast_rate_pct)} of hours, by {mw(calibration.additive_bias)} MW on
          average. The calibrated line scales the forecast by{" "}
          <span className="mono">×{calibration.k}</span>, fitted only on days that had settled before
          this one. Buying to the published number would leave the desk short.
        </div>
      )}

      <Card
        title={`Wind generation forecast — ${dayLabel(data.delivery_date)}`}
        note={
          <>
            Shaded band is the P10–P90 range of outturn implied by how this forecast has erred at each
            hour of day. Outturn is shown for review only; it was unknown at decision time.
          </>
        }
      >
        <Legend
          items={[
            { color: "var(--series-forecast)", label: "Forecast (published)" },
            { color: "var(--series-calibrated)", label: "Forecast (calibrated)" },
            { color: "var(--series-actual)", label: "Actual outturn" },
            { color: "var(--band-fill)", label: "P10–P90 range", area: true },
          ]}
        />
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={chart} margin={{ top: 6, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="hour"
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--border)"
              interval={2}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--border)"
              tickLine={false}
              width={52}
              label={{
                value: "MW",
                angle: -90,
                position: "insideLeft",
                fill: "var(--text-muted)",
                fontSize: 11,
              }}
            />
            <Tooltip content={<DecisionTooltip />} cursor={{ stroke: "var(--border-strong)" }} />
            <Area
              dataKey={(d: { p10: number | null; p90: number | null }) => [d.p10, d.p90]}
              stroke="none"
              fill={C.band}
              isAnimationActive={false}
              activeDot={false}
              name="P10–P90"
            />
            <Line
              dataKey="generation"
              stroke={C.forecast}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="Forecast (published)"
            />
            <Line
              dataKey="calibrated"
              stroke={C.calibrated}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="Forecast (calibrated)"
            />
            <Line
              dataKey="actual"
              stroke={C.actual}
              strokeWidth={2}
              strokeDasharray="5 3"
              dot={false}
              isAnimationActive={false}
              name="Actual outturn"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <Card
        title="Decision provenance"
        note="Everything above is reproducible from these four facts."
      >
        <div className="table-wrap">
          <table>
            <tbody>
              <tr>
                <td>Auction gate closure</td>
                <td className="mono">{data.gate_closure_utc}</td>
              </tr>
              <tr>
                <td>Forecast vintage used</td>
                <td className="mono">{data.vintage_used}</td>
              </tr>
              <tr>
                <td>Vintages published for this day</td>
                <td>
                  {data.vintages_available_total} total — later revisions withheld as they postdate
                  the decision
                </td>
              </tr>
              <tr>
                <td>Forecast lead time</td>
                <td>
                  {data.horizon_hours.min}–{data.horizon_hours.max} hours ahead of delivery
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
