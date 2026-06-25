import React, { useState, useEffect } from 'react';
import { Bot, Save, CheckCircle2, Plus, User, Phone, PhoneCall, PhoneOutgoing, LayoutGrid, Settings, Trash2, ArrowLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE = 'https://kakamutta-production.up.railway.app/api';
// Use local endpoint for dialers because they are not under /api currently in main.py
const DIAL_BASE = 'https://kakamutta-production.up.railway.app';

function App() {
  const [view, setView] = useState('library'); // 'library', 'type_select', 'templates', 'builder'
  
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  
  const [selectedType, setSelectedType] = useState('inbound'); // 'inbound', 'outbound', 'multilingual_outbound'
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  const [config, setConfig] = useState({ name: '', company_name: '', niche: 'custom', agent_type: 'inbound', system_prompt: '', voice: 'priya', knowledge_base: '' });
  
  const [activeTab, setActiveTab] = useState('config'); // 'config', 'phones', 'dialer', 'logs'
  const [phones, setPhones] = useState([]);
  const [newPhone, setNewPhone] = useState('');
  const [logs, setLogs] = useState([]);
  
  // Dialer state
  const [dialPhone, setDialPhone] = useState('');
  const [dialName, setDialName] = useState('');
  const [isDialing, setIsDialing] = useState(false);

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
      company_name: agent.company_name || '',
      niche: agent.niche,
      agent_type: agent.agent_type || 'inbound',
      system_prompt: agent.system_prompt,
      voice: agent.voice,
      knowledge_base: agent.knowledge_base || ''
    });
    setActiveTab('config');
    setView('builder');
  };

  const handleCreateFromTemplate = async (template) => {
    try {
      const newAgent = {
        name: `New ${template.name}`,
        niche: template.id,
        agent_type: selectedType,
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

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedAgentId) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/agents/${selectedAgentId}/upload`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setToast(true);
        setTimeout(() => setToast(false), 3000);
        const agentRes = await fetch(`${API_BASE}/agents/${selectedAgentId}`);
        const updatedAgent = await agentRes.json();
        setConfig(prev => ({ ...prev, knowledge_base: updatedAgent.knowledge_base }));
      } else {
        alert('Failed to upload file');
      }
    } catch (err) {
      console.error('Upload error:', err);
    }
    setIsSaving(false);
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

  const handleDialOut = async () => {
    if (!dialPhone) {
      alert('Please enter a phone number to call.');
      return;
    }
    setIsDialing(true);
    const endpoint = config.agent_type === 'multilingual_outbound' ? '/dial-multilingual' : '/dial';
    try {
      const res = await fetch(`${DIAL_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgentId,
          to: dialPhone,
          name: dialName,
          voice: config.voice,
          system_prompt: config.system_prompt
        })
      });
      const data = await res.json();
      if (data.status === 'dialing' || data.status === 'dialing_multilingual') {
        alert('Call initiated successfully! Check Call Logs in a moment.');
      } else {
        alert('Failed: ' + (data.error || JSON.stringify(data)));
      }
    } catch (err) {
      alert('Error triggering call: ' + err);
    }
    setIsDialing(false);
  };

  if (isLoading) {
    return <div className="dashboard-container"><div style={{ textAlign: 'center', marginTop: '20vh' }}>Loading platform...</div></div>;
  }

  const isInbound = config.agent_type === 'inbound';

  return (
    <>
      <div className="app-background">
        <div className="mesh-blob blob-1"></div>
        <div className="mesh-blob blob-2"></div>
        <div className="mesh-blob blob-3"></div>
      </div>

      <div className="dashboard-container">
      <motion.nav 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="top-nav"
      >
        <div className="nav-logo" style={{ cursor: 'pointer' }} onClick={() => setView('library')}>
          <Bot size={32} color="var(--accent)" />
          <span>Kakkamutta Platform</span>
        </div>
        <div className="nav-actions">
          {view === 'library' && (
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="btn-primary" onClick={() => setView('type_select')}>
              <Plus size={18} /> Create Agent
            </motion.button>
          )}
          {view !== 'library' && (
            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="btn-secondary" onClick={() => { setView('library'); setActiveTab('config'); }}>
              <LayoutGrid size={18} /> Back to Library
            </motion.button>
          )}
        </div>
      </motion.nav>

      <AnimatePresence mode="wait">
      {view === 'library' && (
        <motion.div
          key="library"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3 }}
        >
          <h2>Your Agents</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Manage and configure your custom AI voice agents.</p>
          
          {agents.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ textAlign: 'center', padding: '5rem', background: 'var(--glass-bg)', borderRadius: '16px', marginTop: '2rem' }}
            >
              <Bot size={48} color="var(--text-secondary)" style={{ marginBottom: '1rem' }} />
              <h3>No agents yet</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Create your first voice agent to get started.</p>
              <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="btn-primary" style={{ margin: '0 auto' }} onClick={() => setView('type_select')}>
                <Plus size={18} /> Create Agent
              </motion.button>
            </motion.div>
          ) : (
            <motion.div 
              className="agent-grid"
              variants={{ show: { transition: { staggerChildren: 0.1 } } }}
              initial="hidden"
              animate="show"
            >
              {agents.map(agent => (
                <motion.div 
                  key={agent.id} 
                  variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
                  whileHover={{ y: -5, scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="agent-card" 
                  onClick={() => handleOpenAgent(agent)}
                >
                  <div className="agent-card-header">
                    <div className="agent-card-icon">
                      {agent.agent_type === 'inbound' ? <Phone size={24} /> : <PhoneOutgoing size={24} />}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                      <span className={`badge ${agent.agent_type === 'inbound' ? 'inbound' : 'outbound'}`} style={{ textTransform: 'capitalize' }}>
                        {agent.agent_type ? agent.agent_type.replace('_', ' ') : 'Inbound'}
                      </span>
                      <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)' }}>
                        {agent.niche.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                  <div>
                    <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem' }}>{agent.name}</h3>
                    <p 
                      style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'copy', fontFamily: 'monospace' }}
                      title="Click to copy ID"
                      onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(agent.id); alert('Agent ID copied!'); }}
                    >
                      ID: {agent.id}
                    </p>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </motion.div>
      )}

      {view === 'type_select' && (
        <motion.div
          key="type_select"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.3 }}
        >
          <button className="btn-secondary" onClick={() => setView('library')} style={{ marginBottom: '2rem', border: 'none', paddingLeft: 0 }}>
            <ArrowLeft size={18} /> Cancel
          </button>
          <h2>Step 1: Select Agent Type</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>What kind of core pipeline should this agent use?</p>
          
          <div className="template-grid">
            <div className="template-card" onClick={() => { setSelectedType('inbound'); setView('templates'); }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                <Phone size={20} />
              </div>
              <h3>Inbound Agent</h3>
              <p>Receives incoming calls. You will map a phone number to this agent to route calls to it.</p>
            </div>
            
            <div className="template-card" onClick={() => { setSelectedType('outbound'); setView('templates'); }}>
              <div style={{ background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent)', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                <PhoneOutgoing size={20} />
              </div>
              <h3>Outbound Agent</h3>
              <p>Makes outgoing calls to leads. You can trigger calls manually from the dashboard.</p>
            </div>

            <motion.div 
              whileHover={{ y: -5, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="template-card" 
              onClick={() => { setSelectedType('multilingual_outbound'); setView('templates'); }}
            >
              <div style={{ background: 'rgba(236, 72, 153, 0.1)', color: '#ec4899', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                <Bot size={20} />
              </div>
              <h3>Multilingual Outbound</h3>
              <p>Outbound calling with automatic language detection and switching capabilities.</p>
            </motion.div>
          </div>
        </motion.div>
      )}

      {view === 'templates' && (
        <motion.div
          key="templates"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.3 }}
        >
          <button className="btn-secondary" onClick={() => setView('type_select')} style={{ marginBottom: '2rem', border: 'none', paddingLeft: 0 }}>
            <ArrowLeft size={18} /> Back
          </button>
          <h2>Step 2: Choose a Persona Template</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Start with a pre-configured persona or build from scratch.</p>
          
          <div className="template-grid">
            {templates.map(t => (
              <motion.div 
                key={t.id} 
                whileHover={{ y: -5, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="template-card" 
                onClick={() => handleCreateFromTemplate(t)}
              >
                <div style={{ background: 'rgba(255,255,255,0.1)', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                  {t.id === 'real_estate' ? '🏠' : t.id === 'healthcare' ? '🏥' : t.id === 'recruitment' ? '🤝' : t.id === 'customer_support' ? '🎧' : '✨'}
                </div>
                <h3>{t.name}</h3>
                <p>{t.description}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {view === 'builder' && (
        <motion.div
          key="builder"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.4 }}
          className="builder-layout"
        >
          <div className="builder-sidebar">
            <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>
              <Settings size={18} /> Configuration
            </button>
            
            {isInbound ? (
              <button className={`tab-btn ${activeTab === 'phones' ? 'active' : ''}`} onClick={() => setActiveTab('phones')}>
                <Phone size={18} /> Phone Numbers
              </button>
            ) : (
              <button className={`tab-btn ${activeTab === 'dialer' ? 'active' : ''}`} onClick={() => setActiveTab('dialer')}>
                <PhoneOutgoing size={18} /> Dialer
              </button>
            )}

            <button className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
              <PhoneCall size={18} /> Call Logs
            </button>
          </div>

          <div className="builder-main">
            <div style={{ marginBottom: '2rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span className={`badge ${isInbound ? 'inbound' : 'outbound'}`} style={{ textTransform: 'capitalize' }}>
                  {config.agent_type.replace('_', ' ')}
                </span>
                <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)' }}>
                  {config.niche.replace('_', ' ')}
                </span>
              </div>
              <input 
                className="text-input"
                style={{ fontSize: '1.5rem', fontWeight: 'bold', background: 'transparent', border: 'none', borderBottom: '1px dashed var(--glass-border)', borderRadius: 0, padding: '0.5rem 0' }}
                value={config.name}
                onChange={e => setConfig({ ...config, name: e.target.value })}
              />
              <p 
                style={{ margin: '0.5rem 0 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem', cursor: 'copy', fontFamily: 'monospace', display: 'inline-block' }}
                title="Click to copy ID"
                onClick={() => { navigator.clipboard.writeText(selectedAgentId); alert('Agent ID copied!'); }}
              >
                Agent ID: {selectedAgentId} (click to copy)
              </p>
            </div>

            {activeTab === 'config' && (
              <div>
                <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label>Company Name</label>
                    <input 
                      type="text" 
                      value={config.company_name} 
                      onChange={e => setConfig({ ...config, company_name: e.target.value })} 
                      placeholder="e.g. Prestige Realty"
                    />
                  </div>
                  <div>
                    <label>Agent Niche / Capabilities</label>
                    <select value={config.niche} onChange={e => setConfig({ ...config, niche: e.target.value })}>
                      <option value="real_estate">Real Estate (Property Search Tools)</option>
                      <option value="custom">Custom / Generic (Basic Tools)</option>
                      <option value="healthcare">Healthcare</option>
                      <option value="customer_support">Customer Support</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label>Voice Provider</label>
                  <select value={config.voice} onChange={e => setConfig({ ...config, voice: e.target.value })}>
                    <option value="priya">Priya (Female - India)</option>
                    <option value="bulbul">Bulbul (Female - India)</option>
                    <option value="arjun">Arjun (Male - India)</option>
                    <option value="shubh">Shubh (Male - India)</option>
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

                <div className="form-group" style={{ marginTop: '2rem' }}>
                  <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Knowledge Base (Context)</span>
                    <label className="btn-secondary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem', cursor: 'pointer', margin: 0 }}>
                      Upload PDF/Word
                      <input type="file" style={{ display: 'none' }} accept=".pdf,.txt,.docx" onChange={handleFileUpload} />
                    </label>
                  </label>
                  <textarea 
                    style={{ height: '200px' }}
                    value={config.knowledge_base}
                    onChange={e => setConfig({ ...config, knowledge_base: e.target.value })}
                    placeholder="Paste FAQs, pricing, or product details here... Or click the upload button to extract text from a file."
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>The AI has instant access to everything written here.</p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
                  <button className="btn-primary" onClick={handleSaveConfig} disabled={isSaving}>
                    <Save size={18} /> {isSaving ? 'Saving...' : 'Save Agent'}
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'phones' && isInbound && (
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

            {activeTab === 'dialer' && !isInbound && (
              <div>
                <h3>Manual Dialer</h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>Trigger an outbound call using this agent's pipeline and persona.</p>
                
                <div className="form-group">
                  <label>Lead Name (Optional)</label>
                  <input className="text-input" placeholder="John Doe" value={dialName} onChange={e => setDialName(e.target.value)} />
                </div>
                
                <div className="form-group">
                  <label>Phone Number (Required)</label>
                  <input className="text-input" placeholder="+1234567890" value={dialPhone} onChange={e => setDialPhone(e.target.value)} />
                </div>

                <button className="btn-primary" onClick={handleDialOut} disabled={isDialing || !dialPhone} style={{ marginTop: '1rem', width: '100%', justifyContent: 'center', height: '50px' }}>
                  <PhoneOutgoing size={18} /> {isDialing ? 'Initiating Call...' : 'Call Lead Now'}
                </button>
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
                      <React.Fragment key={log.id}>
                        <tr>
                          <td style={{ borderBottom: log.transcript ? 'none' : undefined }}>{new Date(log.created_at).toLocaleString()}</td>
                          <td style={{ borderBottom: log.transcript ? 'none' : undefined }}><span className={`badge ${log.direction.includes('inbound') ? 'inbound' : 'outbound'}`}>{log.direction}</span></td>
                          <td style={{ borderBottom: log.transcript ? 'none' : undefined }}><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><PhoneCall size={16} color="var(--text-secondary)" /> {log.caller_number}</div></td>
                        </tr>
                        {log.transcript && (
                          <tr>
                            <td colSpan={3} style={{ paddingTop: 0 }}>
                              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem', whiteSpace: 'pre-wrap', fontFamily: 'monospace', color: 'var(--text-secondary)', maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--glass-border)' }}>
                                {log.transcript}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </motion.div>
      )}
      </AnimatePresence>

      {toast && (
        <AnimatePresence>
          <motion.div 
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="toast"
          >
            <CheckCircle2 size={24} />
            Agent saved successfully!
          </motion.div>
        </AnimatePresence>
      )}
    </div>
    </>
  );
}

export default App;
