import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function LeftSidebar({ selectedKey, parsedGraphs, onSelectKey }) {
  const location = useLocation();

  return (
    <aside className="ds-sidebar">
      <div className="ds-sidebar-section">
        <label className="ds-sidebar-label">Organization</label>
        <select className="ds-sidebar-select" value={selectedKey || ''} onChange={onSelectKey}>
          <option value="">Select...</option>
          {(parsedGraphs || []).map((g) => (
            <option key={g.key} value={g.key}>{g.repository || g.key}</option>
          ))}
        </select>
      </div>

      <nav className="ds-sidebar-nav">
        <span className="ds-sidebar-label" style={{ padding: '0 0.75rem' }}>Hub</span>
        <Link to="/hub" className={`ds-nav-item ${location.pathname === '/hub' ? 'active' : ''}`}>
          <span className="ds-nav-icon">▣</span>
          Overview
        </Link>
        {selectedKey?.startsWith('org:') && (
          <Link
            to={`/organization/${selectedKey.replace(/^org:/, '')}/learning-path`}
            className={`ds-nav-item ${location.pathname.includes('learning-path') ? 'active' : ''}`}
          >
            <span className="ds-nav-icon">→</span>
            Learning Path
          </Link>
        )}
        <Link to="/docs" className={`ds-nav-item ${location.pathname === '/docs' ? 'active' : ''}`}>
          <span className="ds-nav-icon">¶</span>
          Documentation
        </Link>
        <Link to="/hub/settings" className={`ds-nav-item ${location.pathname.includes('settings') ? 'active' : ''}`}>
          <span className="ds-nav-icon">⚙</span>
          Settings
        </Link>
      </nav>
    </aside>
  );
}

function ChatbotPanel({ messages, input, onInputChange, onSend, loading }) {
  return (
    <aside className="ds-chat-panel">
      <div className="ds-chat-header">
        <h3 className="ds-chat-title">Architecture Assistant</h3>
        <p className="ds-chat-subtitle">Ask about services, dependencies, flows…</p>
      </div>
      <div className="ds-chat-messages">
        {messages.length === 0 && (
          <p className="ds-chat-placeholder">No messages yet. Ask a question about your architecture.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`ds-chat-msg ds-chat-msg-${m.role}`}>
            <div className="ds-chat-bubble">
              {m.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown> : m.content}
            </div>
          </div>
        ))}
        {loading && <div className="ds-chat-msg ds-chat-msg-assistant"><div className="ds-chat-bubble">…</div></div>}
      </div>
      <div className="ds-chat-input-row">
        <input
          className="ds-chat-input"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSend()}
          placeholder="Ask about services, dependencies..."
          aria-label="Chat message"
        />
        <button type="button" className="ds-chat-send" onClick={onSend} disabled={loading} aria-label="Send">
          →
        </button>
      </div>
    </aside>
  );
}

export default function DashboardLayout({
  children,
  selectedKey,
  parsedGraphs,
  onSelectKey = () => {},
  showChat = true,
  chatMessages = [],
  chatInput = '',
  onChatInputChange = () => {},
  onChatSend = () => {},
  chatLoading = false,
}) {
  return (
    <div className="ds-layout">
      <LeftSidebar selectedKey={selectedKey} parsedGraphs={parsedGraphs} onSelectKey={onSelectKey} />
      <main className="ds-main">{children}</main>
      {showChat && (
        <ChatbotPanel
          messages={chatMessages}
          input={chatInput}
          onInputChange={onChatInputChange}
          onSend={onChatSend}
          loading={chatLoading}
        />
      )}
    </div>
  );
}
