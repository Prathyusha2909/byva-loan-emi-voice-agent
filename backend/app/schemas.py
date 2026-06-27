from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StartCallRequest(BaseModel):
    customer_id: str
    call_type: Literal["inbound", "outbound"] = "inbound"


class AgentTurnRequest(BaseModel):
    call_id: int | None = None
    customer_id: str
    call_type: Literal["inbound", "outbound"] = "inbound"
    message: str = Field(min_length=1)


class ToolWebhookRequest(BaseModel):
    tool_name: str
    customer_id: str
    call_id: int | None = None
    arguments: dict = Field(default_factory=dict)

