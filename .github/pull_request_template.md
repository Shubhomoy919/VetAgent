## What and why

<!-- What this change does and the problem it solves. Link the issue: Closes #123 -->

## Type

- [ ] Bug fix
- [ ] New feature or page
- [ ] Data change (cases, drug table): changes the benchmark hash
- [ ] Scoring or metric change
- [ ] Docs, CI or tooling

## Checks

- [ ] `npm test` (pytest) passes
- [ ] `npm --prefix frontend run check` (tsc, eslint, style, contrast, motion) passes
- [ ] `npm --prefix frontend run build` succeeds
- [ ] `python -m app.scripts.snapshot verify` still prints OK, or the change explains why results move
- [ ] Screenshots attached for interface changes (1440 and 1024 px)

## Research integrity

- [ ] No dose, withdrawal period or ban reference was added without a cited source
- [ ] New cases and drug rows are marked unverified
- [ ] No API keys, access codes or `.env` files are included
