"""Connects the notebook exercises (backend/app/student_code) to the app. Do not edit."""

import importlib

from .exercise_wiring import wire


def load_exercise(number: int):
    # Reloaded on every call, so the running app picks up the latest notebook edits.
    return importlib.reload(importlib.import_module(f"backend.app.student_code.exercise_{number}"))


baseline_call, search_course_docs, build_course_tutor, run_course_chat = wire(load_exercise)
