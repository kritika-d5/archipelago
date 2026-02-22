import React, { useState, useEffect, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';

cytoscape.use(coseBilkent);

function KnowledgeGraph() {
  const location = useLocation();
  const [repoKey, setRepoKey] = useState('');
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [showJson, setShowJson] = useState(false);

  const EXAMPLE_QUESTIONS = [
    'How does authentication work in this codebase?',
    'What if I change the UserService API to accept JSON?',
    'Where are the main API endpoints defined?',
    'What would happen if I remove this database dependency?',
    'Explain the flow from login to checkout.',
    'What\'s the impact of renaming this function?',
  ];
  const [jsonData, setJsonData] = useState(null);
  const [subgraphElement, setSubgraphElement] = useState('');
  const [subgraphContext, setSubgraphContext] = useState(null);
  const [projectExplanation, setProjectExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [docDiffResult, setDocDiffResult] = useState(null);
  const [loadingDocDiff, setLoadingDocDiff] = useState(false);
  const [notionPageId, setNotionPageId] = useState(null);
  const [appliedSuggestions, setAppliedSuggestions] = useState(new Set());
  const [rejectedSuggestions, setRejectedSuggestions] = useState(new Set());
  const [applyingSuggestion, setApplyingSuggestion] = useState(null);
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    loadParsedGraphs();
  }, []);

  useEffect(() => {
    const state = location.state || {};
    if (state.notionContent) {
      setDocContent(state.notionContent);
      setNotionPageId(state.notionPageId || null);
    }
  }, [location.state]);

  const docDiffRef = useRef(null);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parsedGraphs]);

  useEffect(() => {
    if (docContent && docDiffRef.current && docDiffResult) {
      docDiffRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docContent, docDiffResult]);

  const hasAutoRunDocDiff = useRef(false);
  useEffect(() => {
    if (!hasAutoRunDocDiff.current && repoKey && docContent && !loadingDocDiff) {
      hasAutoRunDocDiff.current = true;
      (async () => {
        setLoadingDocDiff(true);
        setDocDiffResult(null);
        try {
          const resp = await api.post(`/api/query/doc-diff?repo_key=${encodeURIComponent(repoKey)}`, { documentation: docContent });
          setDocDiffResult(resp.data);
        } catch (err) {
          setError(err.response?.data?.detail || 'Failed to compare');
        } finally {
          setLoadingDocDiff(false);
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoKey, docContent]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData]);

  const loadGraph = async (key) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/graph/${encodeURIComponent(key)}/visualize?important_only=false`);
      setGraphData(response.data);
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

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [...graphData.nodes, ...graphData.edges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#667eea',
            'label': 'data(label)',
            'width': 'mapData(degree, 0, 20, 60, 100)',
            'height': 'mapData(degree, 0, 20, 60, 100)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'font-size': '13px',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-max-width': '150px',
            'text-outline-width': 3,
            'text-outline-color': '#000',
            'border-width': 2,
            'border-color': '#fff',
          }
        },
        { selector: 'node[category="agent"]', style: { 'background-color': '#e74c3c', 'shape': 'star', 'width': 60, 'height': 60 } },
        { selector: 'node[category="class"]', style: { 'background-color': '#9b59b6', 'shape': 'rectangle', 'width': 80, 'height': 50 } },
        { selector: 'node[category="function"]', style: { 'background-color': '#3498db', 'shape': 'ellipse', 'width': 50, 'height': 50 } },
        { selector: 'node[category="api"]', style: { 'background-color': '#f39c12', 'shape': 'round-rectangle', 'width': 100, 'height': 60, 'font-size': '14px', 'text-max-width': '150px' } },
        { selector: 'node[category="docker"]', style: { 'background-color': '#0db7ed', 'shape': 'hexagon', 'width': 60, 'height': 60 } },
        { selector: 'node[category="kubernetes"]', style: { 'background-color': '#326ce5', 'shape': 'diamond', 'width': 60, 'height': 60 } },
        { selector: 'node[category="module"]', style: { 'background-color': '#764ba2', 'width': 90, 'height': 55, 'font-size': '14px', 'text-max-width': '150px' } },
        { selector: 'node[category="workflow"]', style: { 'background-color': '#16a085', 'shape': 'round-diamond', 'width': 70, 'height': 70, 'border-width': 3, 'border-color': '#1abc9c' } },
        { selector: 'node[category="database_schema"]', style: { 'background-color': '#d35400', 'shape': 'round-octagon', 'width': 80, 'height': 80, 'border-width': 3, 'border-color': '#e67e22' } },
        { selector: 'node[category="database_table"]', style: { 'background-color': '#c0392b', 'shape': 'round-hexagon', 'width': 60, 'height': 60, 'border-width': 2, 'border-color': '#e74c3c' } },
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
        { selector: 'edge[dependency_type="inheritance"]', style: { 'line-color': '#e74c3c', 'target-arrow-color': '#e74c3c', 'width': 3 } },
        { selector: 'edge[dependency_type="call"]', style: { 'line-color': '#3498db', 'target-arrow-color': '#3498db', 'width': 2 } },
        { selector: 'edge[dependency_type="import"]', style: { 'line-color': '#95a5a6', 'target-arrow-color': '#95a5a6', 'line-style': 'dashed' } },
        { selector: 'edge[dependency_type="uses_agent"]', style: { 'line-color': '#e74c3c', 'target-arrow-color': '#e74c3c', 'width': 3, 'line-style': 'dotted' } },
        { selector: 'edge[dependency_type="triggers_workflow"]', style: { 'line-color': '#16a085', 'target-arrow-color': '#16a085', 'width': 3, 'line-style': 'dashed' } },
        { selector: 'edge[dependency_type="queries_database"]', style: { 'line-color': '#d35400', 'target-arrow-color': '#d35400', 'width': 2.5 } },
        { selector: 'edge[dependency_type="reads_from_database"]', style: { 'line-color': '#3498db', 'target-arrow-color': '#3498db', 'width': 2, 'line-style': 'dashed' } },
        { selector: 'edge[dependency_type="writes_to_database"]', style: { 'line-color': '#c0392b', 'target-arrow-color': '#c0392b', 'width': 2.5, 'line-style': 'solid' } },
        { selector: 'edge[type="REST"]', style: { 'line-color': '#3498db', 'target-arrow-color': '#3498db', 'width': 2.5, 'line-style': 'solid' } },
        { selector: 'edge[type="EVENT"]', style: { 'line-color': '#16a085', 'target-arrow-color': '#16a085', 'width': 2.5, 'line-style': 'dashed' } },
        { selector: 'edge[type="IMPORT"]', style: { 'line-color': '#95a5a6', 'target-arrow-color': '#95a5a6', 'width': 2, 'line-style': 'dotted' } },
        { selector: 'edge[type="DB_ACCESS"]', style: { 'line-color': '#e74c3c', 'target-arrow-color': '#e74c3c', 'width': 3, 'line-style': 'solid' } },
        { selector: 'edge[type="CIRCULAR"]', style: { 'line-color': '#f39c12', 'target-arrow-color': '#f39c12', 'width': 3, 'line-style': 'dashed' } },
        { selector: 'edge[violation="true"]', style: { 'line-color': '#e74c3c', 'target-arrow-color': '#e74c3c', 'width': 3, 'line-style': 'solid', 'opacity': 1.0 } },
        { selector: 'edge[circular="true"]', style: { 'line-color': '#f39c12', 'target-arrow-color': '#f39c12', 'width': 3, 'line-style': 'dashed', 'opacity': 1.0 } },
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
      const data = evt.target.data();
      alert(`Node: ${data.label}\nType: ${data.type}\nCategory: ${data.category}\nFile: ${data.file_path}`);
    });
    cyRef.current.on('tap', 'edge', (evt) => {
      const data = evt.target.data();
      alert(`Edge Relation: ${data.relation || data.dependency_type || 'unknown'}\nStrength: ${data.strength || 1.0}`);
    });
    cyRef.current.on('mouseover', 'node', (evt) => {
      evt.target.style('border-width', 4);
      evt.target.style('border-color', '#fff');
    });
    cyRef.current.on('mouseout', 'node', (evt) => {
      evt.target.style('border-width', 2);
    });
    cyRef.current.userPanningEnabled(true);
    cyRef.current.userZoomingEnabled(true);
    cyRef.current.boxSelectionEnabled(true);
  };

  const isWhatIfPrompt = (text) => /what if|what would happen|suppose|impact of|effect of|if i change|if we remove/i.test((text || '').trim());

  const handleChatSubmit = async (textOverride) => {
    const text = (textOverride ?? chatInput).trim();
    if (!repoKey || !text) return;

    const userMsg = { id: Date.now(), role: 'user', text };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setLoading(true);
    setError(null);

    const isWhatIf = isWhatIfPrompt(text);
    try {
      if (isWhatIf) {
        const response = await api.post(`/api/query/what-if?repo_key=${encodeURIComponent(repoKey)}`, {
          scenario: text,
          include_impact_chain: true,
          max_depth: 5
        });
        const data = response.data;
        const content = [data.analysis, data.recommendations?.length ? '\n**Recommendations:**\n' + data.recommendations.map((r) => `- ${r}`).join('\n') : ''].filter(Boolean).join('\n');
        setChatMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', text: content, type: 'whatif', data: response.data }]);
      } else {
        const response = await api.post(`/api/query/ask?repo_key=${encodeURIComponent(repoKey)}`, {
          query: text,
          include_code: true,
          max_context_elements: 10
        });
        const data = response.data;
        setChatMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', text: data.answer, type: 'answer', data }]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Something went wrong');
      setChatMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', text: 'Sorry, I couldn\'t process that. Try rephrasing or check the repo is loaded.', type: 'error' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleDocDiff = async () => {
    if (!repoKey || !docContent.trim()) return;
    setLoadingDocDiff(true);
    setDocDiffResult(null);
    setAppliedSuggestions(new Set());
    setRejectedSuggestions(new Set());
    hasAutoRunDocDiff.current = true;
    try {
      const response = await api.post(`/api/query/doc-diff?repo_key=${encodeURIComponent(repoKey)}`, {
        documentation: docContent.trim()
      });
      setDocDiffResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to compare documentation');
    } finally {
      setLoadingDocDiff(false);
    }
  };

  const handleKeepSuggestion = async (suggestion) => {
    if (!notionPageId) return;
    setApplyingSuggestion(suggestion.id);
    try {
      await api.post('/api/integrations/notion/update', {
        page_id: notionPageId,
        content: suggestion.suggested || suggestion.description
      });
      setAppliedSuggestions((prev) => new Set([...prev, suggestion.id]));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update Notion');
    } finally {
      setApplyingSuggestion(null);
    }
  };

  const handleRejectSuggestion = (suggestion) => {
    setRejectedSuggestions((prev) => new Set([...prev, suggestion.id]));
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

  const notionPageUrl = notionPageId ? `https://www.notion.so/${notionPageId.replace(/-/g, '')}` : null;

  return (
    <div className="graph-page">

      {/* ── TOP HEADER ── */}
      <div className="graph-page-header">
        <h1 className="graph-page-title">Knowledge Graph</h1>
        <div className="graph-page-controls">
          <label className="graph-page-label">Repository</label>
          <div className="graph-page-select-row">
            <select
              value={repoKey}
              onChange={(e) => { setRepoKey(e.target.value); loadGraph(e.target.value); }}
              className="repo-select"
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
                {repoKey.startsWith('org:') && (
                  <Link to={`/organization/${repoKey.replace(/^org:/, '')}/learning-path`} className="btn btn-primary btn-sm">
                    New to this Company
                  </Link>
                )}
                <button onClick={() => loadGraph(repoKey)} className="btn btn-secondary btn-sm">Refresh</button>
                <button onClick={() => loadJson(repoKey)} className="btn btn-ghost btn-sm">JSON</button>
              </>
            )}
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {loading && !graphData && <div className="loading">Loading graph...</div>}
      </div>

      {graphData && (
        <>
          {/* ── STATS ROW ── */}
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

          {/* ── GRAPH + CHATBOT (side by side) ── */}
          <div className="main-layout">
            {/* Left: Graph */}
            <div className="graph-section">
              <div ref={containerRef} className="graph-container" />
            </div>

            {/* Right: Chatbot */}
            <div className="chatbot-section">
              <div className="card" style={{ background: '#111', color: '#f0f0f0', border: '1px solid #222' }}>
                <h2 className="card-title" style={{ color: '#fff' }}>Ask anything</h2>

                {/* Example question chips */}
                <div className="chat-examples">
                  <span className="chat-examples-label" style={{ color: '#aaa' }}>Example questions:</span>
                  <div className="chat-examples-list">
                    {EXAMPLE_QUESTIONS.map((q, i) => (
                      <button
                        key={i}
                        type="button"
                        className="chat-example-chip"
                        style={{ background: '#1e1e1e', color: '#ccc', border: '1px solid #333' }}
                        onClick={() => handleChatSubmit(q)}
                        disabled={loading}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Messages */}
                <div className="chat-messages">
                  {chatMessages.length === 0 ? (
                    <div className="chat-welcome" style={{ color: '#aaa', background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '1.5rem' }}>
                      <p>Ask me anything about the codebase! You can:</p>
                      <ul>
                        <li>Ask questions about the code</li>
                        <li>Request "what if" scenarios</li>
                        <li>Get explanations about components</li>
                      </ul>
                    </div>
                  ) : (
                    chatMessages.map((msg) =>
                      msg.role === 'user' ? (
                        <div key={msg.id} className="chat-bubble user">{msg.text}</div>
                      ) : (
                        <div key={msg.id} className={`chat-bubble assistant ${msg.type === 'error' ? 'chat-bubble-error' : ''}`}>
                          {msg.type === 'whatif' && msg.data?.risk_level && (
                            <span className={`risk-badge risk-${msg.data.risk_level}`}>{msg.data.risk_level}</span>
                          )}
                          <div className="answer-content">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code: ({ node, inline, className, children, ...props }) =>
                                  (!inline && /language-(\w+)/.exec(className || ''))
                                    ? <pre className="answer-code-block"><code className={className} {...props}>{children}</code></pre>
                                    : <code className="answer-inline-code" {...props}>{children}</code>,
                                p: ({ node, ...props }) => <p style={{ marginBottom: '0.5rem', lineHeight: '1.5' }} {...props} />,
                                ul: ({ node, ...props }) => <ul style={{ marginLeft: '1rem', marginBottom: '0.5rem' }} {...props} />,
                                li: ({ node, ...props }) => <li style={{ marginBottom: '0.25rem' }} {...props} />,
                                strong: ({ node, ...props }) => <strong {...props} />,
                              }}
                            >
                              {msg.text}
                            </ReactMarkdown>
                            {msg.type === 'answer' && msg.data?.relevant_elements?.length > 0 && (
                              <div className="relevant-elements">
                                <strong>Relevant:</strong> {msg.data.relevant_elements.slice(0, 5).join(', ')}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    )
                  )}
                </div>

                {/* Input row */}
                <div className="chat-input-row">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask anything..."
                    onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleChatSubmit()}
                    className="chat-input"
                    style={{ background: '#1e1e1e', color: '#f0f0f0', border: '1px solid #333' }}
                    disabled={loading}
                  />
                  <button onClick={() => handleChatSubmit()} className="btn btn-primary" disabled={loading}>
                    {loading ? '...' : 'Ask'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* ── BOTTOM SECTION: Database Schema + Doc Diff + Subgraph ── */}
          <div className="bottom-section">

            {/* Documentation vs Code */}
            <div ref={docDiffRef} className="card" style={{ marginTop: '2rem' }}>
              <h2 className="card-title">Documentation vs Code</h2>
              <p className="query-desc">{docContent ? 'Comparing your Notion page with the codebase.' : 'Paste docs to compare and get suggested edits.'}</p>
              <textarea
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
                placeholder="Paste architecture docs or runbooks..."
                rows={3}
                className="doc-textarea"
              />
              <button onClick={handleDocDiff} className="btn btn-primary btn-sm" disabled={loadingDocDiff || !docContent.trim()}>
                {loadingDocDiff ? 'Analyzing...' : 'Compare'}
              </button>
              {notionPageId && notionPageUrl && (
                <p className="notion-where-hint">
                  When you click &quot;Keep & update Notion&quot;, the suggestion is <strong>added as a new paragraph at the bottom</strong> of this page.{' '}
                  <a href={notionPageUrl} target="_blank" rel="noopener noreferrer">Open page in Notion →</a>
                </p>
              )}
              {docDiffResult && (
                <div className="answer-box doc-diff-result">
                  <h3>{docDiffResult.has_differences ? 'Suggested edits' : 'Aligned'}</h3>
                  <div className="answer-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{docDiffResult.suggestions || 'No differences.'}</ReactMarkdown>
                  </div>
                  {docDiffResult.structured && docDiffResult.structured.length > 0 && (
                    <div className="suggestions-list">
                      {docDiffResult.structured.filter((s) => !rejectedSuggestions.has(s.id)).map((s) => (
                        <div key={s.id} className={`suggestion-card ${appliedSuggestions.has(s.id) ? 'applied' : ''}`}>
                          <div className="suggestion-desc">{s.description}</div>
                          {s.suggested && <div className="suggestion-text">{s.suggested}</div>}
                          {!appliedSuggestions.has(s.id) && (
                            <div className="suggestion-actions">
                              {notionPageId && (
                                <button className="btn btn-primary btn-sm" onClick={() => handleKeepSuggestion(s)} disabled={applyingSuggestion === s.id}>
                                  {applyingSuggestion === s.id ? 'Updating...' : 'Keep & add to Notion'}
                                </button>
                              )}
                              <button className="btn btn-ghost btn-sm" onClick={() => handleRejectSuggestion(s)}>Reject</button>
                            </div>
                          )}
                          {appliedSuggestions.has(s.id) && <span className="suggestion-applied">✓ Added to bottom of Notion page</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Subgraph Analysis */}
            <div className="card" style={{ marginTop: '2rem' }}>
              <h2 className="card-title">Subgraph Analysis</h2>
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
                    <div style={{ background: '#f8f9fa', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', whiteSpace: 'pre-line' }}>
                      {subgraphContext.impact_summary}
                    </div>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                    {subgraphContext.direct_dependents?.length > 0 && (
                      <div>
                        <strong>Direct Dependents ({subgraphContext.direct_dependents.length}):</strong>
                        <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                          {subgraphContext.direct_dependents.slice(0, 10).map((dep, idx) => <li key={idx}>{dep}</li>)}
                        </ul>
                      </div>
                    )}
                    {subgraphContext.affected_apis?.length > 0 && (
                      <div>
                        <strong>Affected APIs ({subgraphContext.affected_apis.length}):</strong>
                        <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                          {subgraphContext.affected_apis.slice(0, 10).map((a, idx) => <li key={idx}>{a}</li>)}
                        </ul>
                      </div>
                    )}
                    {subgraphContext.database_tables?.length > 0 && (
                      <div>
                        <strong>Database Tables ({subgraphContext.database_tables.length}):</strong>
                        <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                          {subgraphContext.database_tables.slice(0, 10).map((t, idx) => <li key={idx}>{t}</li>)}
                        </ul>
                      </div>
                    )}
                    {subgraphContext.agents_involved?.length > 0 && (
                      <div>
                        <strong>Agents Involved ({subgraphContext.agents_involved.length}):</strong>
                        <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                          {subgraphContext.agents_involved.slice(0, 10).map((a, idx) => <li key={idx}>{a}</li>)}
                        </ul>
                      </div>
                    )}
                    {subgraphContext.workflows_involved?.length > 0 && (
                      <div>
                        <strong>Workflows Involved ({subgraphContext.workflows_involved.length}):</strong>
                        <ul style={{ fontSize: '0.9rem', maxHeight: '150px', overflowY: 'auto' }}>
                          {subgraphContext.workflows_involved.slice(0, 10).map((w, idx) => <li key={idx}>{w}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

          </div>
        </>
      )}

      {/* JSON Modal */}
      {showJson && jsonData && (
        <div className="modal-overlay" onClick={() => setShowJson(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Parsed JSON</h2>
              <button onClick={() => setShowJson(false)} className="btn btn-ghost btn-sm">Close</button>
            </div>
            <pre className="schema-pre" style={{ maxHeight: '70vh', fontSize: '12px' }}>{JSON.stringify(jsonData, null, 2)}</pre>
          </div>
        </div>
      )}

    </div>
  );
}

export default KnowledgeGraph;