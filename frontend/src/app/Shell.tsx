import { AnimatePresence, motion } from "motion/react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { useHealth } from "../api/health";
import { CollapseIcon, ExpandIcon } from "../components/icons";
import { ThemeSwatches } from "../components/ThemeSwatches";
import { InkDefs, InkUnderline } from "../components/Ink";
import { canViewTransition, markTransition } from "../lib/viewTransition";
import { useKeyPressFeedback } from "../lib/useKeyPressFeedback";
import { CoachMarks } from "./CoachMarks";
import { CommandPalette } from "./CommandPalette";
import { NAV } from "./nav";
import { resultKey } from "../api/runs";
import { useRun } from "./runState";
import { usePersistentFlag } from "./theme";
import "./Shell.css";
import "./toast.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

/** Page colour zone: each section tints the ground with its own pigment. */
function routeZone(pathname: string): "bench" | "scorecard" | "data" | "runs" | "about" {
  if (pathname === "/") return "bench";
  if (pathname.startsWith("/scorecard")) return "scorecard";
  if (pathname.startsWith("/cases") || pathname.startsWith("/drugs")) return "data";
  if (pathname.startsWith("/runs") || pathname.startsWith("/review")) return "runs";
  return "about";
}

function routeTitle(pathname: string): string {
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.to === pathname) return item.label;
    }
  }
  return "";
}

function ModePill() {
  const { data, error, isPending } = useHealth();
  if (isPending) {
    return (
      <span className="pill" data-tone="neutral">
        <span className="pill-dot" aria-hidden="true" />
        Checking
      </span>
    );
  }
  if (error) {
    return (
      <span className="pill" data-tone="danger" title={error.message}>
        <span className="pill-dot" aria-hidden="true" />
        Backend offline
      </span>
    );
  }
  const live = data.mode === "live";
  return (
    <span
      className="pill"
      data-tone={live ? "live" : "demo"}
      title={live ? `Live: ${data.provider}` : "No API key configured — sample responses"}
    >
      <span className="pill-dot" aria-hidden="true" />
      {live ? "Live" : "Demo"}
    </span>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  const { data } = useHealth();

  return (
    <header className="topbar">
      <h1 className="topbar-title serif">{routeTitle(pathname) || "Not found"}</h1>
      <div className="topbar-meta">
        <ModePill />
        <span className="readout">
          <span className="readout-label">Model</span>
          <span className="readout-value mono topbar-value" data-testid="model-id">
            {data?.model ?? "—"}
          </span>
        </span>
        <RunStatus />
        <RunReadouts />
        <button
          type="button"
          className="kbd-button mono"
          onClick={() => window.dispatchEvent(new Event("vab:palette"))}
          aria-label="Open command palette (Ctrl+K)"
          title="Command palette (Ctrl+K) · shortcuts (?)"
          data-testid="open-palette"
          data-coach="palette"
        >
          Ctrl K
        </button>
        <ThemeSwatches />
      </div>
    </header>
  );
}

function RunStatus() {
  const { run } = useRun();
  const text = !run
    ? "Idle"
    : run.status === "running"
      ? `Running ${run.n_done}/${run.n_total}`
      : { done: "Done", done_with_errors: "Done (errors)", cancelled: "Cancelled", failed: "Failed", quota_exhausted: "Quota stop" }[run.status] +
        ` ${run.n_done}/${run.n_total}`;
  const led = !run ? undefined : run.status === "running" ? "running" : run.status === "done" ? "done" : "error";
  return (
    <span className="readout">
      <span className="readout-label">
        <span className="led" data-state={led} aria-hidden="true" /> Run
      </span>
      <span className="readout-value mono topbar-value" data-testid="run-status" data-running={run?.status === "running"}>
        {text}
      </span>
    </span>
  );
}

/** Instrument readouts for the current (or last) run: tokens, mean latency per result, cost. */
function RunReadouts() {
  const { run, live } = useRun();
  const results = run
    ? run.case_ids.flatMap((cid) => run.conditions.map((c) => live[resultKey(cid, c, run.interview)]?.result)).filter((r) => r !== undefined)
    : [];
  const tokens = results.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0);
  const latency = results.length ? results.reduce((s, r) => s + r.latency_ms, 0) / results.length / 1000 : null;
  const costs = results.map((r) => r.cost_usd);
  const cost = results.length === 0 || costs.some((c) => c === null) ? null : costs.reduce<number>((s, c) => s + (c ?? 0), 0);
  return (
    <>
      <span className="readout readout-wide">
        <span className="readout-label">Tokens</span>
        <span className="readout-value mono">{results.length ? tokens.toLocaleString("en-IN") : "—"}</span>
      </span>
      <span className="readout readout-wide">
        <span className="readout-label">Latency</span>
        <span className="readout-value mono">{latency === null ? "—" : `${latency.toFixed(1)} s`}</span>
      </span>
      <span className="readout readout-wide">
        <span className="readout-label">Cost</span>
        <span className="readout-value mono" title={cost === null && results.length ? "Prices not set (Settings)" : undefined}>
          {cost === null ? "—" : `$${cost.toFixed(4)}`}
        </span>
      </span>
    </>
  );
}

function DemoBanner() {
  const { data } = useHealth();
  if (data?.mode !== "demo") return null;
  return (
    <div className="demo-banner" role="status" data-testid="demo-banner">
      Demo mode: sample responses, not live model output
    </div>
  );
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="wordmark">
        <span className="wordmark-name serif">{collapsed ? "V" : "VetAgentBench"}</span>
        {!collapsed && <span className="wordmark-tag mono">IN</span>}
      </div>
      <nav className="nav">
        {NAV.filter((g) => g.items.length > 0).map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-group-label eyebrow" aria-hidden={collapsed}>
              {collapsed ? "" : group.label}
            </div>
            <ul>
              {group.items.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end
                    viewTransition
                    onClick={() => markTransition("route")}
                    className="nav-link"
                    title={collapsed ? label : undefined}
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span
                            layoutId="nav-active"
                            className="nav-active"
                            transition={{ duration: 0.2, ease: EASE }}
                          />
                        )}
                        <Icon className="nav-icon" />
                        <span className={collapsed ? "visually-hidden" : "nav-label"}>
                          {label}
                          {isActive && !collapsed && <InkUnderline key={to} variant={label.length} />}
                        </span>
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <button
        type="button"
        className="sidebar-toggle"
        onClick={onToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!collapsed}
      >
        {collapsed ? <ExpandIcon /> : <CollapseIcon />}
        {!collapsed && <span>Collapse</span>}
      </button>
    </aside>
  );
}

export function Shell() {
  const location = useLocation();
  useKeyPressFeedback();
  // Ground: zone tint + oversized outlined watermark (page name; the Bench sets the case ID itself).
  useEffect(() => {
    document.documentElement.dataset.zone = routeZone(location.pathname);
    if (location.pathname !== "/") document.body.dataset.watermark = routeTitle(location.pathname) || "Specimen";
  }, [location.pathname]);
  // View Transitions animate route changes where supported; motion is the fallback.
  const vt = canViewTransition();
  const [collapsed, setCollapsed] = usePersistentFlag(
    "vab.sidebarCollapsed",
    () => window.innerWidth < 1280,
  );

  return (
    <div className="shell" data-collapsed={collapsed}>
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <div className="main">
        <TopBar />
        <DemoBanner />
        <main id="content" className="content" tabIndex={-1}>
          {vt ? (
            // View Transitions animate the swap (motion.css); the route mounts synchronously.
            <div key={location.pathname} className="route">
              <Outlet />
            </div>
          ) : (
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={location.pathname}
                className="route"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22, ease: EASE }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          )}
        </main>
        <CommandPalette />
        <Toaster
          position="bottom-right"
          toastOptions={{ unstyled: true, classNames: { toast: "toast paper-slip", error: "toast-error" } }}
        />
        <CoachMarks />
        <InkDefs />
        <footer className="footer">
          Research prototype — not for clinical use. Consult a registered veterinarian.
        </footer>
      </div>
    </div>
  );
}
