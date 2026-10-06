import { AnimatePresence, motion } from "motion/react";
import { NavLink, Outlet, useLocation } from "react-router";
import type { MouseEvent } from "react";
import { Toaster } from "sonner";
import { useHealth } from "../api/health";
import { CollapseIcon, ExpandIcon, MoonIcon, SunIcon } from "../components/icons";
import { InkDefs, InkUnderline } from "../components/Ink";
import { canViewTransition, markTransition, withViewTransition } from "../lib/viewTransition";
import { useKeyPressFeedback } from "../lib/useKeyPressFeedback";
import { CoachMarks } from "./CoachMarks";
import { CommandPalette } from "./CommandPalette";
import { NAV } from "./nav";
import { useRun } from "./runState";
import { applyThemePref, usePersistentFlag, useTheme } from "./theme";
import "./Shell.css";
import "./toast.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

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
  const { theme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  // Theme change as a circular reveal from the toggle button (View Transitions; plain swap otherwise).
  const toggle = (e: MouseEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    withViewTransition("theme", () => applyThemePref(next), { x: r.left + r.width / 2, y: r.top + r.height / 2 });
  };

  return (
    <header className="topbar">
      <h1 className="topbar-title serif">{routeTitle(pathname)}</h1>
      <div className="topbar-meta">
        <ModePill />
        <span className="topbar-field">
          <span className="eyebrow">Model</span>
          <span className="mono topbar-value" data-testid="model-id">
            {data?.model ?? "—"}
          </span>
        </span>
        <RunStatus />
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
        <button
          type="button"
          className="icon-button"
          onClick={toggle}
          aria-label={`Switch to ${next} theme`}
          title={`Switch to ${next} theme`}
          data-testid="theme-toggle"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
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
  return (
    <span className="topbar-field">
      <span className="eyebrow">Run</span>
      <span className="mono topbar-value" data-testid="run-status" data-running={run?.status === "running"}>
        {text}
      </span>
    </span>
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
