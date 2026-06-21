import React, { useState, useEffect } from 'react';
import { Bot, Save, CheckCircle2, Plus, User, Phone, List, PhoneCall } from 'lucide-react';
import './index.css';

const API_BASE = 'https://kakamutta-production.up.railway.app/api/agents';

function App() {
  const [agents, setAgents] = useState([]);
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  
  const [config, setConfig] = useState({
    name: '',
    system_prompt: '',
    voice: 'priya'
  });

  const [activeTab, setActiveTab] = useState('config'); // 'config', 'phones', 'logs'
  const [phones, setPhones] = useState([]);
  const [newPhone, setNewPhone] = useState('');
  const [logs, setLogs] = useState([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(false);

  const fetchAgents = async () => {
    try {
      const res = await fetch(API_BASE);
      const data = await res.json();
      setAgents(data);
      if (data.length > 0 && !selectedAgentId) {
        handleSelectAgent(data[0]);
      }
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  useEffect(() => {
    if (selectedAgentId) {
      if (activeTab === 'phones') fetchPhones();
      if (activeTab === 'logs') fetchLogs();
    }
  }, [selectedAgentId, activeTab]);

  const fetchPhones = async () => {
    try {
      const res = await fetch(`${API_BASE}/${selectedAgentId}/phones`);
      const data = await res.json();
      setPhones(data);
    } catch (err) {
      console.error('Failed to fetch phones:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/${selectedAgentId}/logs`);
      const data = await res.json();
      setLogs(data);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  const handleSelectAgent = (agent) => {
    setSelectedAgentId(agent.id);
    setConfig({
      name: agent.name,
      system_prompt: agent.system_prompt,
      voice: agent.voice
    });
  };

  const handleCreateAgent = async () => {
    try {
      const newAgent = {
        name: 'New Agent',
        system_prompt: 'You are a helpful AI...',
        voice: 'priya'
      };
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAgent)
      });
      const created = await res.json();
      await fetchAgents();
      handleSelectAgent(created);
    } catch (err) {
      console.error('Failed to create agent:', err);
    }
  };

  const handleSaveConfig = async () => {
    if (!selectedAgentId) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/${selectedAgentId}`, {
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
      const res = await fetch(`${API_BASE}/${selectedAgentId}/phones`, {
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
      await fetch(`${API_BASE}/${selectedAgentId}/phones/${encodeURIComponent(phone)}`, {
        method: 'DELETE'
      });
      fetchPhones();
    } catch (err) {
      console.error('Failed to delete phone:', err);
    }
  };

  if (isLoading) {
    return <div className="dashboard-container"><div className="glass-panel" style={{ textAlign: 'center', color: '#94a3b8' }}>Loading agents from backend...</div></div>;
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-layout">
        
        {/* Sidebar */}
        <div className="sidebar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', color: 'var(--accent)' }}>
            <Bot size={28} />
            <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Agents</h2>
          </div>
          
          <div className="agent-list">
            {agents.map(agent => (
              <div 
                key={agent.id} 
                className={`agent-item ${selectedAgentId === agent.id ? 'active' : ''}`}
                onClick={() => handleSelectAgent(agent)}
              >
                <User size={18} />
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontWeight: '500', fontSize: '0.95rem' }}>{agent.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{agent.voice}</span>
                </div>
              </div>
            ))}
          </div>

          <button className="new-agent-btn" onClick={handleCreateAgent}>
            <Plus size={20} /> New Agent
          </button>
        </div>

        {/* Main Panel */}
        <div className="glass-panel" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 4rem)' }}>
          {selectedAgentId ? (
            <>
              <div className="header">
                <div className="header-icon">
                  <Bot size={32} />
                </div>
                <div>
                  <h1 style={{ marginBottom: '0.5rem' }}>
                    <input 
                      value={config.name}
                      onChange={e => setConfig({ ...config, name: e.target.value })}
                      style={{ 
                        background: 'transparent', 
                        border: 'none', 
                        color: 'inherit', 
                        fontSize: '1.75rem', 
                        fontWeight: '600',
                        borderBottom: '1px dashed var(--glass-border)',
                        paddingBottom: '0.2rem',
                        outline: 'none',
                        width: '100%'
                      }}
                    />
                  </h1>
                  <p style={{ margin: 0, fontSize: '0.85rem' }}>ID: {selectedAgentId}</p>
                </div>
              </div>

              {/* Tabs */}
              <div className="tabs">
                <button 
                  className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`}
                  onClick={() => setActiveTab('config')}
                >
                  Configuration
                </button>
                <button 
                  className={`tab-btn ${activeTab === 'phones' ? 'active' : ''}`}
                  onClick={() => setActiveTab('phones')}
                >
                  Phone Numbers
                </button>
                <button 
                  className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
                  onClick={() => setActiveTab('logs')}
                >
                  Call Logs
                </button>
              </div>

              {/* Config Tab */}
              {activeTab === 'config' && (
                <div>
                  <div className="form-group">
                    <label>Voice Model</label>
                    <div style={{ position: 'relative' }}>
                      <select 
                        value={config.voice} 
                        onChange={e => setConfig({ ...config, voice: e.target.value })}
                      >
                        <option value="priya">Priya (Female - Recommended)</option>
                        <option value="bulbul">Bulbul (Female)</option>
                        <option value="arjun">Arjun (Male)</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>System Prompt (Persona)</label>
                    <textarea 
                      value={config.system_prompt}
                      onChange={e => setConfig({ ...config, system_prompt: e.target.value })}
                      placeholder="You are Priya, a warm and professional voice agent..."
                    />
                  </div>

                  <div className="button-group">
                    <button 
                      className="save-btn" 
                      onClick={handleSaveConfig}
                      disabled={isSaving}
                    >
                      <Save size={20} />
                      {isSaving ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              )}

              {/* Phone Numbers Tab */}
              {activeTab === 'phones' && (
                <div>
                  <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                    Map your Vobiz DID numbers to this agent. When someone calls these numbers, Vobiz will route them directly to this agent's persona.
                  </p>
                  
                  <div className="input-group">
                    <input 
                      placeholder="+1234567890" 
                      value={newPhone}
                      onChange={e => setNewPhone(e.target.value)}
                    />
                    <button className="save-btn" onClick={handleAddPhone} style={{ margin: 0 }}>
                      <Plus size={20} /> Assign Number
                    </button>
                  </div>

                  {phones.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Phone Number</th>
                          <th style={{ textAlign: 'right' }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {phones.map(p => (
                          <tr key={p.phone_number}>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <Phone size={16} color="var(--text-secondary)" />
                                {p.phone_number}
                              </div>
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="delete-btn" onClick={() => handleDeletePhone(p.phone_number)}>Unassign</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)', border: '1px dashed var(--glass-border)', borderRadius: '12px' }}>
                      No phone numbers mapped to this agent yet.
                    </div>
                  )}
                </div>
              )}

              {/* Call Logs Tab */}
              {activeTab === 'logs' && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                    <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
                      Historical call logs for this agent across all numbers.
                    </p>
                    <button className="new-agent-btn" onClick={fetchLogs} style={{ padding: '0.5rem 1rem' }}>
                      Refresh
                    </button>
                  </div>

                  {logs.length > 0 ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date & Time</th>
                          <th>Direction</th>
                          <th>Caller / Lead</th>
                        </tr>
                      </thead>
                      <tbody>
                        {logs.map(log => (
                          <tr key={log.id}>
                            <td>{new Date(log.created_at).toLocaleString()}</td>
                            <td>
                              <span className={`badge ${log.direction.includes('inbound') ? 'inbound' : 'outbound'}`}>
                                {log.direction}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <PhoneCall size={16} color="var(--text-secondary)" />
                                {log.caller_number}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)', border: '1px dashed var(--glass-border)', borderRadius: '12px' }}>
                      No calls logged for this agent yet.
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
              Select or create an agent from the sidebar
            </div>
          )}
        </div>

      </div>

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
