from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import database
from .rag import retriever
from .tools import call_tool


INTENT_PATTERNS: dict[str, list[str]] = {
    "late_fee_question": ["late fee", "charged", "penalty", "extra charge", "why fee"],
    "emi_due_date": ["due", "emi date", "when is", "deadline", "tomorrow"],
    "payment_status": ["paid", "payment status", "received", "successful", "debited"],
    "reschedule_or_callback": ["reschedule", "callback", "call me", "later", "more time"],
    "human_handoff": ["human", "agent", "representative", "manager", "support person"],
    "pay_now": ["pay now", "payment link", "upi", "card", "netbanking"],
    "refund_or_dispute": ["refund", "duplicate", "wrong charge", "dispute", "not my charge"],
    "privacy": ["privacy", "data", "otp", "account number", "personal information"],
    "legal_or_financial_advice": ["lawyer", "legal", "sue", "credit score", "financial advice"],
}

ANGRY_WORDS = {
    "angry",
    "furious",
    "ridiculous",
    "complaint",
    "cheated",
    "harassment",
    "unacceptable",
    "worst",
}

POSITIVE_WORDS = {"thanks", "thank you", "helpful", "ok", "okay", "great", "fine"}


@dataclass
class IntentResult:
    intent: str
    confidence: float


def _tool_history(call_id: int) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for event in database.list_tool_events(call_id):
        history.append(
            {
                "tool": event["tool_name"],
                "payload": event["payload"],
                "result": event["result"],
                "created_at": event["created_at"],
            }
        )
    return history


def classify_intent(message: str) -> IntentResult:
    normalized = message.lower()
    if any(pattern in normalized for pattern in INTENT_PATTERNS["refund_or_dispute"]):
        return IntentResult(intent="refund_or_dispute", confidence=0.9)
    if any(pattern in normalized for pattern in INTENT_PATTERNS["human_handoff"]):
        return IntentResult(intent="human_handoff", confidence=0.9)
    if any(pattern in normalized for pattern in INTENT_PATTERNS["legal_or_financial_advice"]):
        return IntentResult(intent="legal_or_financial_advice", confidence=0.9)

    scores: dict[str, int] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern in normalized)
        if score:
            scores[intent] = score

    if not scores:
        return IntentResult(intent="general_policy_question", confidence=0.4)

    intent = max(scores, key=scores.get)
    confidence = min(0.95, 0.55 + (scores[intent] * 0.16))
    return IntentResult(intent=intent, confidence=confidence)


def analyze_sentiment(message: str) -> dict[str, Any]:
    words = set(re.findall(r"[a-zA-Z']+", message.lower()))
    angry_hits = len(words.intersection(ANGRY_WORDS))
    positive_hits = len(words.intersection(POSITIVE_WORDS))

    if angry_hits:
        score = max(-1.0, -0.45 - (angry_hits * 0.18))
        return {"label": "angry", "score": round(score, 2)}
    if positive_hits:
        score = min(1.0, 0.35 + (positive_hits * 0.12))
        return {"label": "positive", "score": round(score, 2)}
    return {"label": "neutral", "score": 0.05}


def extract_callback_time(message: str) -> str | None:
    normalized = message.lower()
    if "tomorrow" in normalized:
        match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", normalized)
        if match:
            return f"tomorrow {match.group(0).strip()}"
        return "tomorrow 10:00 AM"
    if "evening" in normalized:
        return "today 6:00 PM"
    if "morning" in normalized:
        return "tomorrow 10:00 AM"
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", normalized)
    if match:
        return match.group(0).upper()
    return None


def should_escalate(intent: IntentResult, sentiment: dict[str, Any], message: str) -> str | None:
    normalized = message.lower()
    if intent.intent == "human_handoff":
        return "Customer requested a human agent"
    if sentiment["label"] == "angry":
        return "Customer sentiment is angry"
    if intent.intent == "legal_or_financial_advice":
        return "Legal or financial advice requested"
    if intent.intent == "refund_or_dispute":
        return "Complex payment dispute"
    if "fraud" in normalized or "court" in normalized:
        return "Potential fraud or legal escalation"
    if intent.confidence < 0.5:
        return "Low confidence response"
    return None


def _format_money(amount: int | float) -> str:
    return f"INR {int(amount):,}"


def _policy_sentence(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return ""
    names = ", ".join({str(item["title"]) for item in citations[:2]})
    return f" I checked the {names} for this answer."


def _summary_for(intent: str, customer_name: str, message: str) -> str:
    concise = message.strip()
    if len(concise) > 100:
        concise = concise[:97] + "..."
    readable_intent = intent.replace("_", " ")
    return f"{customer_name} contacted support about {readable_intent}: {concise}"


def start_call(customer_id: str, call_type: str) -> dict[str, Any]:
    customer = database.get_customer(customer_id)
    if customer is None:
        raise ValueError("customer_not_found")

    call_id = database.create_call(customer_id, call_type)
    initial_message = ""
    tool_trace: list[dict[str, Any]] = []

    if call_type == "outbound":
        due = call_tool("get_customer_emi_status", call_id, customer_id=customer_id)
        tool_trace.append({"tool": "get_customer_emi_status", "result": due})
        initial_message = (
            f"Hi {customer['name']}, this is Karta's EMI assistant. "
            f"Your EMI of {_format_money(due['total_due'])} is due on {due['emi_due_date']}. "
            "Would you like to pay now, request a callback, or speak to support?"
        )
        database.add_transcript(call_id, "agent", initial_message)
        database.update_call_analytics(
            call_id,
            {
                "intent": "outbound_emi_reminder",
                "sentiment_label": "neutral",
                "sentiment_score": 0.05,
                "summary": f"Outbound EMI reminder started for {customer['name']}.",
                "resolution_status": "in_progress",
                "next_action": "Await customer response",
                "escalation_reason": None,
            },
        )

    return {
        "call_id": call_id,
        "customer": customer,
        "call_type": call_type,
        "initial_message": initial_message,
        "tool_trace": _tool_history(call_id),
        "latest_tool_trace": tool_trace,
    }


def handle_turn(call_id: int, customer_id: str, message: str, call_type: str) -> dict[str, Any]:
    customer = database.get_customer(customer_id)
    if customer is None:
        raise ValueError("customer_not_found")

    intent = classify_intent(message)
    sentiment = analyze_sentiment(message)
    citations = retriever.search(message)
    escalation_reason = should_escalate(intent, sentiment, message)
    tool_trace: list[dict[str, Any]] = []
    response = ""
    next_action = "Close call after customer confirmation"
    resolution_status = "resolved"

    database.add_transcript(call_id, "customer", message)

    def tool(name: str, **kwargs: Any) -> dict[str, Any]:
        result = call_tool(name, call_id, **kwargs)
        tool_trace.append({"tool": name, "payload": kwargs, "result": result})
        return result

    if intent.intent == "emi_due_date":
        due = tool("get_customer_emi_status", customer_id=customer_id)
        response = (
            f"Your EMI is due on {due['emi_due_date']}. The current payable amount is "
            f"{_format_money(due['total_due'])}."
        )
        if due["payment_status"] == "due_tomorrow":
            response += " It is due tomorrow, so paying today keeps the account fully on track."
        next_action = "Send secure payment link if customer agrees"

    elif intent.intent == "late_fee_question":
        due = tool("get_customer_emi_status", customer_id=customer_id)
        response = (
            f"I see a late fee of {_format_money(due['late_fee'])} on your account. "
            f"The EMI due date was {due['emi_due_date']}, and the account status is "
            f"{due['payment_status'].replace('_', ' ')}."
            f"{_policy_sentence(citations)}"
        )
        if due["late_fee"] > 0:
            response += " I can raise a dispute ticket if you believe the payment was made on time."
            next_action = "Offer dispute ticket"
        else:
            response += " There is no late fee currently posted on this account."

    elif intent.intent == "payment_status":
        status = tool("check_payment_status", customer_id=customer_id)
        response = (
            f"Your payment status is {status['payment_status'].replace('_', ' ')}. "
            f"The last recorded payment date is {status['last_payment_date']}."
        )
        if status["late_fee"] > 0:
            response += f" There is also a late fee of {_format_money(status['late_fee'])}."

    elif intent.intent == "reschedule_or_callback":
        callback = tool(
            "schedule_callback",
            customer_id=customer_id,
            time=extract_callback_time(message),
        )
        response = (
            "I have scheduled a support callback for "
            f"{callback['scheduled_time']}. Your callback reference is {callback['callback_id']}."
        )
        next_action = "Support callback scheduled"

    elif intent.intent == "pay_now":
        due = tool("get_customer_emi_status", customer_id=customer_id)
        response = (
            f"I can send a secure payment link for {_format_money(due['total_due'])}. "
            "For privacy, I will not ask for card, bank, or OTP details on this call."
        )
        next_action = "Send secure payment link"

    elif intent.intent == "refund_or_dispute":
        ticket = tool("create_support_ticket", customer_id=customer_id, issue=message)
        response = (
            f"I created support ticket {ticket['ticket_id']} for this dispute. "
            "A human support specialist will review it before any refund or fee adjustment decision."
            f"{_policy_sentence(citations)}"
        )
        resolution_status = "escalated"
        next_action = "Human review of dispute ticket"

    elif intent.intent == "privacy":
        response = (
            "For privacy, I can only use the minimum details needed for this request. "
            "I will not ask you to say OTPs, full account numbers, or card details aloud."
            f"{_policy_sentence(citations)}"
        )
        next_action = "Continue with privacy-safe verification"

    elif intent.intent == "human_handoff":
        response = "I understand. I am transferring this to a human support specialist now."
        next_action = "Transfer to human support"
        resolution_status = "escalated"

    elif intent.intent == "legal_or_financial_advice":
        response = (
            "I cannot provide legal or financial advice. I can connect you to human support "
            "for account-specific next steps."
        )
        next_action = "Transfer to human support"
        resolution_status = "escalated"

    else:
        response = (
            "I want to be careful with that. Based on the support policies, I can help with "
            "EMI due date, payment status, late fee explanation, callbacks, disputes, and human handoff."
            f"{_policy_sentence(citations)}"
        )
        next_action = "Clarify customer request"
        resolution_status = "pending"

    if escalation_reason:
        handoff = tool("handoff_to_human", customer_id=customer_id, reason=escalation_reason)
        response += f" I am also routing this to {handoff['handoff_queue']} because: {escalation_reason}."
        resolution_status = "escalated"
        next_action = "Human support follow-up"

    analytics = {
        "intent": intent.intent,
        "sentiment_label": sentiment["label"],
        "sentiment_score": sentiment["score"],
        "summary": _summary_for(intent.intent, customer["name"], message),
        "resolution_status": resolution_status,
        "next_action": next_action,
        "escalation_reason": escalation_reason,
    }
    database.add_transcript(call_id, "agent", response)
    database.update_call_analytics(call_id, analytics)

    return {
        "call_id": call_id,
        "response": response,
        "intent": intent.intent,
        "confidence": intent.confidence,
        "sentiment": sentiment,
        "resolution_status": resolution_status,
        "next_action": next_action,
        "escalation_reason": escalation_reason,
        "tool_trace": _tool_history(call_id),
        "latest_tool_trace": tool_trace,
        "citations": citations,
        "analytics": analytics,
        "transcript": database.list_transcripts(call_id),
    }
