import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Landing() {
  const navigate = useNavigate();
  const [showStartFresh, setShowStartFresh] = useState(false);
  const [prompt, setPrompt] = useState('');

  const handleStartFresh = () => {
    setShowStartFresh(true);
  };

  const handleConnectGitHub = () => {
    navigate('/connect-github');
  };

  const handleSubmitPrompt = (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    navigate('/blueprint', { state: { initialPrompt: prompt.trim() } });
  };

  return (
    <div className="landing">
      <div className="landing-hero">
        <h1 className="landing-title">MangoBytes</h1>
        <p className="landing-subtitle">Engineering Knowledge Platform</p>
        {!showStartFresh ? (
          <div className="landing-options">
            <button className="landing-card" onClick={handleConnectGitHub}>
              <div className="landing-card-icon">⌘</div>
              <h3>Connect to GitHub</h3>
              <p>Import your repositories and build a knowledge graph from your codebase</p>
            </button>
            <button className="landing-card" onClick={handleStartFresh}>
              <div className="landing-card-icon">✦</div>
              <h3>Start with Words</h3>
              <p>Describe your idea and get system design, tech stack, and database schema</p>
            </button>
          </div>
        ) : (
          <form className="landing-prompt-form" onSubmit={handleSubmitPrompt}>
            <label>Describe what you want to build</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. A medical app for patient scheduling with telehealth features, HIPAA compliance, and integration with EHR systems..."
              rows={5}
              autoFocus
            />
            <div className="landing-prompt-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowStartFresh(false)}>
                Back
              </button>
              <button type="submit" className="btn btn-primary" disabled={!prompt.trim()}>
                Generate Blueprint
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default Landing;
