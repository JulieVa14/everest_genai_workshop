"""Connects the four notebook exercises to the app. Supplied code: students do not edit it."""

import ast
import asyncio
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from agents import Agent, ModelSettings, RunResult, SQLiteSession
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI

from .config import Settings
from .errors import UnfinishedExercise, WorkshopError, provider_error
from .retrieval import DocumentStore
from .schemas import ErrorCode, Evidence, TutorAnswer
from .tutor import TutorRuntime, compact_text

FUNCTIONS = {1: "ask_model", 2: "search", 3: "build_agent", 4: "ask_tutor"}
BLANK = "____"
CODING_ERRORS = (NameError, TypeError, AttributeError, KeyError, IndexError, SyntaxError)


def has_blanks(module: ModuleType) -> bool:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return any(isinstance(node, ast.Name) and node.id == BLANK for node in ast.walk(tree))


def exercise_function(load: Callable[[int], ModuleType], number: int):
    try:
        module = load(number)
    except SyntaxError as error:
        raise UnfinishedExercise(number, FUNCTIONS[number], f"line {error.lineno}: {error.msg}")
    if has_blanks(module):
        raise UnfinishedExercise(number, FUNCTIONS[number])
    return getattr(module, FUNCTIONS[number])


def code_bug(number: int, error: Exception, api_key: str) -> UnfinishedExercise:
    detail = compact_text(f"{type(error).__name__}: {error}", api_key)
    return UnfinishedExercise(number, FUNCTIONS[number], detail)


def wire(load: Callable[[int], ModuleType]):
    """Build the four app functions around the exercise functions returned by load(n)."""

    async def baseline_call(client: AsyncOpenAI, settings: Settings, prompt: str) -> str:
        if not prompt.strip() or len(prompt) > 4000:
            raise WorkshopError(ErrorCode.INVALID_INPUT, "Prompt must contain 1-4000 characters.")
        ask_model = exercise_function(load, 1)
        if client is None:
            raise provider_error()
        try:
            async with asyncio.timeout(settings.timeout_seconds):
                text = await ask_model(client, settings, prompt)
        except WorkshopError:
            raise
        except CODING_ERRORS as error:
            raise code_bug(1, error, settings.api_key) from None
        except Exception:
            raise provider_error() from None
        if not isinstance(text, str) or not text.strip():
            raise UnfinishedExercise(1, FUNCTIONS[1], "return the answer text (a string)")
        return text

    async def search_course_docs(
        store: DocumentStore, course_id: str, query: str, lecture_id: str | None = None
    ) -> list[Evidence]:
        store.validate_scope(course_id, lecture_id)
        if not query.strip() or len(query) > 1000:
            raise WorkshopError(
                ErrorCode.INVALID_INPUT, "Search query must contain 1-1000 characters."
            )
        search = exercise_function(load, 2)
        try:
            evidence = await search(store, course_id, query, lecture_id)
        except WorkshopError:
            raise
        except CODING_ERRORS as error:
            raise code_bug(2, error, store.settings.api_key) from None
        if not isinstance(evidence, list) or not all(isinstance(e, Evidence) for e in evidence):
            raise UnfinishedExercise(2, FUNCTIONS[2], "return the list from store.query_vectors")
        # Scope is re-checked here, so a wrong filter can never leak another course.
        store.validate_evidence(evidence, course_id, lecture_id)
        return evidence

    def build_course_tutor(
        store: DocumentStore, course_id: str, lecture_id: str | None = None
    ) -> TutorRuntime:
        store.validate_scope(course_id, lecture_id)
        build_agent = exercise_function(load, 3)
        if store.client is None:
            raise provider_error()
        runtime = TutorRuntime(None, store, course_id, lecture_id, {})

        async def search_documents(query: str) -> list[dict]:
            return runtime.record(await search_course_docs(store, course_id, query, lecture_id))

        model = OpenAIResponsesModel(model=store.settings.model, openai_client=store.client)
        model_settings = ModelSettings(
            max_tokens=store.settings.max_output_tokens, parallel_tool_calls=False, store=False
        )
        try:
            agent = build_agent(search_documents, model, model_settings)
        except CODING_ERRORS as error:
            raise code_bug(3, error, store.settings.api_key) from None
        tools = getattr(agent, "tools", None) or []
        if not isinstance(agent, Agent) or [tool.name for tool in tools] != ["search_course_docs"]:
            raise UnfinishedExercise(3, FUNCTIONS[3], "put your search tool in the tools list")
        if set(tools[0].params_json_schema.get("properties", {})) != {"query"}:
            raise UnfinishedExercise(3, FUNCTIONS[3], "the tool may only take a query argument")
        runtime.agent = agent.clone(
            model=model, model_settings=model_settings, output_type=TutorAnswer
        )
        return runtime

    async def run_course_chat(
        tutor: TutorRuntime, message: str, session: SQLiteSession
    ) -> RunResult:
        ask_tutor = exercise_function(load, 4)
        tutor.evidence.clear()
        try:
            async with asyncio.timeout(tutor.store.settings.timeout_seconds):
                result = await ask_tutor(
                    tutor.agent, message, session, tutor.store.settings.max_turns
                )
        except (WorkshopError, TimeoutError):
            raise
        except CODING_ERRORS as error:
            raise code_bug(4, error, tutor.store.settings.api_key) from None
        if result is None:
            raise UnfinishedExercise(4, FUNCTIONS[4], "return the result of Runner.run(...)")
        return result

    return baseline_call, search_course_docs, build_course_tutor, run_course_chat
