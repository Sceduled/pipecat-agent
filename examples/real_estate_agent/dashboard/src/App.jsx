import React, { useState, useEffect } from 'react';
import { Bot, Save, CheckCircle2, Plus, User, Phone, PhoneCall, LayoutGrid, Settings, Trash2, ArrowLeft } from 'lucide-react';
import './index.css';

const API_BASE = 'https://kakamutta-production.up.railway.app/api';

function App() {
  const [view, setView] = useState('library'); // 'library', 'templates', 'builder'
  
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  const [config, setConfig] = useState({ name: '', niche: 'custom', system_prompt: '', voice: 'priya' });
  
  const [activeTab, setActiveTab] = useState('config'); // 'config', 'phones', 'logs'
  const [phones, setPhones] = useState([]);
  const [newPhone, setNewPhone] = useState('');
  const [logs, setLogs] = useState([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(false);

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents`);
      const data = await res.json();
      setAgents(data);
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
      setIsLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/templates`);
      const data = await res.json();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchTemplates();
  }, []);

  useEffect(() => {
    if (selectedAgentId && view === 'builder') {
      if (activeTab === 'phones') fetchPhones();
      if (activeTab === 'logs') fetchLogs();
    }
  }, [selectedAgentId, activeTab, view]);

  const fetchPhones = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents/${selectedAgentId}/phones`);
      const data = await res.json();
      setPhones(data);
    } catch (err) {
      console.error('Failed to fetch phones:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents/${selectedAgentId}/logs`);
      const data = await res.json();
      setLogs(data);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  const handleOpenAgent = (agent) => {
    setSelectedAgentId(agent.id);
    setConfig({
      name: agent.name,
      niche: agent.niche,
      system_prompt: agent.system_prompt,
      voice: agent.voice
    });
    setActiveTab('config');
    setView('builder');
  };

  const handleCreateFromTemplate = async (template) => {
    try {
      const newAgent = {
        name: `New ${template.name}`,
        niche: template.id,
        system_prompt: template.prompt,
        voice: 'priya'
      };
      const res = await fetch(`${API_BASE}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAgent)
      });
      const created = await res.json();
      await fetchAgents();
      handleOpenAgent(created);
    } catch (err) {
      console.error('Failed to create agent:', err);
    }
  };

  const handleSaveConfig = async () => {
    if (!selectedAgentId) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/agents/${selectedAgentId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        setToast(true);
        setTimeout(() => setToast(false), 3000);
        await fetchAgents();
      }
    } catch (err) {
      console.error('Failed to save config:', err);
    }
    setIsSaving(false);
  };

  const handleAddPhone = async () => {
    if (!newPhone) return;
    try {
      const res = await fetch(`${API_BASE}/agents/${selectedAgentId}/phones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: newPhone })
      });
      if (res.ok) {
        setNewPhone('');
        fetchPhones();
      } else {
        const error = await res.json();
        alert(error.detail || 'Failed to add phone');
      }
    } catch (err) {
      console.error('Failed to add phone:', err);
    }
  };

  const handleDeletePhone = async (phone) => {
    try {
      await fetch(`${API_BASE}/agents/${selectedAgentId}/phones/${encodeURIComponent(phone)}`, {
        method: 'DELETE'
      });
      fetchPhones();
    } catch (err) {
      console.error('Failed to delete phone:', err);
    }
  };

  if (isLoading) {
    return <div className="dashboard-container"><div style={{ textAlign: 'center', marginTop: '20vh' }}>Loading platform...</div></div>;
  }

  return (
    <div className="dashboard-container">
      <nav className="top-nav">
        <div className="nav-logo" style={{ cursor: 'pointer' }} onClick={() => setView('library')}>
          <Bot size={32} color="var(--accent)" />
          <span>Kakkamutta Platform</span>
        </div>
        <div className="nav-actions">
          {view === 'library' && (
            <button className="btn-primary" onClick={() => setView('templates')}>
              <Plus size={18} /> Create Agent
            </button>
          )}
          {view !== 'library' && (
            <button className="btn-secondary" onClick={() => setView('library')}>
              <LayoutGrid size={18} /> Back to Library
            </button>
          )}
        </div>
      </nav>

      {view === 'library' && (
        <div>
          <h2>Your Agents</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Manage and configure your custom AI voice agents.</p>
          
          {agents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '5rem', background: 'var(--glass-bg)', borderRadius: '16px', marginTop: '2rem' }}>
              <Bot size={48} color="var(--text-secondary)" style={{ marginBottom: '1rem' }} />
              <h3>No agents yet</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Create your first voice agent to get started.</p>
              <button className="btn-primary" style={{ margin: '0 auto' }} onClick={() => setView('templates')}>
                <Plus size={18} /> Create Agent
              </button>
            </div>
          ) : (
            <div className="agent-grid">
              {agents.map(agent => (
                <div key={agent.id} className="agent-card" onClick={() => handleOpenAgent(agent)}>
                  <div className="agent-card-header">
                    <div className="agent-card-icon">
                      <Bot size={24} />
                    </div>
                    <span className="badge outbound" style={{ textTransform: 'capitalize' }}>
                      {agent.niche.replace('_', ' ')}
                    </span>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem' }}>{agent.name}</h3>
                    <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>ID: {agent.id.slice(0,8)}...</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {view === 'templates' && (
        <div>
          <button className="btn-secondary" onClick={() => setView('library')} style={{ marginBottom: '2rem', border: 'none', paddingLeft: 0 }}>
            <ArrowLeft size={18} /> Back
          </button>
          <h2>Choose a Template</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Start with a pre-configured persona or build from scratch.</p>
          
          <div className="template-grid">
            {templates.map(t => (
              <div key={t.id} className="template-card" onClick={() => handleCreateFromTemplate(t)}>
                <div style={{ background: 'rgba(255,255,255,0.1)', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                  {t.id === 'real_estate' ? '🏠' : t.id === 'healthcare' ? '🏥' : t.id === 'recruitment' ? '🤝' : t.id === 'customer_support' ? '🎧' : '✨'}
                </div>
                <h3>{t.name}</h3>
                <p>{t.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'builder' && (
        <div className="builder-layout">
          <div className="builder-sidebar">
            <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>
              <Settings size={18} /> Configuration
            </button>
            <button className={`tab-btn ${activeTab === 'phones' ? 'active' : ''}`} onClick={() => setActiveTab('phones')}>
              <Phone size={18} /> Phone Numbers
            </button>
            <button className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
              <List size={18} /> Call Logs
            </button>
          </div>

          <div className="builder-main">
            <div style={{ marginBottom: '2rem' }}>
              <input 
                className="text-input"
                style={{ fontSize: '1.5rem', fontWeight: 'bold', background: 'transparent', border: 'none', borderBottom: '1px dashed var(--glass-border)', borderRadius: 0, padding: '0.5rem 0' }}
                value={config.name}
                onChange={e => setConfig({ ...config, name: e.target.value })}
              />
              <p style={{ margin: '0.5rem 0 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Agent ID: {selectedAgentId}</p>
            </div>

            {activeTab === 'config' && (
              <div>
                <div className="form-group">
                  <label>Voice Provider</label>
                  <select value={config.voice} onChange={e => setConfig({ ...config, voice: e.target.value })}>
                    <option value="priya">Priya (Female - India)</option>
                    <option value="bulbul">Bulbul (Female - India)</option>
                    <option value="arjun">Arjun (Male - India)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>System Prompt (Persona)</label>
                  <textarea 
                    value={config.system_prompt}
                    onChange={e => setConfig({ ...config, system_prompt: e.target.value })}
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>This prompt defines the agent's behavior, goal, and how it handles objections.</p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
                  <button className="btn-primary" onClick={handleSaveConfig} disabled={isSaving}>
                    <Save size={18} /> {isSaving ? 'Saving...' : 'Save Agent'}
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'phones' && (
              <div>
                <h3>Inbound Routing</h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>Map your Vobiz DIDs to this agent. Incoming calls to these numbers will automatically trigger this specific persona.</p>
                
                <div className="form-group" style={{ flexDirection: 'row', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1 }}>
                    <label>Phone Number</label>
                    <input className="text-input" placeholder="+1234567890" value={newPhone} onChange={e => setNewPhone(e.target.value)} />
                  </div>
                  <button className="btn-primary" onClick={handleAddPhone} style={{ height: '50px' }}>Assign</button>
                </div>

                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Phone Number</th>
                      <th style={{ textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {phones.length === 0 ? (
                      <tr><td colSpan={2} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No numbers assigned</td></tr>
                    ) : phones.map(p => (
                      <tr key={p.phone_number}>
                        <td><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Phone size={16} color="var(--text-secondary)" /> {p.phone_number}</div></td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn-secondary" style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.2)', padding: '0.5rem' }} onClick={() => handleDeletePhone(p.phone_number)}>
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === 'logs' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <h3>Call History</h3>
                  <button className="btn-secondary" onClick={fetchLogs}>Refresh</button>
                </div>
                
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Direction</th>
                      <th>Caller / Lead</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 ? (
                      <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No calls logged yet</td></tr>
                    ) : logs.map(log => (
                      <tr key={log.id}>
                        <td>{new Date(log.created_at).toLocaleString()}</td>
                        <td><span className={`badge ${log.direction.includes('inbound') ? 'inbound' : 'outbound'}`}>{log.direction}</span></td>
                        <td><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><PhoneCall size={16} color="var(--text-secondary)" /> {log.caller_number}</div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {toast && (
        <div className="toast">
          <CheckCircle2 size={24} />
          Agent saved successfully!
        </div>
      )}
    </div>
  );
}

export default App;
