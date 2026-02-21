import React, { useState } from 'react';
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

  React.useEffect(() => {
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
    <div>
      <div className="card">
        <h2 className="card-title">Parse Repository</h2>
        <form onSubmit={handleParse}>
          <div className="form-group">
            <label>Repository URL or Organization</label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo.git or https://github.com/org-name"
              required
            />
            <small style={{ color: '#666', display: 'block', marginTop: '0.5rem' }}>
              Enter a repository URL (e.g., https://github.com/user/repo.git) or organization URL (e.g., https://github.com/org-name) to parse all repos
            </small>
          </div>
          <div className="form-group">
            <label>Branch (optional)</label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
            />
          </div>
          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={includeTests}
                onChange={(e) => setIncludeTests(e.target.checked)}
              />
              {' '}Include test files
            </label>
          </div>
          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={includeVendor}
                onChange={(e) => setIncludeVendor(e.target.checked)}
              />
              {' '}Include vendor/node_modules
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Parsing...' : 'Parse Repository'}
          </button>
        </form>

        {error && <div className="error">{error}</div>}
        {result && (
          <div className="success">
            <h3>Parsing Complete!</h3>
            <div className="info-grid">
              <div className="info-card">
                <div className="info-card-label">{result.graph ? 'Files Parsed' : 'Repositories Parsed'}</div>
                <div className="info-card-value">{result.files_parsed}</div>
              </div>
              <div className="info-card">
                <div className="info-card-label">Time Taken</div>
                <div className="info-card-value">{result.parsing_time.toFixed(2)}s</div>
              </div>
              {result.graph ? (
                <>
                  <div className="info-card">
                    <div className="info-card-label">Repository</div>
                    <div className="info-card-value">{result.graph?.metadata?.repository_name}</div>
                  </div>
                  <div className="info-card">
                    <div className="info-card-label">Total Elements</div>
                    <div className="info-card-value">{result.graph?.elements?.length || 0}</div>
                  </div>
                </>
              ) : (
                <div className="info-card" style={{ gridColumn: 'span 2' }}>
                  <div className="info-card-label">Organization Analysis</div>
                  <div className="info-card-value">Cross-repo dependency graph generated</div>
                </div>
              )}
            </div>
            {result.graph ? (
              <a href="/graph" className="btn btn-secondary" style={{ marginTop: '1rem' }}>
                View Graph
              </a>
            ) : (
              <div style={{ marginTop: '1rem' }}>
                <p>Organization analysis complete! The cross-repository dependency graph has been generated and saved.</p>
                <a href="/graph" className="btn btn-secondary" style={{ marginTop: '0.5rem' }}>
                  View Dependency Graph
                </a>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">Parsed Repositories</h2>
        {parsedGraphs.length === 0 ? (
          <p>No repositories parsed yet.</p>
        ) : (
          <div>
            {parsedGraphs.map((graph, idx) => (
              <div key={idx} className="info-card" style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{graph.repository}</strong>
                    <br />
                    <small>Parsed: {new Date(graph.parsed_at).toLocaleString()}</small>
                  </div>
                  <a href={`/graph?repo=${encodeURIComponent(graph.key)}`} className="btn btn-primary">
                    View
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
