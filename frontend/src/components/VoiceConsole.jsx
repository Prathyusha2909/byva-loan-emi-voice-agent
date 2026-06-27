import { useEffect, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  PhoneForwarded,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";

const QUICK_PROMPTS = [
  "Why was I charged a late fee?",
  "When is my EMI due?",
  "Can I reschedule and get a callback tomorrow at 5 pm?",
  "I want to talk to a human.",
  "I already paid and want a refund.",
];

function formatAmount(value) {
  if (value === undefined || value === null) return "INR 0";
  return `INR ${Number(value).toLocaleString("en-IN")}`;
}

export function VoiceConsole({
  customer,
  callType,
  callId,
  messages,
  latestResult,
  onSend,
  onStartOutbound,
}) {
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("Voice ready");
  const [lastHeard, setLastHeard] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const recognitionRef = useRef(null);
  const transcriptRef = useRef(null);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!voiceEnabled || !last || last.speaker !== "agent") return;
    window.speechSynthesis?.cancel();
    const utterance = new SpeechSynthesisUtterance(last.message);
    utterance.rate = 0.96;
    utterance.pitch = 1.02;
    utterance.onstart = () => setVoiceStatus("Agent speaking");
    utterance.onend = () => setVoiceStatus("Voice ready");
    utterance.onerror = () => setVoiceStatus("Voice output blocked");
    window.speechSynthesis?.speak(utterance);
  }, [messages, voiceEnabled]);

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus("Speech recognition unavailable");
      setDraft("Browser speech recognition is unavailable. Type the customer message here.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      setListening(true);
      setVoiceStatus("Listening to customer");
    };
    recognition.onend = () => {
      setListening(false);
      setVoiceStatus((status) =>
        status === "Listening to customer" ? "Voice ready" : status,
      );
    };
    recognition.onerror = () => {
      setListening(false);
      setVoiceStatus("Mic input blocked or unavailable");
    };
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      setLastHeard(text);
      setVoiceStatus("Processing customer voice");
      setDraft(text);
      handleSend(text);
    };
    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
    setVoiceStatus("Voice ready");
  }

  async function handleSend(value = draft) {
    const text = value.trim();
    if (!text) return;
    setLastHeard(text);
    setVoiceStatus("Processing customer voice");
    setDraft("");
    await onSend(text);
    if (!voiceEnabled) {
      setVoiceStatus("Agent response ready");
    }
  }

  const dueTotal = customer
    ? Number(customer.due_amount || 0) + Number(customer.late_fee || 0)
    : 0;

  return (
    <section className="voice-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{callType} call</p>
          <h2>{customer?.name || "Customer"}</h2>
        </div>
        <div className="call-chip">{callId ? `Call #${callId}` : "No active call"}</div>
      </div>

      <div className="customer-snapshot">
        <div>
          <span>Due</span>
          <strong>{customer?.emi_due_date || "-"}</strong>
        </div>
        <div>
          <span>Amount</span>
          <strong>{formatAmount(dueTotal)}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{customer?.payment_status?.replaceAll("_", " ") || "-"}</strong>
        </div>
      </div>

      <div className="voice-actions">
        <button
          className={`record-button ${listening ? "recording" : ""}`}
          onClick={listening ? stopListening : startListening}
          title={listening ? "Stop listening" : "Start listening"}
        >
          {listening ? <MicOff size={24} /> : <Mic size={24} />}
        </button>
        <button
          className="icon-button"
          onClick={() => setVoiceEnabled((value) => !value)}
          title={voiceEnabled ? "Mute voice output" : "Enable voice output"}
        >
          {voiceEnabled ? <Volume2 size={19} /> : <VolumeX size={19} />}
        </button>
        <button className="outline-action" onClick={onStartOutbound}>
          <PhoneForwarded size={18} />
          Outbound reminder
        </button>
      </div>

      <div className="voice-status-strip">
        <span className={listening ? "live" : ""}>{voiceStatus}</span>
        <strong>{lastHeard ? `Heard: ${lastHeard}` : "Mic turn not started"}</strong>
      </div>

      <div className="quick-prompts">
        {QUICK_PROMPTS.map((prompt) => (
          <button key={prompt} onClick={() => handleSend(prompt)}>
            <Sparkles size={14} />
            {prompt}
          </button>
        ))}
      </div>

      <div className="transcript" ref={transcriptRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <Mic size={22} />
            <span>Ready for a customer turn</span>
          </div>
        )}
        {messages.map((message, index) => (
          <div className={`bubble ${message.speaker}`} key={`${message.created_at}-${index}`}>
            <span>{message.speaker}</span>
            <p>{message.message}</p>
          </div>
        ))}
      </div>

      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          handleSend();
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type customer message"
        />
        <button type="submit" title="Send message">
          <Send size={18} />
        </button>
      </form>

      <div className="confidence-row">
        <span>Confidence</span>
        <meter min="0" max="1" value={latestResult?.confidence || 0} />
        <strong>{latestResult?.confidence ? Math.round(latestResult.confidence * 100) : 0}%</strong>
      </div>
    </section>
  );
}
