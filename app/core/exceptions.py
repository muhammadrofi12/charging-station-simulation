"""
Domain and application-level exceptions.
Framework-agnostic error definitions for business logic decoupling.
"""

class AppError(Exception):
    """Base class for all domain and application errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    """Raised when an entity or resource is not found (maps to HTTP 404)."""
    def __init__(self, message: str = "Resource tidak ditemukan."):
        super().__init__(message, status_code=404)


class ValidationError(AppError):
    """Raised when validation or business constraints fail (maps to HTTP 400)."""
    def __init__(self, message: str = "Validasi bisnis gagal."):
        super().__init__(message, status_code=400)


class InsufficientBalanceError(ValidationError):
    """Raised when user wallet or card has insufficient funds (maps to HTTP 400)."""
    def __init__(self, message: str = "Saldo tidak mencukupi."):
        super().__init__(message)


class ResourceConflictError(AppError):
    """Raised on state conflicts such as locked or already charging nozzle (maps to HTTP 409)."""
    def __init__(self, message: str = "Konflik status sumber daya."):
        super().__init__(message, status_code=409)


class ForbiddenActionError(AppError):
    """Raised when an operation is not permitted for the user (maps to HTTP 403)."""
    def __init__(self, message: str = "Aksi tidak diizinkan."):
        super().__init__(message, status_code=403)


class UnauthorizedError(AppError):
    """Raised when credentials or authentication fails (maps to HTTP 401)."""
    def __init__(self, message: str = "Autentikasi gagal."):
        super().__init__(message, status_code=401)
