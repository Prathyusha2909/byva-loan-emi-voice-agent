from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "byva_demo.sqlite3"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


CUSTOMERS: list[dict[str, Any]] = [
    {
        "customer_id": "CUST-1024",
        "name": "Aarav Mehta",
        "phone": "+91 98765 10240",
        "emi_due_date": tomorrow_iso(),
        "due_amount": 18450,
        "late_fee": 0,
        "payment_status": "due_tomorrow",
        "last_payment_date": (date.today() - timedelta(days=29)).isoformat(),
        "risk_segment": "standard",
    },
    {
        "customer_id": "CUST-1188",
        "name": "Nisha Rao",
        "phone": "+91 98765 11880",
        "emi_due_date": (date.today() - timedelta(days=4)).isoformat(),
        "due_amount": 22100,
        "late_fee": 450,
        "payment_status": "overdue",
        "last_payment_date": (date.today() - timedelta(days=64)).isoformat(),
        "risk_segment": "attention",
    },
    {
        "customer_id": "CUST-1407",
        "name": "Kabir Sharma",
        "phone": "+91 98765 14070",
        "emi_due_date": (date.today() + timedelta(days=7)).isoformat(),
        "due_amount": 10990,
        "late_fee": 0,
        "payment_status": "paid",
        "last_payment_date": (date.today() - timedelta(days=2)).isoformat(),
        "risk_segment": "low",
    },
]


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                emi_due_date TEXT NOT NULL,
                due_amount INTEGER NOT NULL,
                late_fee INTEGER NOT NULL,
                payment_status TEXT NOT NULL,
                last_payment_date TEXT NOT NULL,
                risk_segment TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                call_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                intent TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                summary TEXT,
                resolution_status TEXT,
                next_action TEXT,
                escalation_reason TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                speaker TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(call_id) REFERENCES calls(id)
            );

            CREATE TABLE IF NOT EXISTS tool_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                payload TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(call_id) REFERENCES calls(id)
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                issue TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS callbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        for customer in CUSTOMERS:
            conn.execute(
                """
                INSERT OR IGNORE INTO customers (
                    customer_id, name, phone, emi_due_date, due_amount, late_fee,
                    payment_status, last_payment_date, risk_segment
                )
                VALUES (
                    :customer_id, :name, :phone, :emi_due_date, :due_amount,
                    :late_fee, :payment_status, :last_payment_date, :risk_segment
                )
                """,
                customer,
            )


def list_customers() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def get_customer(customer_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    return row_to_dict(row)


def create_call(customer_id: str, call_type: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO calls (customer_id, call_type, started_at, resolution_status)
            VALUES (?, ?, ?, ?)
            """,
            (customer_id, call_type, now_iso(), "in_progress"),
        )
        return int(cursor.lastrowid)


def get_call(call_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    return row_to_dict(row)


def update_call_analytics(call_id: int, analytics: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE calls
            SET intent = :intent,
                sentiment_label = :sentiment_label,
                sentiment_score = :sentiment_score,
                summary = :summary,
                resolution_status = :resolution_status,
                next_action = :next_action,
                escalation_reason = :escalation_reason
            WHERE id = :call_id
            """,
            {**analytics, "call_id": call_id},
        )


def add_transcript(call_id: int, speaker: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transcripts (call_id, speaker, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (call_id, speaker, message, now_iso()),
        )


def add_tool_event(
    call_id: int, tool_name: str, payload: dict[str, Any], result: dict[str, Any]
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tool_events (call_id, tool_name, payload, result, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (call_id, tool_name, json.dumps(payload), json.dumps(result), now_iso()),
        )


def create_ticket(customer_id: str, issue: str) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO support_tickets (customer_id, issue, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (customer_id, issue, "open", now_iso()),
        )
        ticket_id = int(cursor.lastrowid)
    return {
        "ticket_id": f"TKT-{ticket_id:04d}",
        "status": "open",
        "issue": issue,
        "customer_id": customer_id,
    }


def create_callback(customer_id: str, scheduled_time: str) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO callbacks (customer_id, scheduled_time, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (customer_id, scheduled_time, "scheduled", now_iso()),
        )
        callback_id = int(cursor.lastrowid)
    return {
        "callback_id": f"CB-{callback_id:04d}",
        "status": "scheduled",
        "scheduled_time": scheduled_time,
        "customer_id": customer_id,
    }


def list_calls() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT calls.*, customers.name AS customer_name
            FROM calls
            JOIN customers ON customers.customer_id = calls.customer_id
            ORDER BY calls.id DESC
            LIMIT 50
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def list_transcripts(call_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT speaker, message, created_at
            FROM transcripts
            WHERE call_id = ?
            ORDER BY id
            """,
            (call_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def list_tool_events(call_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT tool_name, payload, result, created_at
            FROM tool_events
            WHERE call_id = ?
            ORDER BY id
            """,
            (call_id,),
        ).fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        if item is None:
            continue
        item["payload"] = json.loads(item["payload"])
        item["result"] = json.loads(item["result"])
        events.append(item)
    return events


def analytics_summary() -> dict[str, Any]:
    calls = list_calls()
    total = len(calls)
    escalated = sum(1 for call in calls if call.get("resolution_status") == "escalated")
    resolved = sum(1 for call in calls if call.get("resolution_status") == "resolved")
    avg_sentiment = 0.0
    scored_calls = [call for call in calls if call.get("sentiment_score") is not None]
    if scored_calls:
        avg_sentiment = sum(float(call["sentiment_score"]) for call in scored_calls) / len(
            scored_calls
        )
    intents: dict[str, int] = {}
    for call in calls:
        intent = call.get("intent") or "unknown"
        intents[intent] = intents.get(intent, 0) + 1
    return {
        "total_calls": total,
        "resolved_calls": resolved,
        "escalated_calls": escalated,
        "avg_sentiment": round(avg_sentiment, 2),
        "intent_counts": intents,
    }

