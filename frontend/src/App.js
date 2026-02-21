import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Health from './pages/Health';
import ArchitectureStudio from './pages/ArchitectureStudio';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <h1 className="nav-title">🧠 Knowledge Graph System</h1>
            <div className="nav-links">
              <a href="/">Dashboard</a>
              <a href="/graph">Graph</a>
              <a href="/health">Health</a>
              <a href="/architecture">Architecture</a>
            </div>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/graph" element={<KnowledgeGraph />} />
            <Route path="/health" element={<Health />} />
            <Route path="/architecture" element={<ArchitectureStudio />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
