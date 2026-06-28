# Babel Loses Here

*Stub seeded by the pre-Studio scaffolding (2026-06-27). Canonical:
`STUDIO_MAXIMIZATION_2026_06_27.md` §12.5, §12.11, §11.7.*

This is a **standing, public** page, linked from the leaderboard header, listing every
accent cell where Babel is **not** the best row. Its existence is the strongest single
answer to the self-dealing critique (§12.2): if Babel won every cell, the board would look
rigged. The page must be **non-empty** at launch (§12.11).

It is updated on every baseline refresh (§12.9 cadence).

## Schema (one row per cell Babel loses)

| accent_family | model that beats Babel | their WER | Babel WER | quality_card | date |
|---|---|---:|---:|---|---|

## Current state

_Empty — no Babel checkpoint has been scored yet (the acoustic distill is Studio work, §13.B
S1). Until a Babel row exists, the only rows on the board are the external baselines in
`BASELINES.md` (turbo, tiny). This page is populated the first time Babel is scored against
the frozen `manifest.csv` and loses at least one cell — which, per §12.11, it must, or the
labeling/grouping is suspect._
