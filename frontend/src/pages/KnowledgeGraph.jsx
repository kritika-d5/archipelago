import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import dagre from 'cytoscape-dagre';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';

cytoscape.use(coseBilkent);
cytoscape.use(dagre);

// Views whose edges mean "depends on" read best as a left-to-right layered layout (dagre),
// so dependency direction is visible. The element-level files hairball stays on the force
// layout (cose-bilkent), which handles hundreds of loosely-hierarchical nodes better.
const DIRECTIONAL_VIEWS = ['modules', 'architecture', 'organization'];

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

  const [viewMode, setViewMode] = useState('modules'); // 'modules' | 'architecture' | 'files'
  const [minDegree, setMinDegree] = useState(0);       // committed density threshold (refetches)
  const [minDegreeDraft, setMinDegreeDraft] = useState(0); // live slider value while dragging
  const [selectedNode, setSelectedNode] = useState(null);

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
        const res = await api.get(`/api/graph/${encodeURIComponent(activeKey)}/visualize?view=${viewMode}&min_degree=${minDegree}`);
        if (!cancelled) { setGraphData(res.data); setSelectedNode(null); }
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
  }, [activeKey, viewMode, minDegree]);

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

    // Black / orange / white palette. Category hue for the file view; the architecture view is
    // all "module" so it leans on size (files) + edge width (dependencies) to read.
    const CATEGORY_COLORS = {
      module: '#d97706', class: '#f59e0b', function: '#fbbf24', method: '#fbbf24',
      agent: '#ea580c', workflow: '#fb923c', database_schema: '#e5e7eb',
      database_table: '#cbd5e1', api: '#fcd34d', service: '#f97316', default: '#d97706',
    };

    const rawNodes = (graphData.nodes || []).map((n) => (n.data ? n.data : n));
    const rawEdges = (graphData.edges || []).map((e) => (e.data ? e.data : e));

    const nodeEls = rawNodes.map((d) => {
      const cat = d.category || d.type || 'default';
      const files = Number(d.file_count) || 0;
      const elems = Number(d.element_count) || 0;
      const degree = Number(d.degree) || 0;
      const size = 24 + Math.min(66, files * 5 + elems * 0.4 + degree * 4);
      return { data: { ...d, _size: size, _color: CATEGORY_COLORS[cat] || CATEGORY_COLORS.default } };
    });
    const edgeEls = rawEdges.map((d, i) => {
      const w = Number(d.weight) || 1;
      return { data: { ...d, id: d.id || `e${i}`, _width: Math.min(9, 1.2 + Math.log2(w + 1) * 1.8) } };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodeEls, ...edgeEls],
      wheelSensitivity: 0.25,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': 'data(_color)',
            width: 'data(_size)',
            height: 'data(_size)',
            color: '#ffffff',
            'font-size': '11px',
            'font-weight': '600',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-wrap': 'wrap',
            'text-max-width': '130px',
            'text-outline-width': 2,
            'text-outline-color': '#0a0a0a',
            'text-outline-opacity': 0.9,
            'border-width': 0,
            'transition-property': 'opacity, border-width, background-color',
            'transition-duration': '0.15s',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'data(_width)',
            'line-color': 'rgba(217, 119, 6, 0.45)',
            'target-arrow-color': 'rgba(217, 119, 6, 0.7)',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.9,
            'curve-style': 'bezier',
            opacity: 0.75,
          },
        },
        { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#ffffff' } },
        { selector: '.faded', style: { opacity: 0.1 } },
        {
          selector: '.hl-edge',
          style: { 'line-color': '#f97316', 'target-arrow-color': '#f97316', opacity: 1 },
        },
      ],
      layout: DIRECTIONAL_VIEWS.includes(graphData.metadata?.graph_type)
        ? { name: 'dagre', rankDir: 'LR', nodeSep: 45, rankSep: 95, edgeSep: 12, animate: false, padding: 24 }
        : { name: 'cose-bilkent', animate: false, nodeRepulsion: 8000, idealEdgeLength: 90, padding: 24 },
    });
    cyRef.current = cy;

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.data());
      cy.elements().addClass('faded');
      const nb = node.closedNeighborhood();
      nb.removeClass('faded');
      node.connectedEdges().addClass('hl-edge');
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('faded hl-edge');
        setSelectedNode(null);
      }
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData]);

  const handleFit = () => cyRef.current && cyRef.current.fit(undefined, 30);

  // Dependencies (outgoing edges) of the selected node, for the detail panel.
  const selectedDeps = selectedNode
    ? (graphData?.edges || [])
        .map((e) => e.data || e)
        .filter((e) => e.source === selectedNode.id)
        .map((e) => e.target)
    : [];

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

      {activeKey && (
        <div className="graph-toolbar" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          <div className="graph-view-toggle" style={{ display: 'inline-flex', border: '1px solid #333', borderRadius: 8, overflow: 'hidden' }}>
            {[
              ['modules', 'Dependencies'],
              ['architecture', 'Architecture'],
              ['files', 'Files'],
            ].map(([m, label]) => (
              <button
                key={m}
                type="button"
                onClick={() => setViewMode(m)}
                style={{
                  padding: '0.4rem 0.9rem', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
                  border: 'none',
                  background: viewMode === m ? '#d97706' : 'transparent',
                  color: viewMode === m ? '#0a0a0a' : '#e5e7eb',
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-secondary" onClick={handleFit} style={{ padding: '0.4rem 0.9rem' }}>
            Fit
          </button>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: '#9ca3af' }}>
            Min connections: <strong style={{ color: '#e5e7eb' }}>{minDegreeDraft}</strong>
            <input
              type="range"
              min={0}
              max={6}
              step={1}
              value={minDegreeDraft}
              onChange={(e) => setMinDegreeDraft(Number(e.target.value))}
              onMouseUp={(e) => setMinDegree(Number(e.target.value))}
              onKeyUp={(e) => setMinDegree(Number(e.target.value))}
              style={{ accentColor: '#d97706' }}
              aria-label="Minimum connections to show a node"
            />
          </label>
          <span style={{ fontSize: '0.78rem', color: '#9ca3af' }}>
            Node size = {viewMode === 'architecture' ? 'files in module' : 'connections'} · Edge width = dependency weight · Drag the slider to hide low-connectivity nodes · Click a node to focus
          </span>
        </div>
      )}

      <div style={{ position: 'relative', marginTop: '0.75rem' }}>
        <div
          ref={containerRef}
          className="graph-container"
          style={{ height: '520px', background: '#0d0d0d', borderRadius: 10, border: '1px solid #262626' }}
        />

        {selectedNode && (
          <div
            className="graph-detail-panel"
            style={{
              position: 'absolute', top: 12, right: 12, width: 260, maxHeight: 'calc(100% - 24px)', overflowY: 'auto',
              background: 'rgba(20,20,20,0.96)', border: '1px solid #d97706', borderRadius: 10, padding: '0.9rem 1rem',
              color: '#e5e7eb', boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
              <strong style={{ color: '#fbbf24', wordBreak: 'break-word' }}>{selectedNode.label || selectedNode.id}</strong>
              <button type="button" onClick={() => { cyRef.current?.elements().removeClass('faded hl-edge'); setSelectedNode(null); }}
                style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '1.1rem', lineHeight: 1 }}>×</button>
            </div>
            <div style={{ fontSize: '0.8rem', marginTop: '0.6rem', display: 'grid', gap: 4 }}>
              {selectedNode.file_count != null && <div><span style={{ color: '#9ca3af' }}>Files:</span> {selectedNode.file_count}</div>}
              {selectedNode.element_count != null && <div><span style={{ color: '#9ca3af' }}>Elements:</span> {selectedNode.element_count}</div>}
              {selectedNode.type && <div><span style={{ color: '#9ca3af' }}>Type:</span> {selectedNode.type}</div>}
              {selectedNode.language && selectedNode.language !== 'unknown' && <div><span style={{ color: '#9ca3af' }}>Language:</span> {selectedNode.language}</div>}
              {selectedNode.file_path && <div style={{ wordBreak: 'break-all' }}><span style={{ color: '#9ca3af' }}>Path:</span> {selectedNode.file_path}</div>}
              <div><span style={{ color: '#9ca3af' }}>Depends on ({selectedDeps.length}):</span></div>
              {selectedDeps.length > 0 ? (
                <ul style={{ margin: '2px 0 0', paddingLeft: '1.1rem' }}>
                  {selectedDeps.slice(0, 12).map((t) => (
                    <li key={t} style={{ wordBreak: 'break-all' }}>{String(t).split('/').pop()}</li>
                  ))}
                </ul>
              ) : (
                <div style={{ color: '#6b7280' }}>No outgoing dependencies</div>
              )}
            </div>
          </div>
        )}
      </div>

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
