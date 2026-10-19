import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { RouterProvider } from "react-router";
import { RunProvider } from "./app/RunContext";
import { router } from "./app/routes";
import "./styles/global.css";

const queryClient = new QueryClient({
  // One quick retry: a dropped connection or a stopped server shows its error within a few seconds.
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, retryDelay: 800 } },
});

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing from index.html");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <RunProvider>
          <RouterProvider router={router} />
        </RunProvider>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
