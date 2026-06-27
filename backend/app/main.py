from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .agent import handle_turn, start_call
from .rag import retriever
from .schemas import AgentTurnRequest, StartCallRequest, ToolWebhookRequest
from .tools import call_tool


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="BYVA Loan EMI Voice Agent",
    description="FastAPI backend for a BFSI voice agent demo with tools, RAG, and analytics.",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=os.getenv(
        "ALLOWED_ORIGIN_REGEX",
        r"https://.*\.onrender\.com|https://.*\.vercel\.app|https://.*\.loca\.lt|https://.*\.hf\.space",
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": "BYVA Loan EMI Voice Agent API",
        "status": "ok",
        "docs": "http://127.0.0.1:8000/docs",
        "health": "http://127.0.0.1:8000/api/health",
    }


@app.get("/api/customers")
def customers() -> list[dict]:
    return database.list_customers()


@app.post("/api/calls/start")
def start_call_endpoint(payload: StartCallRequest) -> dict:
    try:
        return start_call(payload.customer_id, payload.call_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/agent/respond")
def respond(payload: AgentTurnRequest) -> dict:
    call_id = payload.call_id
    if call_id is None:
        call_id = start_call(payload.customer_id, payload.call_type)["call_id"]

    try:
        return handle_turn(
            call_id=call_id,
            customer_id=payload.customer_id,
            message=payload.message,
            call_type=payload.call_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/calls")
def calls() -> list[dict]:
    return database.list_calls()


@app.get("/api/calls/{call_id}")
def call_detail(call_id: int) -> dict:
    call = database.get_call(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call_not_found")
    call["transcript"] = database.list_transcripts(call_id)
    call["tool_events"] = database.list_tool_events(call_id)
    return call


@app.get("/api/analytics/summary")
def analytics_summary() -> dict:
    return database.analytics_summary()


@app.get("/api/policies")
def policies() -> list[dict]:
    return retriever.list_policies()


@app.post("/api/rag/search")
def rag_search(payload: dict) -> dict:
    return {"results": retriever.search(str(payload.get("query", "")))}


@app.post("/api/tools/webhook")
def tool_webhook(payload: ToolWebhookRequest) -> dict:
    call_id = payload.call_id
    if call_id is None:
        call_id = database.create_call(payload.customer_id, "tool_webhook")
    try:
        result = call_tool(
            payload.tool_name,
            call_id,
            customer_id=payload.customer_id,
            **payload.arguments,
        )
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"call_id": call_id, "result": result}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        requested_path = FRONTEND_DIST / full_path
        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(FRONTEND_DIST / "index.html")
