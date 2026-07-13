# linkedin-queue

Personal tooling to support a remote job search.

## Non-negotiable principle
Nothing touches LinkedIn programmatically. No scraping, no automated
visits, no auto-connect. The script decides the targets and generates
links; the click is human. This protects the account against bans.

## Architecture
- queue_agent.py — fetches job boards (RemoteOK/Remotive/WWR), scores by
  keyword (role keyword in title required, stack keywords add points),
  filters by location, dedups in SQLite, outputs markdown to `queues/`.
  Optional `--notes` drafts sub-200-char connection notes via a local
  Ollama model.
- tracker.py — outreach CLI (add/due/done/board/history); shares the same
  state.db. Company names resolve by prefix when unambiguous.
- config.toml — all configuration (sources, filters, targets, ollama).
- install.sh — bash setup helper: ensures Ollama is installed, detects GPU
  VRAM (nvidia-smi, or amdgpu sysfs for AMD), picks a fitting qwen3 model
  from a size ladder, pulls it, and updates the `[ollama]` model in
  config.toml.
- state.db, queues/ and cron.log are local and gitignored (they contain
  data about real people).

## Conventions
- Pure stdlib, no dependencies.
- Python 3.11+ (uses tomllib).
- Surgical edits, no rewrites.

## Owner context
Senior SWE / Tech Lead, stack React/Next/TS/Node/NestJS, based in Brazil,
looking for international remote roles (hence the `brazil_friendly_only`
location filter). Local Ollama on an RTX 3050 6GB — models up to ~4B in
Q4 fit entirely on the GPU.
