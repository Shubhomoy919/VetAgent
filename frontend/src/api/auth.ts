/* Access code: public visitors read; runs, edits, Review and Settings need the code (server-side session cookie). */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/** Mirrors backend/app/api/auth.py::_status */
export interface AuthStatus {
  admin: boolean;
  access_required: boolean;
  unlock_available: boolean;
  locked_for_s: number;
}

export class UnlockError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly attemptsLeft: number | null,
    readonly lockedForS: number | null,
  ) {
    super(message);
  }
}

async function fetchStatus(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/status", { credentials: "same-origin" });
  if (!res.ok) throw new Error(`GET /api/auth/status → ${res.status} ${res.statusText}`);
  return (await res.json()) as AuthStatus;
}

export function useAuth() {
  return useQuery({ queryKey: ["auth"], queryFn: fetchStatus, staleTime: 60_000, retry: 1 });
}

/** True when this visitor may run, edit, review and change settings. False while unknown. */
export function useIsAdmin(): boolean {
  const { data } = useAuth();
  return data?.admin === true;
}

export async function unlock(code: string): Promise<void> {
  const res = await fetch("/api/auth/unlock", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (res.ok) return;
  let body: { detail?: string; attempts_left?: number; locked_for_s?: number } = {};
  try {
    body = (await res.json()) as typeof body;
  } catch {
    // no body
  }
  throw new UnlockError(body.detail ?? res.statusText, res.status, body.attempts_left ?? null, body.locked_for_s ?? null);
}

export async function lock(): Promise<void> {
  await fetch("/api/auth/lock", { method: "POST", credentials: "same-origin" });
}

/** Unlock or lock, then refresh everything that depends on the visitor's role. */
export function useAuthActions() {
  const qc = useQueryClient();
  const refresh = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["auth"] });
    await qc.invalidateQueries({ queryKey: ["health"] });
    await qc.invalidateQueries({ queryKey: ["settings"] });
    await qc.invalidateQueries({ queryKey: ["review-queue"] });
  }, [qc]);
  return {
    unlock: async (code: string) => {
      await unlock(code);
      await refresh();
    },
    lock: async () => {
      await lock();
      await refresh();
    },
  };
}
