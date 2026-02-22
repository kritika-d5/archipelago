import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Timeline from './pages/Timeline';
import Health from './pages/Health';
import ArchitectureStudio from './pages/ArchitectureStudio';
import GreenfieldBlueprint from './pages/GreenfieldBlueprint';
import ConnectGitHub from './pages/ConnectGitHub';
import ConnectCallback from './pages/ConnectCallback';
import LearningPathPage from './pages/LearningPathPage';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <h1 className="nav-title">MangoBytes</h1>
            <div className="nav-links">
              <a href="/">Home</a>
              <a href="/dashboard">Dashboard</a>
              <a href="/graph">Graph</a>
              <a href="/timeline">Timeline</a>
              <a href="/health">Health</a>
              <a href="/architecture">Architecture</a>
            </div>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/connect-github" element={<ConnectGitHub />} />
            <Route path="/connect-callback" element={<ConnectCallback />} />
            <Route path="/blueprint" element={<GreenfieldBlueprint />} />
            <Route path="/graph" element={<KnowledgeGraph />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/health" element={<Health />} />
            <Route path="/architecture" element={<ArchitectureStudio />} />
            <Route path="/organization/:orgId/learning-path" element={<LearningPathPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
