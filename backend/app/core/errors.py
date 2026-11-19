class AppError(Exception):
    """Expected application error that is safe to return to the API client."""

    status_code = 400
    code = "application_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ConfigurationError(AppError):
    status_code = 503
    code = "configuration_error"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


class RateLimitError(ExternalServiceError):
    status_code = 429
    code = "upstream_rate_limited"


class NoGroundedContextError(AppError):
    status_code = 422
    code = "no_grounded_context"
