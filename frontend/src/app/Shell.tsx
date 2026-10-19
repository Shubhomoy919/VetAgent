import { AnimatePresence, motion } from "motion/react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { useAuth, useAuthActions } from "../api/auth";
import { useHealth } from "../api/health";
import { RUN_STATUS_LABEL } from "../api/runs";
import { CollapseIcon, ExpandIcon } from "../components/icons";
import { InkDefs } from "../components/Ink";
import { AccessDialogProvider } from "./Access";
import { useAccessDialog } from "./accessDialog";
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

/** Browser tab title per route. */
function useDocumentTitle(pathname: string) {
  useEffect(() => {
    const t = routeTitle(pathname);
    document.title = t ? `${t} · VetAgentBench-IN` : "Page not found · VetAgentBench-IN";
  }, [pathname]);
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
  const live = data.llm_mode === "live";
  return (
    <span className="pill" data-tone={live ? "live" : "demo"} title={live ? `Live: ${data.provider}` : "No API key configured: sample responses"}>
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
        <AccessControl />
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

/** Read-only / unlocked state, with the action to change it. */
function AccessControl() {
  const { data } = useAuth();
  const { open } = useAccessDialog();
  const { lock } = useAuthActions();
  if (!data || !data.access_required) return null;
  if (data.admin) {
    return (
      <button type="button" className="btn" onClick={() => void lock()} data-testid="lock">
        Lock
      </button>
    );
  }
  return (
    <button type="button" className="btn" onClick={open} data-testid="unlock" title="Browse freely; the access code unlocks runs, editing, Review and Settings">
      Read-only · Unlock
    </button>
  );
}

function RunStatus() {
  const { run } = useRun();
  const text = !run ? "Idle" : `${RUN_STATUS_LABEL[run.status]} ${run.n_done}/${run.n_total}`;
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

/** Shown when the server cannot be reached (offline, or the service is restarting). */
function OfflineBanner() {
  const { error } = useHealth();
  if (!error) return null;
  return (
    <div className="demo-banner" role="alert" data-testid="offline-banner">
      Can&rsquo;t reach the server. Check your connection; pages show what was already loaded and retry on their own.
    </div>
  );
}

function DemoBanner() {
  const { data } = useHealth();
  if (data?.llm_mode !== "demo") return null;
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
  useDocumentTitle(location.pathname);
  const [collapsed, setCollapsed] = usePersistentFlag("vab.sidebarCollapsed", () => window.innerWidth < 1280);

  return (
    <AccessDialogProvider>
    <div className="shell" data-collapsed={collapsed}>
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <div className="main">
        <TopBar />
        <OfflineBanner />
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
        <footer className="footer">Research prototype, not for clinical use. Consult a registered veterinarian.</footer>
      </div>
    </div>
    </AccessDialogProvider>
  );
}
