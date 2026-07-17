import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link, useLocation } from 'react-router-dom';
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
  const location = useLocation();
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
  // Notion doc-diff: when arriving from the "Add documentation from Notion" flow we carry the
  // page content + id so suggestions can be pushed back to the real Notion page via "Apply".
  const [notionPageId, setNotionPageId] = useState(null);
  const [notionTitle, setNotionTitle] = useState(null);
  const [appliedSuggestions, setAppliedSuggestions] = useState(new Set());
  const [rejectedSuggestions, setRejectedSuggestions] = useState(new Set());
  const [applyingSuggestion, setApplyingSuggestion] = useState(null);
  const autoRanDocDiff = useRef(false);

  const [viewMode, setViewMode] = useState('modules'); // 'modules' | 'architecture' | 'files'
  const [minDegree, setMinDegree] = useState(0);       // committed density threshold (refetches)
  const [minDegreeDraft, setMinDegreeDraft] = useState(0); // live slider value while dragging
  const [selectedNode, setSelectedNode] = useState(null);
  const [sideTab, setSideTab] = useState('ask'); // right panel: 'ask' | 'docs'

  const cyRef = useRef(null);
  const containerRef = useRef(null);
  const workspaceRef = useRef(null);

  useEffect(() => {
    api.get('/api/parse/')
      .then((response) => setParsedGraphs(response.data.graphs || []))
      .catch((err) => console.error(err));
  }, []);

  // Consume Notion doc content handed over by the "Add documentation from Notion" flow.
  useEffect(() => {
    const st = location.state || {};
    if (st.notionContent) {
      setDocContent(st.notionContent);
      setNotionPageId(st.notionPageId || null);
      setNotionTitle(st.notionTitle || null);
      setSideTab('docs'); // surface the doc panel when arriving from the Notion flow
      autoRanDocDiff.current = false; // allow one auto-compare for this incoming doc
    }
  }, [location.state]);

  // Auto-run the comparison once when we arrive with a Notion doc and a selected repo.
  useEffect(() => {
    if (autoRanDocDiff.current) return;
    if (!activeKey || !docContent || loadingDocDiff) return;
    if (!location.state?.notionContent) return;
    autoRanDocDiff.current = true;
    (async () => {
      setLoadingDocDiff(true);
      setDocDiffResult(null);
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
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, docContent]);

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

  // Size the workspace to fill the rest of the screen (viewport minus everything above it),
  // so the graph + side panel fit the page without scrolling. Recomputed on resize and
  // whenever the content above it changes height. Cytoscape is resized to match.
  useEffect(() => {
    const fit = () => {
      const el = workspaceRef.current;
      if (!el) return;
      if (window.innerWidth < 1024) {
        el.style.height = ''; // stacked layout: let CSS heights apply
      } else {
        const top = el.getBoundingClientRect().top;
        el.style.height = `${Math.max(360, Math.round(window.innerHeight - top - 24))}px`;
      }
      if (cyRef.current) cyRef.current.resize();
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [activeKey, graphData]);

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
      autoRanDocDiff.current = true; // manual run also counts, don't auto-run again
    } catch (err) {
      setError(err.response?.data?.detail || 'Doc diff failed');
    } finally {
      setLoadingDocDiff(false);
    }
  };

  // Push a single suggestion back to the connected Notion page.
  const handleApplySuggestion = async (s) => {
    if (!notionPageId) {
      setError('No Notion page connected. Select a doc from the "Add documentation from Notion" flow first.');
      return;
    }
    setApplyingSuggestion(s.id);
    setError(null);
    try {
      await api.post('/api/integrations/notion/update', {
        page_id: notionPageId,
        content: s.suggested || s.description,
        suggestion_type: s.type || 'add',
        current_text: s.current || '',
        suggested_text: s.suggested || s.description,
      });
      setAppliedSuggestions((prev) => new Set([...prev, s.id]));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to update Notion');
    } finally {
      setApplyingSuggestion(null);
    }
  };

  const handleRejectSuggestion = (s) => {
    setRejectedSuggestions((prev) => new Set([...prev, s.id]));
  };

  const structuredSuggestions = (docDiffResult?.structured || []).filter(
    (s) => !rejectedSuggestions.has(s.id)
  );
  const notionPageUrl = notionPageId
    ? `https://www.notion.so/${notionPageId.replace(/-/g, '')}`
    : null;

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
        <div className="graph-workspace" ref={workspaceRef}>
          <div className="graph-workspace-main">
            <div className="graph-toolbar" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
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
            <div className="graph-canvas-wrap">
              <div
                ref={containerRef}
                className="graph-container"
                style={{ background: '#0d0d0d', borderRadius: 10, border: '1px solid #262626' }}
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
          </div>

          <div className="graph-side">
            <div className="graph-side-tabs">
              <button
                type="button"
                className={`graph-side-tab${sideTab === 'ask' ? ' active' : ''}`}
                onClick={() => setSideTab('ask')}
              >
                Ask the graph
              </button>
              <button
                type="button"
                className={`graph-side-tab${sideTab === 'docs' ? ' active' : ''}`}
                onClick={() => setSideTab('docs')}
              >
                Documentation
              </button>
            </div>
            <div className="graph-side-body">
              {sideTab === 'ask' && (
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
              )}
              {sideTab === 'docs' && (
                <div className={`mb-doc-panel${loadingDocDiff ? ' mb-doc-panel--busy' : ''}`}>
            <div className="mb-doc-panel-head">
              <h2 className="mb-panel-title">Documentation check</h2>
              <p className="mb-panel-lede">
                Paste docs and compare with the graph. Results stay in the panel below—scroll inside the box.
              </p>
              {notionPageId && (
                <div className="mb-notion-banner">
                  <span className="mb-notion-dot" aria-hidden>◆</span>
                  <span>
                    Connected to Notion{notionTitle ? `: ${notionTitle}` : ''}. Applied edits go
                    straight to the page.{' '}
                    {notionPageUrl && (
                      <a href={notionPageUrl} target="_blank" rel="noreferrer">Open in Notion ↗</a>
                    )}
                  </span>
                </div>
              )}
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
                  {structuredSuggestions.length > 0 && (
                    <div className="doc-suggestion-list">
                      {structuredSuggestions.map((s) => {
                        const isApplied = appliedSuggestions.has(s.id);
                        const isApplying = applyingSuggestion === s.id;
                        const type = (s.type || 'fix').toLowerCase();
                        return (
                          <div key={s.id} className={`doc-suggestion doc-suggestion--${type}${isApplied ? ' is-applied' : ''}`}>
                            <div className="doc-suggestion-head">
                              <span className={`doc-suggestion-badge doc-suggestion-badge--${type}`}>
                                {(s.type || 'fix').toUpperCase()}
                              </span>
                              <p className="doc-suggestion-desc">{s.description}</p>
                            </div>
                            {s.current && (
                              <div className="doc-suggestion-diff doc-suggestion-diff--current">
                                <span className="doc-suggestion-diff-label">Current</span>
                                <div>{s.current}</div>
                              </div>
                            )}
                            {s.suggested && (
                              <div className="doc-suggestion-diff doc-suggestion-diff--suggested">
                                <span className="doc-suggestion-diff-label">Suggested</span>
                                <div>{s.suggested}</div>
                              </div>
                            )}
                            <div className="doc-suggestion-actions">
                              {isApplied ? (
                                <span className="doc-suggestion-applied">✓ Added to Notion</span>
                              ) : (
                                <>
                                  <button
                                    type="button"
                                    className="btn btn-primary btn-sm"
                                    onClick={() => handleApplySuggestion(s)}
                                    disabled={!notionPageId || isApplying}
                                    title={notionPageId ? '' : 'Connect a Notion doc to apply'}
                                  >
                                    {isApplying ? 'Applying…' : 'Apply to Notion'}
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => handleRejectSuggestion(s)}
                                    disabled={isApplying}
                                  >
                                    Dismiss
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {docDiffResult.suggestions && (
                    <div className="doc-summary">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {docDiffResult.suggestions}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="dashboard-alert dashboard-alert--error" style={{ marginTop: '1.25rem' }} role="alert">
          {typeof error === 'string' ? error : 'Something went wrong'}
        </div>
      )}
    </div>
  );
}

export default KnowledgeGraph;
