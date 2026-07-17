import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom';
import './App.css';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Health from './pages/Health';
import ArchitectureStudio from './pages/ArchitectureStudio';
import GreenfieldBlueprint from './pages/GreenfieldBlueprint';
import ConnectGitHub from './pages/ConnectGitHub';
import ConnectCallback from './pages/ConnectCallback';
import LearningPathPage from './pages/LearningPathPage';
import ArchitectureDashboard from './pages/ArchitectureDashboard';
import DocumentationPage from './pages/DocumentationPage';
import HubSettings from './pages/HubSettings';
import './styles/ds-dashboard.css';
import './styles/ds-themed-pages.css';

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/graph', label: 'Graph' },
  { to: '/hub', label: 'Architecture Hub' },
  { to: '/health', label: 'Health' },
];

function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-container">
        <NavLink to="/" className="nav-title">Archipelago</NavLink>
        <div className="nav-links">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}

function AppContent() {
  const location = useLocation();
  // Hub pages render their own full-width workspace shell (sidebar + chat); everything else
  // sits inside the centered main-content column. The global navbar is shown on both.
  const isHubLayout =
    ['/hub', '/hub/settings', '/docs'].includes(location.pathname) ||
    location.pathname.includes('/learning-path');

  return (
    <>
      <Navbar />
      {isHubLayout ? (
        <Routes>
          <Route path="/hub" element={<ArchitectureDashboard />} />
          <Route path="/hub/settings" element={<HubSettings />} />
          <Route path="/docs" element={<DocumentationPage />} />
          <Route path="/organization/:orgId/learning-path" element={<LearningPathPage />} />
        </Routes>
      ) : (
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/connect-github" element={<ConnectGitHub />} />
            <Route path="/connect-callback" element={<ConnectCallback />} />
            <Route path="/blueprint" element={<GreenfieldBlueprint />} />
            <Route path="/graph" element={<KnowledgeGraph />} />
            <Route path="/health" element={<Health />} />
            <Route path="/architecture" element={<ArchitectureStudio />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      )}
    </>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <AppContent />
      </div>
    </Router>
  );
}

export default App;
