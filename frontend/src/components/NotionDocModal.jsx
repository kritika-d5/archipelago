import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

/**
 * Reusable "add documentation from Notion" picker. Handles connecting Notion, listing pages,
 * selecting one, and fetching its content. On confirm it calls onSelect({ pageId, content, title });
 * the parent decides what to do with it (navigate to the graph, run a doc-diff, etc.).
 */
export default function NotionDocModal({ open, onClose, onSelect }) {
  const [pages, setPages] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loadingPages, setLoadingPages] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState(null);

  const loadPages = useCallback(async () => {
    setLoadingPages(true);
    setError(null);
    try {
      const { data } = await api.get('/api/integrations/notion/pages');
      setPages(data?.pages || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load Notion pages');
    } finally {
      setLoadingPages(false);
    }
  }, []);

  // Reset selection whenever the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setSelected(null);
      setError(null);
    }
  }, [open]);

  // Reload pages when a Notion OAuth popup reports success.
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (e.origin !== window.location.origin) return;
      if (e.data?.type === 'NOTION_CONNECTED') loadPages();
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [open, loadPages]);

  const connectNotion = async () => {
    setError(null);
    try {
      const { data } = await api.get('/api/integrations/connect-url/notion');
      if (data?.connected || !data?.redirect_url) {
        loadPages();
        return;
      }
      window.open(data.redirect_url, 'composio-notion', 'width=600,height=700');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect Notion');
    }
  };

  const apply = async () => {
    if (!selected) return;
    setApplying(true);
    setError(null);
    try {
      const { data } = await api.get(`/api/integrations/notion/page/${encodeURIComponent(selected.id)}`);
      onSelect({ pageId: selected.id, content: data?.content || '', title: selected.title });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load page content');
    } finally {
      setApplying(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={() => !applying && onClose()}>
      <div className="modal-content modal-docs" onClick={(e) => e.stopPropagation()}>
        <h3>Add documentation from Notion?</h3>
        <p>Pick a Notion page to compare with your codebase. We'll show differences and suggest updates.</p>

        {loadingPages ? (
          <div className="notion-loading">
            <div className="connect-loading-spinner connect-loading-spinner--sm" />
            <span>Loading your Notion pages…</span>
          </div>
        ) : pages.length === 0 ? (
          <button className="btn btn-secondary notion-connect-btn" onClick={connectNotion}>
            Connect Notion &amp; load pages
          </button>
        ) : (
          <>
            <div className="notion-pages-head">
              <span className="notion-pages-label">Your pages</span>
              <button type="button" className="notion-reload-link" onClick={loadPages}>Reload</button>
            </div>
            <div className="notion-pages-list">
              {pages.map((p) => (
                <div
                  key={p.id}
                  className={`notion-page-tile ${selected?.id === p.id ? 'selected' : ''}`}
                  onClick={() => setSelected(p)}
                >
                  <span className="notion-page-title">{p.title}</span>
                  {selected?.id === p.id && <span className="notion-page-check" aria-hidden>✓</span>}
                </div>
              ))}
            </div>
          </>
        )}

        {error && (
          <div className="error connect-error" style={{ marginTop: '0.75rem' }}>{error}</div>
        )}

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={applying}>
            Skip for now
          </button>
          <button className="btn btn-primary" onClick={apply} disabled={!selected || applying}>
            {applying ? 'Adding…' : 'Continue with this doc'}
          </button>
        </div>
      </div>
    </div>
  );
}
