/* Runs after every other release spec (files run in name order, one worker): it uses up this IP's
 * per-minute allowance on purpose. Point E2E_LIMIT_URL at an instance with a low RATE_LIMIT_PER_MINUTE
 * (the browsing specs run against one with a high limit, since they make hundreds of requests a minute). */
import { expect, request, test } from "@playwright/test";

test("the per-IP rate limit answers 429 with Retry-After (runs last)", async ({ baseURL }) => {
  const ctx = await request.newContext({ baseURL: process.env.E2E_LIMIT_URL ?? baseURL! });
  let limited: { status: number; retry: string | undefined } | null = null;
  for (let i = 0; i < 400 && !limited; i++) {
    const r = await ctx.get("/api/meta/metrics");
    if (r.status() === 429) limited = { status: 429, retry: r.headers()["retry-after"] };
  }
  expect(limited?.status).toBe(429);
  expect(Number(limited?.retry)).toBeGreaterThan(0);
  // health checks stay exempt so the platform never marks the service down
  expect((await ctx.get("/api/health")).status()).toBe(200);
  await ctx.dispose();
});
