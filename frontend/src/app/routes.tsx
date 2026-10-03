import { createBrowserRouter } from "react-router";
import { BenchPage } from "../features/bench/BenchPage";
import { ScorecardPage } from "../features/scorecard/ScorecardPage";
import { Shell } from "./Shell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <BenchPage /> },
      { path: "scorecard", element: <ScorecardPage /> },
    ],
  },
]);
