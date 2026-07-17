import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api, { generateArchitectureBlueprint } from '../services/api';
import mermaid from 'mermaid';

function escapeHtml(s) {
  if (!s) return '';
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * LLM output is often one long line; Mermaid's flowchart parser needs line breaks between
 * statements. Insert them after the diagram header and between adjacent node/edge statements.
 */
function normalizeMermaidDiagram(raw) {
  let s = (raw || '').trim();
  if (!s) return s;
  s = s.replace(/^(flowchart\s+(?:TD|TB|BT|RL|LR))\s+/im, '$1\n  ');
  s = s.replace(/^(graph\s+(?:TD|TB|BT|RL|LR))\s+/im, '$1\n  ');
  s = s.replace(/(\])\s+([A-Za-z][\w]*)\s*(-->|\[)/g, '$1\n  $2$3');
  return s.trim();
}

function GreenfieldBlueprint() {
  const location = useLocation();
  const navigate = useNavigate();
  const initialPrompt = location.state?.initialPrompt;
  const [blueprint, setBlueprint] = useState(null);
  const [loading, setLoading] = useState(!!initialPrompt);
  const [modifying, setModifying] = useState(false);
  const [modifyPrompt, setModifyPrompt] = useState('');
  const [error, setError] = useState(null);
  const mermaidHostRef = useRef(null);

  useEffect(() => {
    if (!initialPrompt) {
      setError('No initial prompt. Start from the landing page.');
      return;
    }
    fetchBlueprint(initialPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initialPrompt from location.state, run once on mount
  }, [initialPrompt]);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true },
    });
  }, []);

  // Render the diagram via mermaid.render (deterministic, unique id per run) rather than
  // mermaid.run on a shared node — that plus suppressErrors used to fail silently and leave
  // the panel blank. On any parse/render failure, fall back to showing the raw source.
  useEffect(() => {
    const def = blueprint?.mermaid_diagram;
    const el = mermaidHostRef.current;
    if (!def || !el) return undefined;

    let cancelled = false;

    const runRender = async () => {
      try {
        el.innerHTML = '';
        const normalized = normalizeMermaidDiagram(def);
        const id = `mmd-blueprint-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
        const { svg, bindFunctions } = await mermaid.render(id, normalized);
        if (cancelled || mermaidHostRef.current !== el) return;
        el.innerHTML = svg;
        if (typeof bindFunctions === 'function') bindFunctions(el);
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (!cancelled && mermaidHostRef.current === el) {
          el.innerHTML = `<pre class="arch-studio-mermaid-fallback">${escapeHtml(def)}</pre>`;
        }
      }
    };

    const raf = requestAnimationFrame(runRender);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [blueprint]);

  const fetchBlueprint = async (requirements) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await generateArchitectureBlueprint({
        mode: 'greenfield',
        requirements,
        constraints: {}
      });
      setBlueprint(resp);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate blueprint');
    } finally {
      setLoading(false);
    }
  };

  const handleModify = async (e) => {
    e.preventDefault();
    if (!modifyPrompt.trim() || !blueprint) return;
    setModifying(true);
    setError(null);
    try {
      const resp = await api.post('/architecture/modify', {
        current_blueprint: blueprint,
        modification_request: modifyPrompt.trim()
      });
      setBlueprint(resp.data);
      setModifyPrompt('');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to modify');
    } finally {
      setModifying(false);
    }
  };

  const downloadDocumentation = () => {
    if (!blueprint) return;
    const lines = [
      '# Architecture Blueprint',
      '',
      `**Architecture Style:** ${blueprint.architecture_style}`,
      `**Confidence:** ${((blueprint.confidence_score || 0) * 100).toFixed(0)}%`,
      '',
      '## System Overview',
      '',
      blueprint.system_overview,
      '',
      '## Proposed Tech Stack',
      ''
    ];
    if (blueprint.services?.length) {
      blueprint.services.forEach(s => {
        lines.push(`### ${s.name}`);
        lines.push('');
        lines.push(`- **Technology:** ${s.technology}`);
        lines.push(`- **Description:** ${s.description}`);
        if (s.responsibilities?.length) {
          lines.push('- **Responsibilities:**');
          s.responsibilities.forEach(r => lines.push(`  - ${r}`));
        }
        lines.push('');
      });
    }
    lines.push('## Database Schema');
    lines.push('');
    if (blueprint.data_architecture?.databases?.length) {
      blueprint.data_architecture.databases.forEach((db, i) => {
        lines.push(`### Database ${i + 1}`);
        lines.push('');
        lines.push('```json');
        lines.push(JSON.stringify(db, null, 2));
        lines.push('```');
        lines.push('');
      });
    }
    if (blueprint.data_architecture?.data_flow) {
      lines.push('**Data Flow:**', blueprint.data_architecture.data_flow, '');
    }
    if (blueprint.infrastructure) {
      lines.push('## Infrastructure');
      lines.push('');
      lines.push(`- **Cloud Provider:** ${blueprint.infrastructure.cloud_provider || 'N/A'}`);
      if (blueprint.infrastructure.compute) {
        lines.push('- **Compute:** ' + JSON.stringify(blueprint.infrastructure.compute));
      }
      lines.push('');
    }
    if (blueprint.recommendations?.length) {
      lines.push('## Recommendations');
      lines.push('');
      blueprint.recommendations.forEach(r => lines.push(`- ${r}`));
      lines.push('');
    }
    if (blueprint.tradeoffs?.length) {
      lines.push('## Tradeoffs');
      lines.push('');
      blueprint.tradeoffs.forEach(t => lines.push(`- ${t}`));
      lines.push('');
    }
    lines.push('## Architecture Diagram');
    lines.push('');
    lines.push('```mermaid');
    lines.push(blueprint.mermaid_diagram || 'graph TD\n  A[Architecture]');
    lines.push('```');
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `architecture-blueprint-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (!initialPrompt && !loading && !blueprint) {
    return (
      <div className="card">
        <p className="error">No initial prompt. <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}>Go back</a> to start.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="blueprint-loading">
        <div className="blueprint-loading-spinner" />
        <p>Analyzing your requirements and generating architecture...</p>
      </div>
    );
  }

  return (
    <div className="blueprint-page">
      <div className="card">
        <div className="blueprint-header">
          <h1 className="card-title">Architecture Blueprint</h1>
          <div className="blueprint-meta">
            <span className="blueprint-badge">{blueprint?.architecture_style}</span>
            <span className="blueprint-confidence">{(blueprint?.confidence_score || 0) * 100}% confidence</span>
          </div>
        </div>
        {error && <div className="error">{error}</div>}

        {blueprint?.mermaid_diagram && (
          <div className="blueprint-section">
            <h2>System Design</h2>
            <div className="arch-mermaid-wrap blueprint-diagram">
              <div ref={mermaidHostRef} className="arch-mermaid-host" aria-live="polite" />
            </div>
          </div>
        )}

        <div className="blueprint-section">
          <h2>Tech Stack</h2>
          <div className="tech-stack-grid">
            {blueprint?.services?.map((s, i) => (
              <div key={i} className="tech-card">
                <h3>{s.name}</h3>
                <p>{s.description}</p>
                <span className="tech-tag">{s.technology}</span>
                {s.responsibilities?.length > 0 && (
                  <ul>
                    {s.responsibilities.map((r, j) => <li key={j}>{r}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="blueprint-section">
          <h2>Database Schema</h2>
          <div className="schema-reasoning">
            {blueprint?.data_architecture?.data_flow && (
              <p><strong>Data Flow:</strong> {blueprint.data_architecture.data_flow}</p>
            )}
          </div>
          {blueprint?.data_architecture?.databases?.length > 0 ? (
            <div className="schema-cards">
              {blueprint.data_architecture.databases.map((db, i) => (
                <pre key={i} className="schema-pre">{JSON.stringify(db, null, 2)}</pre>
              ))}
            </div>
          ) : (
            <p>No database schema defined.</p>
          )}
        </div>

        <div className="blueprint-section">
          <h2>Reasoning</h2>
          <div className="reasoning-box">
            <p>{blueprint?.system_overview}</p>
            {blueprint?.recommendations?.length > 0 && (
              <>
                <h4>Recommendations</h4>
                <ul>
                  {blueprint.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </>
            )}
            {blueprint?.tradeoffs?.length > 0 && (
              <>
                <h4>Tradeoffs</h4>
                <ul>
                  {blueprint.tradeoffs.map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              </>
            )}
          </div>
        </div>

        <div className="blueprint-modify">
          <h3>Modify further</h3>
          <form onSubmit={handleModify}>
            <textarea
              value={modifyPrompt}
              onChange={(e) => setModifyPrompt(e.target.value)}
              placeholder="e.g. Add Redis for caching, switch to PostgreSQL..."
              rows={3}
            />
            <button type="submit" className="btn btn-primary" disabled={modifying || !modifyPrompt.trim()}>
              {modifying ? 'Applying...' : 'Apply Changes'}
            </button>
          </form>
        </div>

        <div className="blueprint-actions">
          <button className="btn btn-primary btn-download" onClick={downloadDocumentation}>
            Accept & Download Documentation
          </button>
        </div>
      </div>
    </div>
  );
}

export default GreenfieldBlueprint;
