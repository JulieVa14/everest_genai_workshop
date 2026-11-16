"""Helpers that keep the workshop notebook short. Supplied code: students do not edit it."""

import asyncio
import atexit
import inspect
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

from .config import ROOT, load_settings
from .errors import UnfinishedExercise, WorkshopError
from .exercise_wiring import exercise_function
from .retrieval import DEFAULT_LECTURES
from .tutor import compact_text, create_workshop, present_result, redact, setup_workshop

COURSE = "generative-ai"
LECTURES = (
    ("introduction", "Introduction", "00-Intro.pdf"),
    ("ethics", "Generative AI Ethics", "05-GAI_ethics.pdf"),
)
STUDENT_CODE = ROOT / "backend" / "app" / "student_code"
NO_KEY = (
    "🔑 No API key found. Put your OPENAI_API_KEY in backend/.env (never in this notebook),\n"
    "   then restart the kernel and run the notebook again from the top."
)


class Lab:
    def __init__(self, mode: str):
        self.mode = mode
        self.offline = os.getenv("COURSE_COMPANION_OFFLINE") == "1"
        if self.offline:
            os.environ["OPENAI_API_KEY"] = ""
        base = os.getenv("COURSE_COMPANION_NOTEBOOK_DATA") or ROOT / ".workshop-data" / "notebook"
        self.workshop = setup_workshop(mode, data_dir=Path(base).resolve())
        self.steps = self.workshop.steps
        self.conversation_id = str(uuid4())
        self.passed: set[int] = set()
        self._processes: list[subprocess.Popen] = []
        self._logs: list = []
        self._url = ""
        atexit.register(self.close_app, quiet=True)

    @property
    def key(self) -> str:
        return self.workshop.settings.api_key

    @property
    def live(self) -> bool:
        return not self.offline and self.workshop.store.client is not None

    def status(self):
        settings = self.workshop.settings
        name = "Student" if self.mode == "student" else "Instructor"
        print(f"✅ Setup done ({name} notebook). Chat model: {settings.model}; "
              f"embedding model: {settings.embedding_model}.")
        if self.offline:
            print("⏸️ Offline mode: tests only check for unfinished blanks; no API calls.")
        elif not self.live:
            print(NO_KEY)

    def explain(self, error: Exception):
        if isinstance(error, UnfinishedExercise):
            print(f"✏️ {error.message}")
        elif isinstance(error, WorkshopError):
            print(f"⚠️ {error.message}")
        else:
            detail = compact_text(f"{type(error).__name__}: {error}", self.key)
            print(f"🐞 Something went wrong: {detail}")
            print("   Check your exercise cells, run them again, then rerun this cell.")

    def save_exercise(self, number: int, source: str):
        if self.mode != "student":
            print("Instructor notebook: exercise cells are not saved.")
            return
        if number not in (1, 2, 3, 4):
            print("The first line must be %%exercise 1, 2, 3 or 4.")
            return
        try:
            compile(source, f"Exercise {number}", "exec")
        except SyntaxError as error:
            print(f"✏️ Exercise {number} has a typo on line {error.lineno}: {error.msg}. "
                  "Fix it and run the cell again.")
            return
        if os.getenv("COURSE_COMPANION_NO_SAVE") == "1":
            print(f"Exercise {number} checked (check mode: not saved).")
            return
        path = STUDENT_CODE / f"exercise_{number}.py"
        path.write_text(source.rstrip() + "\n", encoding="utf-8")
        for cached in (STUDENT_CODE / "__pycache__").glob(f"exercise_{number}.*.pyc"):
            cached.unlink(missing_ok=True)
        try:
            exercise_function(self.steps.load_exercise, number)
            print(f"💾 Exercise {number} saved. Now run the test cell below. ▶️")
        except UnfinishedExercise:
            print(f"💾 Saved, but some ____ blanks are still empty in Exercise {number}.")

    def show_answer(self, number: int):
        print(inspect.getsource(exercise_function(self.steps.load_exercise, number)))

    async def test(self, number: int, question: str | None = None):
        tests = {1: self._test_1, 2: self._test_2, 3: self._test_3, 4: self._test_4}
        try:
            exercise_function(self.steps.load_exercise, number)
            if self.offline:
                print(f"⏸️ Offline: Exercise {number} has no blanks left; live test skipped.")
                return
            if not self.live:
                print(NO_KEY)
                return
            await tests[number](question)
            self.passed.add(number)
            print(f"✅ Exercise {number} works!")
        except Exception as error:
            self.explain(error)

    async def _test_1(self, question):
        question = question or "In one sentence, what is a large language model?"
        print(f"🙋 You asked: {question}")
        answer = await self.steps.baseline_call(
            self.workshop.store.client, self.workshop.settings, question
        )
        print(f"🤖 The model answered: {redact(answer, self.key)}")

    async def _test_2(self, question):
        await self._index_lectures()
        store = self.workshop.store
        question = question or "Which application uses Retrieval Augmented Generation?"
        print(f"🔎 Searching for: {question}")
        hits = await self.steps.search_course_docs(store, COURSE, question)
        if not hits:
            raise UnfinishedExercise(2, "search", "the search found no passages")
        print(f"Best matches in the Generative AI course ({len(hits)} found):")
        for hit in hits[:3]:
            snippet = compact_text(hit.text, self.key)[:100]
            print(f"   📄 {hit.filename}, page {hit.page}: {snippet}...")
        intro = await self.steps.search_course_docs(store, COURSE, question, "introduction")
        other = await self.steps.search_course_docs(store, "study-notes", question)
        print(f"Only the Introduction lecture: {len(intro)} passages, "
              f"all from {sorted({hit.filename for hit in intro})}.")
        print(f"Another course (Study Notes): {len(other)} passages. Courses stay separate.")
        print("👀 Open that PDF page in the docs folder: does it really answer the question?")

    async def _test_3(self, _question):
        tutor = self.steps.build_course_tutor(self.workshop.store, COURSE)
        tool = tutor.agent.tools[0]
        arguments = list(tool.params_json_schema.get("properties", {}))
        print(f"🧰 Your tutor has one tool, '{tool.name}', with arguments {arguments}.")
        print("   The AI only chooses the search words. The app fixes the course,")
        print("   so the AI can never search another course.")

    async def _test_4(self, question):
        await self._index_lectures()
        question = question or (
            "Which ethical concerns from the Ethics lecture matter for the Introduction topics?"
        )
        follow_up = "Summarize your previous answer in at most ten words."
        same = str(uuid4())
        print("1️⃣ A first question:")
        await self._ask(same, question)
        print("\n2️⃣ A follow-up in the SAME conversation:")
        await self._ask(same, follow_up)
        print("\n3️⃣ The same follow-up in a NEW conversation:")
        await self._ask(str(uuid4()), follow_up)
        print("\n👀 Compare 2 and 3: only the same conversation remembers the earlier answer.")

    async def chat(self, message: str, lecture: str | None = None):
        if not self._can_go_live():
            return
        try:
            await self._index_lectures()
            await self._ask(self.conversation_id, message, lecture)
        except Exception as error:
            self.explain(error)

    def new_chat(self):
        self.conversation_id = str(uuid4())
        print("🆕 New conversation: the tutor no longer remembers earlier messages.")

    def _can_go_live(self) -> bool:
        if self.offline:
            print("⏸️ Offline: skipped.")
        elif not self.live:
            print(NO_KEY)
        return self.live

    async def embed(self, texts: list[str]):
        if not self._can_go_live():
            return None
        try:
            return await self.workshop.store.embed(texts)
        except Exception as error:
            self.explain(error)
            return None

    async def trace(self, question: str, lecture: str | None = None):
        """Run the agent once and print every step of its loop."""
        if not self._can_go_live():
            return
        try:
            await self._index_lectures()
            tutor = self.steps.build_course_tutor(self.workshop.store, COURSE, lecture)
            conversation_id = str(uuid4())
            session = self.workshop.conversations.session(COURSE, conversation_id)
            result = await self.steps.run_course_chat(tutor, question, session)
        except Exception as error:
            self.explain(error)
            return
        print(f"🙋 Question: {question}")
        step = 0
        for item in result.new_items:
            if item.type == "tool_call_item":
                step += 1
                arguments = redact(str(item.raw_item.arguments), self.key)
                print(f"Step {step}  🤖→🧰 The AI asks to run {item.raw_item.name}({arguments})")
            elif item.type == "tool_call_output_item":
                step += 1
                output = json.loads(item.output) if isinstance(item.output, str) else item.output
                pages = [f"{entry['filename']} p{entry['page']}" for entry in output or []]
                print(f"Step {step}  🧰→🤖 Our code ran the search and sent back "
                      f"{len(pages)} passages: {', '.join(pages)}")
            elif item.type == "message_output_item":
                step += 1
                print(f"Step {step}  🤖 The AI decides it has enough and writes the answer.")
        try:
            response = present_result(result, tutor, conversation_id)
        except Exception as error:
            self.explain(error)
            return
        print(f"\n🤖 {redact(response.answer, self.key)}")
        for source in response.sources:
            print(f"   📄 {source.filename}, page {source.page}")
        used_in = sum(answer.usage.input_tokens for answer in result.raw_responses)
        used_out = sum(answer.usage.output_tokens for answer in result.raw_responses)
        print(f"\n💰 The model was called {len(result.raw_responses)} times: "
              f"{used_in} input tokens + {used_out} output tokens.")

    async def _ask(self, conversation_id: str, message: str, lecture: str | None = None):
        print(f"🙋 {message}")
        response = await self.workshop.chat(COURSE, lecture, conversation_id, message)
        print(f"🤖 {redact(response.answer, self.key)}")
        for source in response.sources:
            print(f"   📄 {source.filename}, page {source.page}")
        print(f"   🔧 The tutor searched the lectures {len(response.tool_events)} time(s).")

    async def _index_lectures(self):
        await index_lectures(self.workshop)

    def summary(self):
        if self.offline:
            print("⏸️ Offline mode: no live tests were run.")
            return
        for number in range(1, 5):
            print(f"{'✅' if number in self.passed else '⬜'} Exercise {number}")

    def open_app(self, backend_port: int = 8000, frontend_port: int = 5173):
        if self._processes and all(process.poll() is None for process in self._processes):
            print(f"🚀 Your app is already running: {self._url}")
            return
        if self.offline:
            print("⏸️ Offline mode: the app is not started.")
            return
        node = shutil.which("node")
        vite = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
        if node is None or not vite.is_file():
            print("⚠️ The app needs Node.js and its packages. Run once in a terminal:")
            print("   npm --prefix frontend ci")
            return
        backend_port = free_port(backend_port)
        frontend_port = free_port(frontend_port, avoid=backend_port)
        self._url = f"http://127.0.0.1:{frontend_port}"
        app_data = ROOT / ".workshop-data" / "app"
        logs = app_data / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        backend_env = {**os.environ, "WORKSHOP_MODE": self.mode, "PYTHONIOENCODING": "utf-8",
                       "WORKSHOP_DATA_DIR": str(app_data), "FRONTEND_ORIGIN": self._url}
        # The browser side never receives the API key.
        frontend_env = {name: value for name, value in os.environ.items()
                        if name != "OPENAI_API_KEY"}
        frontend_env["WORKSHOP_API_URL"] = f"http://127.0.0.1:{backend_port}"
        if self.live:
            print("📚 Indexing all six lectures for the app (first time only, about a minute)...")
            prepared = subprocess.run(
                [sys.executable, "-m", "backend.app.notebook_support", "--prepare-app"],
                cwd=ROOT, env=backend_env, capture_output=True, timeout=600,
            )
            if prepared.returncode != 0:
                print("⚠️ Lectures could not be indexed now; use the app's Documents tab instead.")
        self._start([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                     "--host", "127.0.0.1", "--port", str(backend_port)],
                    ROOT, backend_env, logs / "backend.log")
        self._start([node, str(vite), "--host", "127.0.0.1", "--port", str(frontend_port),
                     "--strictPort"], ROOT / "frontend", frontend_env, logs / "frontend.log")
        if self._wait(f"http://127.0.0.1:{backend_port}/health") and self._wait(self._url):
            print(f"🚀 Your app is running: {self._url}")
            print("   Open the link in your browser. If you change an exercise cell and run it,")
            print("   the app uses your new code right away. Stop it with lab.close_app().")
        else:
            print("⚠️ The app did not start. Details: .workshop-data/app/logs/")
            self.close_app(quiet=True)

    def close_app(self, quiet: bool = False):
        running = [process for process in self._processes if process.poll() is None]
        for process in running:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, check=False)
            else:
                process.terminate()
        for handle in self._logs:
            handle.close()
        self._processes, self._logs = [], []
        if not quiet:
            print("🛑 App stopped." if running else "The app is not running.")

    def _start(self, command, cwd, env, log_path):
        log = open(log_path, "w", encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._logs.append(log)
        self._processes.append(subprocess.Popen(
            command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        ))

    def _wait(self, url: str, seconds: int = 60) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in self._processes):
                return False
            try:
                with urllib.request.urlopen(url, timeout=2):
                    return True
            except OSError:
                time.sleep(0.5)
        return False


def free_port(start: int, avoid: int = 0) -> int:
    for port in range(start, 65536):
        if port == avoid:
            continue
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free localhost port found.")


def register_exercise_magic(lab: Lab):
    try:
        from IPython import get_ipython
    except ImportError:
        return
    shell = get_ipython()
    if shell is None:
        return

    def exercise(line, cell):
        try:
            number = int(line.strip())
        except ValueError:
            number = 0
        lab.save_exercise(number, cell)

    shell.register_magic_function(exercise, magic_kind="cell", magic_name="exercise")


def start(mode: str = "student") -> Lab:
    lab = Lab(mode)
    register_exercise_magic(lab)
    lab.status()
    return lab


async def index_lectures(workshop, lectures=LECTURES):
    store = workshop.store
    for lecture_id, title, filename in lectures:
        if store.lectures[store.key(COURSE, lecture_id)].state != "ready":
            print(f"📚 Indexing {filename} (first time only, this takes a moment)...")
            data = (ROOT / "docs" / filename).read_bytes()
            await store.index_document(COURSE, lecture_id, filename, data, title)


async def prepare_app():
    workshop = create_workshop(load_settings())
    try:
        await index_lectures(workshop, DEFAULT_LECTURES)
    finally:
        if workshop.store.client is not None:
            await workshop.store.client.close()


if __name__ == "__main__" and sys.argv[1:] == ["--prepare-app"]:
    asyncio.run(prepare_app())
