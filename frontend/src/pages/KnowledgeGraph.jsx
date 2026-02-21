import React, { useState, useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
      const response = await api.get(`/api/graph/${encodeURIComponent(key)}/visualize`);
      setGraphData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load graph');
    } finally {
      setLoading(false);
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
          selector: 'edge',
          style: {
            'width': 'mapData(strength, 0, 1, 1, 4)',
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.7,
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
        }
      ],
      layout: {
        name: 'cose-bilkent',
        idealEdgeLength: 150,
        nodeOverlap: 50,
        refresh: 30,
        fit: true,
        padding: 50,
        randomize: true,
        componentSpacing: 150,
        nodeRepulsion: 850000,
        edgeElasticity: 150,
        nestingFactor: 1.2,
        gravity: 0.25,
        numIter: 2500,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0,
        animate: true,
        animationDuration: 1000,
        animationEasing: 'ease-out'
      }
    });

    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      const data = node.data();
      alert(`Node: ${data.label}\nType: ${data.type}\nCategory: ${data.category}\nFile: ${data.file_path}`);
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
                <div className="answer-content">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code: ({node, inline, className, children, ...props}) => {
                        const match = /language-(\w+)/.exec(className || '');
                        return !inline && match ? (
                          <pre style={{
                            background: '#f4f4f4',
                            padding: '1rem',
                            borderRadius: '4px',
                            overflow: 'auto',
                            border: '1px solid #ddd'
                          }}>
                            <code className={className} {...props}>
                              {children}
                            </code>
                          </pre>
                        ) : (
                          <code className={className} style={{
                            background: '#f4f4f4',
                            padding: '0.2em 0.4em',
                            borderRadius: '3px',
                            fontSize: '0.9em'
                          }} {...props}>
                            {children}
                          </code>
                        );
                      },
                      p: ({node, ...props}) => <p style={{ marginBottom: '1rem', lineHeight: '1.6' }} {...props} />,
                      h1: ({node, ...props}) => <h1 style={{ fontSize: '1.5rem', marginTop: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      h2: ({node, ...props}) => <h2 style={{ fontSize: '1.3rem', marginTop: '1.3rem', marginBottom: '0.8rem' }} {...props} />,
                      h3: ({node, ...props}) => <h3 style={{ fontSize: '1.1rem', marginTop: '1.1rem', marginBottom: '0.6rem' }} {...props} />,
                      ul: ({node, ...props}) => <ul style={{ marginLeft: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      ol: ({node, ...props}) => <ol style={{ marginLeft: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      li: ({node, ...props}) => <li style={{ marginBottom: '0.5rem' }} {...props} />,
                      blockquote: ({node, ...props}) => (
                        <blockquote style={{
                          borderLeft: '4px solid #ddd',
                          paddingLeft: '1rem',
                          marginLeft: '0',
                          marginBottom: '1rem',
                          color: '#666',
                          fontStyle: 'italic'
                        }} {...props} />
                      ),
                      strong: ({node, ...props}) => <strong style={{ fontWeight: 'bold' }} {...props} />,
                      em: ({node, ...props}) => <em style={{ fontStyle: 'italic' }} {...props} />,
                    }}
                  >
                    {answer.answer}
                  </ReactMarkdown>
                </div>
                {answer.relevant_elements && answer.relevant_elements.length > 0 && (
                  <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid #ddd' }}>
                    <strong>Relevant Elements:</strong>
                    <ul style={{ marginTop: '0.5rem' }}>
                      {answer.relevant_elements.slice(0, 5).map((elem, idx) => (
                        <li key={idx} style={{ marginBottom: '0.3rem' }}>{elem}</li>
                      ))}
                    </ul>
                  </div>
                )}
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
                <div className="answer-content">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code: ({node, inline, className, children, ...props}) => {
                        const match = /language-(\w+)/.exec(className || '');
                        return !inline && match ? (
                          <pre style={{
                            background: '#f4f4f4',
                            padding: '1rem',
                            borderRadius: '4px',
                            overflow: 'auto',
                            border: '1px solid #ddd'
                          }}>
                            <code className={className} {...props}>
                              {children}
                            </code>
                          </pre>
                        ) : (
                          <code className={className} style={{
                            background: '#f4f4f4',
                            padding: '0.2em 0.4em',
                            borderRadius: '3px',
                            fontSize: '0.9em'
                          }} {...props}>
                            {children}
                          </code>
                        );
                      },
                      p: ({node, ...props}) => <p style={{ marginBottom: '1rem', lineHeight: '1.6' }} {...props} />,
                      h1: ({node, ...props}) => <h1 style={{ fontSize: '1.5rem', marginTop: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      h2: ({node, ...props}) => <h2 style={{ fontSize: '1.3rem', marginTop: '1.3rem', marginBottom: '0.8rem' }} {...props} />,
                      h3: ({node, ...props}) => <h3 style={{ fontSize: '1.1rem', marginTop: '1.1rem', marginBottom: '0.6rem' }} {...props} />,
                      h4: ({node, ...props}) => <h4 style={{ fontSize: '1rem', marginTop: '1rem', marginBottom: '0.6rem' }} {...props} />,
                      ul: ({node, ...props}) => <ul style={{ marginLeft: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      ol: ({node, ...props}) => <ol style={{ marginLeft: '1.5rem', marginBottom: '1rem' }} {...props} />,
                      li: ({node, ...props}) => <li style={{ marginBottom: '0.5rem' }} {...props} />,
                      blockquote: ({node, ...props}) => (
                        <blockquote style={{
                          borderLeft: '4px solid #ddd',
                          paddingLeft: '1rem',
                          marginLeft: '0',
                          marginBottom: '1rem',
                          color: '#666',
                          fontStyle: 'italic'
                        }} {...props} />
                      ),
                      strong: ({node, ...props}) => <strong style={{ fontWeight: 'bold' }} {...props} />,
                      em: ({node, ...props}) => <em style={{ fontStyle: 'italic' }} {...props} />,
                    }}
                  >
                    {whatIfResult.analysis}
                  </ReactMarkdown>
                </div>
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
