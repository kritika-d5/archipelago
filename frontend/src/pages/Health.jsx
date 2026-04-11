import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

function statusLabel(status) {
  if (!status) return 'Unknown';
  if (status === 'healthy') return 'All clear';
  if (status === 'healthy_with_violations') return 'Operational — review violations';
  if (status === 'degraded') return 'Degraded';
  return status.replace(/_/g, ' ');
}

function Health() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/health/');
      setHealth(response.data);
    } catch (err) {
      setHealth(null);
      setError(err.response?.data?.detail || err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const violations = health?.violations || [];
  const llmText = health?.llm_health_summary;

  return (
    <div className="health-page">
      <header className="health-page-header">
        <p className="health-page-eyebrow">Archipelago</p>
        <h1 className="health-page-title">System health</h1>
        <p className="health-page-lede">
          Live checks for the API, MongoDB, stored graphs, architecture violations, and an LLM summary when{' '}
          <code className="health-inline-code">GROQ_API_KEY</code> is set.
        </p>
        <button type="button" onClick={checkHealth} className="btn btn-primary health-refresh" disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {loading && !health && (
        <div className="health-loading">Running diagnostics (LLM insight may take a few seconds)…</div>
      )}
      {loading && health && <div className="health-loading health-loading--inline">Updating diagnostics…</div>}

      {error && (
        <div className="health-banner health-banner--error" role="alert">
          {error}
        </div>
      )}

      {health && (
        <>
          <div className="health-metrics">
            <div className="health-metric">
              <span className="health-metric-label">Posture</span>
              <span
                className={`health-metric-value health-metric-value--${
                  health.status === 'degraded' ? 'bad' : health.status === 'healthy_with_violations' ? 'warn' : 'ok'
                }`}
              >
                {statusLabel(health.status)}
              </span>
            </div>
            <div className="health-metric">
              <span className="health-metric-label">API</span>
              <span className="health-metric-value health-metric-value--ok">{health.api || 'up'}</span>
            </div>
            <div className="health-metric">
              <span className="health-metric-label">MongoDB</span>
              <span
                className={`health-metric-value ${
                  health.mongodb_connected ? 'health-metric-value--ok' : 'health-metric-value--bad'
                }`}
              >
                {health.mongodb_connected ? 'Connected' : 'Not connected'}
              </span>
            </div>
            <div className="health-metric">
              <span className="health-metric-label">Stored graphs</span>
              <span className="health-metric-value">{health.stored_graphs ?? 0}</span>
            </div>
            <div className="health-metric">
              <span className="health-metric-label">Violations</span>
              <span
                className={`health-metric-value ${
                  (health.violation_count || 0) > 0 ? 'health-metric-value--warn' : 'health-metric-value--ok'
                }`}
              >
                {health.violation_count ?? 0}
              </span>
            </div>
            <div className="health-metric">
              <span className="health-metric-label">Groq (LLM)</span>
              <span className={`health-metric-value ${health.groq_configured ? 'health-metric-value--ok' : 'health-metric-value--muted'}`}>
                {health.groq_configured ? 'Configured' : 'Not set'}
              </span>
            </div>
          </div>

          {health.mongodb_error && (
            <div className="health-banner health-banner--warn">{health.mongodb_error}</div>
          )}

          {health.mongodb && health.mongodb.collections && (
            <section className="health-section">
              <h2 className="health-section-title">Database</h2>
              <p className="health-section-meta">
                <span className="health-tag">{health.mongodb.database}</span>
                Collections: {health.mongodb.collections.join(', ')}
              </p>
            </section>
          )}

          {(health.graph_names || []).length > 0 && (
            <section className="health-section">
              <h2 className="health-section-title">Graph keys in MongoDB</h2>
              <ul className="health-chip-list">
                {(health.graph_names || []).map((name) => (
                  <li key={name} className="health-chip">
                    {name}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="health-section health-section--llm">
            <h2 className="health-section-title">LLM analysis</h2>
            {!health.groq_configured && (
              <p className="health-muted">Set <code className="health-inline-code">GROQ_API_KEY</code> in <code className="health-inline-code">backend/.env</code> to enable narrative insights.</p>
            )}
            {health.groq_configured && llmText && (
              <div className="health-llm-body">{llmText}</div>
            )}
            {health.groq_configured && !llmText && !loading && (
              <p className="health-muted">No summary returned. Check Groq quota and logs.</p>
            )}
          </section>

          <section className="health-section">
            <h2 className="health-section-title">
              Architecture violations <span className="health-count">({violations.length})</span>
            </h2>
            {violations.length === 0 ? (
              <p className="health-muted">No violations found in stored graph metadata or flagged edges.</p>
            ) : (
              <ul className="health-violation-list">
                {violations.map((v, i) => (
                  <li key={i} className="health-violation-item">
                    <span className="health-violation-graph">{v.graph_name}</span>
                    <span className="health-violation-detail">{v.detail}</span>
                    {(v.type || v.from) && (
                      <span className="health-violation-meta">
                        {[v.type, v.from && v.to ? `${v.from} → ${v.to}` : null].filter(Boolean).join(' · ')}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default Health;
