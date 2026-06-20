import React, { useState, useEffect } from 'react';
import { Bot, Save, CheckCircle2 } from 'lucide-react';
import './index.css';

const API_URL = 'http://localhost:8080/api/config';

function App() {
  const [config, setConfig] = useState({
    system_prompt: '',
    voice: 'priya',
    enabled_tools: ['search_properties', 'book_site_visit', 'update_call_outcome']
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState(false);

  useEffect(() => {
    fetch(API_URL)
      .then(res => res.json())
      .then(data => {
        setConfig(data);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load config:', err);
        setIsLoading(false);
      });
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        setToast(true);
        setTimeout(() => setToast(false), 3000);
      }
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('Failed to save configuration. Ensure FastAPI is running on port 8080.');
    }
    setIsSaving(false);
  };

  if (isLoading) {
    return <div className="dashboard-container"><div className="glass-panel" style={{ textAlign: 'center', color: '#94a3b8' }}>Loading configuration from backend...</div></div>;
  }

  return (
    <div className="dashboard-container">
      <div className="glass-panel">
        <div className="header">
          <div className="header-icon">
            <Bot size={32} />
          </div>
          <div>
            <h1>Agent Configuration</h1>
            <p>Modify your real estate agent's persona and voice dynamically.</p>
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
      </div>

      {toast && (
        <div className="toast">
          <CheckCircle2 size={24} />
          Configuration saved successfully!
        </div>
      )}
    </div>
  );
}

export default App;
