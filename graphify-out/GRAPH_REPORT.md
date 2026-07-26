# Graph Report - .  (2026-07-26)

## Corpus Check
- Corpus is ~22,774 words - fits in a single context window. You may not need a graph.

## Summary
- 434 nodes · 1242 edges · 17 communities
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 57 edges (avg confidence: 0.63)
- Token cost: 0 input · 115,971 output

## Community Hubs (Navigation)
- SQLite Data Layer
- Vendored htmx Library
- Web UI Page Rendering
- Resume Profile Ingestion
- HTTP Request Handler
- Extension Manifest & Permissions
- Config & Concept Docs
- Core State & Config
- LLM Backend Adapters
- LinkedIn Safety Principle
- Extension Popup UI
- Outreach Tracker CLI
- Web UI Documentation
- Jobs Page Extraction
- Ollama Install Script
- Resume-in-the-Loop Spec
- Feed Extraction Script

## God Nodes (most connected - your core abstractions)
1. `server/CLAUDE.md architecture & conventions doc` - 55 edges
2. `Job` - 39 edges
3. `ne()` - 28 edges
4. `De()` - 28 edges
5. `se()` - 27 edges
6. `ue()` - 27 edges
7. `e()` - 26 edges
8. `esc()` - 20 edges
9. `ee()` - 19 edges
10. `pt()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Privacy by design` --semantically_similar_to--> `Nothing touches LinkedIn programmatically (non-negotiable principle)`  [INFERRED] [semantically similar]
  server/docs/architecture.md → CLAUDE.md
- `The human-click principle` --semantically_similar_to--> `Nothing touches LinkedIn programmatically (non-negotiable principle)`  [INFERRED] [semantically similar]
  server/docs/concepts.md → CLAUDE.md
- `LinkedIn Queue Assistant (Chrome extension) README` --semantically_similar_to--> `Nothing touches LinkedIn programmatically (non-negotiable principle)`  [INFERRED] [semantically similar]
  extension/README.md → CLAUDE.md
- `Spec: Resume-in-the-loop job matching` --conceptually_related_to--> `draft_note()`  [INFERRED]
  server/.specs/resume-in-the-loop/SPEC.md → server/pipeline/resume.py
- `Spec: Resume-in-the-loop job matching` --conceptually_related_to--> `score_job()`  [INFERRED]
  server/.specs/resume-in-the-loop/SPEC.md → server/pipeline/scoring.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Daily queue build pipeline: collect -> gate -> dedupe -> optional LLM re-rank -> cap -> persist** — server_sources_init_collect_jobs, server_pipeline_scoring_score_job, server_pipeline_resume_rerank_with_resume, server_pipeline_select_select_queue, server_db_queue_save_queue, server_pipeline_build_build_queue [INFERRED 0.85]
- **Uniform fetch(cfg) -> list[Job] interface implemented by every job-board source module** — server_sources_remoteok, server_sources_remotive, server_sources_wwr, server_sources_hn, server_sources_base [EXTRACTED 1.00]
- **webapp/pages/ modules registered as routes via the GET_ROUTES facade** — server_webapp_pages_queue, server_webapp_pages_board, server_webapp_pages_due, server_webapp_pages_log, server_webapp_pages_company, server_webapp_pages_stats, server_webapp_pages_profile, server_webapp_pages_init [EXTRACTED 1.00]

## Communities (17 total, 0 thin omitted)

### Community 0 - "SQLite Data Layer"
Cohesion: 0.05
Nodes (75): HTMLParser, connect(), Connection, Bare connection to the shared state.db, rows addressable by name.  No schema cre, db_connect(), Connection, Connection + schema: owns the pipeline tables on the shared state.db., SQLite state layer, one concern per module (mirrors sources/).  `db_connect` own (+67 more)

### Community 1 - "Vendored htmx Library"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 2 - "Web UI Page Rendering"
Cohesion: 0.09
Nodes (43): Spec: htmx on the daily-queue page, assets.py HTMX_JS constant, page(), Row, Page chrome: the HTML shell (`page`) and the outreach `timeline_row`., timeline_row(), page_board(), `/board` — pipeline overview by latest outreach stage. (+35 more)

### Community 3 - "Resume Profile Ingestion"
Cohesion: 0.15
Nodes (21): proposed profile.py CLI (import/show), cmd_import(), cmd_show(), main(), Namespace, Command-line interface: import a LinkedIn export ZIP, or show the profile., ingest(), ProfileError (+13 more)

### Community 4 - "HTTP Request Handler"
Cohesion: 0.16
Nodes (8): BaseHTTPRequestHandler, HTTPStatus, parse_multipart(), Minimal multipart/form-data parser (stdlib dropped `cgi` in 3.13)., Returns field-name → raw bytes; enough for a single file upload and     binary-s, Handler, Score items the browser extension read off LinkedIn; queue         anything that, Reject cross-site POSTs; same-origin forms send a matching Origin.

### Community 5 - "Extension Manifest & Permissions"
Cohesion: 0.12
Nodes (15): action, default_popup, default_title, content_scripts, description, host_permissions, manifest_version, name (+7 more)

### Community 6 - "Config & Concept Docs"
Cohesion: 0.30
Nodes (15): Owner context: senior SWE/Tech Lead in Brazil, local Ollama on RX 6700 XT, [filters] config section, [resume] config section, [targets] config section, Privacy by design, CLI reference doc, The daily queue, Concepts doc (+7 more)

### Community 7 - "Core State & Config"
Cohesion: 0.18
Nodes (13): Surgical, not a rewrite (non-negotiable), Conventions: pure stdlib, no dependencies; surgical edits, no rewrites, server/CLAUDE.md architecture & conventions doc, [ollama] config section, [sources] config section, cron.log, outreach table, queued_companies table (+5 more)

### Community 8 - "LLM Backend Adapters"
Cohesion: 0.15
Nodes (9): generate(), Pluggable LLM backend, one module per provider (mirrors sources/).  `[llm].provi, qwen3 leaks <think>…</think> even with think disabled; drop it., One completion from the configured provider; None if unreachable., strip_think(), generate(), Local Ollama backend: one /api/generate call., Returns raw response text, or None if the server is unreachable. (+1 more)

### Community 9 - "LinkedIn Safety Principle"
Cohesion: 0.23
Nodes (12): simple-job-seeker root CLAUDE.md, extension/ Chrome extension, Nothing touches LinkedIn programmatically (non-negotiable principle), server/ Python pipeline, content/feed.js SELECTORS object, content/jobs.js SELECTORS object, Popup UI (Scan this page form), LinkedIn Queue Assistant (Chrome extension) README (+4 more)

### Community 10 - "Extension Popup UI"
Cohesion: 0.24
Nodes (10): isSupportedUrl(), refreshScanAvailability(), renderResults(), resultsEl, scan(), scanBtn, serverUrlInput, setStatus() (+2 more)

### Community 11 - "Outreach Tracker CLI"
Cohesion: 0.47
Nodes (10): cmd_add(), cmd_board(), cmd_done(), cmd_due(), cmd_history(), main(), Connection, Namespace (+2 more)

### Community 12 - "Web UI Documentation"
Cohesion: 0.22
Nodes (9): The checkbox (worked today), Board tab, Company timeline page, Web UI guide doc, Due tab, Log tab, Queue tab, Resume tab (+1 more)

### Community 13 - "Jobs Page Extraction"
Cohesion: 0.73
Nodes (5): absoluteUrl(), cleanText(), extractDetailPane(), extractItems(), extractListCards()

### Community 14 - "Ollama Install Script"
Cohesion: 0.47
Nodes (3): ensure_ollama(), set_config_model(), install.sh script

### Community 15 - "Resume-in-the-Loop Spec"
Cohesion: 0.40
Nodes (5): Spec: Resume-in-the-loop job matching, proposed fetch_hn() source, Graceful degradation (no profile / Ollama down), profile table, queue_items table

### Community 16 - "Feed Extraction Script"
Cohesion: 0.83
Nodes (3): cleanText(), extractItems(), permalinkFor()

## Knowledge Gaps
- **33 isolated node(s):** `manifest_version`, `name`, `version`, `description`, `default_popup` (+28 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `server/CLAUDE.md architecture & conventions doc` connect `Core State & Config` to `SQLite Data Layer`, `Web UI Page Rendering`, `Resume Profile Ingestion`, `HTTP Request Handler`, `Config & Concept Docs`, `LLM Backend Adapters`, `LinkedIn Safety Principle`, `Outreach Tracker CLI`, `Ollama Install Script`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Why does `Job` connect `SQLite Data Layer` to `Web UI Page Rendering`, `HTTP Request Handler`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `Handler` connect `HTTP Request Handler` to `SQLite Data Layer`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `manifest_version`, `name`, `version` to the rest of the system?**
  _33 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `SQLite Data Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.051648351648351645 - nodes in this community are weakly interconnected._
- **Should `Vendored htmx Library` be split into smaller, more focused modules?**
  _Cohesion score 0.07935026138909634 - nodes in this community are weakly interconnected._
- **Should `Web UI Page Rendering` be split into smaller, more focused modules?**
  _Cohesion score 0.0936408106219427 - nodes in this community are weakly interconnected._