import { createBrowserRouter } from "react-router";
import { BenchPage } from "../features/bench/BenchPage";
import { NotFoundPage } from "../features/notfound/NotFoundPage";
import { Shell } from "./Shell";

// Bench ("/") ships in the main bundle; every other page loads on first visit.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <BenchPage /> },
      { path: "cases", lazy: () => import("../features/cases/CasesPage").then((m) => ({ Component: m.CasesPage })) },
      { path: "drugs", lazy: () => import("../features/drugs/DrugsPage").then((m) => ({ Component: m.DrugsPage })) },
      { path: "scorecard", lazy: () => import("../features/scorecard/ScorecardPage").then((m) => ({ Component: m.ScorecardPage })) },
      { path: "runs", lazy: () => import("../features/runs/RunsPage").then((m) => ({ Component: m.RunsPage })) },
      { path: "review", lazy: () => import("../features/review/ReviewPage").then((m) => ({ Component: m.ReviewPage })) },
      { path: "study", lazy: () => import("../features/study/StudyPage").then((m) => ({ Component: m.StudyPage })) },
      { path: "overview", lazy: () => import("../features/overview/OverviewPage").then((m) => ({ Component: m.OverviewPage })) },
      { path: "settings", lazy: () => import("../features/settings/SettingsPage").then((m) => ({ Component: m.SettingsPage })) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
