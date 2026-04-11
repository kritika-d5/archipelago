import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

function Dashboard() {
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('');
  const [includeTests, setIncludeTests] = useState(true);
  const [includeVendor, setIncludeVendor] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [parsedGraphs, setParsedGraphs] = useState([]);
  const [connectHint, setConnectHint] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connect = params.get('connect');
    if (connect === 'github') {
      setConnectHint(
        'Paste your GitHub repository or organization URL below and click Parse. Or use Connect to GitHub from the home page for OAuth.'
      );
    }
  }, []);

  useEffect(() => {
    loadParsedGraphs();
  }, []);

  const loadParsedGraphs = async () => {
    try {
      const response = await api.get('/api/parse/');
      setParsedGraphs(response.data.graphs || []);
    } catch (err) {
      console.error('Error loading graphs:', err);
    }
  };

  const handleParse = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.post('/api/parse/', {
        repository_url: repoUrl,
        branch: branch || null,
        include_tests: includeTests,
        include_vendor: includeVendor,
      });

      if (response.data.success) {
        setResult(response.data);
        loadParsedGraphs();
      } else {
        setError(response.data.error || 'Parsing failed');
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to parse repository');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-page">
      <header className="dashboard-hero">
        <p className="dashboard-eyebrow">Archipelago</p>
        <h1 className="dashboard-title">Dashboard</h1>
        <p className="dashboard-lede">
          Parse a repo or an entire GitHub organization, then open the graph or architecture hub.
        </p>
      </header>

      <div className="dashboard-grid">
        <section className="dashboard-panel dashboard-panel--accent">
          <div className="dashboard-panel-head">
            <span className="dashboard-panel-icon" aria-hidden>
              ◈
            </span>
            <div>
              <h2 className="dashboard-panel-title">Parse repository</h2>
              <p className="dashboard-panel-sub">Clone, analyze, and build your knowledge graph.</p>
            </div>
          </div>

          {connectHint && <div className="dashboard-callout">{connectHint}</div>}

          <form className="dashboard-form" onSubmit={handleParse}>
            <div className="form-group">
              <label htmlFor="dash-repo-url">Repository URL or organization</label>
              <input
                id="dash-repo-url"
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/user/repo.git or https://github.com/org-name"
                required
              />
              <small className="dashboard-field-hint">
                Single repo URL or an organization URL to analyze all accessible repositories.
              </small>
            </div>

            <div className="form-row">
              <div className="form-group form-group--grow">
                <label htmlFor="dash-branch">Branch (optional)</label>
                <input
                  id="dash-branch"
                  type="text"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  placeholder="main"
                />
              </div>
            </div>

            <div className="dashboard-checkboxes">
              <label className="dashboard-check">
                <input
                  type="checkbox"
                  checked={includeTests}
                  onChange={(e) => setIncludeTests(e.target.checked)}
                />
                <span>Include test files</span>
              </label>
              <label className="dashboard-check">
                <input
                  type="checkbox"
                  checked={includeVendor}
                  onChange={(e) => setIncludeVendor(e.target.checked)}
                />
                <span>Include vendor / node_modules</span>
              </label>
            </div>

            <button type="submit" className="btn btn-primary dashboard-submit" disabled={loading}>
              {loading ? 'Parsing…' : 'Parse repository'}
            </button>
          </form>

          {error && <div className="dashboard-alert dashboard-alert--error">{error}</div>}

          {result && (
            <div className="dashboard-success-block">
              <h3 className="dashboard-success-title">Parsing complete</h3>
              <div className="dashboard-stats">
                <div className="dashboard-stat">
                  <span className="dashboard-stat-label">
                    {result.graph ? 'Files parsed' : 'Repositories parsed'}
                  </span>
                  <span className="dashboard-stat-value">{result.files_parsed}</span>
                </div>
                <div className="dashboard-stat">
                  <span className="dashboard-stat-label">Time</span>
                  <span className="dashboard-stat-value">{result.parsing_time.toFixed(2)}s</span>
                </div>
                {result.graph ? (
                  <>
                    <div className="dashboard-stat dashboard-stat--wide">
                      <span className="dashboard-stat-label">Repository</span>
                      <span className="dashboard-stat-value dashboard-stat-value--text">
                        {result.graph?.metadata?.repository_name || '—'}
                      </span>
                    </div>
                    <div className="dashboard-stat">
                      <span className="dashboard-stat-label">Elements</span>
                      <span className="dashboard-stat-value">
                        {result.graph?.elements?.length || 0}
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="dashboard-stat dashboard-stat--wide">
                    <span className="dashboard-stat-label">Organization</span>
                    <span className="dashboard-stat-value dashboard-stat-value--text">
                      Cross-repo dependency graph generated
                    </span>
                  </div>
                )}
              </div>
              {result.graph ? (
                <Link to="/graph" className="btn btn-secondary dashboard-cta">
                  View graph
                </Link>
              ) : (
                <div className="dashboard-org-actions">
                  <p className="dashboard-org-copy">
                    Organization analysis is saved. Open the dependency graph to explore.
                  </p>
                  <Link to="/graph" className="btn btn-secondary dashboard-cta">
                    View dependency graph
                  </Link>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="dashboard-panel">
          <div className="dashboard-panel-head">
            <span className="dashboard-panel-icon" aria-hidden>
              ⎔
            </span>
            <div>
              <h2 className="dashboard-panel-title">Parsed repositories</h2>
              <p className="dashboard-panel-sub">Jump back into any saved graph.</p>
            </div>
          </div>

          {parsedGraphs.length === 0 ? (
            <div className="dashboard-empty">
              <p className="dashboard-empty-title">Nothing parsed yet</p>
              <p className="dashboard-empty-text">
                Run a parse on the left, or{' '}
                <Link to="/connect-github" className="dashboard-inline-link">
                  connect GitHub
                </Link>{' '}
                from the home page.
              </p>
            </div>
          ) : (
            <ul className="dashboard-repo-list">
              {parsedGraphs.map((graph) => (
                <li key={graph.key} className="dashboard-repo-item">
                  <div className="dashboard-repo-meta">
                    <span className="dashboard-repo-name">{graph.repository}</span>
                    <span className="dashboard-repo-date">
                      Parsed {new Date(graph.parsed_at).toLocaleString()}
                    </span>
                  </div>
                  <Link
                    to={`/graph?repo=${encodeURIComponent(graph.key)}`}
                    className="btn btn-primary btn-sm"
                  >
                    Open graph
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default Dashboard;
