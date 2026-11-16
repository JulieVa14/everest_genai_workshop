# Project Plan

**Status**: Integrated
**Verification**: Local API/frontend integration verified; provider-dependent indexing, inference and live notebooks blocked by absent individual OpenAI API key. SQL/PostgreSQL migrations are not applicable to the approved SDK-managed storage.
**Created**: 2026-11-13
**Mode**: NEW

---

## 1. Project Overview

**Goal**: Implement the approved Course Companion educational workshop: four bounded Python exercises, a usable React/FastAPI app, a runnable instructor solution and completed notebook, a student notebook, and Windows teaching materials. Every module must be independently testable. This document distills the approved session plan; the user explicitly authorized implementation on 2026-11-13. Do not repeat requirements intake.

**App Type**: SPA + API

**API Login**: No

**Mode**: NEW

**Deployment Plan**: No deployment plan found. LOCAL workshop only; no Azure deployment, Azure services, Azure Functions, cloud database replacements, Docker requirement, or infrastructure provisioning. The .azure directory is workflow metadata, not authorization to deploy.

Use individual OpenAI API keys on each participant's localhost backend. Local persistence does not make inference local: retrieved text is sent to OpenAI. Never collect a key through chat, put one in React, or save one in notebooks, logs, git, or exported materials. ChatGPT subscriptions do not supply API billing. Use public/non-sensitive lecture documents only.

Outcome: upload course/lecture documents, index them, ask cited cross-lecture questions within a selected course, optionally filter a lecture, and persist follow-up conversation across reconnects. This is single-user localhost software, not production security. Authentication, deployment, OCR, streaming, multimodal agents, multi-agent orchestration and scaling are excluded.

---

## 2. Backend - FastAPI

| Component | Technology |
|-----------|------------|
| **Language** | Python |
| **Runtime** | CPython |
| **Framework** | FastAPI |
| **Package Manager** | uv |
| **Test Runner** | pytest |
| **Mocking Library** | unittest.mock |
| **Test Command** | uv run --project backend pytest backend/tests |
| **Orchestration** | Local Windows launcher; no containers required |

Select a supported Python interpreter after verifying SDK/Chroma compatibility; the detected default Python path is C:/Python315/python.exe, not evidence that Python 3.15 is compatible. Pin compatible dependencies and generate a lockfile. Explicitly configure an accessible low-cost chat model and embedding model; do not rely on SDK defaults. Use OpenAI Agents Python SDK Agent, Runner, function_tool and SQLiteSession, AsyncOpenAI Responses/embeddings APIs, and persistent ChromaDB.

Four shared interfaces: baseline_call, search_course_docs, build_course_tutor, run_course_chat. Completed implementations belong ONLY in instructor/solution.py. Student implementations belong in backend/app/exercise_steps.py with four bounded tasks, each at most 1-3 small TODO locations. Both implementations share supplied ingestion, storage, schemas, source validation and API presentation. Student mode imports only exercise_steps and reports unfinished tasks clearly; NEVER import or silently fall back to instructor code. Solution mode is startup configuration, not an HTTP parameter.

Ingestion is supplied infrastructure: validate PDF/text size/type, extract actual page text, reject empty extraction, chunk, embed with explicit same-model vectors, and upsert stable IDs with course_id, lecture_id, filename and page metadata. No accidental default embedding downloads, duplicate re-indexing, queue or mandatory OCR. Verify a small subset of existing PDFs and document usable pages/questions; do not invent PDF-based expected answers. Supply extracted-text fallback only if actual extraction needs it.

Scope is server-owned and validated. Search combines course and optional lecture filters with Chroma $and where needed and returns chunk ID, text, lecture, filename and page. Model tool arguments cannot override course scope. Metadata filtering is not authorization. Grounding instructions treat document text as untrusted evidence, not instructions. Validate structured citation IDs against evidence actually retrieved for the run; prompt instructions alone are insufficient. Do not use arbitrary distance thresholds as calibrated confidence.

Use file-backed SQLiteSession with a stable course-bound conversation ID. Send only the new message to Runner.run; never resend browser history alongside automatic sessions. SQLiteSession is conversation storage, not document storage or a custom trace database. Preserve course conversations independently; lecture changes narrow retrieval. Return compact observable tool names, arguments and evidence summaries from RunResult.new_items, not hidden reasoning or a mandatory exact tool sequence.

Separate student app, instructor app, student notebook and instructor notebook writable upload/Chroma/SQLite paths. Avoid concurrent notebook/backend writers sharing a directory. Restrict CORS to configured localhost frontend, bind localhost, bound uploads/tokens/retrieval count/max_turns, set provider/request timeouts, disable sensitive SDK trace export for core, and sanitize credentials/quota/tool errors. Provider budget alerts are not guaranteed hard spending caps.

---

## 3. Frontend - Web App

| Component | Technology |
|-----------|------------|
| **Language** | TypeScript |
| **Framework** | React + Vite |
| **Package Manager** | npm |
| **Test Runner** | vitest |
| **Mocking Library** | vi.mock |
| **Test Command** | npm --prefix frontend test -- --run |

Supply complete React fetch and POST /chat wiring in core. No required frontend exercise. A fetch/handler TODO is optional extension only. No marketing landing page. The first screen is the functional course companion: course/lecture selection, document upload/catalog, ready/indexing/error states, cited answers, conversation history, tool-event summary, pending/error handling and New conversation. Course changes create/select a separate conversation; refresh/reconnect restores persistent history. PDFs are real content assets, accessible from source citations using validated server-owned identifiers.

---

## 4. Services Required

| Azure Service | Role in App | Environment Variable | Default Value (Local) | Classification |
|---------------|-------------|----------------------|-----------------------|----------------|
| OpenAI API (not Azure) | Responses, agent inference and explicit embeddings | OPENAI_API_KEY; OPENAI_MODEL; OPENAI_EMBEDDING_MODEL | Key absent; explicit verified model IDs in .env.example | Essential |
| Local persistent ChromaDB (not Azure) | Course/lecture semantic retrieval | WORKSHOP_DATA_DIR | Separate generated data directory per mode and notebook/app | Essential |
| Local file-backed SQLiteSession (not Azure) | Persistent course-bound conversation | WORKSHOP_DATA_DIR | sessions.sqlite within isolated data directory | Essential |
| Local filesystem (not Azure) | Validated uploads and existing lecture PDFs | WORKSHOP_DATA_DIR | Generated uploads separate from immutable docs | Essential |

No Azure resources or credentials are required. No datastore substitutions. Missing OpenAI credentials must not prevent deterministic mocked checks or the UI shell from starting; live inference/indexing reports actionable errors, never fabricated success.

---

## 5. Prerequisites

### Run

| Tool | Service(s) | Installed | Version |
|------|------------|-----------|---------|
| CPython compatible with locked dependencies | Backend, notebooks | Confirmed command; compatibility unverified | Default path C:/Python315/python.exe |
| Python launcher py | Backend, notebooks | Confirmed command | Not measured |
| uv | Backend, notebooks | Confirmed command | Not measured |
| Node.js | Frontend | Confirmed command | Not measured |
| npm | Frontend | Confirmed command | Not measured |
| Windows PowerShell | Launcher | Confirmed running shell | 5.1 tool environment |

### Debug

| Tool | Service(s) | Installed | Version |
|------|------------|-----------|---------|
| VS Code Python extension | Backend | Unverified | Verify during setup |
| VS Code Jupyter extension/kernel | Notebooks | Unverified | Verify during setup |
| Browser/Playwright verification tools | Frontend | Unverified | Use available browser tooling |

Verify versions and a compatible interpreter during implementation, install dependencies, and preflight individual model/quota access before class. Never ask for an API key through model-mediated tools. No global execution-policy changes or elevation prompts. Document process-scoped launch instructions and manual commands.

---

## 6. Design System & UI

**Component Library**: Fluent UI v9
**Style Direction**: Restrained, polished educational document workspace with dense readable navigation, unframed main sections, 4-8px control corners and subtle dividers. Use lucide-react action icons with accessible labels/tooltips; predictable desktop and mobile workflows, no decorative heroes or nested cards.
**Typography**: Source Sans 3 for reading and controls; modest Source Serif 4 course heading; zero negative letter spacing and no viewport-scaled fonts.

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| primary | #176B58 | Active course, send/upload commands and document links |
| accent | #B94052 | Citation highlights and focused evidence markers |
| surface | #F6F7F8 | Neutral reading workspace |
| text | #232629 | Lecture and conversation content |
| muted | #626A70 | Page metadata and tool-event summaries |
| border | #D8DEE0 | Catalog separators and input outlines |

### Pages

| Page | Route | Purpose | Layout |
|------|-------|---------|--------|
| Course Companion | / | Upload, select course/lectures, ask questions and inspect cited evidence | header, sidebar, main, form, tabs |

### Sample Content

Use actual docs/ assets without modifying them. Before indexing, label them Available, not Indexed. Do not fabricate extracted facts, answers or page citations.

| Lecture | Asset | Initial State |
|---------|-------|---------------|
| Introduction | 00-Intro.pdf | Available |
| Large Language Models | 01-LLMs.pdf | Available |
| Applications and Tools | 02-LLMS_Applications_and_Tools.pdf | Available |
| Image Generation | 03-Image_Generation.pdf | Available |
| Audio Generation | 04-Audio_Generation.pdf | Available |
| Generative AI Ethics | 05-GAI_ethics.pdf | Available |

Course default: Generative AI. Lecture default: All lectures. Empty conversation is genuine, not a fake successful answer. Show an error inline for unconfigured credentials, loading while indexing/running, and an unfinished-exercise error in student mode. Sources open actual document/page content where supported. Responsive sidebar/drawer and composer must avoid overflow, overlapping text and layout shifts.

---

## 7. Project Structure

```text
.azure/project-plan.md
.gitignore
README.md
backend/
  pyproject.toml
  uv.lock
  .env.example
  app/
    __init__.py
    main.py
    exercise_steps.py
    retrieval.py
    tutor.py
  tests/test_workshop.py
frontend/
  package.json
  package-lock.json
  src/App.tsx
  src/ [only necessary shared styles/entry/tests]
notebooks/course_companion.ipynb
instructor/
  __init__.py
  solution.py
  course_companion_solution.ipynb
  runbook.md
exercises/workshop.md
scripts/
  launch.ps1
  [student export and explicit generated-data reset helpers]
docs/ [six existing PDFs preserved]
```

Manual text/code edits use apply_patch. Notebook creation/edits use notebook tools or nbformat structured generation, never apply_patch. Notebooks use top-level await, module imports with explicit reload between attempts, fresh-kernel reproducibility, theory/expected-observation/check/debrief cells, and no saved secrets. Completed notebook imports the single instructor solution; no duplicate solution implementation in cells. Student notebook imports only exercise_steps. Student export excludes instructor directory, completed notebooks, answer-bearing tests/artifacts, local data/keys and planning artifacts carrying answers. Narrow recovery checkpoints/hints are instructor-released after attempts, not a distributed full solution or overwrite of student work.

Launcher: explicit Student/Solution modes, preflight, compatible venv, absolute environment/data paths, configurable available frontend/backend ports, two processes, cleanup/shutdown instructions and separate manual commands. Never rewrite student files or start another writer against notebook data. Student export must work with instructor physically absent; Solution selection then fails clearly. Reset is explicit and restricted to generated data, never docs/code. Ignore keys, outputs with secrets, uploaded files, SQLite/Chroma data, dependencies and build artifacts. No git commits.

---

## 8. Route Definitions

| # | Method | Path | Description | Request Body | Response Body | Status Codes |
|---|--------|------|-------------|--------------|---------------|--------------|
| 1 | GET | /health | Shell/configuration and service health without exposing secrets | None | status, mode, capabilities | 200, 503 |
| 2 | GET | /courses | Validated course catalog | None | courses | 200 |
| 3 | GET | /courses/{course_id}/lectures | Lecture catalog/index states | None | lectures | 200, 404 |
| 4 | POST | /courses/{course_id}/lectures | Upload and synchronous small-corpus indexing | Multipart lecture metadata and PDF/text | lecture, indexing state | 200, 400, 413, 415, 502 |
| 5 | POST | /chat | Supplied handler delegates selected exercise implementation | course_id, optional lecture_id, conversation_id, new message | answer, validated sources, tool_events, conversation_id | 200, 400, 404, 409, 422, 502 |
| 6 | GET | /courses/{course_id}/conversations/{conversation_id} | Restore course-bound display history | None | messages | 200, 404 |
| 7 | GET | /sources/{source_id} | Validated actual document asset, not an arbitrary filesystem path | None | Document bytes with safe headers | 200, 404 |

Finalize coherent route schemas in implementation; keep all supplied frontend calls synchronized. No endpoint may select instructor implementation or accept arbitrary paths. Core chat/React wiring is supplied, not a fifth required exercise.

---

## 9. Next Steps

1. Hand off to azure-project-scaffold to IMPLEMENT this already approved local package. Preserve every explicit constraint; do not repeat intake, introduce Azure, or stop at placeholders. Setup mechanics may be used downstream when compatible with this local scope.
2. Verify the smallest instructor vertical slice first: real PDF extraction, explicit embeddings, persistent filtered Chroma, typed agent tool, file-backed SQLite restart. Implement shared interfaces and single instructor solution, then derive the four student tasks and notebooks. Mock OpenAI for deterministic tests. Without a configured individual key, disclose live-source verification as blocked; do not request a key through the model or fake live success.
3. Complete FastAPI/React integration, launchers, documentation and student export. Run compatible dependency installation, focused Python tests, frontend tests/typecheck/build, completed notebook fresh-kernel checks where credentials permit, and export checks with instructor absent. Test course/lecture isolation, idempotent indexing, persistence through a new instance/process, fresh sessions, valid citation provenance, sanitized errors, invalid scope and unsupported/oversize/empty uploads. Do not require exact model answer strings or tool ordering.
4. Start the local solution dev server on available ports and verify desktop/mobile with available browser tools: upload/index/question/sources/follow-up/reconnect/new conversation/course change, pending/errors, real PDF assets, no overflow and no browser key exposure. Test occupied ports and paths with spaces where feasible. Report actual commands/results, runnable URLs and unverified gates. Do not claim tests, browser checks or timing rehearsals occurred unless executed.
5. Author instructor runbook, student worksheet, hints and narrow recovery checkpoints. Explain API calls/token usage; chunks/embeddings/filters; tool schemas/model-tool-result loop; conversation history versus retrieval index. Protect independent work time, debrief after each exercise, and do not teach the next concept while students code.
6. Provide exact 120-minute pacing INCLUDING theory: 0-8 orientation/preflight; 8-23 exercise 1 (4 theory/8 work/3 debrief); 23-48 exercise 2 (6/15/4); 48-78 exercise 3 (7/18/5); 78-98 exercise 4 (4/12/4); 98-108 app walkthrough (4 explain/6 checks); 108-120 evaluation/reveal (7 pair testing/5 demo). Totals: 8 orientation + 25 theory + 66 work/checks + 16 debrief + 5 demo. Dependencies/install/key checks happen before class.
7. Provide exact 90-minute pacing INCLUDING theory: 0-5 orientation; 5-17 API (3/7/2); 17-35 retrieval (4/11/3), supplied pre-indexed small corpus with same verified embedding model; 35-60 agent tool (6/15/4); 60-76 session (3/10/3); 76-82 app (2 explain/4 checks); 82-90 evaluation/reveal (4 testing/4 demo). Totals: 5 orientation + 18 theory + 51 work/checks + 12 debrief + 4 demo. Explain how to prepare compatible pre-indexed student data; do not ship instructor session history or silently replace live embeddings. No required frontend TODO.
8. Include known-answer, cross-lecture, missing-evidence, malicious-document-instruction, unavailable-retrieval, course-isolation and fresh-session evaluations with verified real source references. Instructor demo: upload, indexed cited comparison, remembered follow-up and abstention. Timing is an estimate requiring representative human 90/120-minute rehearsals; disclose unperformed rehearsals. Environment overruns consume extensions/discussion, not protected agent-tool work or minimum evaluation.
9. Stop at working LOCAL delivery and an honest verification report. Do not invoke Azure deployment/debug infrastructure workflows. Integration/testing is authorized within this scope; no cloud provisioning or commits.