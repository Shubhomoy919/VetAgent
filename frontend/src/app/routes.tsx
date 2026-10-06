import { createBrowserRouter } from "react-router";
import { BenchPage } from "../features/bench/BenchPage";
import { CasesPage } from "../features/cases/CasesPage";
import { DrugsPage } from "../features/drugs/DrugsPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { ReviewPage } from "../features/review/ReviewPage";
import { RunsPage } from "../features/runs/RunsPage";
import { ScorecardPage } from "../features/scorecard/ScorecardPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { StudyPage } from "../features/study/StudyPage";
import { NotFoundPage } from "../features/notfound/NotFoundPage";
import { Shell } from "./Shell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <BenchPage /> },
      { path: "cases", element: <CasesPage /> },
      { path: "drugs", element: <DrugsPage /> },
      { path: "scorecard", element: <ScorecardPage /> },
      { path: "runs", element: <RunsPage /> },
      { path: "review", element: <ReviewPage /> },
      { path: "study", element: <StudyPage /> },
      { path: "overview", element: <OverviewPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
