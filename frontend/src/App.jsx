import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  CircleDollarSign,
  Clock,
  Headphones,
  PhoneCall,
  PhoneIncoming,
  PlayCircle,
  ReceiptText,
  RefreshCcw,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { api } from "./api";
import { VoiceConsole } from "./components/VoiceConsole";
import { Dashboard } from "./components/Dashboard";
import { PolicyPanel } from "./components/PolicyPanel";

function App() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [callType, setCallType] = useState("inbound");
  const [callId, setCallId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [latestResult, setLatestResult] = useState(null);
  const [calls, setCalls] = useState([]);
  const [summary, setSummary] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [apiStatus, setApiStatus] = useState("checking");
  const [error, setError] = useState("");
  const [demoRunning, setDemoRunning] = useState(false);

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.customer_id === selectedCustomerId),
    [customers, selectedCustomerId],
  );

  async function refreshAnalytics() {
    const [callRows, analytics] = await Promise.all([api.calls(), api.analytics()]);
    setCalls(callRows);
    setSummary(analytics);
  }

  useEffect(() => {
    async function load() {
      try {
        const [health, customerRows, policyRows] = await Promise.all([
          api.health(),
          api.customers(),
          api.policies(),
        ]);
        setApiStatus(health.status);
        setCustomers(customerRows);
        setPolicies(policyRows);
        setSelectedCustomerId(customerRows[0]?.customer_id || "");
        await refreshAnalytics();
      } catch (loadError) {
        setApiStatus("offline");
        setError(loadError.message);
      }
    }
    load();
  }, []);

  async function beginCall(type = callType) {
    setError("");
    const started = await api.startCall({
      customer_id: selectedCustomerId,
      call_type: type,
    });
    setCallType(type);
    setCallId(started.call_id);
    setLatestResult({
      tool_trace: started.tool_trace || [],
      citations: [],
      analytics: {
        intent: type === "outbound" ? "outbound_emi_reminder" : "inbound_started",
        sentiment_label: "neutral",
        resolution_status: "in_progress",
      },
    });
    setMessages(
      started.initial_message
        ? [{ speaker: "agent", message: started.initial_message, created_at: new Date().toISOString() }]
        : [],
    );
    await refreshAnalytics();
    return started;
  }

  async function sendMessage(message) {
    if (!message.trim()) return null;
    setError("");
    let activeCallId = callId;
    if (!activeCallId) {
      const started = await beginCall(callType);
      activeCallId = started.call_id;
    }

    const result = await api.respond({
      call_id: activeCallId,
      customer_id: selectedCustomerId,
      call_type: callType,
      message,
    });
    setCallId(result.call_id);
    setMessages(result.transcript);
    setLatestResult(result);
    await refreshAnalytics();
    return result;
  }

  async function loadCall(call) {
    const detail = await api.callDetail(call.id);
    setCallId(detail.id);
    setSelectedCustomerId(detail.customer_id);
    setCallType(detail.call_type === "outbound" ? "outbound" : "inbound");
    setMessages(detail.transcript || []);
    setLatestResult({
      analytics: detail,
      tool_trace: detail.tool_events || [],
      citations: [],
      escalation_reason: detail.escalation_reason,
      next_action: detail.next_action,
      resolution_status: detail.resolution_status,
      intent: detail.intent,
    });
  }

  function pause(ms) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  async function runDemoSequence() {
    if (demoRunning) return;

    const demoCustomerId =
      customers.find((customer) => customer.customer_id === "CUST-1024")?.customer_id ||
      selectedCustomerId;
    if (!demoCustomerId) {
      setError("No demo customer available");
      return;
    }

    setDemoRunning(true);
    setError("");

    try {
      setSelectedCustomerId(demoCustomerId);
      setCallType("inbound");
      setCallId(null);
      setMessages([]);
      setLatestResult(null);
      await pause(500);

      const started = await api.startCall({
        customer_id: demoCustomerId,
        call_type: "inbound",
      });
      setCallId(started.call_id);
      setLatestResult({
        tool_trace: started.tool_trace || [],
        citations: [],
        analytics: {
          intent: "inbound_started",
          sentiment_label: "neutral",
          resolution_status: "in_progress",
        },
      });
      setMessages([]);
      await refreshAnalytics();
      await pause(1100);

      const prompts = [
        "When is my EMI due?",
        "Can I reschedule and get a callback tomorrow at 5 pm?",
        "I want to talk to a human.",
      ];

      for (const prompt of prompts) {
        const result = await api.respond({
          call_id: started.call_id,
          customer_id: demoCustomerId,
          call_type: "inbound",
          message: prompt,
        });
        setMessages(result.transcript);
        setLatestResult(result);
        await refreshAnalytics();
        await pause(1800);
      }

      const outbound = await api.startCall({
        customer_id: demoCustomerId,
        call_type: "outbound",
      });
      setCallType("outbound");
      setCallId(outbound.call_id);
      setLatestResult({
        tool_trace: outbound.tool_trace || [],
        citations: [],
        analytics: {
          intent: "outbound_emi_reminder",
          sentiment_label: "neutral",
          resolution_status: "in_progress",
          next_action: "Await customer response",
        },
      });
      setMessages(
        outbound.initial_message
          ? [
              {
                speaker: "agent",
                message: outbound.initial_message,
                created_at: new Date().toISOString(),
              },
            ]
          : [],
      );
      await refreshAnalytics();
    } catch (demoError) {
      setError(demoError.message);
    } finally {
      setDemoRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="voice-mark" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div>
            <p className="eyebrow">BYVA demo</p>
            <h1>Loan EMI Voice Agent</h1>
          </div>
        </div>
        <div className="status-row">
          <span className={`status-dot ${apiStatus === "ok" ? "online" : "offline"}`} />
          <span>{apiStatus === "ok" ? "Backend live" : "Backend offline"}</span>
          <button className="icon-button" onClick={refreshAnalytics} title="Refresh analytics">
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="control-strip">
        <label>
          Customer
          <select
            value={selectedCustomerId}
            onChange={(event) => {
              setSelectedCustomerId(event.target.value);
              setCallId(null);
              setMessages([]);
              setLatestResult(null);
            }}
          >
            {customers.map((customer) => (
              <option key={customer.customer_id} value={customer.customer_id}>
                {customer.name} - {customer.customer_id}
              </option>
            ))}
          </select>
        </label>

        <div className="segmented" aria-label="Call type">
          <button
            className={callType === "inbound" ? "active" : ""}
            onClick={() => {
              setCallType("inbound");
              setCallId(null);
              setMessages([]);
            }}
          >
            <PhoneIncoming size={16} />
            Inbound
          </button>
          <button
            className={callType === "outbound" ? "active" : ""}
            onClick={() => beginCall("outbound")}
          >
            <PhoneCall size={16} />
            Outbound
          </button>
        </div>

        <button className="primary-action" onClick={() => beginCall(callType)}>
          <Headphones size={18} />
          New call
        </button>

        <button className="demo-action" onClick={runDemoSequence} disabled={demoRunning}>
          <PlayCircle size={18} />
          {demoRunning ? "Running" : "Run demo"}
        </button>
      </section>

      {demoRunning && (
        <div className="demo-banner">
          Running recording flow: EMI due, callback scheduling, human handoff, outbound reminder.
        </div>
      )}

      <main className="workspace-grid">
        <VoiceConsole
          customer={selectedCustomer}
          callType={callType}
          callId={callId}
          messages={messages}
          latestResult={latestResult}
          onSend={sendMessage}
          onStartOutbound={() => beginCall("outbound")}
        />
        <PolicyPanel latestResult={latestResult} policies={policies} />
      </main>

      <section className="signal-grid">
        <div className="signal-card teal">
          <ReceiptText size={20} />
          <span>Intent</span>
          <strong>{latestResult?.intent || latestResult?.analytics?.intent || "waiting"}</strong>
        </div>
        <div className="signal-card coral">
          <UserCheck size={20} />
          <span>Resolution</span>
          <strong>{latestResult?.resolution_status || latestResult?.analytics?.resolution_status || "new"}</strong>
        </div>
        <div className="signal-card amber">
          <Clock size={20} />
          <span>Next action</span>
          <strong>{latestResult?.next_action || latestResult?.analytics?.next_action || "Start call"}</strong>
        </div>
        <div className="signal-card violet">
          <ShieldCheck size={20} />
          <span>Escalation</span>
          <strong>{latestResult?.escalation_reason || latestResult?.analytics?.escalation_reason || "None"}</strong>
        </div>
      </section>

      <Dashboard
        calls={calls}
        summary={summary}
        onSelectCall={loadCall}
        icon={<BarChart3 size={20} />}
        moneyIcon={<CircleDollarSign size={20} />}
      />
    </div>
  );
}

export default App;
