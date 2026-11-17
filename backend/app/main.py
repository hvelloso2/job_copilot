import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from app.database import init_db
from app.routers import jobs, profile


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="job-copilot", lifespan=lifespan)
app.include_router(profile.router)
app.include_router(jobs.router)


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError):
    # Log where/why validation failed, never the input values (they may contain résumé data).
    for err in exc.errors():
        location = " -> ".join(str(part) for part in err.get("loc", ()))
        logger.warning("422 %s %s: %s em %s", request.method, request.url.path, err.get("msg"), location)
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
