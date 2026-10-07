import { useState, useEffect } from 'react'
import { Camera, AlertTriangle, Play, Shield, WifiOff } from 'lucide-react'
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

// All 12 camera slots in the system
const ALL_CAMERAS = [
  { id: 'cam_01', name: 'MAIN ENTRANCE' },
  { id: 'cam_02', name: 'REAR EXIT' },
  { id: 'cam_03', name: 'PARKING LOT A' },
  { id: 'cam_04', name: 'PARKING LOT B' },
  { id: 'cam_05', name: 'LOBBY' },
  { id: 'cam_06', name: 'STAIRWELL N' },
  { id: 'cam_07', name: 'ROOF ACCESS' },
  { id: 'cam_08', name: 'ALLEY WEST' },
  { id: 'cam_09', name: 'SIDE GATE' },
  { id: 'cam_10', name: 'WAREHOUSE' },
  { id: 'cam_11', name: 'CORRIDOR 1' },
  { id: 'cam_12', name: 'CORRIDOR 2' },
]

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

function CameraFeed({ id, name, isLive }) {
  const [imgError, setImgError] = useState(false)
  const streamUrl = `${API}/cameras/${id}/stream`

  // Reset error state when live status changes
  useEffect(() => { setImgError(false) }, [isLive])

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', background: '#0a0f1a', position: 'relative' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 10px', background: 'var(--brand-navy)', color: 'white', fontSize: '0.62rem', fontWeight: 600, letterSpacing: '1px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {name} <span style={{ color: '#94a3b8' }}>• {id}</span>
        </div>
        {isLive && !imgError ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#22c55e' }}>
            <span className="ws-dot" style={{ width: 5, height: 5 }} /> LIVE
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#64748b' }}>
            <WifiOff size={10} /> OFFLINE
          </div>
        )}
      </div>

      {/* Video area */}
      <div style={{ aspectRatio: '16/9', background: '#050a14', position: 'relative', overflow: 'hidden' }}>
        {isLive && !imgError ? (
          <img
            src={streamUrl}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            onError={() => setImgError(true)}
            alt={`Live feed ${id}`}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 6 }}>
            {/* Scanlines */}
            <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.015) 3px, rgba(255,255,255,0.015) 4px)', pointerEvents: 'none' }} />
            {/* Static noise */}
            <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)', backgroundSize: '6px 6px', pointerEvents: 'none' }} />
            <Camera size={18} style={{ color: '#1e293b', position: 'relative' }} />
            <span style={{ fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '2px', color: '#1e293b', fontWeight: 700, position: 'relative' }}>NO SIGNAL</span>
          </div>
        )}
        {/* Scanlines overlay on live */}
        {isLive && !imgError && (
          <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px)', pointerEvents: 'none' }} />
        )}
      </div>
    </div>
  )
}

export default function Dashboard({ liveAlerts }) {
  const [dbAlerts, setDbAlerts] = useState([])
  const [gridSize, setGridSize] = useState('2x2')
  const [activeCamIds, setActiveCamIds] = useState(new Set())

  const fetchAlerts = async () => {
    try {
      const r = await axios.get(`${API}/alerts?limit=5`)
      setDbAlerts(r.data)
    } catch (_) {}
  }

  const fetchActiveCams = async () => {
    try {
      const r = await axios.get(`${API}/health`)
      const active = new Set(
        (r.data.cameras || [])
          .filter(c => c.status === 'running' || c.fps > 0)
          .map(c => c.camera_id)
      )
      setActiveCamIds(active)
    } catch (_) {}
  }

  useEffect(() => {
    fetchAlerts()
    fetchActiveCams()
    const t1 = setInterval(fetchAlerts, 10000)
    const t2 = setInterval(fetchActiveCams, 3000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [])

  const allAlerts = [
    ...liveAlerts.filter(la => !dbAlerts.find(d => d.id === la.id)),
    ...dbAlerts,
  ].slice(0, 3)

  const camCount = gridSize === '1x1' ? 1 : gridSize === '2x2' ? 4 : 16
  const displayedCams = ALL_CAMERAS.slice(0, camCount)

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
            <span style={{ color: '#22c55e', fontWeight: 600, marginLeft: 8, fontSize: '0.75rem' }}>
              {activeCamIds.size} / {ALL_CAMERAS.length} CAMERAS ONLINE
            </span>
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Good evening, Control Room</div>
          AI monitoring {ALL_CAMERAS.length} camera slots across 5 operational zones.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, marginBottom: 24 }}>
        {/* Left: Camera Grid */}
        <div className="card" style={{ padding: 20 }}>
          <div className="card-header" style={{ marginBottom: 16, paddingBottom: 12 }}>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Play size={14} /> LIVE SURVEILLANCE
            </div>
            <button
              className="btn btn-ghost"
              style={{ padding: '4px 10px', background: 'var(--bg-secondary)', fontWeight: 700 }}
              onClick={() => {
                if (gridSize === '1x1') setGridSize('2x2')
                else if (gridSize === '2x2') setGridSize('4x4')
                else setGridSize('1x1')
              }}
            >
              {gridSize === '1x1' ? '▣ 1×1' : gridSize === '2x2' ? '▦ 2×2' : '▦ 4×4'}
            </button>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: gridSize === '1x1' ? '1fr' : gridSize === '2x2' ? '1fr 1fr' : 'repeat(4, 1fr)',
            gap: 10
          }}>
            {displayedCams.map(cam => (
              <CameraFeed key={cam.id} id={cam.id} name={cam.name} isLive={activeCamIds.has(cam.id)} />
            ))}
          </div>
        </div>

        {/* Right: Active Threats */}
        <div className="card" style={{ padding: 20, background: 'var(--bg-secondary)' }}>
          <div className="card-header" style={{ marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--alert-high)' }}>
              <AlertTriangle size={14} /> ACTIVE THREATS
            </div>
          </div>
          <div className="alert-feed" style={{ marginTop: 8 }}>
            {allAlerts.length > 0 ? (
              allAlerts.map(a => <ActiveThreatCard key={a.id} alert={a} onClick={() => window.location.href = '/alerts'} />)
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                <Shield size={24} style={{ opacity: 0.3, margin: '0 auto 8px' }} />
                No active threats detected.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ gap: 24, marginBottom: 24 }}>
        <StatCard label="CAMERAS ONLINE" value={`${activeCamIds.size}/${ALL_CAMERAS.length}`} color="blue" />
        <StatCard label="ACTIVE THREATS" value={allAlerts.length} color="red" />
        <StatCard label="AVG RESPONSE" value="1:42" color="orange" />
        <StatCard label="AI HEALTH" value="98.7%" color="green" />
      </div>
    </div>
  )
}