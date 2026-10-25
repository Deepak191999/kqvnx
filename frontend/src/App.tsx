import { useEffect, useState } from "react";

import { ErrorState, Loading } from "./components/primitives";
import { AccuracyView } from "./pages/AccuracyView";
import { DecisionView } from "./pages/DecisionView";
import { api } from "./lib/api";
import { useFetch } from "./lib/useFetch";

type Tab = "decision" | "accuracy";

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(
    () => (localStorage.getItem("theme") as "light" | "dark" | null) ?? null,
  );

  useEffect(() => {
    // No stored choice means "follow the OS", so the attribute is removed and
    // the prefers-color-scheme block in the stylesheet takes over.
    if (theme) {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [theme]);

  const resolved =
    theme ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  return { resolved, toggle: () => setTheme(resolved === "dark" ? "light" : "dark") };
}

export default function App() {
  const [tab, setTab] = useState<Tab>("decision");
  const { resolved, toggle } = useTheme();
  const meta = useFetch(() => api.meta(), []);
  const [date, setDate] = useState<string | null>(null);

  // Default to a day with a sizeable forecast miss, so the demo opens on a
  // screen that actually shows the problem the product solves.
  useEffect(() => {
    if (meta.data && !date) setDate("2026-01-21");
  }, [meta.data, date]);

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>Wind Procurement Desk</h1>
          <div className="sub">
            Day-ahead wind forecasts and quantified forecast error · GB national wind · Elexon BMRS
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div className="tabs" role="tablist">
            <button
              className="tab"
              role="tab"
              aria-selected={tab === "decision"}
              onClick={() => setTab("decision")}
            >
              Decision view
            </button>
            <button
              className="tab"
              role="tab"
              aria-selected={tab === "accuracy"}
              onClick={() => setTab("accuracy")}
            >
              Forecast accuracy
            </button>
          </div>
          <button className="icon-btn" onClick={toggle} aria-label="Toggle colour theme">
            {resolved === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </header>

      {meta.loading && <Loading what="application" />}
      {meta.error && <ErrorState message={meta.error} />}

      {meta.data && date && (
        <>
          {tab === "decision" ? (
            <DecisionView meta={meta.data} date={date} onDateChange={setDate} />
          ) : (
            <AccuracyView />
          )}

          <footer className="footer">
            Sources: {meta.data.sources.actuals} · {meta.data.sources.forecast}. Snapshot of{" "}
            {meta.data.actual_rows.toLocaleString("en-GB")} settlement periods and{" "}
            {meta.data.forecast_rows.toLocaleString("en-GB")} forecast points covering delivery days{" "}
            {meta.data.delivery_date_from} to {meta.data.delivery_date_to}. Decisions are locked at{" "}
            {meta.data.gate_closure_local}.
          </footer>
        </>
      )}
    </div>
  );
}
