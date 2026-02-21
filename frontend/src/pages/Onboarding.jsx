import React from 'react';
import { useNavigate } from 'react-router-dom';

function Onboarding() {
  const navigate = useNavigate();

  const goToDashboardWith = (source) => {
    if (source === 'github') {
      navigate('/?connect=github');
    } else if (source === 'docs') {
      // docs: redirect to Dashboard where user can be instructed to connect docs
      navigate('/?connect=docs');
    } else if (source === 'slack') {
      navigate('/?connect=slack');
    } else if (source === 'cicd') {
      navigate('/?connect=cicd');
    } else {
      navigate('/');
    }
  };

  return (
    <div className="card">
      <h2 className="card-title">Welcome to your Engineering Knowledge Platform</h2>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Connect your data sources to start building a unified view of your engineering system.
      </p>

      <div className="info-grid">
        <div className="info-card" style={{ textAlign: 'center' }}>
          <h3>Connect to GitHub</h3>
          <p style={{ color: '#666' }}>Ingest code repositories and extract services, APIs, dependencies and CI/CD insights.</p>
          <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => goToDashboardWith('github')}>Connect GitHub</button>
        </div>

        <div className="info-card" style={{ textAlign: 'center' }}>
          <h3>Connect Documentation</h3>
          <p style={{ color: '#666' }}>Sync Confluence or Notion to include architecture docs and runbooks into analysis.</p>
          <button className="btn" style={{ marginTop: '1rem', background: '#36c', color: '#fff' }} onClick={() => goToDashboardWith('docs')}>Connect Docs</button>
        </div>

        <div className="info-card" style={{ textAlign: 'center' }}>
          <h3>Connect to Slack</h3>
          <p style={{ color: '#666' }}>Capture incident discussions and architecture decisions from Slack channels.</p>
          <button className="btn" style={{ marginTop: '1rem', background: '#4a154b', color: '#fff' }} onClick={() => goToDashboardWith('slack')}>Connect Slack</button>
        </div>

        <div className="info-card" style={{ textAlign: 'center' }}>
          <h3>Connect CI/CD</h3>
          <p style={{ color: '#666' }}>Import CI/CD signals to detect library deprecations, test results, and build failures.</p>
          <button className="btn" style={{ marginTop: '1rem', background: '#ff7a18', color: '#fff' }} onClick={() => goToDashboardWith('cicd')}>Connect CI/CD</button>
        </div>
      </div>

      <div style={{ textAlign: 'center', marginTop: '1rem' }}>
        <small style={{ color: '#999' }}>Once connected, you will be redirected to the Graph & Q&A pages for analysis.</small>
      </div>
    </div>
  );
}

export default Onboarding;
