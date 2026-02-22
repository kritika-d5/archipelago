import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import api from '../services/api';
import DashboardLayout from '../components/DashboardLayout';
import '../styles/ds-dashboard.css';

cytoscape.use(coseBilkent);

const COLORS = { REST: '#5b8def', EVENT: '#34d399', Event: '#34d399', IMPORT: '#8b92a0', Import: '#8b92a0' };

export default function ArchitectureDashboard() {
  const [searchParams] = useSearchParams();
  const repoParam = searchParams.get('repo');
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [selectedKey, setSelectedKey] = useState(repoParam || '');
  const [graphData, setGraphData] = useState(null);
  const [learningData, setLearningData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    api.get('/api/parse/').then((r) => setParsedGraphs(r.data.graphs || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (repoParam && !selectedKey) setSelectedKey(repoParam);
  }, [repoParam, selectedKey]);

  const loadData = useCallback(async () => {
    if (!selectedKey) {
      setGraphData(null);
      setLearningData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [vizRes, lpRes] = await Promise.all([
        api.get(`/api/graph/${encodeURIComponent(selectedKey)}/visualize?important_only=false`),
        selectedKey.startsWith('org:')
          ? api.get(`/api/org/${encodeURIComponent(selectedKey)}/learning-path`).catch(() => null)
          : Promise.resolve(null),
      ]);
      setGraphData(vizRes.data);
      setLearningData(lpRes?.data || null);
    } catch (e) {
      setGraphData(null);
      setLearningData(null);
    } finally {
      setLoading(false);
    }
  }, [selectedKey]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!graphData?.nodes?.length || !containerRef.current) return;
    const nodeEls = (graphData.nodes || []).map((n) => (n.data ? n : { data: { id: n.id, label: n.id, ...n } }));
    const edgeEls = (graphData.edges || []).map((e, i) => (e.data ? e : { data: { id: `e${i}`, source: e.source, target: e.target, ...e } }));
    const elements = [...nodeEls, ...edgeEls];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        { selector: 'node', style: { 'label': 'data(label)', 'background-color': '#5b8def', 'color': '#fff', 'font-size': '10px' } },
        { selector: 'edge', style: { 'width': 1.5, 'line-color': '#8b92a0', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier' } },
      ],
      layout: { name: 'cose-bilkent', animate: false },
    });
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [graphData]);

  const sendChat = async () => {
    if (!chatInput.trim() || !selectedKey) return;
    const msg = chatInput.trim();
    setChatInput('');
    setChatMessages((p) => [...p, { role: 'user', content: msg }]);
    setChatLoading(true);
    try {
      const res = await api.post(`/api/query/ask?repo_key=${encodeURIComponent(selectedKey)}`, {
        query: msg,
        include_code: false,
        max_context_elements: 10,
      });
      setChatMessages((p) => [...p, { role: 'assistant', content: res.data.answer }]);
    } catch (e) {
      setChatMessages((p) => [...p, { role: 'assistant', content: e.response?.data?.detail || 'Failed to get response.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSelectKey = (e) => {
    const v = e.target.value;
    setSelectedKey(v || '');
    if (v) {
      const url = new URL(window.location);
      url.searchParams.set('repo', v);
      window.history.replaceState({}, '', url);
    }
  };

  const metadata = graphData?.metadata || {};
  const nodes = graphData?.nodes || [];
  const edges = graphData?.edges || [];
  const stats = metadata.statistics || {};

  const pieData = [
    { name: 'REST', value: stats.rest_dependencies || 0 },
    { name: 'Event', value: stats.event_dependencies || 0 },
    { name: 'Import', value: stats.import_dependencies || 0 },
  ].filter((d) => d.value > 0);

  const barData = (nodes || []).slice(0, 12).map((n) => ({
    name: (n.data?.label || n.id || '').slice(0, 12),
    count: n.data?.degree ?? 0,
  }));

  const totalServices = metadata.total_nodes ?? nodes.length;
  const totalDeps = metadata.total_edges ?? edges.length;
  const violations = stats.violations ?? metadata.violations?.length ?? 0;
  const eventPct = totalDeps > 0 ? Math.round(((stats.event_dependencies || 0) / totalDeps) * 100) : 0;

  return (
    <DashboardLayout
      selectedKey={selectedKey}
      parsedGraphs={parsedGraphs}
      onSelectKey={handleSelectKey}
      showChat={!!selectedKey}
      chatMessages={chatMessages}
      chatInput={chatInput}
      onChatInputChange={setChatInput}
      onChatSend={sendChat}
      chatLoading={chatLoading}
    >
      <div className="ds-main-inner">
        <div className="ds-header-row" style={{ marginBottom: '1.5rem' }}>
          <select
            className="ds-sidebar-select"
            value={selectedKey}
            onChange={handleSelectKey}
            style={{ maxWidth: 320 }}
          >
            <option value="">Select organization or repository…</option>
            {(parsedGraphs || []).map((g) => (
              <option key={g.key} value={g.key}>{g.repository || g.key}</option>
            ))}
          </select>
        </div>

        {!selectedKey && (
          <div className="ds-bento-card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ color: 'var(--ds-text-muted)', marginBottom: '1rem' }}>
              Select an organization or repository to view the architecture dashboard.
            </p>
            <p style={{ fontSize: '0.875rem', color: 'var(--ds-text-muted)' }}>
              Parse a repo or org from the <a href="/dashboard" style={{ color: 'var(--ds-accent)' }}>Dashboard</a> first.
            </p>
          </div>
        )}

        {selectedKey && loading && (
          <div className="ds-bento-card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ color: 'var(--ds-text-muted)' }}>Loading…</p>
          </div>
        )}

        {selectedKey && !loading && graphData && (
          <>
            <div className="ds-metrics-row">
              <div className="ds-metric-card">
                <div className="ds-metric-label">Total Services</div>
                <div className="ds-metric-value">{totalServices}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Dependencies</div>
                <div className="ds-metric-value">{totalDeps}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Violations</div>
                <div className="ds-metric-value">{violations}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Event-Driven %</div>
                <div className="ds-metric-value">{eventPct}%</div>
              </div>
            </div>

            <div className="ds-bento ds-bento-2" style={{ marginBottom: '1.5rem' }}>
              <div className="ds-bento-card">
                <h3>Architecture composition</h3>
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={70}
                        paddingAngle={2}
                        dataKey="value"
                        label={({ name, value }) => `${name} ${value}`}
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={i} fill={COLORS[entry.name] || COLORS[entry.name.toUpperCase()] || '#8b92a0'} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ background: 'var(--ds-bg-elevated)', border: '1px solid var(--ds-border)' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem' }}>No dependency breakdown</p>
                )}
              </div>
              <div className="ds-bento-card">
                <h3>Service complexity</h3>
                {barData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={barData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                      <XAxis dataKey="name" tick={{ fill: 'var(--ds-text-muted)', fontSize: 10 }} />
                      <YAxis tick={{ fill: 'var(--ds-text-muted)', fontSize: 10 }} />
                      <Bar dataKey="count" fill="var(--ds-accent)" radius={[4, 4, 0, 0]} />
                      <Tooltip contentStyle={{ background: 'var(--ds-bg-elevated)', border: '1px solid var(--ds-border)' }} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem' }}>No service data</p>
                )}
              </div>
            </div>

            <div className="ds-bento-card" style={{ marginBottom: '1.5rem' }}>
              <h3>Dependency graph</h3>
              <div className="ds-graph-wrap" ref={containerRef} />
            </div>

            <div className="ds-bento ds-bento-4">
              <div className="ds-bento-card">
                <h3>Tech stack</h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {(metadata.db_languages || ['—']).slice(0, 5).map((l, i) => (
                    <span key={i} style={{ padding: '0.25rem 0.5rem', background: 'var(--ds-accent-muted)', borderRadius: 6, fontSize: '0.75rem' }}>{l}</span>
                  ))}
                </div>
              </div>
              <div className="ds-bento-card">
                <h3>Primary flow</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--ds-text-muted)' }}>
                  {learningData?.main_flow_highlight?.length
                    ? learningData.main_flow_highlight.join(' → ')
                    : '—'}
                </p>
              </div>
              <div className="ds-bento-card">
                <h3>Violations</h3>
                <p style={{ fontSize: '0.8rem', color: violations > 0 ? 'var(--error, #f87171)' : 'var(--ds-text-muted)' }}>
                  {violations} detected
                </p>
              </div>
              <div className="ds-bento-card">
                <h3>Suggested improvements</h3>
                <ul style={{ margin: 0, paddingLeft: '1rem', fontSize: '0.8rem', color: 'var(--ds-text-muted)' }}>
                  {violations > 0 && <li>Resolve architecture violations</li>}
                  <li>Review circular dependencies</li>
                  <li>Document API contracts</li>
                </ul>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
