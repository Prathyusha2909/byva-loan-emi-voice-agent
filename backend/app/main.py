from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .agent import handle_turn, start_call
from .rag import retriever
from .schemas import AgentTurnRequest, StartCallRequest, ToolWebhookRequest
from .tools import call_tool


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
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
