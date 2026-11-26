"""Application-level exceptions mapped to JSON error responses in main.py."""


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ValidationFailure(AppError):
    status_code = 422
    code = "validation_error"


class RepoNotReadyError(AppError):
    status_code = 409
    code = "repo_not_ready"


class LLMError(AppError):
    status_code = 502
    code = "llm_error"


class IngestionError(AppError):
    """Raised inside the indexing pipeline; message is stored on the repository row."""

    status_code = 400
    code = "ingestion_error"
