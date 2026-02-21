import React, { useState, useEffect } from 'react';
import api, { generateArchitectureBlueprint } from '../services/api';
import mermaid from 'mermaid';

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

  useEffect(() => {
    loadParsedGraphs();
    mermaid.initialize({ 
      startOnLoad: false, 
      theme: 'default',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true }
    });
  }, []);

  useEffect(() => {
    if (blueprint && blueprint.mermaid_diagram) {
      const timer = setTimeout(() => {
        renderMermaidDiagram();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [blueprint]);

  const loadParsedGraphs = async () => {
    try {
      const response = await api.get('/api/parse/');
      setParsedGraphs(response.data.graphs || []);
    } catch (err) {
      console.error('Error loading graphs:', err);
    }
  };

  const renderMermaidDiagram = async () => {
    if (!blueprint || !blueprint.mermaid_diagram) return;
    
    try {
      const element = document.getElementById('mermaid-diagram');
      if (element) {
        element.innerHTML = '';
        const id = `mermaid-${Date.now()}`;
        element.setAttribute('data-processed', 'false');
        
        const graphDefinition = blueprint.mermaid_diagram;
        element.textContent = graphDefinition;
        
        await mermaid.run({
          nodes: [element],
          suppressErrors: true
        });
      }
    } catch (err) {
      console.error('Error rendering Mermaid diagram:', err);
      // Fallback: show raw diagram code
      const element = document.getElementById('mermaid-diagram');
      if (element) {
        element.innerHTML = `<pre style="padding: 1rem; background: #f4f4f4; border-radius: 4px; overflow: auto;">${blueprint.mermaid_diagram}</pre>`;
      }
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
        <div className="card">
          <h2 className="card-title">Architecture Blueprint</h2>

          {/* Architecture Style & Overview */}
          <div className="form-group">
            <h3 style={{ marginBottom: '0.5rem' }}>Architecture Style</h3>
            <div style={{ 
              padding: '1rem', 
              background: '#f8f9fa', 
              borderRadius: '8px',
              marginBottom: '1rem'
            }}>
              <strong>{blueprint.architecture_style}</strong>
              <span style={{ float: 'right', color: '#667eea' }}>
                Confidence: {(blueprint.confidence_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="form-group">
            <h3 style={{ marginBottom: '0.5rem' }}>System Overview</h3>
            <div style={{ 
              padding: '1rem', 
              background: '#f8f9fa', 
              borderRadius: '8px',
              lineHeight: '1.6'
            }}>
              {blueprint.system_overview}
            </div>
          </div>

          {/* Services */}
          {blueprint.services && blueprint.services.length > 0 && (
            <div className="form-group">
              <h3 style={{ marginBottom: '1rem' }}>Services</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
                {blueprint.services.map((service, idx) => (
                  <div key={idx} style={{
                    padding: '1rem',
                    background: '#f8f9fa',
                    borderRadius: '8px',
                    border: '1px solid #ddd'
                  }}>
                    <h4 style={{ marginBottom: '0.5rem', color: '#667eea' }}>{service.name}</h4>
                    <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>{service.description}</p>
                    <div style={{ fontSize: '0.85rem', color: '#666' }}>
                      <strong>Technology:</strong> {service.technology}
                    </div>
                    {service.responsibilities && service.responsibilities.length > 0 && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <strong>Responsibilities:</strong>
                        <ul style={{ marginLeft: '1.5rem', marginTop: '0.25rem' }}>
                          {service.responsibilities.map((resp, i) => (
                            <li key={i} style={{ fontSize: '0.85rem' }}>{resp}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Infrastructure */}
          {blueprint.infrastructure && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem' }}>Infrastructure</h3>
              <div style={{ 
                padding: '1rem', 
                background: '#f8f9fa', 
                borderRadius: '8px'
              }}>
                <div><strong>Cloud Provider:</strong> {blueprint.infrastructure.cloud_provider || 'N/A'}</div>
                {blueprint.infrastructure.compute && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong>Compute:</strong> {JSON.stringify(blueprint.infrastructure.compute, null, 2)}
                  </div>
                )}
                {blueprint.infrastructure.storage && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <strong>Storage:</strong> {JSON.stringify(blueprint.infrastructure.storage, null, 2)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Data Architecture */}
          {blueprint.data_architecture && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem' }}>Data Architecture</h3>
              <div style={{ 
                padding: '1rem', 
                background: '#f8f9fa', 
                borderRadius: '8px'
              }}>
                {blueprint.data_architecture.databases && blueprint.data_architecture.databases.length > 0 && (
                  <div>
                    <strong>Databases:</strong>
                    <ul style={{ marginLeft: '1.5rem', marginTop: '0.5rem' }}>
                      {blueprint.data_architecture.databases.map((db, idx) => (
                        <li key={idx}>{JSON.stringify(db, null, 2)}</li>
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

          {/* Detected Issues */}
          {blueprint.detected_issues && blueprint.detected_issues.length > 0 && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem', color: '#c33' }}>Detected Issues</h3>
              <ul style={{ marginLeft: '1.5rem' }}>
                {blueprint.detected_issues.map((issue, idx) => (
                  <li key={idx} style={{ marginBottom: '0.5rem' }}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {blueprint.recommendations && blueprint.recommendations.length > 0 && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem', color: '#3c3' }}>Recommendations</h3>
              <ul style={{ marginLeft: '1.5rem' }}>
                {blueprint.recommendations.map((rec, idx) => (
                  <li key={idx} style={{ marginBottom: '0.5rem' }}>{rec}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Tradeoffs */}
          {blueprint.tradeoffs && blueprint.tradeoffs.length > 0 && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem' }}>Tradeoffs</h3>
              <ul style={{ marginLeft: '1.5rem' }}>
                {blueprint.tradeoffs.map((tradeoff, idx) => (
                  <li key={idx} style={{ marginBottom: '0.5rem' }}>{tradeoff}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Migration Plan */}
          {blueprint.migration_plan && blueprint.migration_plan.length > 0 && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem' }}>Migration Plan</h3>
              <ol style={{ marginLeft: '1.5rem' }}>
                {blueprint.migration_plan.map((step, idx) => (
                  <li key={idx} style={{ marginBottom: '0.5rem' }}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Mermaid Diagram */}
          {blueprint.mermaid_diagram && (
            <div className="form-group">
              <h3 style={{ marginBottom: '0.5rem' }}>Architecture Diagram</h3>
              <div 
                id="mermaid-diagram" 
                className="mermaid"
                style={{
                  padding: '1rem',
                  background: 'white',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  overflow: 'auto',
                  textAlign: 'center'
                }}
              >
                {blueprint.mermaid_diagram}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ArchitectureStudio;

