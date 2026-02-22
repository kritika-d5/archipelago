import React from 'react';
import DashboardLayout from '../components/DashboardLayout';

export default function HubSettings() {
  return (
    <DashboardLayout selectedKey="" parsedGraphs={[]} showChat={false}>
      <div className="ds-main-inner" style={{ maxWidth: 560 }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem', color: 'var(--ds-text)' }}>Settings</h1>
        <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
          Organization and integration preferences.
        </p>
        <div className="ds-bento-card" style={{ padding: '2rem' }}>
          <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.9rem', margin: 0 }}>
            Settings panel coming soon. Connect Notion, Slack, or other integrations from here.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
