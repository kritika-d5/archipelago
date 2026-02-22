import React, { useEffect, useState } from 'react';
import api from '../services/api';

function Timeline() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get('/api/timeline');
      setEvents(resp.data.events || []);
    } catch (err) {
      console.error('Failed to load timeline:', err);
      setError(err.message || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 className="card-title">Timeline</h2>
      {loading && <div>Loading timeline...</div>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && (
        <div>
          {events.length === 0 ? (
            <div>No events yet. Configure a GitHub webhook to POST to <code>/api/timeline/github-webhook</code>.</div>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {events.map((ev) => (
                <li key={ev._id} style={{ padding: '0.75rem 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                    <div>
                      <strong>{ev.repo || 'unknown'}</strong>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{ev.event_type} — {ev.actor || 'system'}</div>
                      <div style={{ marginTop: '0.5rem' }}>{ev.message}</div>
                    </div>
                    <div style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                      <div>{new Date(ev.timestamp || ev.received_at).toLocaleString()}</div>
                      {ev.is_doc_change && <div style={{ color: 'var(--accent)', marginTop: '0.25rem' }}>Doc change</div>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default Timeline;
