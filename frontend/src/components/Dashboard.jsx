import { AlertTriangle, CheckCircle2, Gauge, ListChecks } from "lucide-react";

function pct(value, total) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

export function Dashboard({ calls, summary, onSelectCall, icon, moneyIcon }) {
  const total = summary?.total_calls || 0;
  const resolved = summary?.resolved_calls || 0;
  const escalated = summary?.escalated_calls || 0;
  const intents = Object.entries(summary?.intent_counts || {}).slice(0, 5);

  return (
    <section className="dashboard">
      <div className="dashboard-header">
        <div className="section-title">
          {icon}
          <h2>Call Analytics</h2>
        </div>
        <div className="mini-money">
          {moneyIcon}
          <span>Loan support workflow</span>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <ListChecks size={19} />
          <span>Total calls</span>
          <strong>{total}</strong>
        </div>
        <div className="metric-card success">
          <CheckCircle2 size={19} />
          <span>Resolved</span>
          <strong>{resolved}</strong>
        </div>
        <div className="metric-card warning">
          <AlertTriangle size={19} />
          <span>Escalated</span>
          <strong>{escalated}</strong>
        </div>
        <div className="metric-card">
          <Gauge size={19} />
          <span>Sentiment</span>
          <strong>{summary?.avg_sentiment ?? 0}</strong>
        </div>
      </div>

      <div className="intent-bars">
        {intents.map(([intent, count]) => (
          <div className="intent-bar" key={intent}>
            <span>{intent.replaceAll("_", " ")}</span>
            <div>
              <b style={{ width: `${Math.max(8, pct(count, total))}%` }} />
            </div>
            <strong>{count}</strong>
          </div>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Call</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Intent</th>
              <th>Sentiment</th>
              <th>Resolution</th>
              <th>Next action</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 && (
              <tr>
                <td colSpan="7" className="empty-cell">
                  No calls yet
                </td>
              </tr>
            )}
            {calls.map((call) => (
              <tr key={call.id} onClick={() => onSelectCall(call)}>
                <td>#{call.id}</td>
                <td>{call.customer_name}</td>
                <td>{call.call_type}</td>
                <td>{call.intent || "unknown"}</td>
                <td>{call.sentiment_label || "neutral"}</td>
                <td>
                  <span className={`pill ${call.resolution_status || "pending"}`}>
                    {call.resolution_status || "pending"}
                  </span>
                </td>
                <td>{call.next_action || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

