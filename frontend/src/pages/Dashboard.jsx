import { useState, useEffect } from 'react'
import { Bell, Camera, Activity, TrendingUp, AlertTriangle } from 'lucide-react'
import axios from 'axios'
import { formatDistanceToNow } from 'date-fns'

const API = 'http://localhost:8000/api/v1'

const RULE_LABELS = {
  loitering:  'Loitering',
  trailing:   'Trailing / Stalking',
  intrusion:  'Zone Intrusion',
  crowd:      'Crowd Alert',
  abandoned:  'Abandoned Object',
  unaccompanied_person: 'Unaccompanied Person',
  signal_jump: 'Traffic Signal Jump',
  wrong_side: 'Wrong-Side Driving',
  possible_hit_and_run: 'Possible Hit & Run',
  watchlist_vehicle_match: 'Watchlist Vehicle Match',
}

const SEV_EMOJI = { high: '🔴', medium: '🟠', low: '🟡', critical: '🚨' }

function StatCard({ label, value, color, icon: Icon }) {
  return (
    <div className={`stat-card ${color}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="stat-label">{label}</span>
        <Icon size={18} color="var(--text-muted)" />
      </div>
      <div className="stat-value">{value}</div>
    </div>
  )
}

function AlertRow({ alert, onClick }) {
  const ago = alert.timestamp
    ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })
    : ''
  return (
    <div
      className={`alert-item severity-${alert.severity}`}
      onClick={() => onClick(alert)}
    >
      <span style={{ fontSize: '1.1rem' }}>{SEV_EMOJI[alert.severity] || '⚠️'}</span>
      <div className="alert-meta">
        <div className="alert-title">
          {RULE_LABELS[alert.rule_type] || alert.rule_type}
          <span className={`alert-severity-badge badge-${alert.status}`} style={{ marginLeft: 8 }}>
            {alert.status}
          </span>
        </div>
        <div className="alert-sub">
          📷 {alert.camera_id}
          {alert.explanation?.zone_name && ` • 📍 ${alert.explanation.zone_name}`}
          {alert.explanation?.dwell_time && ` • ⏱ ${alert.explanation.dwell_time}s`}
          {' • '}
          <span className={`alert-severity-badge badge-${alert.severity}`}>{alert.severity}</span>
          {' '}
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {(alert.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <span className="alert-time">{ago}</span>
    </div>
  )
}

function AlertModal({ alert, onClose, onUpdate }) {
  const [loading, setLoading] = useState(false)

  const update = async (status) => {
    setLoading(true)
    try {
      await axios.patch(`${API}/alerts/${alert.id}`, { status, responder: 'operator' })
      onUpdate()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadPDF = () => {
    window.open(`${API}/reports/${alert.id}/download`, '_blank')
  }

  const handleExportZIP = () => {
    window.open(`${API}/events/${alert.id}/export-evidence?user_id=Officer_Command`, '_blank')
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
              {SEV_EMOJI[alert.severity] || '🔴'} {RULE_LABELS[alert.rule_type] || alert.rule_type}
            </h2>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Event ID: <code style={{ fontFamily: 'JetBrains Mono', color: 'var(--accent-cyan)' }}>{alert.id}</code>
            </div>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>

        {alert.snapshot_url && (
          <img
            src={`http://localhost:8000${alert.snapshot_url}`}
            alt="Snapshot"
            style={{ width: '100%', borderRadius: 8, marginBottom: 16, maxHeight: 260, objectFit: 'cover' }}
            onError={e => e.target.style.display = 'none'}
          />
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          {[
            ['Camera', alert.camera_id],
            ['Severity', alert.severity?.toUpperCase()],
            ['Confidence', `${(alert.confidence * 100).toFixed(0)}%`],
            ['Status', alert.status],
            ['Track IDs', alert.track_ids?.join(', ')],
            ['Zone', alert.explanation?.zone_name || '—'],
            ['Violation Details', alert.explanation?.description || (alert.explanation?.dwell_time ? `${alert.explanation.dwell_time}s dwell` : '—')],
            ['Time', alert.timestamp ? new Date(alert.timestamp).toLocaleString() : '—'],
          ].map(([k, v]) => (
            <div key={k} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '10px 12px' }}>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 3 }}>{k}</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 500 }}>{v || '—'}</div>
            </div>
          ))}
        </div>

        {/* Forensic Police Actions */}
        <div style={{
          display: 'flex', gap: 10, background: 'rgba(59, 130, 246, 0.08)',
          border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: 6, padding: '10px', marginBottom: 16
        }}>
          <button
            className="btn btn-primary"
            onClick={handleDownloadPDF}
            style={{ flex: 1, fontSize: '0.75rem', background: '#2563eb' }}
          >
            📄 PDF Report
          </button>
          <button
            className="btn btn-primary"
            onClick={handleExportZIP}
            style={{ flex: 1, fontSize: '0.75rem', background: '#059669' }}
          >
            📦 Court Evidence (.ZIP)
          </button>
        </div>

        {alert.status === 'new' && (
          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button className="btn btn-primary" onClick={() => update('acknowledged')} disabled={loading}>
              ✅ Acknowledge
            </button>
            <button className="btn btn-success" onClick={() => update('resolved')} disabled={loading}>
              🟢 Resolve
            </button>
            <button className="btn btn-danger" onClick={() => update('dismissed')} disabled={loading}>
              ❌ Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Dashboard({ liveAlerts }) {
  const [dbAlerts, setDbAlerts]     = useState([])
  const [health,   setHealth]       = useState(null)
  const [selected, setSelected]     = useState(null)
  const [, forceRefresh]            = useState(0)

  const fetchAlerts = async () => {
    try {
      const r = await axios.get(`${API}/alerts?limit=30`)
      setDbAlerts(r.data)
    } catch (_) {}
  }

  const fetchHealth = async () => {
    try {
      const r = await axios.get(`${API}/health`)
      setHealth(r.data)
    } catch (_) {}
  }

  useEffect(() => {
    fetchAlerts()
    fetchHealth()
    const t1 = setInterval(fetchAlerts, 10000)
    const t2 = setInterval(fetchHealth, 5000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [])

  // Merge live (WS) alerts on top of DB alerts
  const allAlerts = [
    ...liveAlerts.filter(la => !dbAlerts.find(d => d.id === la.id)),
    ...dbAlerts,
  ]

  const stats = {
    total:  allAlerts.length,
    active: allAlerts.filter(a => a.status === 'new').length,
    high:   allAlerts.filter(a => a.severity === 'high').length,
    cameras: health?.cameras?.length || 0,
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Dashboard</h1>
          <p className="page-subtitle">Real-time surveillance monitoring</p>
        </div>
        {health && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {health.cameras?.map(c => (
              <span key={c.camera_id} style={{ marginLeft: 12 }}>
                📷 {c.camera_id} — {c.fps} fps
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="stats-grid">
        <StatCard label="Total Alerts"   value={stats.total}   color="blue"   icon={Bell} />
        <StatCard label="Active (New)"   value={stats.active}  color="orange" icon={AlertTriangle} />
        <StatCard label="High Severity"  value={stats.high}    color="red"    icon={TrendingUp} />
        <StatCard label="Cameras Online" value={stats.cameras} color="green"  icon={Camera} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 20 }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Recent Alerts</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{allAlerts.length} events</span>
          </div>
          <div className="alert-feed">
            {allAlerts.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                <Activity size={32} style={{ marginBottom: 12, opacity: 0.4 }} />
                <p>No alerts yet — pipeline is monitoring...</p>
              </div>
            )}
            {allAlerts.slice(0, 20).map(a => (
              <AlertRow key={a.id} alert={a} onClick={setSelected} />
            ))}
          </div>
        </div>
      </div>

      {selected && (
        <AlertModal
          alert={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { fetchAlerts(); forceRefresh(n => n + 1) }}
        />
      )}
    </div>
  )
}
