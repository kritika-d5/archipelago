import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
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
  // eslint-disable-next-line no-unused-vars
  const [chatMessages, setChatMessages] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  // eslint-disable-next-line no-unused-vars
  const [chatHistory, setChatHistory] = useState([]);
  // eslint-disable-next-line no-unused-vars
  const [showJson, setShowJson] = useState(false);

  // eslint-disable-next-line no-unused-vars
  const EXAMPLE_QUESTIONS = [
    'How does authentication work in this codebase?',
    'What if I change the UserService API to accept JSON?',
    'Where are the main API endpoints defined?',
    'What would happen if I remove this database dependency?',
    'Explain the flow from login to checkout.',
    'What\'s the impact of renaming this function?',
  ];
  // eslint-disable-next-line no-unused-vars
  const [jsonData, setJsonData] = useState(null);
  const [subgraphElement, setSubgraphElement] = useState('');
  // eslint-disable-next-line no-unused-vars
  const [subgraphContext, setSubgraphContext] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [projectExplanation, setProjectExplanation] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [docDiffResult, setDocDiffResult] = useState(null);
  const [loadingDocDiff, setLoadingDocDiff] = useState(false);
  const [notionPageId, setNotionPageId] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [appliedSuggestions, setAppliedSuggestions] = useState(new Set());
  // eslint-disable-next-line no-unused-vars
  const [rejectedSuggestions, setRejectedSuggestions] = useState(new Set());
  // eslint-disable-next-line no-unused-vars
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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

  useEffect(() => {
    if (docContent && docDiffRef.current && docDiffResult) {
      docDiffRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [docContent, docDiffResult]);

  const hasAutoRunDocDiff = useRef(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
            'width': 100,
            'height': 60,
            'font-size': '14px',
            'text-max-width': '150px',
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
            'width': 90,
            'height': 55,
            'font-size': '14px',
            'text-max-width': '150px',
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
        },
        {
          selector: 'edge[type="REST"]',
          style: {
            'line-color': '#3498db',
            'target-arrow-color': '#3498db',
            'width': 2.5,
            'line-style': 'solid',
          }
        },
        {
          selector: 'edge[type="EVENT"]',
          style: {
            'line-color': '#16a085',
            'target-arrow-color': '#16a085',
            'width': 2.5,
            'line-style': 'dashed',
          }
        },
        {
          selector: 'edge[type="IMPORT"]',
          style: {
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'width': 2,
            'line-style': 'dotted',
          }
        },
        {
          selector: 'edge[type="DB_ACCESS"]',
          style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            'width': 3,
            'line-style': 'solid',
          }
        },
        {
          selector: 'edge[type="CIRCULAR"]',
          style: {
            'line-color': '#f39c12',
            'target-arrow-color': '#f39c12',
            'width': 3,
            'line-style': 'dashed',
          }
        },
        {
          selector: 'edge[violation="true"]',
          style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            'width': 3,
            'line-style': 'solid',
            'opacity': 1.0,
          }
        },
        {
          selector: 'edge[circular="true"]',
          style: {
            'line-color': '#f39c12',
            'target-arrow-color': '#f39c12',
            'width': 3,
            'line-style': 'dashed',
            'opacity': 1.0,
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

  const isWhatIfPrompt = (text) => /what if|what would happen|suppose|impact of|effect of|if i change|if we remove/i.test((text || '').trim());
  // eslint-disable-next-line no-unused-vars
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
      setChatMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', text: 'Sorry, I couldn’t process that. Try rephrasing or check the repo is loaded.', type: 'error' }]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line no-unused-vars
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

  const handleSendMessage = async () => {
    if (!repoKey || !inputMessage.trim()) return;

    const userMessage = { role: 'user', content: inputMessage };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputMessage('');
    setLoading(true);

    try {
      // Determine if it's a what-if scenario or regular query
      const isWhatIf = inputMessage.toLowerCase().includes('what if') || inputMessage.toLowerCase().includes('scenario');
      
      let response;
      if (isWhatIf) {
        response = await api.post(`/api/query/what-if?repo_key=${encodeURIComponent(repoKey)}`, {
          scenario: inputMessage,
          include_impact_chain: true,
          max_depth: 5
        });
        
        const botMessage = {
          role: 'assistant',
          content: response.data.analysis,
          type: 'what-if',
          data: response.data
        };
        setMessages([...newMessages, botMessage]);
      } else {
        response = await api.post(`/api/query/ask?repo_key=${encodeURIComponent(repoKey)}`, {
          query: inputMessage,
          include_code: true,
          max_context_elements: 10
        });
        
        const botMessage = {
          role: 'assistant',
          content: response.data.answer,
          type: 'qa',
          data: response.data
        };
        setMessages([...newMessages, botMessage]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process message');
      const errorMessage = {
        role: 'assistant',
        content: `Error: ${err.response?.data?.detail || err.message || 'Failed to process message'}`,
        type: 'error'
      };
      setMessages([...newMessages, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line no-unused-vars
  const handleKeepSuggestion = async (suggestion) => {
    if (!notionPageId) {
      setError('Notion page ID not found. Please connect Notion first.');
      return;
    }
    setApplyingSuggestion(suggestion.id);
    setError(null);
    try {
      // Send the full suggestion object so backend can insert/update in the right location
      const response = await api.post('/api/integrations/notion/update', {
        page_id: notionPageId,
        content: suggestion.suggested || suggestion.description, // Fallback for compatibility
        suggestion_type: suggestion.type || 'add',
        current_text: suggestion.current || '',
        suggested_text: suggestion.suggested || suggestion.description
      });
      setAppliedSuggestions((prev) => new Set([...prev, suggestion.id]));
      // Show success message
      if (response.data?.notion_page_url) {
        console.log('Suggestion applied to Notion:', response.data.notion_page_url);
        console.log('Message:', response.data?.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update Notion');
    } finally {
      setApplyingSuggestion(null);
    }
  };

  // eslint-disable-next-line no-unused-vars
  const handleRejectSuggestion = (suggestion) => {
    setRejectedSuggestions((prev) => new Set([...prev, suggestion.id]));
  };

  // eslint-disable-next-line no-unused-vars
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

  // eslint-disable-next-line no-unused-vars
  const notionPageUrl = notionPageId ? `https://www.notion.so/${notionPageId.replace(/-/g, '')}` : null;

  return (
    <div className="graph-page">
      <div className="graph-page-header">
        <h1 className="graph-page-title">Knowledge Graph</h1>
        <div className="graph-page-controls">
          <label className="graph-page-label">Repository</label>
          <div className="graph-page-select-row">
            <select
              value={repoKey}
              onChange={(e) => {
                setRepoKey(e.target.value);
                loadGraph(e.target.value);
              }}
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
                <button onClick={() => loadGraph(repoKey)} className="btn btn-secondary btn-sm">Refresh</button>
                <button onClick={() => loadJson(repoKey)} className="btn btn-ghost btn-sm">JSON</button>
              </>
            )}
          </div>
        </div>
      </div>

      <>
        {error && <div className="error">{error}</div>}

        {loading && !graphData && <div className="loading">Loading graph...</div>}

        {graphData && (
          <div className="main-layout">
          {/* Left side - Graph */}
          <div className="graph-section">
            <div ref={containerRef} className="graph-container" />
          </div>

          {/* Right side - Chatbot */}
          <div className="chatbot-section">
            <div className="card">
              <h2 className="card-title">Chat Assistant</h2>
              <div className="chat-messages">
                    {messages.length === 0 ? (
                      <div className="chat-welcome">
                        <p>Ask me anything about the codebase! You can:</p>
                        <ul>
                          <li>Ask questions about the code</li>
                          <li>Request "what if" scenarios</li>
                          <li>Get explanations about components</li>
                        </ul>
                      </div>
                    ) : (
                      messages.map((message, idx) => (
                        <div key={idx} className={`chat-message ${message.role}`}>
                          <div className="message-content">
                            {message.type === 'what-if' && message.data && (
                              <div className="what-if-header">
                                <span className={`risk-badge risk-${message.data.risk_level}`}>
                                  {message.data.risk_level?.toUpperCase() || 'UNKNOWN'} RISK
                                </span>
                              </div>
                            )}
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
                              {message.content}
                            </ReactMarkdown>
                            {message.type === 'qa' && message.data?.relevant_elements && message.data.relevant_elements.length > 0 && (
                              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #ddd' }}>
                                <strong>Relevant Elements:</strong>
                                <ul style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                                  {message.data.relevant_elements.slice(0, 5).map((elem, idx) => (
                                    <li key={idx}>{elem}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {message.type === 'what-if' && message.data && (
                              <>
                                {message.data.recommendations && message.data.recommendations.length > 0 && (
                                  <div className="recommendations">
                                    <h4>Recommendations:</h4>
                                    <ul>
                                      {message.data.recommendations.map((rec, idx) => (
                                        <li key={idx}>{rec}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {message.data.impact_chain && message.data.impact_chain.length > 0 && (
                                  <div style={{ marginTop: '1rem' }}>
                                    <strong>Impact Chain ({message.data.impact_chain.length} impacts):</strong>
                                    <ul style={{ fontSize: '0.9rem' }}>
                                      {message.data.impact_chain.slice(0, 10).map((impact, idx) => (
                                        <li key={idx}>
                                          {impact.source} → {impact.target} (depth: {impact.depth})
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="chat-input">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="ASK ANYTHING"
                      onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                      disabled={loading}
                    />
                    <button onClick={handleSendMessage} className="btn btn-primary" disabled={loading}>
                      {loading ? 'Sending...' : 'Send'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
        )}

        {/* Doc Diff Suggestions Section */}
        {docContent && (
          <div className="card" style={{ marginTop: '2rem' }} ref={docDiffRef}>
            <h2 className="card-title">Documentation Suggestions</h2>
            
            {loadingDocDiff && (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                Comparing documentation with codebase...
              </div>
            )}

            {docDiffResult && !loadingDocDiff && (
              <>
                {docDiffResult.suggestions && (
                  <div style={{ 
                    background: '#f8f9fa', 
                    padding: '1.5rem', 
                    borderRadius: '8px',
                    marginBottom: '1.5rem',
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.6'
                  }}>
                    <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Analysis</h3>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {docDiffResult.suggestions}
                    </ReactMarkdown>
                  </div>
                )}

                {docDiffResult.structured && docDiffResult.structured.length > 0 && (
                  <div>
                    <h3 style={{ marginBottom: '1rem' }}>Actionable Suggestions</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {docDiffResult.structured.map((suggestion) => {
                        const isApplied = appliedSuggestions.has(suggestion.id);
                        const isRejected = rejectedSuggestions.has(suggestion.id);
                        const isApplying = applyingSuggestion === suggestion.id;

                        if (isRejected) return null;

                        return (
                          <div 
                            key={suggestion.id}
                            style={{
                              border: '1px solid #e0e0e0',
                              borderRadius: '8px',
                              padding: '1rem',
                              background: isApplied ? '#f0f9ff' : '#fff'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ 
                                  display: 'inline-block',
                                  padding: '0.25rem 0.75rem',
                                  borderRadius: '4px',
                                  fontSize: '0.75rem',
                                  fontWeight: 'bold',
                                  marginBottom: '0.5rem',
                                  background: suggestion.type === 'add' ? '#d1fae5' : suggestion.type === 'update' ? '#dbeafe' : '#fee2e2',
                                  color: suggestion.type === 'add' ? '#065f46' : suggestion.type === 'update' ? '#1e40af' : '#991b1b'
                                }}>
                                  {suggestion.type?.toUpperCase() || 'FIX'}
                                </div>
                                <p style={{ margin: '0.5rem 0', fontWeight: '500' }}>
                                  {suggestion.description}
                                </p>
                              </div>
                            </div>

                            {suggestion.current && (
                              <div style={{ 
                                background: '#fee2e2',
                                padding: '0.75rem',
                                borderRadius: '4px',
                                marginBottom: '0.5rem',
                                fontSize: '0.9rem'
                              }}>
                                <strong>Current:</strong>
                                <div style={{ marginTop: '0.25rem', color: '#991b1b' }}>
                                  {suggestion.current}
                                </div>
                              </div>
                            )}

                            {suggestion.suggested && (
                              <div style={{ 
                                background: '#d1fae5',
                                padding: '0.75rem',
                                borderRadius: '4px',
                                marginBottom: '0.5rem',
                                fontSize: '0.9rem'
                              }}>
                                <strong>Suggested:</strong>
                                <div style={{ marginTop: '0.25rem', color: '#065f46' }}>
                                  {suggestion.suggested}
                                </div>
                              </div>
                            )}

                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                              {notionPageId && !isApplied && (
                                <button
                                  className="btn btn-primary btn-sm"
                                  onClick={() => handleKeepSuggestion(suggestion)}
                                  disabled={isApplying}
                                  style={{ fontSize: '0.875rem' }}
                                >
                                  {isApplying ? 'Updating...' : 'Keep & add to Notion'}
                                </button>
                              )}
                              {!notionPageId && (
                                <span style={{ 
                                  fontSize: '0.875rem', 
                                  color: '#666',
                                  fontStyle: 'italic'
                                }}>
                                  Connect Notion to add suggestions
                                </span>
                              )}
                              {isApplied && (
                                <span style={{ 
                                  fontSize: '0.875rem', 
                                  color: '#059669',
                                  fontWeight: '500'
                                }}>
                                  ✓ Added to Notion
                                </span>
                              )}
                              {!isApplied && (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleRejectSuggestion(suggestion)}
                                  style={{ fontSize: '0.875rem' }}
                                >
                                  Dismiss
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {(!docDiffResult.structured || docDiffResult.structured.length === 0) && (
                  <div style={{ 
                    padding: '2rem', 
                    textAlign: 'center', 
                    color: '#666',
                    background: '#f8f9fa',
                    borderRadius: '8px'
                  }}>
                    <p>No specific suggestions found. Documentation appears to be in sync with the codebase.</p>
                  </div>
                )}
              </>
            )}

            {!docDiffResult && !loadingDocDiff && docContent && (
              <div style={{ padding: '1rem' }}>
                <button 
                  onClick={handleDocDiff} 
                  className="btn btn-primary"
                  disabled={!repoKey}
                >
                  Compare Documentation
                </button>
              </div>
            )}
          </div>
        )}
      </>
    </div>
  );
}

export default KnowledgeGraph;