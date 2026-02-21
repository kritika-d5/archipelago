import React, { useState, useEffect } from 'react';
import api from '../services/api';

function Health() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await api.get('/api/health/');
      setHealth(response.data);
    } catch (err) {
      setHealth({ status: 'unhealthy', error: err.message });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Checking health...</div>;
  }

  return (
    <div className="card">
      <h2 className="card-title">System Health</h2>
      {health && (
        <div>
          <div className="info-grid">
            <div className="info-card">
              <div className="info-card-label">Status</div>
              <div className="info-card-value" style={{ 
                color: health.status === 'healthy' ? '#28a745' : '#dc3545' 
              }}>
                {health.status || 'unknown'}
              </div>
            </div>
            <div className="info-card">
              <div className="info-card-label">Service</div>
              <div className="info-card-value">{health.service || 'N/A'}</div>
            </div>
          </div>
          {health.error && (
            <div className="error">Error: {health.error}</div>
          )}
          <button onClick={checkHealth} className="btn btn-primary" style={{ marginTop: '1rem' }}>
            Refresh
          </button>
        </div>
      )}
    </div>
  );
}

export default Health;
