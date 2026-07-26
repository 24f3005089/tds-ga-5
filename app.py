"""Entry point. Mounts the A2A agent and a couple of liveness routes.

Run locally:   uvicorn app:app --host 0.0.0.0 --port 8000
"""
import os
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import a2a_agent
from a2a_agent import A2AJSONResponse

app = FastAPI(title="A2A Invoice Action Agent")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = "NOT_FOUND" if exc.status_code == 404 else ("UNAUTHENTICATED" if exc.status_code == 401 else "A2A_ERROR")
    return A2AJSONResponse(
        {"error": {"code": code, "message": str(exc.detail)},
         "code": code, "message": str(exc.detail)},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return A2AJSONResponse(
        {"error": {"code": "INVALID_ARGUMENT", "message": "request failed schema validation"},
         "code": "INVALID_ARGUMENT", "message": "request failed schema validation"},
        status_code=400,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return A2AJSONResponse(
        {"error": {"code": "INTERNAL_ERROR", "message": "an internal server error occurred"},
         "code": "INTERNAL_ERROR", "message": "an internal server error occurred"},
        status_code=500,
    )


@app.middleware("http")
async def normalise_path(request, call_next):
    """Collapse repeated slashes and drop a stray trailing one before routing."""
    path = request.scope.get("path") or "/"
    fixed = re.sub(r"/{2,}", "/", path)
    if len(fixed) > 1 and fixed.endswith("/"):
        fixed = fixed.rstrip("/") or "/"
    if fixed != path:
        request.scope["path"] = fixed
        raw = request.scope.get("raw_path")
        if isinstance(raw, bytes):
            request.scope["raw_path"] = fixed.encode("utf-8")
    return await call_next(request)


app.include_router(a2a_agent.router)


@app.get("/")
async def root():
    return {"service": "a2a-invoice-action-agent", "protocol": "1.0",
            "agentCard": "/.well-known/agent-card.json"}


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
