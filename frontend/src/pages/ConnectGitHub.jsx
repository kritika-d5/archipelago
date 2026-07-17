import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import LoadingModal from '../components/LoadingModal';
import NotionDocModal from '../components/NotionDocModal';

function ConnectGitHub() {
  const navigate = useNavigate();
  const [connecting, setConnecting] = useState(false);
  const [repos, setRepos] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [showRepoPicker, setShowRepoPicker] = useState(false);
  const [showDocsModal, setShowDocsModal] = useState(false);
  const [selectedRepos, setSelectedRepos] = useState([]);
  const [selectedOrgs, setSelectedOrgs] = useState([]);
  const [parsing, setParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState({ step: 0, total: 0, name: '' });
  const [lastParsedKey, setLastParsedKey] = useState(null);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [composioAvailable, setComposioAvailable] = useState(null);
  const [error, setError] = useState(null);

  const didInitRef = useRef(false);      // guard: run the initial status probe exactly once
  const loadingReposRef = useRef(false); // guard: no concurrent/repeat repo+org loads

  const checkComposio = useCallback(async () => {
    // Non-mutating status probe — must NOT create a connection on page load.
    try {
      const { data } = await api.get('/api/integrations/status/github');
      setComposioAvailable(!!data.configured);
      if (data.connected) {
        // Already connected in a previous visit — go straight to repo selection.
        loadReposAndOrgs();
      }
    } catch (err) {
      setComposioAvailable(false);
    }
  }, []);

  useEffect(() => {
    if (didInitRef.current) return; // prevents StrictMode double-invoke and any re-mount loop
    didInitRef.current = true;
    checkComposio();
  }, [checkComposio]);

  useEffect(() => {
    const handler = (e) => {
      if (e.origin !== window.location.origin) return;
      if (e.data?.type === 'COMPOSIO_CONNECTED') {
        setConnecting(false);
        loadReposAndOrgs();
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  const openConnectPopup = async () => {
    setError(null);
    let data;
    try {
      ({ data } = await api.get('/api/integrations/connect-url/github'));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get connect URL');
      return;
    }
    // Already connected (backend reused the existing account) — skip OAuth, load repos.
    if (data.connected || !data.redirect_url) {
      loadReposAndOrgs();
      return;
    }
    setConnecting(true);
    const w = window.open(data.redirect_url, 'composio-github', 'width=600,height=700,scrollbars=yes');
    const iv = setInterval(() => {
      if (w?.closed) {
        clearInterval(iv);
        setConnecting(false);
      }
    }, 500);
  };

  const loadReposAndOrgs = async () => {
    if (loadingReposRef.current) return; // block concurrent/repeat loads
    loadingReposRef.current = true;
    setLoadingRepos(true);
    setError(null);
    try {
      const [reposRes, orgsRes] = await Promise.all([
        api.get('/api/integrations/github/repos').catch(() => ({ data: { repos: [] } })),
        api.get('/api/integrations/github/orgs').catch(() => ({ data: { organizations: [] } })),
      ]);
      setRepos(reposRes.data?.repos || []);
      setOrgs(orgsRes.data?.organizations || []);
      setShowRepoPicker(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load repos');
    } finally {
      loadingReposRef.current = false;
      setLoadingRepos(false);
    }
  };

  const toggleRepo = (repo) => {
    setSelectedRepos((prev) =>
      prev.some((r) => r.clone_url === repo.clone_url)
        ? prev.filter((r) => r.clone_url !== repo.clone_url)
        : [...prev, repo]
    );
  };

  const toggleOrg = (org) => {
    setSelectedOrgs((prev) =>
      prev.some((o) => o.login === org.login)
        ? prev.filter((o) => o.login !== org.login)
        : [...prev, org]
    );
  };

  const handleParseAndContinue = async () => {
    if (selectedRepos.length === 0 && selectedOrgs.length === 0) {
      setError('Select at least one repository or organization');
      return;
    }
    setParsing(true);
    setError(null);
    const total = selectedRepos.length + selectedOrgs.length;
    let step = 0;
    let lastRepoKey = null;
    for (const repo of selectedRepos) {
      step += 1;
      setParseProgress({ step, total, name: repo.full_name || repo.clone_url });
      try {
        const { data } = await api.post('/api/parse/', {
          repository_url: repo.clone_url || `https://github.com/${repo.full_name}.git`,
          branch: null,
          include_tests: true,
          include_vendor: false,
        });
        if (data.success) {
          // Use the key the backend actually stored (real default branch), not an assumed :main.
          lastRepoKey = data.graph_key || `${repo.clone_url || repo.full_name}:main`;
          setLastParsedKey(lastRepoKey);
        } else {
          setError(data.error || `Failed to parse ${repo.full_name}`);
        }
      } catch (err) {
        setError(err.response?.data?.detail || `Failed to parse ${repo.full_name}`);
      }
    }
    for (const org of selectedOrgs) {
      step += 1;
      setParseProgress({ step, total, name: `${org.login} (organization)` });
      try {
        const { data } = await api.post('/api/parse/', {
          repository_url: `https://github.com/${org.login}`,
          branch: null,
          include_tests: true,
          include_vendor: false,
        });
        if (data.success) {
          lastRepoKey = data.graph_key || `org:${org.login}`;
          setLastParsedKey(lastRepoKey);
        } else {
          setError(data.error || `Failed to parse org ${org.login}`);
        }
      } catch (err) {
        setError(err.response?.data?.detail || `Failed to parse org ${org.login}`);
      }
    }
    setParsing(false);
    if (lastRepoKey || selectedRepos.length > 0 || selectedOrgs.length > 0) {
      setShowDocsModal(true);
    }
  };

  const handleSkipDocs = () => {
    setShowDocsModal(false);
    navigate(lastParsedKey ? `/graph?repo=${encodeURIComponent(lastParsedKey)}` : '/graph');
  };

  const handleNotionSelected = ({ pageId, content, title }) => {
    setShowDocsModal(false);
    const graphUrl = lastParsedKey ? `/graph?repo=${encodeURIComponent(lastParsedKey)}` : '/graph';
    navigate(graphUrl, { state: { notionPageId: pageId, notionContent: content, notionTitle: title } });
  };

  if (composioAvailable === null) {
    return (
      <div className="connect-github">
        <div className="connect-card connect-card--loading">
          <div className="connect-loading-spinner" />
          <p>Checking integrations…</p>
        </div>
      </div>
    );
  }

  if (!composioAvailable) {
    return (
      <div className="connect-github">
        <div className="connect-card">
          <h2>Connect to GitHub</h2>
          <p>Composio is not configured. Add <code>COMPOSIO_API_KEY</code> to your backend .env, or paste a repository URL below.</p>
          <div style={{ marginTop: '1.5rem' }}>
            <a href="/dashboard" className="btn btn-primary">Go to Dashboard</a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="connect-github">
      <LoadingModal
        open={parsing}
        title="Parsing repositories…"
        subtext={parseProgress.name ? `Cloning and analyzing ${parseProgress.name}` : 'Cloning and analyzing your selection'}
        step={parseProgress.step}
        total={parseProgress.total}
      />
      <LoadingModal
        open={loadingRepos && !showRepoPicker}
        title="Loading your repositories…"
        subtext="Fetching repositories and organizations from GitHub"
      />
      <div className="connect-card">
        <h2>Connect to GitHub</h2>
        {!showRepoPicker ? (
          <>
            <p>Connect your GitHub account to browse and select repositories.</p>
            <button className="btn btn-primary connect-btn" onClick={openConnectPopup} disabled={connecting}>
              {connecting ? 'Connecting...' : 'Connect with GitHub'}
            </button>
          </>
        ) : (
          <>
            {orgs.length > 0 && (
              <>
                <h3>Organizations</h3>
                <div className="repo-grid org-grid">
                  {orgs.map((org) => (
                    <div
                      key={org.login}
                      className={`repo-tile org-tile ${selectedOrgs.some((o) => o.login === org.login) ? 'selected' : ''}`}
                      onClick={() => toggleOrg(org)}
                    >
                      {org.avatar_url && <img src={org.avatar_url} alt="" className="org-avatar" />}
                      <span className="repo-name">{org.login}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
            <h3>Repositories</h3>
            <div className="repo-grid">
              {repos.map((repo) => (
                <div
                  key={repo.full_name}
                  className={`repo-tile ${selectedRepos.some((r) => r.clone_url === repo.clone_url) ? 'selected' : ''}`}
                  onClick={() => toggleRepo(repo)}
                >
                  <span className="repo-name">{repo.full_name}</span>
                </div>
              ))}
            </div>
            {repos.length === 0 && orgs.length === 0 && <p>No repositories or orgs found. Try connecting again.</p>}
            <div className="connect-actions">
              <button className="btn btn-secondary" onClick={() => setShowRepoPicker(false)}>
                Reconnect
              </button>
              <button className="btn btn-primary" onClick={handleParseAndContinue} disabled={parsing || (selectedRepos.length === 0 && selectedOrgs.length === 0)}>
                {parsing ? 'Parsing...' : `Parse ${selectedRepos.length + selectedOrgs.length} selected`}
              </button>
            </div>
          </>
        )}
        {error && <div className="error connect-error">{error}</div>}
      </div>

      <NotionDocModal
        open={showDocsModal}
        onClose={handleSkipDocs}
        onSelect={handleNotionSelected}
      />
    </div>
  );
}

export default ConnectGitHub;
