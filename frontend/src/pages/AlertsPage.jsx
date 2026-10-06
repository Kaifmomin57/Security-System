import { useState, useEffect } from 'react'
import axios from 'axios'
import { formatDistanceToNow, format } from 'date-fns'
import {
  Filter, RefreshCw, FileText, Archive,
  ShieldCheck, History, Download, AlertOctagon,
  Eye, CheckCircle, X, ChevronLeft, MapPin, Search, Cpu, List, Video
} from 'lucide-react'

const API = 'http://localhost:8000/api/v1'

const RULE_LABELS = {
  loitering: 'Loitering',
  trailing: 'Trailing / Stalking',
  intrusion: 'Zone Intrusion',
  crowd: 'Crowd Density',
  unaccompanied_person: 'Unaccompanied Person',
  signal_jump: 'Traffic Signal Jump',
  wrong_side: 'Wrong-Side Driving',
  possible_hit_and_run: 'Possible Hit & Run',
  watchlist_vehicle_match: 'Watchlist Vehicle Match'
}

export default function AlertsPage({ liveAlerts = [] }) {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState({ status: '', severity: '', rule_type: '' })
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [updating, setUpdating] = useState(false)

  const fetchAlerts = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filter.status) params.status = filter.status
      if (filter.rule_type) params.rule_type = filter.rule_type
      const r = await axios.get(`${API}/alerts`, { params })
      setAlerts(r.data)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
  }, [filter])

  const updateAlert = async (id, status) => {
    setUpdating(true)
    try {
      await axios.patch(`${API}/alerts/${id}`, { status, responder: 'Officer on Duty' })
      fetchAlerts()
      if (selected && selected.id === id) {
        setSelected(prev => ({ ...prev, status }))
      }
    } catch (err) {
      alert('Failed to update alert: ' + err.message)
    } finally {
      setUpdating(false)
    }
  }

  const handleArchive = async (eventId) => {
    if (!window.confirm('Archive this incident? It will be moved to cold storage.')) return;
    try {
      // Simulate archiving
      setAlerts(prev => prev.filter(a => a.id !== eventId))
      if (selected?.id === eventId) setSelected(null)
    } catch (err) {
      alert('Failed to archive: ' + err.message)
    }
  }

  const handleDownloadReportPDF = (eventId) => {
    window.open(`${API}/reports/${eventId}/download`, '_blank')
  }

  const handleExportCourtPackage = (eventId) => {
    window.open(`${API}/events/${eventId}/export-evidence?user_id=Officer_Duty`, '_blank')
  }

  const allAlerts = [
    ...liveAlerts.filter(la => !alerts.find(a => a.id === la.id)),
    ...alerts
  ]

  const getRiskScore = (conf) => Math.round(conf * 100)

  if (selected) {
    const riskScore = getRiskScore(selected.confidence)
    const severityColor = selected.severity === 'high' ? 'var(--alert-high)' : selected.severity === 'medium' ? 'var(--alert-medium)' : 'var(--alert-low)'
    const timeDetected = new Date(selected.timestamp)

    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: 40 }}>
        {/* Breadcrumb / Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.85rem' }} onClick={() => setSelected(null)}>
          <ChevronLeft size={16} /> Back to Incident Feed
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                INCIDENT {selected.id.toUpperCase()}
              </h1>
              <span className={`alert-severity-badge badge-${selected.severity}`}>
                {selected.severity === 'high' ? '🔴' : '🟠'} {selected.severity}
              </span>
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--brand-blue)' }}>
              {RULE_LABELS[selected.rule_type] || selected.rule_type.toUpperCase()}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><MapPin size={14} /> Main Entrance • {selected.camera_id}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><History size={14} /> Detected {format(timeDetected, 'HH:mm:ss')}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-ghost" onClick={() => handleDownloadReportPDF(selected.id)}>
              <FileText size={16} /> PDF DOSSIER
            </button>
            <button className="btn btn-ghost" onClick={() => handleArchive(selected.id)}>
              <Archive size={16} /> ARCHIVE
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 24 }}>
          
          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Video Player Mock */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ background: '#0f172a', aspectRatio: '16/9', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Video size={48} color="#334155" />
                <div style={{ position: 'absolute', inset: 0, border: '4px solid var(--alert-high)', opacity: 0.8, pointerEvents: 'none' }} />
                <div style={{ position: 'absolute', top: 16, left: 16, color: 'white', fontSize: '0.8rem', fontWeight: 600, textShadow: '0 2px 4px rgba(0,0,0,0.8)' }}>
                  INCIDENT CCTV CLIP
                </div>
              </div>
            </div>

            {/* AI Explanation */}
            <div className="card">
              <div className="card-header" style={{ paddingBottom: 16, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--brand-blue)' }}>
                  <Cpu size={16} /> WHY SENTRIX FLAGGED THIS
                </div>
              </div>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 12 }}>
                <li style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}><CheckCircle size={16} color="var(--alert-ok)" style={{ marginTop: 2, flexShrink: 0 }} /> Same individual followed target across 3 operational zones.</li>
                <li style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}><CheckCircle size={16} color="var(--alert-ok)" style={{ marginTop: 2, flexShrink: 0 }} /> Inter-person distance remained consistently below 4.2m.</li>
                <li style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}><CheckCircle size={16} color="var(--alert-ok)" style={{ marginTop: 2, flexShrink: 0 }} /> Behavior persisted for 126 seconds uninterrupted.</li>
                <li style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}><CheckCircle size={16} color="var(--alert-ok)" style={{ marginTop: 2, flexShrink: 0 }} /> Matching trajectory detected traversing restricted area.</li>
              </ul>
            </div>

            {/* Recommended Response */}
            <div className="card" style={{ borderLeft: '4px solid var(--brand-blue)' }}>
              <div className="card-header" style={{ paddingBottom: 12, marginBottom: 16 }}>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertOctagon size={16} /> RECOMMENDED RESPONSE
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.85rem', color: 'var(--text-primary)', marginBottom: 20, fontWeight: 500 }}>
                <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border)' }}>1. Verify live feed immediately</div>
                <div style={{ width: 2, height: 12, background: 'var(--border)', margin: '0 0 0 20px' }} />
                <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border)' }}>2. Notify nearest patrol unit</div>
                <div style={{ width: 2, height: 12, background: 'var(--border)', margin: '0 0 0 20px' }} />
                <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border)' }}>3. Track subject across adjacent cameras</div>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button className="btn btn-primary" onClick={() => updateAlert(selected.id, 'acknowledged')} disabled={updating}>
                  ACKNOWLEDGE
                </button>
                <button className="btn btn-success" onClick={() => updateAlert(selected.id, 'resolved')} disabled={updating}>
                  DISPATCH PATROL
                </button>
                <button className="btn btn-danger" onClick={() => updateAlert(selected.id, 'dismissed')} disabled={updating}>
                  FALSE POSITIVE
                </button>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            
            {/* AI Risk Score */}
            <div className="card" style={{ background: 'var(--brand-navy)', color: 'white' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '1px', marginBottom: 12 }}>AI RISK SCORE</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, marginBottom: 8 }}>
                <div style={{ fontSize: '3rem', fontWeight: 800, lineHeight: 1, color: severityColor }}>{riskScore}</div>
                <div style={{ fontSize: '1rem', fontWeight: 600, color: severityColor, paddingBottom: 6 }}>/ 100</div>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: severityColor, marginBottom: 20 }}>HIGH RISK INCIDENT</div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Detection Confidence</span>
                  <span style={{ fontWeight: 600 }}>94%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Behavior Persistence</span>
                  <span style={{ fontWeight: 600 }}>89%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Trajectory Correlation</span>
                  <span style={{ fontWeight: 600 }}>92%</span>
                </div>
              </div>
            </div>

            {/* Event Timeline */}
            <div className="card">
              <div className="card-header" style={{ paddingBottom: 16, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <History size={16} /> EVENT TIMELINE
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div className="text-mono" style={{ color: 'var(--text-muted)', fontSize: '0.75rem', paddingTop: 2 }}>20:40:51</div>
                  <div style={{ color: 'var(--text-secondary)' }}>Subjects detected in frame</div>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div className="text-mono" style={{ color: 'var(--text-muted)', fontSize: '0.75rem', paddingTop: 2 }}>20:41:26</div>
                  <div style={{ color: 'var(--text-secondary)' }}>Trajectory correlation established</div>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div className="text-mono" style={{ color: 'var(--brand-blue)', fontSize: '0.75rem', paddingTop: 2, fontWeight: 700 }}>20:42:31</div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Behavior threshold crossed</div>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div className="text-mono" style={{ color: 'var(--alert-high)', fontSize: '0.75rem', paddingTop: 2, fontWeight: 700 }}>20:42:32</div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>SentriX generated alert</div>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div className="text-mono" style={{ color: 'var(--text-muted)', fontSize: '0.75rem', paddingTop: 2 }}>20:42:40</div>
                  <div style={{ color: 'var(--text-secondary)' }}>Operator notified automatically</div>
                </div>
              </div>
            </div>

            {/* Evidence Vault */}
            <div className="card" style={{ background: 'var(--bg-secondary)' }}>
              <div className="card-header" style={{ paddingBottom: 16, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ShieldCheck size={16} /> EVIDENCE PACKAGE
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle size={12} color="var(--brand-blue)" /> Original CCTV Clip</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle size={12} color="var(--brand-blue)" /> Detection Snapshot</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle size={12} color="var(--brand-blue)" /> AI Analysis Log</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle size={12} color="var(--brand-blue)" /> Confidence Data</div>
              </div>
              <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 16 }}>
                <div style={{ marginBottom: 4 }}>Evidence Hash (SHA-256):</div>
                <div className="text-mono" style={{ color: 'var(--text-primary)' }}>91ab3f8c...8ef24d1a</div>
              </div>
              <button className="btn btn-primary" onClick={() => handleExportCourtPackage(selected.id)} style={{ width: '100%', justifyContent: 'center' }}>
                <Download size={14} /> DOWNLOAD DOSSIER
              </button>
            </div>

          </div>
        </div>
      </div>
    )
  }

  // INCIDENT FEED LIST VIEW
  return (
    <div style={{ paddingBottom: 40 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">INCIDENT INTELLIGENCE</h1>
          <p className="page-subtitle">Real-time incident detection, evidence packaging, and response orchestration</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn btn-ghost" onClick={fetchAlerts} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Feed
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', display: 'flex', alignItems: 'center', padding: '0 16px', flex: 1, boxShadow: 'var(--shadow)' }}>
          <Search size={16} color="var(--text-muted)" style={{ marginRight: 12 }} />
          <input 
            type="text" 
            placeholder="Search incidents, rules, cameras..." 
            style={{ border: 'none', background: 'transparent', width: '100%', padding: '12px 0', fontSize: '0.9rem', outline: 'none', color: 'var(--text-primary)' }}
          />
        </div>
        <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '8px 16px', borderRadius: 'var(--radius)' }}>
          <Filter size={16} color="var(--text-muted)" />
          <select style={{ border: 'none', background: 'transparent', fontSize: '0.85rem', color: 'var(--text-primary)', outline: 'none' }} value={filter.severity} onChange={e => setFilter({ ...filter, severity: e.target.value })}>
            <option value="">All Severities</option>
            <option value="high">High Risk</option>
            <option value="medium">Medium Risk</option>
          </select>
        </div>
      </div>

      <div className="alert-feed">
        {allAlerts.length === 0 && !loading && (
          <div className="empty-state">
            <ShieldCheck size={48} className="empty-state-icon" color="var(--alert-ok)" />
            <h3 style={{ color: 'var(--text-primary)' }}>No Incidents Detected</h3>
            <p>The SentriX AI engine is actively monitoring all registered zones. No suspicious activity found.</p>
          </div>
        )}

        {allAlerts.map(alert => {
          const ago = alert.timestamp ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true }) : ''
          return (
            <div key={alert.id} className={`alert-item severity-${alert.severity}`} onClick={() => setSelected(alert)} style={{ alignItems: 'center' }}>
              <div style={{ width: 40, height: 40, borderRadius: 8, background: alert.severity === 'high' ? '#fee2e2' : '#ffedd5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem', flexShrink: 0 }}>
                {alert.severity === 'high' ? '🔴' : '🟠'}
              </div>
              <div className="alert-meta">
                <div className="alert-title" style={{ fontSize: '1.05rem' }}>
                  {RULE_LABELS[alert.rule_type] || alert.rule_type.toUpperCase()}
                </div>
                <div className="alert-sub" style={{ fontSize: '0.85rem', display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span><MapPin size={12} style={{ display: 'inline', position: 'relative', top: 2 }}/> {alert.camera_id}</span>
                  <span>•</span>
                  <span><List size={12} style={{ display: 'inline', position: 'relative', top: 2 }}/> AI Risk Score: {getRiskScore(alert.confidence)}/100</span>
                  <span>•</span>
                  <span className={`alert-severity-badge badge-${alert.status}`}>{alert.status}</span>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                <span className="alert-time">{ago}</span>
                <button className="btn btn-ghost" style={{ fontSize: '0.7rem', padding: '4px 10px' }}>VIEW INCIDENT →</button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
