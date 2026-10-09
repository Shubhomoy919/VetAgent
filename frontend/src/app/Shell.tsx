import { AnimatePresence, motion } from "motion/react";
import { NavLink, Outlet, useLocation } from "react-router";
import { Toaster } from "sonner";
import { useHealth } from "../api/health";
import { CollapseIcon, ExpandIcon } from "../components/icons";
import { InkDefs } from "../components/Ink";
import { useKeyPressFeedback } from "../lib/useKeyPressFeedback";
import { NAV } from "./nav";
import { useRun } from "./runState";
import { ShortcutHelp } from "./ShortcutHelp";
import { usePersistentFlag } from "./theme";
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
    <span className="pill" data-tone={live ? "live" : "demo"} title={live ? `Live: ${data.provider}` : "No API key configured — sample responses"}>
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

function DemoBanner() {
  const { data } = useHealth();
  if (data?.mode !== "demo") return null;
  return (
    <div className="demo-banner" role="status" data-testid="demo-banner">
      Demo mode: sample responses, not live model output
    </div>
  );
}

/** Logo: three overlapping pink ink dots at different strengths, overprinting. */
function InkMark() {
  return (
    <svg className="inkmark" viewBox="0 0 30 18" aria-hidden="true" focusable="false">
      <circle cx="8" cy="9" r="7" opacity="1" />
      <circle cx="15" cy="9" r="7" opacity="0.6" />
      <circle cx="22" cy="9" r="7" opacity="0.32" />
    </svg>
  );
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="wordmark">
        <InkMark />
        {!collapsed && <span className="wordmark-name serif">VetAgentBench</span>}
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
                  <NavLink to={to} end className="nav-link" title={collapsed ? label : undefined}>
                    {({ isActive }) => (
                      <>
                        {isActive && <motion.span layoutId="nav-active" className="nav-active" transition={{ duration: 0.16, ease: EASE }} />}
                        <Icon className="nav-icon" />
                        <span className={collapsed ? "visually-hidden" : "nav-label"}>{label}</span>
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
  const [collapsed, setCollapsed] = usePersistentFlag("vab.sidebarCollapsed", () => window.innerWidth < 1280);

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
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              className="route"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.08 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
        <ShortcutHelp />
        <Toaster position="bottom-right" toastOptions={{ unstyled: true, classNames: { toast: "toast", error: "toast-error" } }} />
        <InkDefs />
        <footer className="footer">Research prototype — not for clinical use. Consult a registered veterinarian.</footer>
      </div>
    </div>
  );
}
