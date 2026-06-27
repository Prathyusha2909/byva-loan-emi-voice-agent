import { FileSearch, Wrench } from "lucide-react";

export function PolicyPanel({ latestResult, policies }) {
  const toolTrace = latestResult?.tool_trace || [];
  const citations = latestResult?.citations || [];

  return (
    <aside className="intel-panel">
      <div className="panel-block">
        <div className="section-title">
          <Wrench size={18} />
          <h2>Tool Calls</h2>
        </div>
        <div className="event-list">
          {toolTrace.length === 0 && <p className="muted">No tools called yet</p>}
          {toolTrace.map((event, index) => (
            <div className="event-row" key={`${event.tool || event.tool_name}-${index}`}>
              <strong>{event.tool || event.tool_name}</strong>
              {event.payload && (
                <>
                  <span>args</span>
                  <code>{JSON.stringify(event.payload, null, 2)}</code>
                </>
              )}
              <span>result</span>
              <code>{JSON.stringify(event.result || {}, null, 2)}</code>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-block">
        <div className="section-title">
          <FileSearch size={18} />
          <h2>Policy Matches</h2>
        </div>
        <div className="policy-list">
          {citations.length === 0 &&
            policies.slice(0, 3).map((policy) => (
              <article className="policy-row" key={policy.source}>
                <strong>{policy.title}</strong>
                <span>{policy.source}</span>
              </article>
            ))}
          {citations.map((citation) => (
            <article className="policy-row" key={`${citation.source}-${citation.score}`}>
              <strong>{citation.title}</strong>
              <span>
                {citation.source} | score {citation.score}
              </span>
              <p>{citation.text}</p>
            </article>
          ))}
        </div>
      </div>
    </aside>
  );
}
