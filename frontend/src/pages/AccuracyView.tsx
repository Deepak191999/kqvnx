/* The quantified-error screen: how much the desk should distrust the forecast,
 * and what a bias correction would have recovered. */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, ErrorState, Legend, Loading, Tile } from "../components/primitives";
import { makeTooltip } from "../components/ChartTooltip";
import { api } from "../lib/api";
import { dayLabel, mw, pct, signed } from "../lib/format";
import { useFetch } from "../lib/useFetch";

const HorizonTooltip = makeTooltip((l) => `Lead time ${l}`, [
  { key: "mae", label: "MAE", color: "var(--series-forecast)", format: (v) => `${mw(v)} MW` },
  { key: "rmse", label: "RMSE", format: (v) => `${mw(v)} MW` },
  { key: "nmae_pct", label: "Normalised MAE", format: (v) => `${v.toFixed(1)}%` },
  { key: "n", label: "Observations", format: (v) => String(v) },
]);

const HourTooltip = makeTooltip((l) => `Hour ${l}:00`, [
  { key: "bias", label: "Mean error", color: "var(--series-forecast)", format: (v) => `${signed(v)} MW` },
  { key: "mae", label: "MAE", format: (v) => `${mw(v)} MW` },
]);

const DistTooltip = makeTooltip((l) => `Error ≈ ${l} MW`, [
  { key: "count", label: "Delivery hours", format: (v) => String(v) },
]);

export function AccuracyView() {
  const summary = useFetch(() => api.accuracySummary(), []);
  const horizon = useFetch(() => api.byHorizon(), []);
  const hours = useFetch(() => api.byHour(), []);
  const dist = useFetch(() => api.distribution(), []);
  const days = useFetch(() => api.byDay(), []);

  if (summary.loading) return <Loading what="accuracy analysis" />;
  if (summary.error || !summary.data) return <ErrorState message={summary.error ?? "No data"} />;

  const { metrics, risk, scope, calibration } = summary.data;

  return (
    <>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Tile
          label="Mean absolute error"
          value={mw(metrics.mae)}
          unit="MW"
          caption={`${pct(metrics.nmae_pct)} of mean outturn`}
        />
        <Tile label="RMSE" value={mw(metrics.rmse)} unit="MW" caption={pct(metrics.nrmse_pct)} />
        <Tile
          label="Mean bias"
          value={signed(metrics.bias)}
          unit="MW"
          caption="Positive = wind under-delivered"
          tone="neg"
        />
        <Tile
          label="Over-forecast rate"
          value={pct(risk.over_forecast_rate_pct)}
          unit=""
          caption="Hours where wind fell short"
          tone="neg"
        />
      </div>

      <div className="callout">
        <strong>The error is one-sided, not random.</strong> Over {scope.delivery_days} delivery days
        ({scope.delivery_hours} hours), the published forecast exceeded metered wind in{" "}
        {pct(risk.over_forecast_rate_pct)} of hours and the mean bias is {signed(metrics.bias)} MW.
        A desk hedging only the spread — and not this bias — is structurally short every day.
      </div>

      {calibration.available && (
        <Card
          title="What removing the bias is worth"
          note={
            <>
              Walk-forward test: for each delivery day the correction factor is refitted on only the
              days that had already settled, then scored on that day. No day informs its own
              correction, so these are genuine out-of-sample results over{" "}
              {calibration.evaluated_days} days.
            </>
          }
        >
          <div className="grid cols-3">
            <Tile
              label="MAE — as published"
              value={mw(calibration.raw!.mae)}
              unit="MW"
              caption={`bias ${signed(calibration.raw!.bias)} MW`}
            />
            <Tile
              label="MAE — calibrated"
              value={mw(calibration.calibrated!.mae)}
              unit="MW"
              caption={`bias ${signed(calibration.calibrated!.bias)} MW`}
              accent
            />
            <Tile
              label="Error reduction"
              value={pct(calibration.mae_improvement_pct)}
              caption={`RMSE ${pct(calibration.rmse_improvement_pct)} · factor ×${calibration.latest_k?.toFixed(4)}`}
              tone="pos"
            />
          </div>
        </Card>
      )}

      <Card
        title="Forecast accuracy against lead time"
        note={
          <>
            Error grows steadily the further ahead the forecast looks. The shaded marker shows where
            the day-ahead decision sits: the desk must commit{" "}
            {horizon.data?.gate_closure_horizon_hours.min}–
            {horizon.data?.gate_closure_horizon_hours.max} hours out, well before the forecast
            reaches its best skill.
          </>
        }
      >
        {horizon.loading && <Loading what="horizon analysis" />}
        {horizon.data && (
          <>
            <Legend items={[{ color: "var(--series-forecast)", label: "Mean absolute error" }]} />
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={horizon.data.buckets} margin={{ top: 6, right: 8, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                  width={52}
                  label={{ value: "MW", angle: -90, position: "insideLeft", fill: "var(--text-muted)", fontSize: 11 }}
                />
                <Tooltip content={<HorizonTooltip />} cursor={{ fill: "var(--surface-2)" }} />
                <Bar dataKey="mae" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {horizon.data.buckets.map((b) => {
                    // Highlight the buckets the gate-closure decision actually lands in.
                    const live =
                      b.horizon_to > horizon.data!.gate_closure_horizon_hours.min &&
                      b.horizon_from < horizon.data!.gate_closure_horizon_hours.max;
                    return (
                      <Cell
                        key={b.label}
                        fill="var(--series-forecast)"
                        fillOpacity={live ? 1 : 0.4}
                      />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="note" style={{ marginTop: 8 }}>
              Solid bars are the lead times a day-ahead buyer is forced to use.
            </div>
          </>
        )}
      </Card>

      <div className="grid cols-2">
        <Card title="Distribution of forecast error" note="Gate-closure vintages only. Right of zero means wind under-delivered.">
          {dist.data && (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={dist.data.bins} margin={{ top: 6, right: 8, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis
                  dataKey="mid"
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                  tickFormatter={(v: number) => mw(v)}
                />
                <YAxis
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                  width={38}
                />
                <Tooltip content={<DistTooltip />} cursor={{ fill: "var(--surface-2)" }} />
                <ReferenceLine x={0} stroke="var(--text-muted)" strokeDasharray="3 3" />
                <Bar dataKey="count" fill="var(--series-forecast)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Error by hour of day" note="Mean signed error; reveals any systematic intraday pattern.">
          {hours.data && (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={hours.data} margin={{ top: 6, right: 8, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis
                  dataKey="hour_of_day"
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                  interval={2}
                />
                <YAxis
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  stroke="var(--border)"
                  tickLine={false}
                  width={52}
                />
                <Tooltip content={<HourTooltip />} cursor={{ stroke: "var(--border-strong)" }} />
                <ReferenceLine y={0} stroke="var(--text-muted)" strokeDasharray="3 3" />
                <Line
                  dataKey="bias"
                  stroke="var(--series-forecast)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card
        title="Daily breakdown"
        note="Every delivery day at its own gate-closure vintage. This table is the underlying data for the charts above."
      >
        {days.data && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Delivery day</th>
                  <th>Mean outturn</th>
                  <th>Mean forecast</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>Bias</th>
                  <th>nMAE</th>
                  <th>Max abs error</th>
                </tr>
              </thead>
              <tbody>
                {days.data.map((d) => (
                  <tr key={d.delivery_date}>
                    <td>{dayLabel(d.delivery_date)}</td>
                    <td>{mw(d.mean_actual)}</td>
                    <td>{mw(d.mean_forecast)}</td>
                    <td>{mw(d.mae)}</td>
                    <td>{mw(d.rmse)}</td>
                    <td>{signed(d.bias)}</td>
                    <td>{pct(d.nmae_pct)}</td>
                    <td>{mw(d.max_abs_error)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
