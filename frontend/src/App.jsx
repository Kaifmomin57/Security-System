import { useState, useEffect, useCallback, useRef } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Shield, LayoutGrid, Bell, Camera, Settings, Activity, Eye, Flame, Car, Compass } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import AlertsPage from './pages/AlertsPage'
import CamerasPage from './pages/CamerasPage'
import PatrolHeatmapPage from './pages/PatrolHeatmapPage'
import ANPRWatchlistPage from './pages/ANPRWatchlistPage'
import TrafficOperationsPage from './pages/TrafficOperationsPage'
import ChatBot from './components/ChatBot'
import './index.css'

const WS_URL = 'ws://localhost:8000/ws/alerts'

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Shield size={24} style={{ color: 'var(--brand-blue)' }} />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ lineHeight: 1 }}>SENTRIX</span>
          <span style={{ fontSize: '0.5rem', fontWeight: 600, letterSpacing: '1px', color: 'var(--text-muted)' }}>AI PUBLIC SAFETY</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px', fontSize: '0.65rem', fontWeight: 700, color: '#34d399', marginBottom: 16 }}>
        <span className="logo-dot" style={{ margin: 0, width: 6, height: 6 }} /> Operational
      </div>

      <span className="sidebar-section-label">Command Center</span>
      <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <LayoutGrid size={16} /> Overview
      </NavLink>

      <NavLink to="/alerts" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Bell size={16} /> Incidents
      </NavLink>

      <span className="sidebar-section-label">Field Intelligence</span>
      <NavLink to="/heatmap" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Flame size={16} /> Threat Map
      </NavLink>
      <NavLink to="/anpr" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Car size={16} /> Vehicle Intelligence
      </NavLink>
      <NavLink to="/traffic" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Compass size={16} /> Traffic Intelligence
      </NavLink>




    </aside>
  )
}

function TopBar({ wsConnected, alertCount }) {
  const location = useLocation()
  const titles = {
    '/': 'SENTRIX COMMAND CENTER',
    '/alerts': 'INCIDENT INTELLIGENCE',
    '/cameras': 'CAMERA NETWORK',
    '/heatmap': 'THREAT MAP & PATROL PLANNING',
    '/anpr': 'VEHICLE INTELLIGENCE',
    '/traffic': 'TRAFFIC INTELLIGENCE',
  }
  return (
    <header className="topbar" style={{ padding: '0 24px', display: 'flex', gap: '24px' }}>
      <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div className="topbar-title">{titles[location.pathname] || 'SENTRIX COMMAND CENTER'}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span className="ws-dot" style={{ width: 6, height: 6 }} /> AI ONLINE</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span className="ws-dot" style={{ width: 6, height: 6, background: '#cbd5e1', boxShadow: 'none' }} /> 10/12 CAMERAS</span>
          {alertCount > 0 && <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--alert-high)' }}>⚠ {alertCount} ACTIVE</span>}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        <div style={{ width: '100%', maxWidth: '400px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', padding: '6px 12px', fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
          ⌕ Search cameras, vehicles, incidents...
        </div>
      </div>

      <div className="topbar-right" style={{ gap: 16 }}>
        <div style={{ position: 'relative', cursor: 'pointer' }}>
          <Bell size={18} color="var(--text-secondary)" />
          {alertCount > 0 && (
            <div style={{ position: 'absolute', top: -4, right: -4, background: 'var(--alert-high)', color: 'white', fontSize: '0.55rem', fontWeight: 800, padding: '1px 4px', borderRadius: '10px' }}>
              {alertCount}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer' }}>
          <div style={{ width: 28, height: 28, background: 'var(--brand-navy)', borderRadius: '50%', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem' }}>CR</div>
          Control Room ▾
        </div>
      </div>
    </header>
  )
}

function Toast({ toasts, onRemove }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.severity}`} onClick={() => onRemove(t.id)}>
          <span style={{ fontSize: '1.1rem' }}>
            {t.severity === 'high' ? '🔴' : t.severity === 'medium' ? '🟠' : '🟡'}
          </span>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.8rem' }}>
              {t.rule_type?.replace('_', ' ').toUpperCase()}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              {t.camera_id} • {t.severity}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const [wsConnected, setWsConnected]   = useState(false)
  const [liveAlerts,  setLiveAlerts]    = useState([])
  const [toasts,      setToasts]        = useState([])
  const wsRef = useRef(null)

  const addToast = useCallback((alert) => {
    const id = Date.now()
    setToasts(prev => [{ ...alert, id }, ...prev.slice(0, 4)])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 6000)
  }, [])

  const connectWS = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen  = () => setWsConnected(true)
    ws.onclose = () => {
      setWsConnected(false)
      setTimeout(connectWS, 3000)   // auto-reconnect
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.event === 'new_alert') {
          setLiveAlerts(prev => [msg.data, ...prev.slice(0, 49)])
          addToast(msg.data)
        } else if (msg.event === 'alert_updated') {
          setLiveAlerts(prev =>
            prev.map(a => a.id === msg.data.id ? msg.data : a)
          )
        }
      } catch (_) {}
    }
    ws.onerror = () => ws.close()
  }, [addToast])

  useEffect(() => {
    connectWS()
    return () => wsRef.current?.close()
  }, [connectWS])

  const activeCount = liveAlerts.filter(a => a.status === 'new').length

  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <TopBar wsConnected={wsConnected} alertCount={activeCount} />
        <main className="main-content">
          <Routes>
            <Route path="/"        element={<Dashboard liveAlerts={liveAlerts} />} />
            <Route path="/alerts"  element={<AlertsPage liveAlerts={liveAlerts} />} />
            <Route path="/live"    element={<CamerasPage liveAlerts={liveAlerts} />} />
            <Route path="/cameras" element={<CamerasPage liveAlerts={liveAlerts} />} />
            <Route path="/heatmap" element={<PatrolHeatmapPage />} />
            <Route path="/anpr"    element={<ANPRWatchlistPage />} />
            <Route path="/traffic" element={<TrafficOperationsPage />} />
          </Routes>
        </main>
        <Toast toasts={toasts} onRemove={id => setToasts(p => p.filter(t => t.id !== id))} />
        <ChatBot />
      </div>
    </BrowserRouter>
  )
}
