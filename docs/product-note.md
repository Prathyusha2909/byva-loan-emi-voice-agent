# Product Note: BYVA Loan EMI Voice Agent

## User Problem

Loan customers often call support for repetitive questions: EMI due date, late fee explanation, payment status, callback requests, and escalation to a human. Support teams need fast resolution without losing control over sensitive BFSI workflows.

## Demo Solution

This demo is a voice-first EMI reminder and customer support agent. It supports inbound customer questions and outbound EMI reminders. The agent listens to customer speech, reasons over the request, calls backend tools, retrieves policy context, speaks a response, and writes analytics for the operations team.

## Core Workflows

- Inbound: Customer asks about late fee, due date, payment status, reschedule, refund, privacy, or human handoff.
- Outbound: Agent reminds the customer about an upcoming EMI and offers pay-now, callback, or support.
- Human handoff: Agent escalates for angry sentiment, legal or financial advice, low confidence, complex payment disputes, fraud-like claims, or direct human requests.

## Product Decisions

- The demo uses deterministic routing for reliability during a short screening demo.
- Tools are explicit and visible, so PM and engineering reviewers can see what action was taken.
- RAG policy matches are shown in the dashboard, making answers auditable.
- Payment collection is intentionally limited to "send secure link"; the agent never asks for card, bank, or OTP details.
- Analytics are call-level, not just transcript-level, because operations teams need intent, sentiment, resolution, next action, and escalation reason.

## Success Metrics

- Containment rate for simple EMI/due-date/payment-status calls.
- Escalation precision for angry, legal, privacy-sensitive, or dispute-heavy calls.
- Average handling time reduction for support agents.
- Callback completion rate.
- Policy-grounded answer rate.

## Production Path

- Replace browser STT/TTS with LiveKit or Vapi for telephony.
- Use Deepgram or Whisper streaming for STT.
- Use GPT/Gemini/Claude with function calling for reasoning.
- Use ElevenLabs or OpenAI TTS for natural voice output.
- Move SQLite to PostgreSQL and FAISS to pgvector for production search.
- Add auth, audit logs, PII redaction, and consent capture.

