# Course Companion Frontend

React, Vite, TypeScript, Fluent UI v9 and lucide-react. Source Sans 3 and Source Serif 4 are self-hosted. No authentication, Azure dependencies or browser API keys.

## Commands

From the repository root:

```sh
npm --prefix frontend ci
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Students usually start the app from the notebook with `lab.open_app()`; the Windows launcher in the [main README](../README.md) is an alternative. These test/build commands do not start servers.

## Live Integration

No source edit or API-mode flag is required. [src/api/index.ts](src/api/index.ts) always selects the live client; there is no mock fallback. For a manual launch, run this in a separate frontend PowerShell terminal from the repository root, with the backend already configured for `FRONTEND_ORIGIN=http://127.0.0.1:5173`:

```powershell
$env:WORKSHOP_API_URL = 'http://127.0.0.1:8000'
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. If either port is occupied, choose available ports and update the backend origin and frontend proxy target together; `localhost` and `127.0.0.1` are different origins. Ctrl+C stops this frontend; stop the backend separately. Vite's config permits forwarded hosts/iframe previews, so keep this development server on a trusted local machine. No server is implied to be running already.

All components use `api`; fetch and POST handlers are supplied, not workshop exercises. Vite proxies `/api` to the non-secret `WORKSHOP_API_URL`, stripping `/api`. Builds also use the live client by default. The default `/api` production URL needs a same-origin reverse proxy; Vite's development proxy does not exist in static hosting. A separate API can use the non-secret `VITE_API_BASE_URL` at build time with matching backend CORS. This workshop does not require deployment.

The mock client and preview-state override have been removed. Keep [src/api/previewAssets.ts](src/api/previewAssets.ts), the whitelist for serving original PDFs. [src/api/types.ts](src/api/types.ts) validates route responses with Zod and mirrors the backend schemas; there is no shared TypeScript package. Never put an OpenAI key in a `VITE_*` variable, browser storage, or frontend code.

## API Contract

| Method | Path | Client behavior |
| --- | --- | --- |
| GET | `/health` | `status`, `mode`, `capabilities`; accepts schema-valid degraded 503 responses |
| GET | `/courses` | Unwraps `{courses: Course[]}` |
| GET | `/courses/{course_id}/lectures` | Unwraps `{lectures: Lecture[]}` |
| POST | `/courses/{course_id}/lectures` | FormData `title`, `file`, optional `lecture_id`; unwraps `{lecture: Lecture}` |
| POST | `/chat` | `course_id`, nullable `lecture_id`, `conversation_id`, new `message` only; returns `answer`, `sources`, `tool_events`, `conversation_id` |
| GET | `/courses/{course_id}/conversations/{conversation_id}` | Unwraps `{messages: Message[]}`; fresh 404 is empty history |
| GET | `/sources/{source_id}` | Citation URLs use opaque source IDs and optional `#page=N`, never filesystem paths |

Upload validation rejects empty, non-PDF/text and over-10-MB files. The backend remains authoritative. Catalog states are `available`, `indexing`, `ready`, `error`; only an actual `ready` response is shown as indexed. To index an existing lecture, select its original file with the catalog Index action, then use Upload & index; the optional lecture ID is preserved.

## Live Data and Persistence

- Default course: `generative-ai`. The six agreed lecture IDs map to the six existing PDFs. All initially show Available.
- Without a configured backend key, indexing and chat report the real provider-unavailable error. There are no fabricated answers, citations, indexed documents or history.
- Catalog and request states come only from the backend; no query-string or environment flag enables mock data.
- Development `/docs/*.pdf` requests are served through an exact whitelist from immutable `../docs/`. Production builds emit those same bytes into `dist/docs/`; there are no copies in source/public directories.
- Browser persistence contains course-bound conversation IDs and a theme preference, never chat content or credentials. Refresh, reconnect and the browser online event restore server history. New conversation creates a fresh UUID. Request cancellation prevents stale results from crossing course/session boundaries.
- Markdown does not render raw HTML, images or arbitrary links. Clickable answer links come only from structured source/evidence records and the selected API client's source URL mapping. Server-side citation provenance validation is still required.

## Verification Limits

Tests use deterministic backend fixtures, not live inference. Live provider/indexing, server-side history persistence and PDF page navigation require a configured local backend and separate integration checks. Test/build success does not establish live chat, browser behavior, attack resistance, or workshop timing. The student export includes frontend source but excludes frontend tests; this README is not currently in the export allowlist.