# Local Backend Contract

Run all commands from the workspace root. Python 3.12 is selected by the backend's
version file; the manifest permits 3.12/3.13, not the machine's default 3.15.

```powershell
uv sync --project backend --python 3.12 --locked
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend/app backend/tests backend/__init__.py instructor/solution.py instructor/__init__.py
uv run --project backend python -m compileall -q backend/app instructor/solution.py
uv run --project backend python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The last command is a manual launch instruction, not a server started by this worker.
Set individual credentials in `backend/.env`, never in browser code, notebooks, chat,
logs or git. No key is required for shell health/catalogs or mocked tests. Live
indexing/chat return an actionable 502 without configured API access. Student chat
returns 409 while the relevant exercise is unfinished; there is no instructor fallback.
For solution mode set `WORKSHOP_MODE=solution` before startup. The HTTP API cannot select it.

`WORKSHOP_DATA_DIR` is a base directory: app storage appends `/student` or `/solution`.
Prefer an absolute base in launchers. The default is `.workshop-data/app` under the
workspace root. Notebook storage defaults to `.workshop-data/notebook/<mode>`.
Uploads, Chroma, `sessions.sqlite` and JSON display history are all below that isolated
directory. Never run notebook and server writers against the same directory.

## Four Exercise Signatures

Students write four small functions in notebook `%%exercise` cells, saved to
`backend/app/student_code/exercise_1.py` to `exercise_4.py`:

```python
async def ask_model(client, settings, prompt) -> str: ...
async def search(store, course_id, query, lecture_id=None) -> list[Evidence]: ...
def build_agent(search_documents, model, model_settings) -> Agent: ...
async def ask_tutor(agent, message, session, max_turns) -> RunResult: ...
```

`backend/app/exercise_wiring.py` wraps them into the app's interface
(`baseline_call`, `search_course_docs`, `build_course_tutor`, `run_course_chat`), adding
validation, timeouts, course-scope checks, citation recording and clear errors. Any
remaining `____` blank raises `UnfinishedExercise`. `backend.app.exercise_steps` reloads
the student files on every call; `instructor.solution` defines the completed functions.
A student export may remove the entire instructor package; solution selection then fails
with a clear startup error.

## Notebook Helper

`backend.app.notebook_support.start(mode)` returns a `lab` object and registers the
`%%exercise` cell magic. It offers `await lab.test(n)`, `await lab.chat(...)`,
`lab.new_chat()`, `lab.open_app()` and `lab.close_app()`. Lower-level access remains:

```python
workshop = lab.workshop
steps = lab.steps
course_id = "generative-ai"
```

`setup_workshop(mode: str = "student", data_dir: Path | None = None) -> Workshop`
appends mode to a supplied notebook base directory. `workshop.store.client` is `None`
without a key. Do not display the client, credentials, exception bodies or raw SDK items.
The app-level calls use these arguments:

```python
text = await steps.baseline_call(workshop.store.client, workshop.settings, "Say hello briefly.")
evidence = await steps.search_course_docs(workshop.store, course_id, "What is RAG?", "introduction")
tutor = steps.build_course_tutor(workshop.store, course_id, "introduction")
session = workshop.conversations.session(course_id, conversation_id)
result = await steps.run_course_chat(tutor, "What is RAG?", session)
response = present_result(result, tutor, conversation_id)
```

Only pass the NEW message to the final call. SQLiteSession manages past SDK items.
For the integrated notebook/app check use `await workshop.chat(course_id, None,
conversation_id, "What is RAG?")`; this also saves validated display history and rolls
back failed runs. Do not expose `result.new_items` wholesale: `response.tool_events`
contains compact sanitized query arguments and source metadata, not hidden reasoning.

Real PDFs initially remain Available, not Indexed. Supplied indexing for notebooks is
`await workshop.store.index_document(course_id, lecture_id, filename, bytes, title)`.
For example read the immutable `docs/00-Intro.pdf` bytes with pathlib, using
`lecture_id="introduction"`; indexing requires explicit live embeddings. The same model
is used for query embeddings. Chroma has `embedding_function=None`; no default model
download or fabricated vectors are used in runtime code. Reusing a lecture ID replaces
its chunks idempotently, including stale cleanup. No OCR, seed data or cloud provisioning.

## Routes

| Method | Path | Contract |
|---|---|---|
| GET | /health | status, mode, capabilities; no-key shell is 200 |
| GET | /courses | {courses} |
| GET | /courses/{course_id}/lectures | {lectures} |
| POST | /courses/{course_id}/lectures | multipart title/file/optional lecture_id; {lecture} |
| POST | /chat | course_id/optional lecture_id/conversation_id/new message; ChatResponse |
| GET | /courses/{course_id}/conversations/{conversation_id} | {messages} |
| GET | /sources/{source_id} | registered actual PDF/text bytes, inline safe headers |

Conversation IDs must be canonical lowercase UUIDs and bind to one course. Lecture IDs
are validated within that course. Tool schemas accept query only; injected scope
arguments cannot replace the captured server scope. Chroma combines course/lecture with
`$and`. Citation IDs must match scoped, real retrieved records from this run. Prior-turn
citation IDs, invented IDs and modified records are rejected, with no unsupported answer
saved. No retrieved/cited evidence yields supplied abstention, not guessed confidence.

## Verified PDF Anchors

Tests extract these facts from actual supplied documents, without modifying originals:

| Original PDF | Original Page | Extracted Anchor / Useful Question |
|---|---|---|
| docs/00-Intro.pdf | 2 | Outline names text, image, audio, and ethical considerations; which topics are listed? |
| docs/00-Intro.pdf | 5 | "Ask Helpdesk with Retrieval Augmented Generation"; what application is named? |
| docs/01-LLMs.pdf | 1 | "Text generation with Large Language Models" and "October 13, 2023"; what is the lecture focus/date? |
| docs/05-GAI_ethics.pdf | 2 | Fairness; transparency/explainability/accountability; privacy/data protection; which concerns are named? |

Tests also index a real two-page subset and verify pages 1/2 relative to that subset.
Full-file ingestion preserves original page numbers. Cross-lecture evaluation can compare
the Introduction outline with the Ethics concerns. Missing-evidence evaluation: ask for
a personal phone number absent from those pages. Malicious-document instructions are
untrusted tool data, never system instructions; the deterministic checks do not establish
how a live model will respond to every attack.

The lock pins Agents 0.2.11, OpenAI 1.109.1, Chroma 1.0.20, pypdf 6.0.0, FastAPI 0.115.12,
Pydantic 2.11.9, pytest 8.4.2 and Ruff 0.13.2. Installed SDK signatures and a genuine
Runner/tool/session cycle are checked with unittest.mock model/embedding responses.
Real provider access, model availability, quota, embedding quality and attack resistance
require an individual configured key and live preflight. Mocked vectors test mechanics,
not semantic search quality. Local storage does not make OpenAI inference local.