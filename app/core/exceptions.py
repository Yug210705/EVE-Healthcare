class AppError(Exception):
    """Base exception for domain errors. Mapped to HTTP responses by the handler in main.py."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(detail, status_code=409)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "You do not have permission to access this resource"):
        super().__init__(detail, status_code=403)


class InvalidStateError(AppError):
    """Raised when a state transition is not allowed (e.g. paying a cancelled booking)."""

    def __init__(self, detail: str):
        super().__init__(detail, status_code=409)
