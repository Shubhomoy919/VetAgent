import { createBrowserRouter } from "react-router";
import { BenchPage } from "../features/bench/BenchPage";
import { CasesPage } from "../features/cases/CasesPage";
import { DrugsPage } from "../features/drugs/DrugsPage";
import { ScorecardPage } from "../features/scorecard/ScorecardPage";
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
    ],
  },
]);
