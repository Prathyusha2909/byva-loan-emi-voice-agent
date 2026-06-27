from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from . import database


def get_customer_emi_status(customer_id: str) -> dict[str, Any]:
    customer = database.get_customer(customer_id)
    if customer is None:
        return {"error": "customer_not_found"}
    total_due = int(customer["due_amount"]) + int(customer["late_fee"])
    return {
        "customer_id": customer_id,
        "due_amount": int(customer["due_amount"]),
        "late_fee": int(customer["late_fee"]),
        "total_due": total_due,
        "emi_due_date": customer["emi_due_date"],
        "payment_status": customer["payment_status"],
    }


def check_payment_status(customer_id: str) -> dict[str, Any]:
    customer = database.get_customer(customer_id)
    if customer is None:
        return {"error": "customer_not_found"}
    return {
        "customer_id": customer_id,
        "payment_status": customer["payment_status"],
        "last_payment_date": customer["last_payment_date"],
        "late_fee": int(customer["late_fee"]),
    }


def create_support_ticket(customer_id: str, issue: str) -> dict[str, Any]:
    return database.create_ticket(customer_id, issue)


def schedule_callback(customer_id: str, time: str | None = None) -> dict[str, Any]:
    scheduled_time = time
    if not scheduled_time:
        scheduled_time = (datetime.now() + timedelta(hours=2)).replace(microsecond=0).isoformat()
    return database.create_callback(customer_id, scheduled_time)


def handoff_to_human(customer_id: str, reason: str) -> dict[str, Any]:
    return {
        "customer_id": customer_id,
        "status": "queued_for_human",
        "handoff_queue": "loan_support_priority",
        "reason": reason,
    }


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "get_customer_emi_status": get_customer_emi_status,
    "check_payment_status": check_payment_status,
    "create_support_ticket": create_support_ticket,
    "schedule_callback": schedule_callback,
    "handoff_to_human": handoff_to_human,
    # Backward-compatible aliases for older webhook/demo calls.
    "check_due_amount": get_customer_emi_status,
    "raise_support_ticket": create_support_ticket,
    "transfer_to_human": handoff_to_human,
}


def call_tool(name: str, call_id: int, **kwargs: Any) -> dict[str, Any]:
    if name not in TOOL_REGISTRY:
        result = {"error": "unknown_tool", "tool": name}
    else:
        result = TOOL_REGISTRY[name](**kwargs)
    database.add_tool_event(call_id, name, kwargs, result)
    return result
