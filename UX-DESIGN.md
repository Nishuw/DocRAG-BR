# DocRAG BR — UX Architecture: Terminal-First AI Audit Platform

> Design document for the post-Streamlit experience. Part 1 (CLI) is **implemented**
> (`python -m src.cli`); items marked *roadmap* are the designed next steps.
> Part 2 (web companion) is an architecture proposal.

## Interaction philosophy

DocRAG BR is not a chatbot — it is an **audit cockpit**. Three principles:

1. **The system speaks first.** `/audit` makes the platform read the document and
   report verified findings before any question is asked. Questions are one mode
   of operation, not *the* interface.
2. **Every claim carries proof.** Numbers are marked ✓/⚠ inline, each answer shows
   a fidelity bar, and every source is one `/open N` away from the real PDF page
   with the cited excerpt highlighted. Trust is a UI element, not a promise.
3. **Operations are visible.** Retrieval stages, token usage, estimated cost and
   latency are first-class information — the user watches the machine work.

## 1. Primary interface — CLI (implemented)

### Architecture

```
src/cli.py            REPL + renderer (Rich). Zero business logic.
src/rag.py            query pipeline (routing → retrieval → rerank → stream)
src/verification/     verifier (deterministic) + autonomous auditor
src/embeddings/       local embeddings + ChromaDB
src/chat/pdf_preview  page render + highlight (evidence engine)
```

The CLI is a *view* over the same engine the old UI used — UI layers are
disposable, the audit engine is the product.

### Screen layout

- **Boot header**: platform panel — index size by modality (text/table/chart),
  documents, models, API status, language.
- **Answer panel**: live-streamed tokens (Rich `Live`), then re-rendered with
  per-number audit marks and the fidelity bar.
- **Findings panels** (`/audit`): one bordered panel per finding, color-coded by
  severity (ALERT red / ATTENTION yellow / HIGHLIGHT orange / INFO blue), each
  with its own fidelity bar and evidence pointer.
- **Tables**: sources, semantic search hits, session stats.

### Command system (palette: `/help`)

| Command | Role |
|---|---|
| `<question>` | audited answer, streamed |
| `/audit` | autonomous audit (the system speaks first) |
| `/find <text>` | semantic explorer over the index — local, no LLM |
| `/open <n>` | opens evidence: real page, excerpt highlighted (OS viewer) |
| `/index` | knowledge index status |
| `/lang en\|pt` | output language (numbers keep BR source format) |
| `/stats` | session tokens, estimated cost, LLM time |
| `/exit` | quit |

### Sessions, config, errors, logging

- **Session state**: in-memory (language, usage meters, evidence registry).
  *Roadmap:* `--session` flag persisting transcript + findings as JSON for replay.
- **Config**: `.env` + `src/config.py` (models, chunking, retrieval budgets).
  *Roadmap:* `/config` screen with live overrides.
- **Errors**: every LLM call has a deterministic fallback (search never breaks);
  the REPL catches all exceptions — the cockpit never crashes mid-demo.
- **Logging/observability**: per-call cost line under every answer.
  *Roadmap:* `--debug` streaming the router/reranker decisions live.

### Roadmap (designed, not built)

- Textual full-screen app: split view (findings list ← → page viewer) with
  keyboard navigation (j/k, enter to open evidence) — the terminal version of
  "document as interface".
- Plugin architecture: ingestion adapters (`cvm://`, `sec://`) and custom
  verifiers registered via entry points.
- Multi-workspace: one index per portfolio company, `\ws` switcher.
- Verified calculator agent (`/calc`): LLM emits formula + operands, operands
  audited against sources, arithmetic runs in Python.

## 2. Companion web app (proposal)

**Purpose:** visualization, not interaction. The CLI operates; the web observes.

- **Stack**: Next.js + TailwindCSS + shadcn/ui; FastAPI backend exposing the
  audit engine; WebSocket channel streaming engine events (`retrieval.hit`,
  `verify.number`, `audit.finding`).
- **Views**:
  - *Live execution graph* — the pipeline (route → retrieve → rerank → answer →
    verify) animating as a CLI session runs; each verified number lights green.
  - *Evidence wall* — findings pinned onto rendered document pages
    (pdf.js overlay), the "document as interface" vision.
  - *Company timeline* — metrics across quarters once multiple filings are
    ingested (temporal twin).
  - *Fidelity analytics* — hallucination-catch rate over time.
- **State**: server-driven (engine is the source of truth); TanStack Query +
  WS invalidation; zustand only for view state.
- **Design system**: dark, terminal-adjacent (same palette as the CLI: deep
  green/slate, severity colors), CSS variables for theming.

## Why this beats the old Streamlit UI

1. **Judges are technical.** A rich terminal cockpit reads as *platform
   engineering*; a Streamlit page reads as *demo scaffolding*.
2. **The paradigm is visible.** Fidelity bars, severity-coded findings and
   `/open` evidence make "proof, not promise" something you can *watch*.
3. **Observability is the differentiator.** Cost, tokens, latency and pipeline
   stages on every interaction communicate autonomy + orchestration — an AI
   platform, not a chat page.
4. **It demos fast.** Boot header → `/audit` → panels appear → `/open 1` → the
   real page opens with the highlight. Under 60 seconds, no browser required.
