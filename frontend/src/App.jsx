import { useState, useEffect, useCallback, useRef } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Shield, LayoutGrid, Bell, Camera, Settings, Activity, Eye, Flame, Car, Compass } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import AlertsPage from './pages/AlertsPage'
import CamerasPage from './pages/CamerasPage'
import PatrolHeatmapPage from './pages/PatrolHeatmapPage'
import ANPRWatchlistPage from './pages/ANPRWatchlistPage'
import TrafficOperationsPage from './pages/TrafficOperationsPage'
import './index.css'

const WS_URL = 'ws://localhost:8000/ws/alerts'

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Shield size={22} />
        SentryEye
        <span className="logo-dot" />
      </div>

      <span className="sidebar-section-label">Monitor</span>
      <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <LayoutGrid size={16} /> Dashboard
      </NavLink>
      <NavLink to="/alerts" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Bell size={16} /> Alerts & Forensic
      </NavLink>
      <NavLink to="/cameras" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Camera size={16} /> Cameras
      </NavLink>

      <span className="sidebar-section-label">Police Operations</span>
      <NavLink to="/heatmap" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Flame size={16} /> Patrol Heatmap
      </NavLink>
      <NavLink to="/anpr" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Car size={16} /> ANPR & Watchlist
      </NavLink>
      <NavLink to="/traffic" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
        <Compass size={16} /> Traffic & Junctions
      </NavLink>

      <span className="sidebar-section-label" style={{ marginTop: 'auto' }}>System</span>
      <div className="nav-item"><Activity size={16} /> Health</div>
      <div className="nav-item"><Settings size={16} /> Settings</div>
    </aside>
  )
}

function TopBar({ wsConnected, alertCount }) {
  const location = useLocation()
  const titles = {
    '/': 'Surveillance Command Dashboard',
    '/alerts': 'Forensic Alert Feed & Evidence Vault',
    '/cameras': 'Camera Management & Calibrations',
    '/heatmap': 'Historical Incident Heatmap & Patrol Planning',
    '/anpr': 'ANPR & Vehicle Watchlist Intercept Hub',
    '/traffic': 'Traffic Violation & Junction Control',
  }
  return (
    <header className="topbar">
      <div>
        <div className="topbar-title">{titles[location.pathname] || 'SentryEye Police Operations Suite'}</div>
      </div>
      <div className="topbar-right">
        {alertCount > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: 'var(--alert-high)' }}>
            <Eye size={14} /> {alertCount} active alert{alertCount !== 1 ? 's' : ''}
          </div>
        )}
        <div className="ws-indicator">
          <span className={`ws-dot ${wsConnected ? '' : 'offline'}`} />
          {wsConnected ? 'Live' : 'Reconnecting...'}
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
            <Route path="/cameras" element={<CamerasPage liveAlerts={liveAlerts} />} />
            <Route path="/heatmap" element={<PatrolHeatmapPage />} />
            <Route path="/anpr"    element={<ANPRWatchlistPage />} />
            <Route path="/traffic" element={<TrafficOperationsPage />} />
          </Routes>
        </main>
        <Toast toasts={toasts} onRemove={id => setToasts(p => p.filter(t => t.id !== id))} />
      </div>
    </BrowserRouter>
  )
}
