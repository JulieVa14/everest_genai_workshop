# Course Companion Workshop

A localhost React/FastAPI workshop with four bounded Python exercises: API calls,
course-scoped retrieval, an agent tool, and persistent conversations. No Azure
resources, deployment, containers, or frontend exercise are required.

## Setup and Launch

### Python venv and pip (Student Setup)

Install Python 3.12 and Node.js first. Run these commands in PowerShell from the
checkout or student export root. The pinned requirements include backend, notebook,
and Python check dependencies; the frontend uses its separate npm lockfile.

```powershell
py -3.12 -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install --upgrade pip
./backend/.venv/Scripts/python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

If `py -3.12` is unavailable, install Python 3.12 before class; do not use the
machine's Python 3.15 default. Select `backend/.venv/Scripts/python.exe` as the
VS Code Python interpreter and notebook kernel. No activation is required when
using the full interpreter path. Optional activation is
`./backend/.venv/Scripts/Activate.ps1`; if policy blocks it, use the direct commands
above rather than changing machine/user execution policy.

The virtual environment (`backend/.venv`) contains installed Python packages.
The separate private configuration file (`backend/.env`) holds your own OpenAI
key and model settings. Open it locally and fill in `OPENAI_API_KEY` privately;
never paste the key into chat or a notebook. Both locations are ignored by git.
Use Manual Launch below without uv. The convenience launcher additionally needs
uv on `PATH`; install it separately if choosing that alternative.

Maintainers regenerate [requirements.txt](requirements.txt) from the same locked
dependencies (including notebooks) after intentional dependency changes:

```powershell
uv export --project backend --locked --all-groups --no-hashes --no-emit-project --format requirements-txt --output-file requirements.txt
```

### uv Alternative and Convenience Launcher

Run from the checkout root using Python 3.12, uv, and Node 20.19+ (20.x) or
22.12+. Dependencies and individual model/quota checks belong before class.

```powershell
uv python install 3.12
uv sync --project backend --python 3.12 --locked
npm --prefix frontend ci
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/launch.ps1 -Mode Student -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/launch.ps1 -Mode Student
```

Copy the environment template only if no local environment file already exists.
For an instructor checkout, use `-Mode Solution`. The launcher prints actual available
ports and process IDs; Ctrl+C stops both process trees. `-BackendPort` and
`-FrontendPort` choose starting ports; occupied ports are skipped. `-SkipInstall`
uses already installed dependencies. Invocation-scoped execution policy does not
change machine policy or require elevation.

Privately create `backend/.env` from `backend/.env.example` and enter your own
OpenAI API key there. Never enter a key in chat, React, notebooks, saved outputs,
logs, screenshots, `VITE_*` variables, or git. API
billing is separate from ChatGPT subscriptions. Model IDs are explicit; access
must be checked with your account. Local persistence does not mean local
inference: OpenAI receives document text and relevant conversation context. Use
public/non-sensitive documents only. Budget alerts are not hard spending caps.

Without a key the shell/catalog works, but live indexing and inference report an
actionable error. Student chat reports unfinished exercises until implemented;
there is no instructor fallback. App and notebook data are isolated by surface
and Student/Solution mode. Do not run concurrent writers against one data path.

## Workshop Materials

- [notebooks/course_companion.ipynb](notebooks/course_companion.ipynb): the whole workshop.
- [exercises/workshop.md](exercises/workshop.md): one-page student setup guide.

Students work only in the notebook. Each exercise is a `%%exercise N` cell with `____`
blanks; running it saves the code to `backend/app/student_code/exercise_N.py`, which the
app reloads on every request. A ▶️ test cell explains what to fix, and `lab.open_app()`
starts the web app on the student's own code. Select `backend/.venv/Scripts/python.exe`
(registered as **Course Companion (Python 3.12)**) as the kernel. Default data paths are
`.workshop-data/app/student` and `.workshop-data/notebook/student`; instructor modes use
separate `solution` directories. `COURSE_COMPANION_OFFLINE=1` skips live tests.
The original six PDFs under `docs/` are preserved and start Available, not Indexed.

## Manual Launch

Use two separate PowerShell terminals from the checkout root; load the backend
environment only in the backend terminal:

```powershell
$env:WORKSHOP_MODE = 'student'
$env:WORKSHOP_DATA_DIR = Join-Path (Get-Location) '.workshop-data/app'
$env:FRONTEND_ORIGIN = 'http://127.0.0.1:5173'
$backendEnv = Join-Path (Get-Location) 'backend/.env'
./backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --env-file $backendEnv --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
$env:WORKSHOP_API_URL = 'http://127.0.0.1:8000'
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. Ctrl+C in each terminal stops its own process. Choose
available ports and update the origin and proxy target together: `localhost:5173`
and `127.0.0.1:5173` are different CORS origins. The launcher resolves absolute
environment/data paths and configures matching origins automatically. Ports are
checked, not reserved; a startup race fails. `-CheckOnly` starts no servers, performs
no installs, and does not validate keys/model access. No server is assumed running.

## Checks

```powershell
uv run --project backend pytest backend/tests
npm --prefix frontend test -- --run
npm --prefix frontend run build
uv run --project backend pytest scripts/test_tools.py
```

Backend/tool tests are instructor-checkout checks; answer-bearing tests are absent
from the student export. Test/build commands do not start servers. Mocked checks
verify mechanics, not live model access, semantic retrieval quality, or resistance
to every document instruction. Offline notebook checks establish fresh-kernel safety
with live gates skipped. Live provider/notebook/browser checks are separate gates.
Representative human 90/120-minute rehearsals remain unperformed; planned teaching
times are not measured completion times.

## Export and Reset

```powershell
uv run --project backend python scripts/export_student.py --destination ../course-companion-student
uv run --project backend python scripts/prepare_corpus.py import --surface notebook --mode student --bundle ../course-companion-corpus
```

Choose a fresh export destination outside the checkout. Review the package before
sharing; the allowlist is not a general secret scanner for arbitrary source edits.
It includes this guide, worksheet, student notebook, runtime source, locked manifests,
helpers, and six original PDFs. It excludes instructor solutions, completed notebooks,
answer-bearing tests/planning artifacts, backend reference documentation, secrets,
dependencies, generated data, and saved notebook outputs.

Ask your instructor for the approved Intro/Ethics corpus bundle for the 90-minute
route. Import into an absent/empty target with writers stopped; repeat with
`--surface app` for separate app data. Only `build` calls real paid OpenAI embeddings;
export/import validate model/dimensions, original PDFs/hashes, chunk settings, and
locked Chroma version. They never re-embed or copy session history. No fake vectors;
live queries still need an individual key. Reset requires `--confirm`, refuses
symlinks/junctions, and deletes only the selected generated uploads/index/history.
It does not manage custom data paths. Stop writers first; never reset source PDFs
or student code. Run reset separately only when you intend to erase notebook data:

```powershell
uv run --project backend python scripts/reset_data.py --surface notebook --mode student --confirm
```