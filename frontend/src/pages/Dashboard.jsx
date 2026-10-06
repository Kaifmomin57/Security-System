import { useState, useEffect } from 'react'
import { Bell, Camera, Activity, TrendingUp, AlertTriangle, Play, Maximize, Map, Cpu, Shield } from 'lucide-react'
import axios from 'axios'
import { formatDistanceToNow } from 'date-fns'

const API = 'http://localhost:8000/api/v1'

const RULE_LABELS = {
  loitering:  'Loitering',
  trailing:   'Trailing Behaviour',
  intrusion:  'Zone Intrusion',
  crowd:      'Crowd Alert',
  abandoned:  'Abandoned Object',
  unaccompanied_person: 'Unaccompanied Person',
  signal_jump: 'Traffic Signal Jump',
  wrong_side: 'Wrong-Side Driving',
  possible_hit_and_run: 'Possible Hit & Run',
  watchlist_vehicle_match: 'Watchlist Match',
}

function StatCard({ label, value, color }) {
  return (
    <div className={`stat-card ${color}`} style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div className="stat-value" style={{ margin: 0, fontSize: '2rem' }}>{value}</div>
      <div className="stat-label" style={{ marginTop: 4 }}>{label}</div>
    </div>
  )
}

function ActiveThreatCard({ alert, onClick }) {
  return (
    <div
      className={`alert-item severity-${alert.severity}`}
      style={{ flexDirection: 'column', gap: 8 }}
      onClick={() => onClick(alert)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
        <span className={`alert-severity-badge badge-${alert.severity}`}>{alert.severity}</span>
        <span className="text-mono" style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
          {(alert.confidence * 100).toFixed(0)}% CONFIDENCE
        </span>
      </div>
      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
        {RULE_LABELS[alert.rule_type] || alert.rule_type}
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        {alert.camera_id} • Detected {formatDistanceToNow(new Date(alert.timestamp))} ago
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '6px 8px', borderRadius: '4px', marginTop: 4 }}>
        AI detected persistent trajectory correlation.
      </div>
      <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'center', marginTop: 4, fontSize: '0.7rem' }}>
        INVESTIGATE →
      </button>
    </div>
  )
}

function CameraFeed({ id, name, isMock = false }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', background: 'var(--bg-secondary)', position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', background: 'var(--brand-navy)', color: 'white', fontSize: '0.65rem', fontWeight: 600, letterSpacing: '1px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {name} <span style={{ color: '#94a3b8' }}>• {id}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--alert-ok)' }}>
          <span className="ws-dot" style={{ width: 5, height: 5 }} /> LIVE
        </div>
      </div>
      <div style={{ aspectRatio: '16/9', background: '#0f172a', position: 'relative' }}>
        {isMock ? (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#334155', flexDirection: 'column', gap: 8 }}>
            <Camera size={24} />
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Feed Active</span>
          </div>
        ) : (
          <img src={`http://localhost:8000/api/v1/cameras/${id}/stream`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='flex'; }} />
        )}
        <div style={{ display: 'none', width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, alignItems: 'center', justifyContent: 'center', color: '#334155', flexDirection: 'column', gap: 8 }}>
            <Camera size={24} />
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Signal Lost</span>
        </div>
        
        {/* Overlay scanning effect */}
        <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.05) 2px, rgba(0,0,0,0.05) 4px)', pointerEvents: 'none' }} />
      </div>
    </div>
  )
}

export default function Dashboard({ liveAlerts }) {
  const [dbAlerts, setDbAlerts] = useState([])
  const [gridSize, setGridSize] = useState('2x2')

  const fetchAlerts = async () => {
    try {
      const r = await axios.get(`${API}/alerts?limit=5`)
      setDbAlerts(r.data)
    } catch (_) {}
  }

  useEffect(() => {
    fetchAlerts()
    const t1 = setInterval(fetchAlerts, 10000)
    return () => clearInterval(t1)
  }, [])

  const allAlerts = [
    ...liveAlerts.filter(la => !dbAlerts.find(d => d.id === la.id)),
    ...dbAlerts,
  ].slice(0, 3) // Only show top 3 on dashboard

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 className="page-title">SENTRIX COMMAND CENTER</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 4 }}>
            Mumbai Unified Surveillance Network
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--alert-ok)', fontWeight: 600, marginLeft: 12 }}>
              <span className="ws-dot" style={{ width: 6, height: 6 }} /> LIVE
            </span>
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Good evening, Control Room</div>
          AI monitoring 12 camera feeds across 5 operational zones.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, marginBottom: 24 }}>
        {/* Left Column: Live Video Grid */}
        <div className="card" style={{ padding: 20 }}>
          <div className="card-header" style={{ marginBottom: 16, paddingBottom: 12 }}>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Play size={14} /> LIVE SURVEILLANCE
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button 
                className="btn btn-ghost" 
                style={{ padding: '4px 10px', background: 'var(--bg-secondary)', fontWeight: 700 }} 
                onClick={() => {
                  if (gridSize === '1x1') setGridSize('2x2');
                  else if (gridSize === '2x2') setGridSize('4x4');
                  else setGridSize('1x1');
                }}
              >
                {gridSize === '1x1' ? '▣ 1×1' : gridSize === '2x2' ? '▦ 2×2' : '▦ 4×4'}
              </button>
            </div>
          </div>
          
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: gridSize === '1x1' ? '1fr' : gridSize === '2x2' ? '1fr 1fr' : 'repeat(4, 1fr)', 
            gap: 16 
          }}>
            {Array.from({ length: gridSize === '1x1' ? 1 : gridSize === '2x2' ? 4 : 16 }).map((_, i) => (
              <CameraFeed key={i} id={`cam_${String(i+1).padStart(2, '0')}`} name={i === 0 ? "MAIN ENTRANCE" : `CAMERA ${String(i+1).padStart(2, '0')}`} isMock={i !== 0} />
            ))}
          </div>
        </div>

        {/* Right Column: Active Threats */}
        <div className="card" style={{ padding: 20, background: 'var(--bg-secondary)' }}>
          <div className="card-header" style={{ marginBottom: 16, paddingBottom: 12 }}>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--alert-high)' }}>
              <AlertTriangle size={14} /> ACTIVE THREATS
            </div>
          </div>
          
          <div className="alert-feed">
            {allAlerts.length > 0 ? (
              allAlerts.map(a => <ActiveThreatCard key={a.id} alert={a} onClick={() => window.location.href='/alerts'} />)
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                <Shield size={24} style={{ opacity: 0.3, margin: '0 auto 8px' }} />
                No active threats detected.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="stats-grid" style={{ gap: 24, marginBottom: 24 }}>
        <StatCard label="CAMERAS" value="12" color="blue" />
        <StatCard label="ACTIVE THREATS" value="2" color="red" />
        <StatCard label="AVG RESPONSE" value="1:42" color="orange" />
        <StatCard label="AI HEALTH" value="98.7%" color="green" />
      </div>


    </div>
  )
}
