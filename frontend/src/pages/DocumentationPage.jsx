import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DashboardLayout from '../components/DashboardLayout';

export default function DocumentationPage() {
  const { orgId } = useParams();
  const [docContent] = useState(''); // TODO: fetch from org docs/notion

  return (
    <DashboardLayout selectedKey={orgId ? `org:${orgId}` : ''} parsedGraphs={[]} showChat={false}>
      <div className="ds-main-inner" style={{ maxWidth: 800 }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Documentation</h1>
        {docContent ? (
          <div className="ds-bento-card" style={{ padding: '2rem' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{docContent}</ReactMarkdown>
          </div>
        ) : (
          <div className="ds-bento-card" style={{ padding: '2rem', color: 'var(--ds-text-muted)' }}>
            <p>No documentation linked yet. Connect Notion or add docs for your organization.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
