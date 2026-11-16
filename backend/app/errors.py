from .schemas import ErrorCode


class WorkshopError(Exception):
    def __init__(self, code: ErrorCode, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class UnfinishedExercise(WorkshopError):
    def __init__(self, task: int, function: str, problem: str | None = None):
        if problem:
            detail = f"Exercise {task} ({function}) needs a fix: {problem}."
        else:
            detail = f"Exercise {task} ({function}) is not finished yet: fill in every ____ blank."
        super().__init__(
            ErrorCode.UNFINISHED_EXERCISE,
            f"{detail} Edit the Exercise {task} cell in notebooks/course_companion.ipynb "
            "and run that cell again.",
            409,
        )


def provider_error() -> WorkshopError:
    return WorkshopError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        "OpenAI indexing or chat is unavailable. Configure your individual OPENAI_API_KEY "
        "in backend/.env; check API billing/quota, model access and connectivity, then retry. "
        "A ChatGPT subscription does not include API credit.",
        502,
    )
