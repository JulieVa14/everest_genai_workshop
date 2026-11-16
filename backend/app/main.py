from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from .config import Settings, load_settings
from .errors import WorkshopError, provider_error
from .retrieval import COURSES
from .schemas import ChatRequest, ChatResponse, ErrorCode
from .tutor import Workshop, create_workshop


def error_response(error: WorkshopError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status,
        content={"error": {"code": error.code.value, "message": error.message}},
    )


class UploadLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes + 64 * 1024

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        size = 0
        started = False
        maximum = 16 * 1024 if scope["path"] == "/chat" else self.max_bytes

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > maximum:
                raise HTTPException(status_code=413)
            return message

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except Exception as error:
            if not started:
                sanitized = error if isinstance(error, WorkshopError) else provider_error()
                await error_response(sanitized)(scope, receive, send)


def create_app(settings: Settings | None = None, workshop: Workshop | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(application):
        application.state.workshop = workshop or create_workshop(settings)
        yield
        client = application.state.workshop.store.client
        if client is not None and hasattr(client, "close"):
            await client.close()

    application = FastAPI(title="Course Companion (local)", lifespan=lifespan)
    application.add_middleware(UploadLimitMiddleware, max_bytes=settings.max_upload_bytes)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(WorkshopError)
    async def workshop_error(_request: Request, error: WorkshopError):
        return error_response(error)

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError):
        return error_response(
            WorkshopError(
                ErrorCode.INVALID_INPUT, "Request does not match the workshop API contract.", 422
            )
        )

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException):
        if error.status_code == 413:
            return error_response(
                WorkshopError(
                    ErrorCode.FILE_TOO_LARGE,
                    "Request exceeds the size limit.",
                    413,
                )
            )
        code = ErrorCode.NOT_FOUND if error.status_code == 404 else ErrorCode.INVALID_INPUT
        return error_response(
            WorkshopError(code, "Request or resource is invalid.", error.status_code)
        )

    def service(request: Request) -> Workshop:
        return request.app.state.workshop

    @application.get("/health")
    async def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "capabilities": {
                "api_key_configured": bool(settings.api_key),
                "live_inference": bool(settings.api_key),
                "live_indexing": bool(settings.api_key),
                "local_persistence": True,
                "model": settings.model,
                "embedding_model": settings.embedding_model,
            },
        }

    @application.get("/courses")
    async def courses():
        return {"courses": COURSES}

    @application.get("/courses/{course_id}/lectures")
    async def lectures(course_id: str, request: Request):
        return {"lectures": service(request).store.list_lectures(course_id)}

    @application.post("/courses/{course_id}/lectures")
    async def upload(
        course_id: str,
        request: Request,
        title: str = Form(...),
        file: UploadFile = File(...),
        lecture_id: str | None = Form(None),
    ):
        store = service(request).store
        store.validate_scope(course_id)
        try:
            data = await file.read(settings.max_upload_bytes + 1)
            lecture = await store.index_document(
                course_id, lecture_id, file.filename or "", data, title=title
            )
        finally:
            await file.close()
        return {"lecture": lecture}

    @application.post("/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request):
        return await service(request).chat(
            body.course_id, body.lecture_id, body.conversation_id, body.message
        )

    @application.get("/courses/{course_id}/conversations/{conversation_id}")
    async def history(course_id: str, conversation_id: str, request: Request):
        return {"messages": service(request).conversations.read(course_id, conversation_id)}

    @application.get("/sources/{source_id}")
    async def source(source_id: str, request: Request):
        path = service(request).store.source(source_id)
        suffix = Path(path).suffix.lower()
        media_type = "application/pdf" if suffix == ".pdf" else "text/plain; charset=utf-8"
        return Response(
            content=path.read_bytes(),
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{source_id}{suffix}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
                "Cache-Control": "no-store",
            },
        )

    return application


app = create_app()
