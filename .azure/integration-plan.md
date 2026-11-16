# Course Companion Integration

## Scope

- Approved local-only React + FastAPI workshop. NO Azure services, deployment,
  infrastructure, Docker, custom SQL migrations or seed data.
- Resume existing implementations; do not regenerate exercises or gather requirements.
- Essential: OpenAI API, persistent Chroma, file-backed SDK SQLiteSession, filesystem.
  No Enhancement services. Individual credentials remain backend-only.

## Backend

- Folder: `backend`; imports: `backend.app.*`; Python 3.12; uv lock present.
- Install: `uv sync --project backend --python 3.12 --locked`.
- Student pip alternative: `py -3.12 -m venv backend/.venv`, then
  `backend/.venv/Scripts/python.exe -m pip install -r requirements.txt`.
  Root requirements.txt is exported from uv.lock with all notebook/check dependencies.
  A clean temporary Python 3.12 venv passed actual pip installation, `pip check`, and
  imports of FastAPI, Agents, Chroma, pypdf, ipykernel, nbformat and nbclient.
  Frontend dependencies remain `npm --prefix frontend ci`.
  Copy backend/.env.example only when backend/.env is absent; enter keys privately.
- Build: `uv run --project backend python -m compileall -q backend/app instructor/solution.py`.
- Test: `uv run --project backend pytest backend/tests`.
- Run from root: `uv run --project backend python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file backend/.env`.
  Omit `--env-file` when no file exists; shell/catalog must work without a key.
- Mode: `WORKSHOP_MODE=student|solution` at startup only. Student implementation:
  `backend/app/exercise_steps.py`; only completed implementation: `instructor/solution.py`.
- Health: `GET /health`; port 8000 by default. Set `FRONTEND_ORIGIN` to actual UI origin.
- Launcher: `scripts/launch.ps1 -Mode Student|Solution`; `-CheckOnly`, `-SkipInstall`,
  `-BackendPort`, `-FrontendPort`; occupied ports advance and actual URLs are printed.
- Key/model configuration: ignored `backend/.env`; template `backend/.env.example`.
  Never print secrets or send a key through chat. Explicit models: `gpt-5.6-terra`,
  `text-embedding-3-large`; model access/quota are not established by mocks.

## Frontend

- Folder: `frontend`; install `npm --prefix frontend ci`.
- Build: `npm --prefix frontend run build`; tests `npm --prefix frontend test -- --run`.
- Dev: `npm --prefix frontend run dev`; preview tool owns scaffold preview server.
- Live-only entry: `frontend/src/api/index.ts` always selects `liveClient.ts`.
  The legacy `VITE_WORKSHOP_API_MODE` flag no longer changes client selection.
- Set non-secret `WORKSHOP_API_URL=http://127.0.0.1:<backend-port>` for Vite `/api` proxy.
- Live wiring is supplied. The integration request authorized live-only selection;
  `src/api/mockClient.ts` and `src/api/previewState.ts` were removed along with
  their imports and obsolete preview tests. Deterministic test doubles remain tests only.
- NO mock datasets under `src/mocks`, duplicated standalone types, or corner-switcher
  component exist. `src/api/previewAssets.ts` is the immutable PDF whitelist imported
  by Vite and must remain. `src/api/types.ts` contains necessary Zod runtime schemas.
- Shared contracts: backend `app/schemas.py` mirrored by frontend `src/api/types.ts`;
  no shared TypeScript package or import alias exists. Validate route parity rather
  than inventing a package.

## Routes

| Method | Path | Probe |
| --- | --- | --- |
| GET | /health | status/mode/capabilities; no secrets, no-key shell allowed |
| GET | /courses | course catalog |
| GET | /courses/{course_id}/lectures | available/ready/error lecture catalog |
| POST | /courses/{course_id}/lectures | multipart title/file/optional lecture_id; real indexing only |
| POST | /chat | course_id, nullable lecture_id, canonical UUID conversation_id, NEW message only |
| GET | /courses/{course_id}/conversations/{conversation_id} | course-bound display messages |
| GET | /sources/{source_id} | registered original PDF/text bytes; never arbitrary paths |

## Persistence and Distribution

- Chroma stores documents; SDK SQLiteSession stores conversations; JSON stores
  validated display history. NO SQL/PostgreSQL database or migration directory.
  SDK initializes its own SQLite schema; do not create custom session migrations.
- `WORKSHOP_DATA_DIR` is an app base; mode is appended. Defaults:
  `.workshop-data/app/student|solution`; notebooks:
  `.workshop-data/notebook/student|solution`. Never share concurrent writers.
- NO seed data, synthetic success, instructor sessions, or fake embeddings.
- Corpus: `scripts/prepare_corpus.py` build/export/import; real build requires a key,
  verifies full Intro/Ethics original PDF provenance and exact model/dimensions.
- Packaging tests: `uv run --project backend pytest scripts/test_tools.py`.
- Export `scripts/export_student.py`; reset `scripts/reset_data.py`; inspect `--help`.
  Root requirements.txt is included unchanged in student exports (focused tests passed).
  Student export must work with instructor physically absent. Preserve original PDFs.

## Resumed Verification (2026-11-13)

- Backend: 35 passed on Python 3.12.10; deterministic SDK/embedding fixtures,
  real PDF extraction, storage, scope, provenance and session checks.
- Python Ruff: passed for backend/app, backend/tests, instructor/solution.py, scripts.
- Packaging: 7 passed, 1 skipped (Windows symlink privilege); includes real export
  imports without instructor, Windows junction protection, occupied ports and spaces.
- Frontend production typecheck/build: passed; all six original PDFs emitted.
- Final frontend suite: 29 passed. The drawer opening probe uses a direct click
  to isolate rendering from jsdom's synthetic pointer/focus sequence; browser
  pointer/focus behavior still needs verification. Frontend typecheck/build passed.
  Dependencies restored from npm lock after interrupted installs.
- Regenerated student and solution notebooks: six fresh offline kernels passed
  from workspace/notebooks/instructor directories, no network or saved outputs.
- Final combined backend/export tests: 42 passed, 1 skipped. Clean temporary pip
  installation from requirements.txt passed dependency/import checks.
- No live provider success, semantic retrieval quality, full live notebook run,
  browser end-to-end workflow or human timing rehearsal claimed.
- Teaching schedules exist in instructor/runbook.md and exercises/workshop.md.
  Retain concurrent user updates; finalize any remaining stale instructor anchors
  using backend/README.md extraction facts, not fabricated chunk IDs.

## Required Integration Checks

1. Preserve the passing frontend/backend/export/offline-notebook checks; verify
  real browser drawer opening/closing/focus on desktop and mobile.
2. Launch local backend with available ports; smoke-test all seven routes and
   negative/no-key/unfinished Student states, using actual configured origin.
3. Use existing live flag; verify desktop/mobile upload, sources, pending/error,
   reconnect, new session, course/lecture isolation and overflow without browser keys.
4. Execute notebooks from a fresh kernel; explicit offline skip is not live success.
5. Live embeddings/inference require an individually configured key. If absent,
   report blocked gates without requesting secrets or fabricating success.
6. NO cloud provisioning, SQL migrations, seed data or git commits. Timing is an
   estimate until representative humans rehearse both 90/120-minute routes.

## Integration Results (2026-11-13)

- SQL/PostgreSQL migrations: not applicable to this approved storage design.
  Chroma and SDK-managed SQLite remain unchanged; no custom schema or seed data added.
- Backend compiled and ran at `http://127.0.0.1:8000` in Solution mode with
  isolated `.workshop-data/integration/solution` storage and frontend origin
  `http://localhost:5173`. All seven operations registered across six OpenAPI paths.
- HTTP probes: health, courses, lectures and original PDF source returned 200;
  fresh history returned structured 404; missing upload/chat bodies returned 422;
  unsupported upload returned 415. No runtime-bug 500 responses observed.
- No individual API key is configured. Valid chat and original-PDF upload returned
  sanitized 502 `provider_unavailable`; UI displayed the real error and retained
  the question draft. Successful indexing/inference, cited answers, provider-backed
  follow-ups and live notebook execution remain BLOCKED, not passed.
- Runtime mock files removed; live-only selection and API contracts passed nine
  focused tests. Full frontend suite passed 26 tests; production typecheck/build
  passed and emitted all six immutable PDFs. Backend/export: 42 passed, one skipped
  for Windows symlink privileges.
- Browser verification ran against concurrent Vite/FastAPI processes. Native
  browser `/api/health`, `/api/courses`, and `/api/courses/generative-ai/lectures`
  fetches returned 200. The catalog displayed six actual backend lectures; the
  proxied Intro source returned 200 with 1,375,265 bytes and `%PDF-` signature.
- Desktop 1440x1000 and mobile 390x844 were screenshot-checked without horizontal
  overflow. Verified upload/chat error handling, reconnect, new UUID session,
  reload session preservation, separate Study Notes course and lecture filtering.
- Browser checks exposed and fixed Fluent portal providers inheriting full-page
  layout and blocking clicks. Mobile drawer pointer opening, Escape closing,
  focus containment and focus restoration now pass using Fluent focus hooks.
- Browser request-context/event helpers had protocol limitations; native browser
  fetches and UI assertions supplied evidence instead. No browser credentials,
  fake provider responses, synthetic embeddings or pre-populated integration data.
- Final drawer regression assertion passed (17 workspace tests); final production
  build passed after both browser fixes. Mobile filtered-source request returned
  200 `application/pdf`. Both integration test server processes were stopped.