import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import api from '../services/api';
import DashboardLayout from '../components/DashboardLayout';
import '../styles/ds-dashboard.css';

const COLORS = {
  REST: '#d97706',
  EVENT: '#f59e0b',
  Event: '#f59e0b',
  IMPORT: '#78716c',
  Import: '#78716c',
};

export default function ArchitectureDashboard() {
  const [searchParams] = useSearchParams();
  const repoParam = searchParams.get('repo');
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [selectedKey, setSelectedKey] = useState(repoParam || '');
  const [graphData, setGraphData] = useState(null);
  const [learningData, setLearningData] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

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
      setInsights(null);
      setLoading(false);
      return;
    }
    const isOrgKey = selectedKey.startsWith('org:');
    setLoading(true);
    try {
      const [vizRes, lpRes, insRes] = await Promise.all([
        api.get(`/api/graph/${encodeURIComponent(selectedKey)}/visualize?important_only=false`),
        isOrgKey
          ? api.get(`/api/org/${encodeURIComponent(selectedKey)}/learning-path`).catch(() => null)
          : Promise.resolve(null),
        isOrgKey
          ? Promise.resolve(null)
          : api.get(`/api/graph/${encodeURIComponent(selectedKey)}/insights`).catch(() => null),
      ]);
      setGraphData(vizRes.data);
      setLearningData(lpRes?.data || null);
      setInsights(insRes?.data || null);
    } catch (e) {
      setGraphData(null);
      setLearningData(null);
      setInsights(null);
    } finally {
      setLoading(false);
    }
  }, [selectedKey]);

  useEffect(() => { loadData(); }, [loadData]);

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

  // Single-repo insights (org graphs keep the REST/event stat view above)
  const isOrg = selectedKey.startsWith('org:');
  const im = insights?.metrics || {};
  const TYPE_LABELS = {
    function: 'Functions', method: 'Methods', class: 'Classes', module: 'Modules',
    agent: 'AI agents', workflow: 'Workflows', database_table: 'DB models',
    api_endpoint: 'API endpoints', interface: 'Interfaces', enum: 'Enums',
  };
  const PIE_COLORS = ['#d97706', '#f59e0b', '#fbbf24', '#ea580c', '#fb923c', '#a16207', '#fcd34d', '#78716c'];
  const elementPie = (insights?.element_breakdown || [])
    .filter((d) => d.value > 0)
    .map((d) => ({ name: TYPE_LABELS[d.name] || d.name, value: d.value }));
  const hubsBar = (insights?.top_modules || []).slice(0, 10).map((m) => ({
    name: (m.name || '').slice(0, 12),
    degree: m.degree,
  }));
  const coreModules = insights?.core_modules || [];
  const maxDependents = Math.max(1, ...coreModules.map((m) => m.dependents || 0));
  const circular = insights?.circular_dependencies || [];

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

        {selectedKey && !loading && graphData && isOrg && (
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
                <div
                  className="ds-metric-value"
                  style={violations > 0 ? { color: 'var(--ds-accent)' } : undefined}
                >
                  {violations}
                </div>
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
                          <Cell key={i} fill={COLORS[entry.name] || COLORS[entry.name.toUpperCase()] || '#a16207'} />
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

            <div
              className="ds-bento-card"
              style={{
                marginBottom: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
                flexWrap: 'wrap',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <h3 style={{ margin: 0 }}>Dependency graph</h3>
                <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.85rem', margin: '0.35rem 0 0', lineHeight: 1.5 }}>
                  {totalServices} nodes · {totalDeps} dependencies. Explore interactive dependency,
                  architecture, and file views — with connectivity filtering and node search — in the
                  full Graph explorer.
                </p>
              </div>
              <Link
                to={`/graph?repo=${encodeURIComponent(selectedKey)}`}
                className="btn btn-primary"
                style={{ whiteSpace: 'nowrap' }}
              >
                Open Graph explorer →
              </Link>
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

        {selectedKey && !loading && graphData && !isOrg && insights && (
          <>
            <div className="ds-metrics-row">
              <div className="ds-metric-card">
                <div className="ds-metric-label">Files</div>
                <div className="ds-metric-value">{im.files ?? 0}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Code elements</div>
                <div className="ds-metric-value">{im.elements ?? 0}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Internal deps</div>
                <div className="ds-metric-value">{im.internal_imports ?? 0}</div>
              </div>
              <div className="ds-metric-card">
                <div className="ds-metric-label">Circular imports</div>
                <div className="ds-metric-value" style={(im.circular_deps || 0) > 0 ? { color: '#f87171' } : undefined}>
                  {im.circular_deps ?? 0}
                </div>
              </div>
            </div>

            <div className="ds-chip-row">
              {im.classes > 0 && <span className="ds-chip">{im.classes} classes</span>}
              {im.functions > 0 && <span className="ds-chip">{im.functions} functions</span>}
              {im.agents > 0 && <span className="ds-chip ds-chip--accent">{im.agents} AI agents</span>}
              {im.db_tables > 0 && <span className="ds-chip">{im.db_tables} DB models</span>}
              {im.workflows > 0 && <span className="ds-chip">{im.workflows} workflows</span>}
              {im.languages > 0 && <span className="ds-chip">{im.languages} language{im.languages > 1 ? 's' : ''}</span>}
              {im.max_fan_out > 0 && <span className="ds-chip">max fan-out {im.max_fan_out}</span>}
            </div>

            <div className="ds-bento ds-bento-2" style={{ marginBottom: '1.5rem' }}>
              <div className="ds-bento-card">
                <h3>Code composition</h3>
                {elementPie.length > 0 ? (
                  <>
                    <ResponsiveContainer width="100%" height={170}>
                      <PieChart>
                        <Pie data={elementPie} cx="50%" cy="50%" innerRadius={44} outerRadius={68} paddingAngle={2} dataKey="value">
                          {elementPie.map((e, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip contentStyle={{ background: 'var(--ds-bg-elevated)', border: '1px solid var(--ds-border)' }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="ds-legend">
                      {elementPie.map((e, i) => (
                        <span key={i} className="ds-legend-item">
                          <span className="ds-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                          {e.name} <strong>{e.value}</strong>
                        </span>
                      ))}
                    </div>
                  </>
                ) : <p className="ds-empty">No elements detected</p>}
              </div>
              <div className="ds-bento-card">
                <h3>Most connected modules</h3>
                {hubsBar.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={hubsBar} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                      <XAxis dataKey="name" tick={{ fill: 'var(--ds-text-muted)', fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={54} />
                      <YAxis tick={{ fill: 'var(--ds-text-muted)', fontSize: 10 }} allowDecimals={false} />
                      <Bar dataKey="degree" fill="var(--ds-accent)" radius={[4, 4, 0, 0]} />
                      <Tooltip contentStyle={{ background: 'var(--ds-bg-elevated)', border: '1px solid var(--ds-border)' }} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <p className="ds-empty">No connections</p>}
              </div>
            </div>

            <div className="ds-bento-card" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0 }}>
                <h3 style={{ margin: 0 }}>Dependency graph</h3>
                <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.85rem', margin: '0.35rem 0 0', lineHeight: 1.5 }}>
                  {totalServices} nodes · {totalDeps} dependencies. Explore interactive dependency, architecture, and file views in the full Graph explorer.
                </p>
              </div>
              <Link to={`/graph?repo=${encodeURIComponent(selectedKey)}`} className="btn btn-primary" style={{ whiteSpace: 'nowrap' }}>
                Open Graph explorer →
              </Link>
            </div>

            <div className="ds-bento ds-bento-2" style={{ marginBottom: '1.5rem' }}>
              <div className="ds-bento-card">
                <h3>Key insights</h3>
                <ul className="ds-insight-list">
                  {(insights.insights || []).map((s, i) => <li key={i}>{s.replace(/`/g, '')}</li>)}
                </ul>
              </div>
              <div className="ds-bento-card">
                <h3>Most depended-upon</h3>
                {coreModules.length > 0 ? (
                  <div className="ds-bars">
                    {coreModules.map((m, i) => (
                      <div key={i} className="ds-bar-row">
                        <span className="ds-bar-name" title={m.name}>{m.name}</span>
                        <span className="ds-bar-track"><span className="ds-bar-fill" style={{ width: `${Math.round((m.dependents / maxDependents) * 100)}%` }} /></span>
                        <span className="ds-bar-val">{m.dependents}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="ds-empty">No shared modules</p>}
              </div>
            </div>

            <div className="ds-bento ds-bento-2">
              <div className="ds-bento-card">
                <h3>Circular dependencies</h3>
                {circular.length > 0 ? (
                  <ul className="ds-cycle-list">
                    {circular.map((cyc, i) => <li key={i}>{cyc.join(' → ')} → {cyc[0]}</li>)}
                  </ul>
                ) : <p className="ds-ok">✓ None — the import graph is acyclic.</p>}
              </div>
              <div className="ds-bento-card">
                <h3>Project structure</h3>
                <div className="ds-bars">
                  {(insights.folders || []).map((f, i) => (
                    <div key={i} className="ds-bar-row">
                      <span className="ds-bar-name">{f.name}</span>
                      <span className="ds-bar-track"><span className="ds-bar-fill" style={{ width: `${Math.round((f.files / (insights.folders[0]?.files || 1)) * 100)}%` }} /></span>
                      <span className="ds-bar-val">{f.files}</span>
                    </div>
                  ))}
                </div>
                {(insights.entry_points || []).length > 0 && (
                  <div style={{ marginTop: '0.85rem' }}>
                    <div className="ds-sub-label">Entry points</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.35rem' }}>
                      {insights.entry_points.map((e, i) => <span key={i} className="ds-chip">{e}</span>)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {selectedKey && !loading && graphData && !isOrg && !insights && (
          <div className="ds-bento-card" style={{ marginBottom: '1.5rem' }}>
            <h3>Insights unavailable</h3>
            <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem' }}>
              Couldn't compute insights for this repository — you can still explore it in the graph.
            </p>
            <Link to={`/graph?repo=${encodeURIComponent(selectedKey)}`} className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
              Open Graph explorer →
            </Link>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
