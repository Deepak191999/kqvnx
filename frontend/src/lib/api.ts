/* Typed access to the procurement API.
 *
 * In development Vite proxies /api to the backend container, so the base URL is
 * empty. In production VITE_API_BASE_URL points at the deployed API.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface Meta {
  delivery_date_from: string;
  delivery_date_to: string;
  gate_closure_local: string;
  actual_rows: number;
  forecast_rows: number;
  ingested_at: string | null;
  sources: { actuals: string; forecast: string };
}

export interface Calibration {
  k: number;
  additive_bias: number;
  over_forecast_rate_pct: number;
  fitted_on_days: number;
  fitted_on_hours: number;
}

export interface DecisionPoint {
  start_time: string;
  generation: number;
  publish_time: string;
  horizon_hours: number;
  p10: number | null;
  p90: number | null;
  calibrated: number | null;
  actual: number | null;
}

export interface Decision {
  delivery_date: string;
  gate_closure_utc: string;
  vintage_used: string;
  vintages_available_total: number;
  horizon_hours: { min: number; max: number };
  calibration: Calibration | null;
  summary: {
    expected_wind_mwh_raw: number;
    expected_wind_mwh_calibrated: number;
    adjustment_mwh: number;
    p10_mwh: number | null;
    p90_mwh: number | null;
  };
  points: DecisionPoint[];
}

export interface ErrorStats {
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  nmae_pct: number | null;
  nrmse_pct: number | null;
  mean_actual: number;
  mean_forecast: number;
  max_abs_error: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface AccuracySummary {
  scope: { delivery_days: number; delivery_hours: number; basis: string };
  metrics: ErrorStats;
  risk: {
    over_forecast_rate_pct: number;
    p10_error_mw: number;
    p90_error_mw: number;
    interpretation: string;
  };
  calibration: {
    available: boolean;
    evaluated_days?: number;
    evaluated_hours?: number;
    min_history_days?: number;
    latest_k?: number;
    raw?: { mae: number; rmse: number; bias: number };
    calibrated?: { mae: number; rmse: number; bias: number };
    mae_improvement_pct?: number;
    rmse_improvement_pct?: number;
  };
}

export interface HorizonBucket extends ErrorStats {
  horizon_from: number;
  horizon_to: number;
  label: string;
}

export interface DayStats extends ErrorStats {
  delivery_date: string;
}

export interface HourStats extends ErrorStats {
  hour_of_day: number;
}

export interface HistogramBin {
  from: number;
  to: number;
  mid: number;
  count: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  decision: (date: string) => get<Decision>(`/api/decision/${date}`),
  accuracySummary: () => get<AccuracySummary>("/api/accuracy/summary"),
  byHorizon: () =>
    get<{ buckets: HorizonBucket[]; gate_closure_horizon_hours: { min: number; max: number } }>(
      "/api/accuracy/by-horizon",
    ),
  byDay: () => get<DayStats[]>("/api/accuracy/by-day"),
  byHour: () => get<HourStats[]>("/api/accuracy/by-hour"),
  distribution: () => get<{ bins: HistogramBin[]; metrics: ErrorStats }>("/api/accuracy/distribution"),
};
