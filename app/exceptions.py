from fastapi import Request
from fastapi.responses import ORJSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, id: str | None = None):
        self.resource = resource
        self.id = id
        super().__init__(f"{resource} not found" + (f": {id}" if id else ""))


class ConflictError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class AuthenticationError(Exception):
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message)


class AuthorizationError(Exception):
    def __init__(self, required_scope: str):
        self.required_scope = required_scope
        super().__init__(f"Insufficient permissions. Required scope: {required_scope}")


class PlanLimitError(Exception):
    def __init__(self, resource: str, current: int, limit: int):
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(
            f"Plan limit reached for {resource}: {current}/{limit}. Upgrade your plan to continue."
        )


class PlanFeatureError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class ExternalServiceError(Exception):
    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"External service error ({service}): {message}")


async def not_found_handler(request: Request, exc: NotFoundError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=404,
        content={"detail": str(exc), "resource": exc.resource},
    )


async def conflict_handler(request: Request, exc: ConflictError) -> ORJSONResponse:
    return ORJSONResponse(status_code=409, content={"detail": str(exc)})


async def validation_handler(request: Request, exc: ValidationError) -> ORJSONResponse:
    return ORJSONResponse(status_code=422, content={"detail": str(exc)})


async def authentication_handler(request: Request, exc: AuthenticationError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=401,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def authorization_handler(request: Request, exc: AuthorizationError) -> ORJSONResponse:
    return ORJSONResponse(status_code=403, content={"detail": str(exc)})


async def plan_limit_handler(request: Request, exc: PlanLimitError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=402,
        content={"detail": str(exc), "resource": exc.resource, "current": exc.current, "limit": exc.limit},
    )


async def plan_feature_handler(request: Request, exc: PlanFeatureError) -> ORJSONResponse:
    return ORJSONResponse(status_code=403, content={"detail": str(exc)})


async def external_service_handler(request: Request, exc: ExternalServiceError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=502,
        content={"detail": str(exc), "service": exc.service},
    )
