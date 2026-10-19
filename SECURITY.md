# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |
| < 1.0 | No |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through GitHub: **Security → Report a vulnerability** on this repository
([direct link](https://github.com/Shubhomoy919/VetAgent/security/advisories/new)). Include:

- what is affected (endpoint, page, configuration) and the version from `/api/health`;
- steps to reproduce, and what an attacker could do with it;
- any suggested fix.

You can expect an acknowledgement within 7 days and an assessment within 30 days. Fixes are released as a patch
version and credited in the changelog unless you prefer otherwise.

Please test only against your own deployment (see [docs/DEPLOY.md](docs/DEPLOY.md)), not against sites run by
others, and do not access data that is not yours.

## Scope

In scope:

- bypassing read-only mode or the access code, session forgery, lockout or rate-limit bypass;
- exceeding the daily token budget or the case cap;
- reading the SVTG PDF, uncited passages, demo data in production, or anything from `.env`;
- injection, XSS, CSRF, path traversal, header or CORS weaknesses;
- secrets in logs, responses or the repository history.

Out of scope: denial of service by volume, findings that need a compromised host, and the clinical accuracy of
model answers (that is a research question. Open a normal issue).

## How the deployment is protected

A summary. The details are in [docs/DEPLOY.md](docs/DEPLOY.md#operations).

- **Read-only public mode** in production. Running cases, editing data, Review and Settings need
  `ADMIN_ACCESS_CODE`.
- **Access code:** compared as a salted scrypt hash in constant time. Unlocking sets a signed (HMAC-SHA256),
  httpOnly, Secure, SameSite=Strict cookie. Per-IP and global lockout after repeated wrong codes.
- **Limits:** a per-IP rate limit on every endpoint except health, a daily live-token budget, a cap on cases per
  run and a request body size limit. The counters are kept in the database, shared by every serverless instance.
- **Headers:** Content-Security-Policy, HSTS, X-Frame-Options, nosniff, Referrer-Policy, and a same-origin
  check on writes. CORS is limited to `ALLOWED_ORIGINS`.
- **Secrets:** server-only environment variables, never logged (redacted at record creation) or returned. Health
  shows only `key_present` and the database engine name. A build check scans the frontend bundle for secret
  values, and the git history is scanned with gitleaks.
