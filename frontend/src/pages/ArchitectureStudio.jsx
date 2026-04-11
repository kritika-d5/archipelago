import React, { useState, useEffect, useRef } from 'react';
import api, { generateArchitectureBlueprint } from '../services/api';
import mermaid from 'mermaid';

function escapeHtml(s) {
  if (!s) return '';
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * LLM output is often one long line; Mermaid's flowchart parser needs line breaks between statements.
 */
function normalizeMermaidDiagram(raw) {
  let s = (raw || '').trim();
  if (!s) return s;
  s = s.replace(/^(flowchart\s+(?:TD|TB|BT|RL|LR))\s+/im, '$1\n  ');
  s = s.replace(/^(graph\s+(?:TD|TB|BT|RL|LR))\s+/im, '$1\n  ');
  s = s.replace(/(\])\s+([A-Za-z][\w]*)\s*(-->|\[)/g, '$1\n  $2$3');
  return s.trim();
}

function ArchitectureStudio() {
  const [mode, setMode] = useState('greenfield');
  const [requirements, setRequirements] = useState('');
  const [repoKey, setRepoKey] = useState('');
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [scalability, setScalability] = useState('');
  const [performance, setPerformance] = useState('');
  const [budget, setBudget] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [blueprint, setBlueprint] = useState(null);
  const [systemSummary, setSystemSummary] = useState(null);
  const mermaidHostRef = useRef(null);

  useEffect(() => {
    loadParsedGraphs();
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true },
    });
  }, []);

  useEffect(() => {
    const def = blueprint?.mermaid_diagram;
    const el = mermaidHostRef.current;
    if (!def || !el) return undefined;

    let cancelled = false;

    const runRender = async () => {
      try {
        el.innerHTML = '';
        const normalized = normalizeMermaidDiagram(def);
        const id = `mmd-arch-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
        const { svg, bindFunctions } = await mermaid.render(id, normalized);
        if (cancelled || mermaidHostRef.current !== el) return;
        el.innerHTML = svg;
        if (typeof bindFunctions === 'function') {
          bindFunctions(el);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (!cancelled && mermaidHostRef.current === el) {
          el.innerHTML = `<pre class="arch-studio-mermaid-fallback">${escapeHtml(def)}</pre>`;
        }
      }
    };

    const t = requestAnimationFrame(() => {
      runRender();
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(t);
    };
  }, [blueprint]);

  const loadParsedGraphs = async () => {
    try {
      const response = await api.get('/api/parse/');
      setParsedGraphs(response.data.graphs || []);
    } catch (err) {
      console.error('Error loading graphs:', err);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setBlueprint(null);

    try {
      const payload = {
        mode: mode,
        requirements: mode === 'greenfield' ? requirements : requirements || 'Optimize the existing architecture',
        repo_key: mode === 'brownfield' ? repoKey : null,
        constraints: mode === 'greenfield' ? {
          scalability: scalability || null,
          performance: performance || null,
          budget: budget || null
        } : null
      };

      const response = await generateArchitectureBlueprint(payload);
      setBlueprint(response);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate architecture blueprint');
    } finally {
      setLoading(false);
    }
  };

  const handleRepoChange = async (selectedRepoKey) => {
    setRepoKey(selectedRepoKey);
    if (selectedRepoKey && mode === 'brownfield') {
      try {
        // Fetch system summary (optional - can be done on generate)
        const graphResponse = await api.get(`/api/graph/saved/${selectedRepoKey}`);
        if (graphResponse.data && graphResponse.data.graph_data) {
          const stats = graphResponse.data.graph_data.stats || {};
          setSystemSummary({
            totalServices: stats.services || 0,
            totalSchemas: stats.schemas || 0,
            totalEndpoints: stats.endpoints || 0,
            totalNodes: stats.total_nodes || 0
          });
        }
      } catch (err) {
        console.error('Error loading system summary:', err);
      }
    }
  };

  return (
    <div className="main-content">
      <div className="card">
        <h1 className="card-title">🏗️ Architecture Studio</h1>

        {/* Mode Toggle */}
        <div className="form-group">
          <label>Mode</label>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              className={`btn ${mode === 'greenfield' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('greenfield')}
            >
              Greenfield
            </button>
            <button
              type="button"
              className={`btn ${mode === 'brownfield' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('brownfield')}
            >
              Brownfield
            </button>
          </div>
        </div>

        <form onSubmit={handleGenerate}>
          {mode === 'greenfield' ? (
            <>
              <div className="form-group">
                <label>Requirements *</label>
                <textarea
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  placeholder="Describe your system requirements, features, and goals..."
                  rows={6}
                  required
                />
              </div>

              <div className="form-group">
                <label>Scalability Requirements</label>
                <input
                  type="text"
                  value={scalability}
                  onChange={(e) => setScalability(e.target.value)}
                  placeholder="e.g., Handle 1M concurrent users"
                />
              </div>

              <div className="form-group">
                <label>Performance Requirements</label>
                <input
                  type="text"
                  value={performance}
                  onChange={(e) => setPerformance(e.target.value)}
                  placeholder="e.g., <100ms response time"
                />
              </div>

              <div className="form-group">
                <label>Budget Constraints</label>
                <input
                  type="text"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="e.g., $10k/month cloud budget"
                />
              </div>
            </>
          ) : (
            <>
              <div className="form-group">
                <label>Repository *</label>
                <select
                  value={repoKey}
                  onChange={(e) => handleRepoChange(e.target.value)}
                  required
                >
                  <option value="">Select a repository...</option>
                  {parsedGraphs.map((graph) => (
                    <option key={graph.key} value={graph.key}>
                      {graph.repository || graph.key}
                    </option>
                  ))}
                </select>
              </div>

              {systemSummary && (
                <div className="info-grid" style={{ marginBottom: '1.5rem' }}>
                  <div className="info-card">
                    <div className="info-card-label">Services</div>
                    <div className="info-card-value">{systemSummary.totalServices}</div>
                  </div>
                  <div className="info-card">
                    <div className="info-card-label">Schemas</div>
                    <div className="info-card-value">{systemSummary.totalSchemas}</div>
                  </div>
                  <div className="info-card">
                    <div className="info-card-label">Endpoints</div>
                    <div className="info-card-value">{systemSummary.totalEndpoints}</div>
                  </div>
                  <div className="info-card">
                    <div className="info-card-label">Total Nodes</div>
                    <div className="info-card-value">{systemSummary.totalNodes}</div>
                  </div>
                </div>
              )}

              <div className="form-group">
                <label>User Intent / Optimization Goals</label>
                <textarea
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  placeholder="Describe what you want to optimize or change in the existing architecture..."
                  rows={4}
                />
              </div>
            </>
          )}

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Generating...' : 'Generate Architecture Blueprint'}
          </button>
        </form>
      </div>

      {blueprint && (
        <div className="card arch-studio-blueprint">
          <h2 className="card-title">Architecture Blueprint</h2>

          <div className="form-group">
            <h3 className="arch-studio-section-title">Architecture Style</h3>
            <div className="arch-studio-box">
              <span className="arch-studio-confidence">
                Confidence: {(blueprint.confidence_score * 100).toFixed(1)}%
              </span>
              <strong>{blueprint.architecture_style}</strong>
            </div>
          </div>

          <div className="form-group">
            <h3 className="arch-studio-section-title">System Overview</h3>
            <div className="arch-studio-box">{blueprint.system_overview}</div>
          </div>

          {blueprint.services && blueprint.services.length > 0 && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Services</h3>
              <div className="arch-studio-services-grid">
                {blueprint.services.map((service, idx) => (
                  <div key={idx} className="arch-studio-service-card">
                    <h4>{service.name}</h4>
                    <p>{service.description}</p>
                    <div className="arch-studio-tech">
                      <strong>Technology:</strong> {service.technology}
                    </div>
                    {service.responsibilities && service.responsibilities.length > 0 && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <strong>Responsibilities:</strong>
                        <ul>
                          {service.responsibilities.map((resp, i) => (
                            <li key={i}>{resp}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {blueprint.infrastructure && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Infrastructure</h3>
              <div className="arch-studio-box">
                <div>
                  <strong>Cloud Provider:</strong> {blueprint.infrastructure.cloud_provider || 'N/A'}
                </div>
                {blueprint.infrastructure.compute && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong>Compute:</strong>
                    <pre className="arch-studio-mermaid-fallback" style={{ marginTop: '0.35rem' }}>
                      {JSON.stringify(blueprint.infrastructure.compute, null, 2)}
                    </pre>
                  </div>
                )}
                {blueprint.infrastructure.storage && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong>Storage:</strong>
                    <pre className="arch-studio-mermaid-fallback" style={{ marginTop: '0.35rem' }}>
                      {JSON.stringify(blueprint.infrastructure.storage, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {blueprint.data_architecture && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Data Architecture</h3>
              <div className="arch-studio-box">
                {blueprint.data_architecture.databases && blueprint.data_architecture.databases.length > 0 && (
                  <div>
                    <strong>Databases:</strong>
                    <ul className="arch-studio-list">
                      {blueprint.data_architecture.databases.map((dbItem, idx) => (
                        <li key={idx}>
                          <pre className="arch-studio-mermaid-fallback" style={{ marginTop: '0.25rem' }}>
                            {JSON.stringify(dbItem, null, 2)}
                          </pre>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {blueprint.data_architecture.data_flow && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong>Data Flow:</strong> {blueprint.data_architecture.data_flow}
                  </div>
                )}
              </div>
            </div>
          )}

          {blueprint.detected_issues && blueprint.detected_issues.length > 0 && (
            <div className="form-group">
              <h3 className="arch-studio-section-title arch-studio-issues-title">Detected Issues</h3>
              <ul className="arch-studio-list">
                {blueprint.detected_issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {blueprint.recommendations && blueprint.recommendations.length > 0 && (
            <div className="form-group">
              <h3 className="arch-studio-section-title arch-studio-recs-title">Recommendations</h3>
              <ul className="arch-studio-list">
                {blueprint.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}

          {blueprint.tradeoffs && blueprint.tradeoffs.length > 0 && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Tradeoffs</h3>
              <ul className="arch-studio-list">
                {blueprint.tradeoffs.map((tradeoff, idx) => (
                  <li key={idx}>{tradeoff}</li>
                ))}
              </ul>
            </div>
          )}

          {blueprint.migration_plan && blueprint.migration_plan.length > 0 && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Migration Plan</h3>
              <ol className="arch-studio-list">
                {blueprint.migration_plan.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {blueprint.mermaid_diagram && (
            <div className="form-group">
              <h3 className="arch-studio-section-title">Architecture Diagram</h3>
              <div className="arch-mermaid-wrap">
                <div ref={mermaidHostRef} className="arch-mermaid-host" aria-live="polite" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ArchitectureStudio;

