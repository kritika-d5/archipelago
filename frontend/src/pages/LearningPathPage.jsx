import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';
import DashboardLayout from '../components/DashboardLayout';
import '../styles/ds-dashboard.css';
import './LearningPathPage.css';

cytoscape.use(coseBilkent);

const NODE_COLORS = { service: '#3b82f6', library: '#8b5cf6', shared: '#8b5cf6' };
const EDGE_COLORS = { REST: '#f97316', EVENT: '#22c55e', IMPORT: '#6b7280', DB_ACCESS: '#ef4444' };

function buildCytoscapeElements(globalGraph, mainFlowHighlight = []) {
  const nodes = globalGraph?.nodes || [];
  const edges = globalGraph?.edges || [];
  const highlightSet = new Set(mainFlowHighlight || []);

  const elements = [];
  nodes.forEach((n) => {
    const id = n.id || n.data?.id;
    if (!id) return;
    const type = (n.type || n.data?.type || 'service').toLowerCase();
    const isLibrary = type === 'library' || type === 'shared';
    elements.push({
      data: {
        id,
        label: id,
        type,
        nodeType: isLibrary ? 'library' : 'service',
        highlight: highlightSet.has(id) ? 'true' : 'false',
      },
    });
  });

  edges.forEach((e, i) => {
    const from = e.from ?? e.source ?? e.data?.source;
    const to = e.to ?? e.target ?? e.data?.target;
    if (!from || !to) return;
    const edgeType = (e.type || e.data?.type || 'IMPORT').toUpperCase();
    const isViolation = e.violation || edgeType === 'DB_ACCESS';
    elements.push({
      data: {
        id: `e-${from}-${to}-${i}`,
        source: from,
        target: to,
        label: edgeType,
        edgeType,
        violation: isViolation ? 'true' : 'false',
      },
    });
  });

  return elements;
}

function ServiceCard({ detail, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const v = detail.violations || [];
  return (
    <div className="lp-service-card">
      <button className="lp-service-card-header" onClick={() => setOpen(!open)} type="button">
        <span className="lp-service-card-title">{detail.name}</span>
        <span className="lp-service-card-badge">{detail.language}</span>
        {v.length > 0 && <span className="lp-service-card-violation">Violations: {v.length}</span>}
        <span className="lp-service-card-chevron">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="lp-service-card-body">
          <p className="lp-service-purpose">{detail.purpose}</p>
          {detail.apis?.length > 0 && (
            <div>
              <strong>APIs</strong>
              <ul>{detail.apis.slice(0, 15).map((a, i) => <li key={i}>{a}</li>)}</ul>
            </div>
          )}
          {detail.incoming_dependencies?.length > 0 && (
            <div><strong>Incoming</strong> {detail.incoming_dependencies.join(', ')}</div>
          )}
          {detail.outgoing_dependencies?.length > 0 && (
            <div><strong>Outgoing</strong> {detail.outgoing_dependencies.join(', ')}</div>
          )}
          {detail.events_produced?.length > 0 && (
            <div><strong>Events produced</strong> {detail.events_produced.join(', ')}</div>
          )}
          {detail.events_consumed?.length > 0 && (
            <div><strong>Events consumed</strong> {detail.events_consumed.join(', ')}</div>
          )}
          {v.length > 0 && (
            <div className="lp-violations">
              <strong>Violations</strong>
              {v.map((viol, i) => (
                <div key={i}>{viol.type}: {JSON.stringify(viol)}</div>
              ))}
            </div>
          )}
          {detail.documentation_link && (
            <a href={detail.documentation_link} target="_blank" rel="noopener noreferrer">Documentation</a>
          )}
        </div>
      )}
    </div>
  );
}

function FlowCard({ flow, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const pathList = flow.path || flow.path_ids || [];
  return (
    <div className="lp-flow-card">
      <button className="lp-flow-card-header" onClick={() => setOpen(!open)} type="button">
        <span className="lp-flow-card-title">{flow.title || pathList.join(' → ')}</span>
        <span className="lp-flow-card-chevron">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="lp-flow-card-body">
          <p className="lp-flow-description">{flow.description}</p>
          <div className="lp-flow-steps">
            {pathList.map((step, i) => (
              <span key={i} className="lp-flow-step">
                {step}{i < pathList.length - 1 ? ' → ' : ''}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LearningPathPage() {
  const { orgId } = useParams();
  const [data, setData] = useState(null);
  const [flows, setFlows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  const loadData = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError(null);
    try {
      const orgKey = orgId.startsWith('org:') ? orgId : `org:${orgId}`;
      const [pathRes, flowsRes] = await Promise.all([
        api.get(`/api/org/${encodeURIComponent(orgKey)}/learning-path`),
        api.get(`/api/org/${encodeURIComponent(orgKey)}/flows`).catch(() => ({ data: { flows: [] } })),
      ]);
      const d = pathRes.data;
      setData(d);
      setFlows(flowsRes.data?.flows || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load learning path');
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    const globalGraph = data.global_graph || {};
    const elements = buildCytoscapeElements(
      { nodes: globalGraph.nodes || [], edges: globalGraph.edges || [] },
      data.main_flow_highlight || []
    );
    if (elements.length === 0) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#fff',
            'font-size': '10px',
            'text-max-width': '120px',
            'text-wrap': 'ellipsis',
            'background-color': NODE_COLORS.service,
            'border-width': 1,
            'border-color': '#334155',
          },
        },
        {
          selector: 'node[nodeType="library"]',
          style: { 'background-color': NODE_COLORS.library },
        },
        {
          selector: 'node[highlight="true"]',
          style: { 'border-width': 3, 'border-color': '#fbbf24' },
        },
        {
          selector: 'edge',
          style: {
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '8px',
            'text-rotation': 'autorotate',
            'line-color': '#6b7280',
            'target-arrow-color': '#6b7280',
            'width': 2,
          },
        },
        { selector: 'edge[edgeType="REST"]', style: { 'line-color': EDGE_COLORS.REST, 'target-arrow-color': EDGE_COLORS.REST } },
        { selector: 'edge[edgeType="EVENT"]', style: { 'line-color': EDGE_COLORS.EVENT, 'target-arrow-color': EDGE_COLORS.EVENT } },
        { selector: 'edge[edgeType="DB_ACCESS"]', style: { 'line-color': EDGE_COLORS.DB_ACCESS, 'target-arrow-color': EDGE_COLORS.DB_ACCESS, 'width': 3 } },
        { selector: 'edge[violation="true"]', style: { 'width': 3 } },
      ],
      layout: { name: 'cose-bilkent', animate: false, nodeDimensionsIncludeLabels: true },
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode({ id: node.id(), data: node.data() });
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data]);

  const sendChat = async () => {
    if (!chatInput.trim() || !orgId) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    try {
      const orgKey = orgId.startsWith('org:') ? orgId : `org:${orgId}`;
      const history = (chatMessages.slice(-10)).map(m => ({ role: m.role, content: m.content }));
      const res = await api.post(`/api/org/${encodeURIComponent(orgKey)}/chat`, {
        message: userMsg,
        history,
      });
      setChatMessages(prev => [...prev, { role: 'assistant', content: res.data.answer }]);
    } catch (e) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: e.response?.data?.detail || e.message || 'Failed to get response',
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const orgKey = orgId?.startsWith('org:') ? orgId : `org:${orgId || ''}`;

  if (loading) {
    return (
      <DashboardLayout selectedKey={orgKey} parsedGraphs={[]} showChat={false}>
        <div className="ds-bento-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <div className="loading">Loading learning path…</div>
        </div>
      </DashboardLayout>
    );
  }
  if (error) {
    return (
      <DashboardLayout selectedKey={orgKey} parsedGraphs={[]} showChat={false}>
        <div className="ds-bento-card" style={{ padding: '2rem' }}>
          <div className="lp-error">{error}</div>
          <button type="button" className="btn btn-primary" onClick={loadData}>Retry</button>
        </div>
      </DashboardLayout>
    );
  }
  if (!data) return null;

  return (
    <DashboardLayout
      selectedKey={orgKey}
      parsedGraphs={[]}
      showChat
      chatMessages={chatMessages}
      chatInput={chatInput}
      onChatInputChange={setChatInput}
      onChatSend={sendChat}
      chatLoading={chatLoading}
    >
      <div className="lp-main">
        <header className="lp-header">
          <h1>Learning Path — {data.org_id?.replace('org:', '')}</h1>
          <p>New to this company? Follow this path to understand the architecture.</p>
        </header>

        <section className="lp-section">
          <h2>1. System Overview</h2>
          <div className="lp-graph-wrap" ref={containerRef} />
          {selectedNode && (
            <div className="lp-metadata-panel">
              <strong>Node:</strong> {selectedNode.data?.label} ({selectedNode.data?.type})
            </div>
          )}
          {data.system_overview_summary && (
            <div className="lp-summary-box">
              <h3>Service interaction summary</h3>
              <div className="lp-summary-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.system_overview_summary}</ReactMarkdown>
              </div>
            </div>
          )}
          {data.main_flow_highlight?.length > 0 && (
            <div className="lp-flow-highlight">
              <strong>Primary flow:</strong> {data.main_flow_highlight.join(' → ')}
            </div>
          )}
        </section>

        <section className="lp-section">
          <h2>2. Recommended learning order</h2>
          <div className="lp-timeline">
            {(data.learning_order || []).map((id, i) => (
              <div key={id} className="lp-timeline-item">
                <span className="lp-timeline-marker">{i + 1}</span>
                <span className="lp-timeline-label">{id}</span>
              </div>
            ))}
          </div>
          <div className="lp-service-cards">
            <h3>Service details</h3>
            {(data.service_details || []).map((detail, i) => (
              <ServiceCard key={detail.id || i} detail={detail} defaultOpen={i === 0} />
            ))}
          </div>
        </section>

        <section className="lp-section">
          <h2>3. Common flows</h2>
          {flows.length === 0 ? (
            <p>No flows detected.</p>
          ) : (
            flows.map((flow, i) => <FlowCard key={i} flow={flow} defaultOpen={i === 0} />)
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
