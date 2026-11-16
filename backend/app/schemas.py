from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    UNFINISHED_EXERCISE = "unfinished_exercise"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNSUPPORTED_FILE = "unsupported_file"
    FILE_TOO_LARGE = "file_too_large"


class Course(BaseModel):
    id: str
    name: str


class Lecture(BaseModel):
    id: str
    course_id: str
    title: str
    filename: str
    source_id: str
    state: Literal["available", "indexing", "ready", "error"] = "available"
    error: str | None = None


class Evidence(BaseModel):
    chunk_id: str
    text: str
    lecture_id: str
    filename: str
    page: int
    source_id: str


class Source(BaseModel):
    chunk_id: str
    lecture_id: str
    filename: str
    page: int
    source_id: str


class ToolEvent(BaseModel):
    name: str
    arguments: dict[str, str | int | None] = Field(default_factory=dict)
    evidence: list[Source] = Field(default_factory=list)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    lecture_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    conversation_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    conversation_id: str


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)


class TutorAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=8000)
    citation_ids: list[str] = Field(default_factory=list, max_length=8)
