import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';

cytoscape.use(coseBilkent);

function KnowledgeGraph() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeKey = searchParams.get('repo') || '';

  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [error, setError] = useState(null);

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);

  const [docContent, setDocContent] = useState('');
  const [docDiffResult, setDocDiffResult] = useState(null);
  const [loadingDocDiff, setLoadingDocDiff] = useState(false);

  const cyRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    api.get('/api/parse/')
      .then((response) => setParsedGraphs(response.data.graphs || []))
      .catch((err) => console.error(err));
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!activeKey) {
      setGraphData(null);
      setError(null);
      return () => { cancelled = true; };
    }
    (async () => {
      setGraphLoading(true);
      setError(null);
      try {
        const res = await api.get(`/api/graph/${encodeURIComponent(activeKey)}/visualize`);
        if (!cancelled) setGraphData(res.data);
      } catch (err) {
        if (!cancelled) {
          setGraphData(null);
          setError(err.response?.data?.detail || 'Failed to load graph');
        }
      } finally {
        if (!cancelled) setGraphLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [activeKey]);

  useEffect(() => {
    if (!graphData?.nodes?.length || !containerRef.current) {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
      return;
    }

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const nodeEls = (graphData.nodes || []).map((n) =>
      n.data ? n : { data: { id: n.id, label: n.id, ...n } }
    );
    const edgeEls = (graphData.edges || []).map((e, i) =>
      e.data ? e : { data: { id: `e${i}`, source: e.source, target: e.target, ...e } }
    );

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [...nodeEls, ...edgeEls],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': '#d97706',
            color: '#ffffff',
            'font-size': '11px',
            'font-weight': '600',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-outline-width': 2,
            'text-outline-color': '#1a0a00',
            'text-outline-opacity': 0.85,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': 'rgba(217, 119, 6, 0.45)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: { name: 'cose-bilkent', animate: false },
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData]);

  const handleChatSubmit = async () => {
    if (!activeKey || !chatInput.trim() || chatBusy) return;

    const q = chatInput.trim();
    const userMsg = { role: 'user', text: q };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');

    setChatBusy(true);
    try {
      const res = await api.post(
        `/api/query/ask?repo_key=${encodeURIComponent(activeKey)}`,
        { query: q }
      );

      setChatMessages((prev) => [...prev, { role: 'assistant', text: res.data.answer }]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Chat failed');
    } finally {
      setChatBusy(false);
    }
  };

  const handleDocDiff = async () => {
    if (!activeKey || !docContent.trim()) return;

    setLoadingDocDiff(true);

    try {
      const res = await api.post(
        `/api/query/doc-diff?repo_key=${encodeURIComponent(activeKey)}`,
        { documentation: docContent }
      );

      setDocDiffResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Doc diff failed');
    } finally {
      setLoadingDocDiff(false);
    }
  };

  const metadata = graphData?.metadata || {};
  const nodeCount = metadata.total_nodes ?? graphData?.nodes?.length ?? 0;
  const edgeCount = metadata.total_edges ?? graphData?.edges?.length ?? 0;
  const repoLabel = metadata.repository_name || activeKey || '—';

  return (
    <div className="graph-page">
      <header className="graph-page-header graph-page-header--brand">
        <h1 className="graph-page-title">Knowledge Graph</h1>
        <div className="graph-page-controls">
          {activeKey ? (
            <Link
              className="btn btn-secondary"
              to={`/hub?repo=${encodeURIComponent(activeKey)}`}
            >
              Open Architecture Hub
            </Link>
          ) : null}
        </div>
      </header>

      <div className="graph-page-select-row" style={{ marginBottom: '1rem' }}>
        <label className="graph-page-label" htmlFor="graph-repo-select">
          Repository / organization
        </label>
        <select
          id="graph-repo-select"
          className="graph-page-select"
          value={activeKey}
          onChange={(e) => {
            const v = e.target.value;
            if (v) setSearchParams({ repo: v }, { replace: true });
            else setSearchParams({}, { replace: true });
          }}
        >
          <option value="">Select repo</option>
          {parsedGraphs.map((g, i) => (
            <option key={g.key || i} value={g.key}>
              {g.repository || g.key}
            </option>
          ))}
        </select>
      </div>

      {activeKey && graphData && !graphLoading && (
        <div className="info-grid">
          <div className="info-card">
            <div className="info-card-label">Nodes</div>
            <div className="info-card-value">{nodeCount}</div>
          </div>
          <div className="info-card">
            <div className="info-card-label">Edges</div>
            <div className="info-card-value">{edgeCount}</div>
          </div>
          <div className="info-card">
            <div className="info-card-label">Repository</div>
            <div className="info-card-value" style={{ fontSize: '1rem', lineHeight: 1.3 }}>
              {repoLabel}
            </div>
          </div>
        </div>
      )}

      {graphLoading && activeKey && <p>Loading graph…</p>}
      {!activeKey && (
        <p style={{ color: 'var(--text-secondary)' }}>
          Choose a parsed repository above, or open a link with{' '}
          <code>?repo=your-key</code> (e.g. organization graphs use{' '}
          <code>org:YourOrg</code>).
        </p>
      )}

      <div
        ref={containerRef}
        className="graph-container"
        style={{ height: '480px', marginTop: '1rem' }}
      />

      <div className="graph-page-bento" style={{ marginTop: '2rem' }}>
        <div className="graph-page-left">
          <div className="mb-chat-panel">
            <h2 className="mb-panel-title">Ask the graph</h2>
            <p className="mb-panel-lede">
              Natural-language questions use the repository or organization you selected above.
            </p>
            <div className="mb-chat-scroll">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`mb-bubble ${msg.role}`}>
                  <span className="mb-bubble-role">{msg.role}</span>
                  <div className="answer-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
            <div className="mb-compose">
              <input
                className="mb-chat-input"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleChatSubmit();
                  }
                }}
                placeholder={activeKey ? 'Ask about this codebase…' : 'Select a repository first'}
                disabled={!activeKey}
                aria-label="Chat message"
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleChatSubmit}
                disabled={!activeKey || chatBusy}
              >
                {chatBusy ? '…' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        <div className="graph-page-right">
          <div
            className={`mb-doc-panel${loadingDocDiff ? ' mb-doc-panel--busy' : ''}`}
          >
            <div className="mb-doc-panel-head">
              <h2 className="mb-panel-title">Documentation check</h2>
              <p className="mb-panel-lede">
                Paste docs and compare with the graph. Results stay in the panel below—scroll inside the box.
              </p>
            </div>
            <div className="mb-doc-input-block">
              <textarea
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
                placeholder="Paste documentation markdown or notes…"
                disabled={!activeKey}
                aria-label="Documentation to compare"
              />
              <button
                type="button"
                className="btn btn-secondary mb-doc-submit"
                onClick={handleDocDiff}
                disabled={!activeKey || loadingDocDiff}
              >
                {loadingDocDiff ? 'Analyzing…' : 'Compare with graph'}
              </button>
            </div>
            {loadingDocDiff && (
              <div className="mb-doc-analyzing" aria-live="polite">
                <div className="mb-doc-analyzing-track">
                  <div className="mb-doc-analyzing-bar" />
                </div>
                <p className="mb-doc-analyzing-text">Matching documentation to the dependency graph…</p>
              </div>
            )}
            {docDiffResult && !loadingDocDiff && (
              <div className="mb-doc-output">
                <div className="mb-doc-output-header">
                  <span className="mb-doc-output-badge">Suggestions</span>
                  <span className="mb-doc-output-meta">Scroll inside this panel</span>
                </div>
                <div className="mb-doc-result answer-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {docDiffResult.suggestions}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="dashboard-alert dashboard-alert--error" style={{ marginTop: '1.25rem' }} role="alert">
          {typeof error === 'string' ? error : 'Something went wrong'}
        </div>
      )}
    </div>
  );
}

export default KnowledgeGraph;
