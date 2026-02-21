import React, { useState, useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import api from '../services/api';

cytoscape.use(coseBilkent);

function KnowledgeGraph() {
  const [repoKey, setRepoKey] = useState('');
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState(null);
  const [whatIfScenario, setWhatIfScenario] = useState('');
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [showJson, setShowJson] = useState(false);
  const [jsonData, setJsonData] = useState(null);
  const [subgraphElement, setSubgraphElement] = useState('');
  const [subgraphContext, setSubgraphContext] = useState(null);
  const [projectExplanation, setProjectExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    loadParsedGraphs();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const repo = params.get('repo');
    if (repo) {
      setRepoKey(repo);
      loadGraph(repo);
    } else if (parsedGraphs.length > 0 && !repoKey) {
      setRepoKey(parsedGraphs[0].key);
      loadGraph(parsedGraphs[0].key);
    }
  }, [parsedGraphs]);

  const loadParsedGraphs = async () => {
    try {
      const response = await api.get('/api/parse/');
      setParsedGraphs(response.data.graphs || []);
    } catch (err) {
      console.error('Error loading graphs:', err);
    }
  };

  useEffect(() => {
    if (graphData && containerRef.current) {
      renderGraph();
    }
  }, [graphData]);

  const loadGraph = async (key) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/graph/${encodeURIComponent(key)}/visualize?important_only=false`);
      setGraphData(response.data);
      // Load project explanation
      loadProjectExplanation(key);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  };

  const loadProjectExplanation = async (key) => {
    setLoadingExplanation(true);
    try {
      const response = await api.get(`/api/graph/${encodeURIComponent(key)}/explain`);
      setProjectExplanation(response.data);
    } catch (err) {
      console.error('Failed to load project explanation:', err);
      // Don't show error, just don't display explanation
    } finally {
      setLoadingExplanation(false);
    }
  };

  const loadJson = async (key) => {
    try {
      const response = await api.get(`/api/parse/${encodeURIComponent(key)}/json`);
      setJsonData(response.data);
      setShowJson(true);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load JSON');
    }
  };

  const renderGraph = () => {
    if (!graphData || !containerRef.current) return;

    // Destroy existing instance
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    // Create Cytoscape instance
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [...graphData.nodes, ...graphData.edges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#667eea',
            'label': 'data(label)',
            'width': 'mapData(degree, 0, 20, 40, 80)',
            'height': 'mapData(degree, 0, 20, 40, 80)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'font-size': '11px',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-outline-width': 2,
            'text-outline-color': '#333',
            'border-width': 2,
            'border-color': '#fff',
          }
        },
        {
          selector: 'node[category="agent"]',
          style: {
            'background-color': '#e74c3c',
            'shape': 'star',
            'width': 60,
            'height': 60,
          }
        },
        {
          selector: 'node[category="class"]',
          style: {
            'background-color': '#9b59b6',
            'shape': 'rectangle',
            'width': 80,
            'height': 50,
          }
        },
        {
          selector: 'node[category="function"]',
          style: {
            'background-color': '#3498db',
            'shape': 'ellipse',
            'width': 50,
            'height': 50,
          }
        },
        {
          selector: 'node[category="api"]',
          style: {
            'background-color': '#f39c12',
            'shape': 'round-rectangle',
            'width': 70,
            'height': 45,
          }
        },
        {
          selector: 'node[category="docker"]',
          style: {
            'background-color': '#0db7ed',
            'shape': 'hexagon',
            'width': 60,
            'height': 60,
          }
        },
        {
          selector: 'node[category="kubernetes"]',
          style: {
            'background-color': '#326ce5',
            'shape': 'diamond',
            'width': 60,
            'height': 60,
          }
        },
        {
          selector: 'node[category="module"]',
          style: {
            'background-color': '#764ba2',
            'width': 50,
            'height': 50,
          }
        },
        {
          selector: 'node[category="workflow"]',
          style: {
            'background-color': '#16a085',
            'shape': 'round-diamond',
            'width': 70,
            'height': 70,
            'border-width': 3,
            'border-color': '#1abc9c',
          }
        },
        {
          selector: 'node[category="database_schema"]',
          style: {
            'background-color': '#d35400',
            'shape': 'round-octagon',
            'width': 80,
            'height': 80,
            'border-width': 3,
            'border-color': '#e67e22',
          }
        },
        {
          selector: 'node[category="database_table"]',
          style: {
            'background-color': '#c0392b',
            'shape': 'round-hexagon',
            'width': 60,
            'height': 60,
            'border-width': 2,
            'border-color': '#e74c3c',
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 'mapData(strength, 0, 1, 1, 4)',
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.7,
            'label': 'data(relation)',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'font-size': '10px',
            'color': '#34495e',
            'text-outline-width': 2,
            'text-outline-color': '#fff',
            'text-background-color': '#fff',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
          }
        },
        {
          selector: 'edge[dependency_type="inheritance"]',
          style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            'width': 3,
          }
        },
        {
          selector: 'edge[dependency_type="call"]',
          style: {
            'line-color': '#3498db',
            'target-arrow-color': '#3498db',
            'width': 2,
          }
        },
        {
          selector: 'edge[dependency_type="import"]',
          style: {
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'line-style': 'dashed',
          }
        },
        {
          selector: 'edge[dependency_type="uses_agent"]',
          style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            'width': 3,
            'line-style': 'dotted',
          }
        },
        {
          selector: 'edge[dependency_type="triggers_workflow"]',
          style: {
            'line-color': '#16a085',
            'target-arrow-color': '#16a085',
            'width': 3,
            'line-style': 'dashed',
          }
        },
        {
          selector: 'edge[dependency_type="queries_database"]',
          style: {
            'line-color': '#d35400',
            'target-arrow-color': '#d35400',
            'width': 2.5,
          }
        },
        {
          selector: 'edge[dependency_type="reads_from_database"]',
          style: {
            'line-color': '#3498db',
            'target-arrow-color': '#3498db',
            'width': 2,
            'line-style': 'dashed',
          }
        },
        {
          selector: 'edge[dependency_type="writes_to_database"]',
          style: {
            'line-color': '#c0392b',
            'target-arrow-color': '#c0392b',
            'width': 2.5,
            'line-style': 'solid',
          }
        }
      ],
      layout: {
        name: 'cose-bilkent',
        idealEdgeLength: 300,
        nodeOverlap: 10,
        refresh: 30,
        fit: true,
        padding: 150,
        randomize: true,
        componentSpacing: 300,
        nodeRepulsion: 2000000,
        edgeElasticity: 300,
        nestingFactor: 2.0,
        gravity: 0.1,
        numIter: 4000,
        initialTemp: 300,
        coolingFactor: 0.99,
        minTemp: 0.1,
        animate: true,
        animationDuration: 2000,
        animationEasing: 'ease-out'
      }
    });

    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      const data = node.data();
      alert(`Node: ${data.label}\nType: ${data.type}\nCategory: ${data.category}\nFile: ${data.file_path}`);
    });
    
    cyRef.current.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      const data = edge.data();
      alert(`Edge Relation: ${data.relation || data.dependency_type || 'unknown'}\nStrength: ${data.strength || 1.0}`);
    });

    cyRef.current.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      node.style('border-width', 4);
      node.style('border-color', '#fff');
    });

    cyRef.current.on('mouseout', 'node', (evt) => {
      const node = evt.target;
      node.style('border-width', 2);
    });

    cyRef.current.userPanningEnabled(true);
    cyRef.current.userZoomingEnabled(true);
    cyRef.current.boxSelectionEnabled(true);
  };

  const handleQuery = async () => {
    if (!repoKey || !query.trim()) return;

    setLoading(true);
    setAnswer(null);
    try {
      const response = await api.post(`/api/query/ask?repo_key=${encodeURIComponent(repoKey)}`, {
        query: query,
        include_code: true,
        max_context_elements: 10
      });
      setAnswer(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process query');
    } finally {
      setLoading(false);
    }
  };

  const handleWhatIf = async () => {
    if (!repoKey || !whatIfScenario.trim()) return;

    setLoading(true);
    setWhatIfResult(null);
    try {
      const response = await api.post(`/api/query/what-if?repo_key=${encodeURIComponent(repoKey)}`, {
        scenario: whatIfScenario,
        include_impact_chain: true,
        max_depth: 5
      });
      setWhatIfResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to perform analysis');
    } finally {
      setLoading(false);
    }
  };

  const handleSubgraphExtraction = async () => {
    if (!repoKey || !subgraphElement.trim()) return;

    setLoading(true);
    setSubgraphContext(null);
    try {
      const response = await api.get(`/api/graph/${encodeURIComponent(repoKey)}/subgraph/${encodeURIComponent(subgraphElement)}?max_depth=3`);
      setSubgraphContext(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to extract subgraph');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h2 className="card-title">Knowledge Graph</h2>
        
        <div className="form-group">
          <label>Select Repository</label>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <select
              value={repoKey}
              onChange={(e) => {
                setRepoKey(e.target.value);
                loadGraph(e.target.value);
              }}
              style={{ flex: 1, padding: '0.75rem', border: '2px solid #e0e0e0', borderRadius: '8px' }}
            >
              {parsedGraphs.length === 0 ? (
                <option value="">No repositories parsed yet</option>
              ) : (
                parsedGraphs.map((graph, idx) => (
                  <option key={idx} value={graph.key}>
                    {graph.repository} ({new Date(graph.parsed_at).toLocaleDateString()})
                  </option>
                ))
              )}
            </select>
            {repoKey && (
              <>
                <button onClick={() => loadGraph(repoKey)} className="btn btn-primary">
                  Refresh
                </button>
                <button onClick={() => loadJson(repoKey)} className="btn btn-secondary">
                  View JSON
                </button>
              </>
            )}
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        {loading && !graphData && <div className="loading">Loading graph...</div>}

        {graphData && (
          <>
            <div className="info-grid">
              <div className="info-card">
                <div className="info-card-label">Nodes</div>
                <div className="info-card-value">{graphData.metadata?.total_nodes || 0}</div>
              </div>
              <div className="info-card">
                <div className="info-card-label">Edges</div>
                <div className="info-card-value">{graphData.metadata?.total_edges || 0}</div>
              </div>
              <div className="info-card">
                <div className="info-card-label">Repository</div>
                <div className="info-card-value">{graphData.metadata?.repository_name || 'N/A'}</div>
              </div>
            </div>

            <div ref={containerRef} className="graph-container" />
          </>
        )}
      </div>

        {graphData && (
        <div className="card" style={{ marginTop: '2rem' }}>
          <h2 className="card-title">Database Schema</h2>
          {loadingExplanation && (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
              Generating project explanation...
            </div>
          )}
          {projectExplanation && !loadingExplanation && (
            <div style={{ 
              background: '#f8f9fa', 
              padding: '1.5rem', 
              borderRadius: '8px',
              lineHeight: '1.8',
              whiteSpace: 'pre-wrap',
              fontFamily: 'system-ui, -apple-system, sans-serif'
            }}>
              {projectExplanation.explanation.split('\n').map((line, idx) => {
                // Format headings
                if (line.startsWith('#') || line.match(/^\d+\.\s+\*\*/)) {
                  return <h3 key={idx} style={{ marginTop: '1rem', marginBottom: '0.5rem', color: '#333' }}>{line.replace(/^#+\s*/, '').replace(/\*\*/g, '')}</h3>;
                }
                // Format bold text
                if (line.includes('**')) {
                  const parts = line.split(/(\*\*.*?\*\*)/g);
                  return (
                    <p key={idx} style={{ marginBottom: '0.5rem' }}>
                      {parts.map((part, pIdx) => 
                        part.startsWith('**') && part.endsWith('**') ? 
                          <strong key={pIdx}>{part.slice(2, -2)}</strong> : part
                      )}
                    </p>
                  );
                }
                return <p key={idx} style={{ marginBottom: '0.5rem' }}>{line}</p>;
              })}
            </div>
          )}
        </div>
      )}

      {showJson && jsonData && (
        <div className="card" style={{ marginTop: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="card-title">Parsed JSON Data</h2>
            <button onClick={() => setShowJson(false)} className="btn btn-secondary">Close</button>
          </div>
          <pre style={{ 
            background: '#f8f9fa', 
            padding: '1.5rem', 
            borderRadius: '8px', 
            overflow: 'auto', 
            maxHeight: '600px',
            fontSize: '12px',
            lineHeight: '1.5'
          }}>
            {JSON.stringify(jsonData, null, 2)}
          </pre>
        </div>
      )}

      {graphData && (
        <>
          <div className="card query-section">
            <h2 className="card-title">Ask Questions</h2>
            <div className="query-input">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a question about the codebase..."
                onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
              />
              <button onClick={handleQuery} className="btn btn-primary" disabled={loading}>
                Ask
              </button>
            </div>
            {answer && (
              <div className="answer-box">
                <h3>Answer</h3>
                <p>{answer.answer}</p>
                {answer.relevant_elements && answer.relevant_elements.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <strong>Relevant Elements:</strong>
                    <ul>
                      {answer.relevant_elements.slice(0, 5).map((elem, idx) => (
                        <li key={idx}>{elem}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card query-section">
            <h2 className="card-title">Subgraph Extraction</h2>
            <p style={{ color: '#666', marginBottom: '1rem' }}>
              Enter an element name (e.g., "UserService") to see what would be affected if you modify it.
            </p>
            <div className="query-input">
              <input
                type="text"
                value={subgraphElement}
                onChange={(e) => setSubgraphElement(e.target.value)}
                placeholder="Enter element name (e.g., UserService, OrderService)"
                onKeyPress={(e) => e.key === 'Enter' && handleSubgraphExtraction()}
              />
              <button onClick={handleSubgraphExtraction} className="btn btn-primary" disabled={loading}>
                Extract Subgraph
              </button>
            </div>
            {subgraphContext && (
              <div className="answer-box" style={{ marginTop: '1rem' }}>
                <h3>Impact Context: {subgraphContext.target_service || subgraphContext.target_element_id}</h3>
                {subgraphContext.impact_summary && (
                  <div style={{ 
                    background: '#f8f9fa', 
                    padding: '1rem', 
                    borderRadius: '8px', 
                    marginBottom: '1rem',
                    whiteSpace: 'pre-line'
                  }}>
                    {subgraphContext.impact_summary}
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                  {subgraphContext.direct_dependents && subgraphContext.direct_dependents.length > 0 && (
                    <div>
                      <strong>Direct Dependents ({subgraphContext.direct_dependents.length}):</strong>
                      <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                        {subgraphContext.direct_dependents.slice(0, 10).map((dep, idx) => (
                          <li key={idx}>{dep}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {subgraphContext.affected_apis && subgraphContext.affected_apis.length > 0 && (
                    <div>
                      <strong>Affected APIs ({subgraphContext.affected_apis.length}):</strong>
                      <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                        {subgraphContext.affected_apis.slice(0, 10).map((api, idx) => (
                          <li key={idx}>{api}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {subgraphContext.database_tables && subgraphContext.database_tables.length > 0 && (
                    <div>
                      <strong>Database Tables ({subgraphContext.database_tables.length}):</strong>
                      <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                        {subgraphContext.database_tables.slice(0, 10).map((table, idx) => (
                          <li key={idx}>{table}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {subgraphContext.agents_involved && subgraphContext.agents_involved.length > 0 && (
                    <div>
                      <strong>Agents Involved ({subgraphContext.agents_involved.length}):</strong>
                      <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                        {subgraphContext.agents_involved.slice(0, 10).map((agent, idx) => (
                          <li key={idx}>{agent}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {subgraphContext.workflows_involved && subgraphContext.workflows_involved.length > 0 && (
                    <div>
                      <strong>Workflows Involved ({subgraphContext.workflows_involved.length}):</strong>
                      <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                        {subgraphContext.workflows_involved.slice(0, 10).map((workflow, idx) => (
                          <li key={idx}>{workflow}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card query-section">
            <h2 className="card-title">What-If Analysis</h2>
            <div className="form-group">
              <label>Scenario</label>
              <textarea
                value={whatIfScenario}
                onChange={(e) => setWhatIfScenario(e.target.value)}
                placeholder="What if I change this function to accept a different parameter type?"
                rows={4}
              />
            </div>
            <button onClick={handleWhatIf} className="btn btn-primary" disabled={loading}>
              Analyze Impact
            </button>
            {whatIfResult && (
              <div className="answer-box" style={{ marginTop: '1rem' }}>
                <h3>
                  Impact Analysis
                  <span className={`risk-badge risk-${whatIfResult.risk_level}`}>
                    {whatIfResult.risk_level.toUpperCase()}
                  </span>
                </h3>
                <p>{whatIfResult.analysis}</p>
                {whatIfResult.recommendations && whatIfResult.recommendations.length > 0 && (
                  <div className="recommendations">
                    <h4>Recommendations:</h4>
                    <ul>
                      {whatIfResult.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {whatIfResult.impact_chain && whatIfResult.impact_chain.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <strong>Impact Chain ({whatIfResult.impact_chain.length} impacts):</strong>
                    <ul>
                      {whatIfResult.impact_chain.slice(0, 10).map((impact, idx) => (
                        <li key={idx}>
                          {impact.source} → {impact.target} (depth: {impact.depth})
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default KnowledgeGraph;
