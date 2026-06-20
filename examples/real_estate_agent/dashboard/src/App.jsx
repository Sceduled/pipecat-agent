import React, { useState, useEffect } from 'react';
import { Bot, Save, CheckCircle2, Plus, User } from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8080/api/agents';

function App() {
  const [agents, setAgents] = useState([]);
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  
  const [config, setConfig] = useState({
    name: '',
    system_prompt: '',
    voice: 'priya'
  });
  
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

  const handleSave = async () => {
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
        await fetchAgents(); // Refresh list to update name if changed
      }
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('Failed to save configuration. Ensure FastAPI is running on port 8080.');
    }
    setIsSaving(false);
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
        <div className="glass-panel">
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
                  onClick={handleSave}
                  disabled={isSaving}
                >
                  <Save size={20} />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
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
