from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.envelope import fail
from app.domain.services.project_service import ProjectNotFound
from app.pipeline.transitions import InvalidTransition


class ApiError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400, data=None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


def register_handlers(app: FastAPI) -> None:

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(fail(exc.code, exc.message, exc.data), status_code=exc.http_status)

    @app.exception_handler(ProjectNotFound)
    async def handle_not_found(_: Request, exc: ProjectNotFound):
        return JSONResponse(fail(40401, "资源不存在"), status_code=404)

    @app.exception_handler(InvalidTransition)
    async def handle_invalid_transition(_: Request, exc: InvalidTransition):
        return JSONResponse(
            fail(40301, f"当前 stage 不允许该操作: {exc.current} → {exc.target}"),
            status_code=403,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            fail(40001, "参数校验失败", {"errors": exc.errors()}), status_code=422
        )

    @app.exception_handler(Exception)
    async def handle_unknown(_: Request, exc: Exception):
        return JSONResponse(fail(50001, "内部错误"), status_code=500)
