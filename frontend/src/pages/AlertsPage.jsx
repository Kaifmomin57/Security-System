import { useState, useEffect } from 'react'
import axios from 'axios'
import { formatDistanceToNow } from 'date-fns'
import {
  Filter,
  RefreshCw,
  FileText,
  Archive,
  Edit3,
  ShieldCheck,
  History,
  Download,
  AlertOctagon,
  Eye,
  CheckCircle,
  X
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

const SEV_EMOJI = {
  critical: '🚨',
  high: '🔴',
  medium: '🟠',
  low: '🟡'
}

export default function AlertsPage({ liveAlerts = [] }) {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState({ status: '', severity: '', rule_type: '' })
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [updating, setUpdating] = useState(false)

  // Forensic Dialog States
  const [showNotesModal, setShowNotesModal] = useState(false)
  const [officerNotes, setOfficerNotes] = useState('')
  const [reportingOfficer, setReportingOfficer] = useState('Officer on Duty (Badge #SE-402)')
  const [savingNotes, setSavingNotes] = useState(false)

  const [custodyLogs, setCustodyLogs] = useState([])
  const [showCustodyDrawer, setShowCustodyDrawer] = useState(false)
  const [loadingCustody, setLoadingCustody] = useState(false)

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

  const handleOpenNotes = async (event) => {
    try {
      const res = await axios.get(`${API}/reports/${event.id}`)
      setOfficerNotes(res.data.officer_notes || '')
      setReportingOfficer(res.data.reporter_name || 'Officer on Duty (Badge #SE-402)')
    } catch (e) {
      setOfficerNotes('')
    }
    setShowNotesModal(true)
  }

  const handleSaveNotes = async () => {
    if (!selected) return
    setSavingNotes(true)
    try {
      await axios.patch(`${API}/reports/${selected.id}`, {
        officer_notes: officerNotes,
        reporter_name: reportingOfficer
      })
      setShowNotesModal(false)
      alert('Officer notes saved and PDF report updated!')
    } catch (err) {
      alert('Failed to save notes: ' + err.message)
    } finally {
      setSavingNotes(false)
    }
  }

  const handleDownloadReportPDF = (eventId) => {
    window.open(`${API}/reports/${eventId}/download`, '_blank')
  }

  const handleExportCourtPackage = (eventId) => {
    window.open(`${API}/events/${eventId}/export-evidence?user_id=Officer_Duty`, '_blank')
  }

  const handleViewCustody = async (eventId) => {
    setLoadingCustody(true)
    setShowCustodyDrawer(true)
    try {
      const res = await axios.get(`${API}/events/${eventId}/custody-log`)
      setCustodyLogs(res.data)
    } catch (err) {
      console.error('Failed to load custody log:', err)
    } finally {
      setLoadingCustody(false)
    }
  }

  const all = [
    ...liveAlerts.filter(la => !alerts.find(a => a.id === la.id)),
    ...alerts,
  ]

  return (
    <div style={{ paddingBottom: 40 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Forensic Alert Feed</h1>
          <p className="page-subtitle">Real-time incident detection, evidence packaging, and police reporting dossier</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchAlerts} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Feed
        </button>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Filter size={14} color="var(--text-muted)" />
        <select
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
          style={{
            background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            color: 'var(--text-primary)', borderRadius: 6, padding: '6px 12px',
            fontSize: '0.8rem', cursor: 'pointer',
          }}
        >
          <option value="">All Statuses</option>
          <option value="new">New / Unhandled</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved / Confirmed</option>
          <option value="dismissed">Dismissed</option>
        </select>

        <select
          value={filter.rule_type}
          onChange={e => setFilter(f => ({ ...f, rule_type: e.target.value }))}
          style={{
            background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            color: 'var(--text-primary)', borderRadius: 6, padding: '6px 12px',
            fontSize: '0.8rem', cursor: 'pointer',
          }}
        >
          <option value="">All Violation Rules</option>
          {Object.entries(RULE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>

        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {all.length} total incidents
        </span>
      </div>

      {/* Alert Table */}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Rule / Crime Category</th>
                <th>Camera ID</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Time</th>
                <th>Forensic Actions</th>
              </tr>
            </thead>
            <tbody>
              {all.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    No alerts found.
                  </td>
                </tr>
              ) : (
                all.slice(0, 100).map(a => (
                  <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => setSelected(a)}>
                    <td>
                      <span className={`alert-severity-badge badge-${a.severity}`}>
                        {SEV_EMOJI[a.severity] || '🟡'} {a.severity}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                      {RULE_LABELS[a.rule_type] || a.rule_type.replace('_', ' ')}
                    </td>
                    <td>
                      <code style={{ fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>{a.camera_id}</code>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div className="conf-bar" style={{ width: 60 }}>
                          <div className="conf-fill" style={{ width: `${a.confidence * 100}%` }} />
                        </div>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                          {(a.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`alert-severity-badge badge-${a.status}`}>{a.status}</span>
                    </td>
                    <td className="alert-time">
                      {a.timestamp ? formatDistanceToNow(new Date(a.timestamp), { addSuffix: true }) : '—'}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '4px 8px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4 }}
                          title="Download PDF Incident Dossier"
                          onClick={() => handleDownloadReportPDF(a.id)}
                        >
                          <FileText size={12} color="#3b82f6" /> PDF
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '4px 8px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4 }}
                          title="Export Court Evidence ZIP"
                          onClick={() => handleExportCourtPackage(a.id)}
                        >
                          <Archive size={12} color="#10b981" /> ZIP
                        </button>
                        {a.status === 'new' && (
                          <>
                            <button
                              className="btn btn-primary"
                              style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                              onClick={() => updateAlert(a.id, 'acknowledged')}
                            >
                              ACK
                            </button>
                            <button
                              className="btn btn-danger"
                              style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                              onClick={() => updateAlert(a.id, 'dismissed')}
                            >
                              Dismiss
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed Alert Forensic Modal */}
      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" style={{ maxWidth: 640 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
                  {SEV_EMOJI[selected.severity] || '🔴'} {RULE_LABELS[selected.rule_type] || selected.rule_type}
                </h2>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                  Incident ID: {selected.id}
                </span>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelected(null)}>✕</button>
            </div>

            {selected.snapshot_url && (
              <img
                src={`http://localhost:8000${selected.snapshot_url}`}
                alt="Evidence Snapshot"
                style={{ width: '100%', borderRadius: 8, marginBottom: 14, maxHeight: 260, objectFit: 'cover' }}
                onError={e => e.target.style.display = 'none'}
              />
            )}

            {/* Metadata Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {Object.entries({
                'Camera / Sensor': selected.camera_id,
                'Zone / Area': selected.explanation?.zone_name || selected.zone_id || 'General Field',
                'Confidence': `${(selected.confidence * 100).toFixed(0)}%`,
                'Track IDs': selected.track_ids?.join(', ') || 'N/A',
                'Violation Telemetry': selected.explanation?.dwell_time ? `${selected.explanation.dwell_time}s dwell` : (selected.explanation?.description || 'Standard violation'),
                'SHA-256 Checksum': selected.clip_hash ? `${selected.clip_hash.slice(0, 16)}...` : 'Verified on export',
                'Status': selected.status.toUpperCase(),
                'Timestamp': selected.timestamp ? new Date(selected.timestamp).toUTCString() : '—',
              }).map(([k, v]) => (
                <div key={k} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginTop: 2, fontWeight: 500 }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Police Actions Toolbar */}
            <div style={{
              background: 'rgba(59, 130, 246, 0.08)', borderRadius: 8, padding: '12px',
              border: '1px solid rgba(59, 130, 246, 0.2)', marginBottom: 16,
              display: 'flex', gap: 10, flexWrap: 'wrap'
            }}>
              <button
                className="btn btn-primary"
                onClick={() => handleDownloadReportPDF(selected.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', background: '#2563eb' }}
              >
                <FileText size={14} /> Auto-Generated Report (PDF)
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleExportCourtPackage(selected.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', background: '#059669' }}
              >
                <Archive size={14} /> Court Evidence Bundle (.ZIP)
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => handleOpenNotes(selected)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem' }}
              >
                <Edit3 size={14} /> Officer Notes
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => handleViewCustody(selected.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem' }}
              >
                <History size={14} /> Custody Log
              </button>
            </div>

            {/* Status Update Buttons */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              {selected.status === 'new' && (
                <button className="btn btn-primary" onClick={() => updateAlert(selected.id, 'acknowledged')} disabled={updating}>
                  Acknowledge
                </button>
              )}
              {selected.status !== 'resolved' && (
                <button className="btn btn-success" onClick={() => updateAlert(selected.id, 'resolved')} disabled={updating}>
                  Confirm & Resolve Incident
                </button>
              )}
              {selected.status !== 'dismissed' && (
                <button className="btn btn-danger" onClick={() => updateAlert(selected.id, 'dismissed')} disabled={updating}>
                  Dismiss
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Officer Notes Modal */}
      {showNotesModal && (
        <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => setShowNotesModal(false)}>
          <div className="modal" style={{ maxWidth: 500 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Edit3 size={16} color="#3b82f6" /> Investigating Officer Diary Notes
              </h3>
              <button className="btn btn-ghost" onClick={() => setShowNotesModal(false)}>✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Responding Officer / Badge Reference
                </label>
                <input
                  type="text"
                  value={reportingOfficer}
                  onChange={e => setReportingOfficer(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 12px', background: 'var(--bg-secondary)',
                    border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                    fontSize: '0.8rem'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Case Observations / Action Taken
                </label>
                <textarea
                  rows={4}
                  value={officerNotes}
                  onChange={e => setOfficerNotes(e.target.value)}
                  placeholder="Enter preliminary investigation notes, suspect description, or dispatch instructions..."
                  style={{
                    width: '100%', padding: '8px 12px', background: 'var(--bg-secondary)',
                    border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                    fontSize: '0.8rem', resize: 'vertical'
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="btn btn-ghost" onClick={() => setShowNotesModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveNotes} disabled={savingNotes}>
                {savingNotes ? 'Saving & Generating PDF...' : 'Save & Update Report'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chain of Custody Audit Log Drawer */}
      {showCustodyDrawer && (
        <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => setShowCustodyDrawer(false)}>
          <div className="modal" style={{ maxWidth: 540 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <ShieldCheck size={16} color="#10b981" /> Chain of Custody Audit Trail (FR 4)
              </h3>
              <button className="btn btn-ghost" onClick={() => setShowCustodyDrawer(false)}>✕</button>
            </div>

            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 14px 0' }}>
              Immutable audit history of all forensic accesses and exports for this incident dossier.
            </p>

            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
              {loadingCustody ? (
                <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>Loading audit log...</div>
              ) : custodyLogs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  No access records yet. Any view or export action will be recorded here.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {custodyLogs.map((log) => (
                    <div
                      key={log.id}
                      style={{
                        padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: 6,
                        borderLeft: `3px solid ${log.action === 'exported' ? '#10b981' : '#3b82f6'}`
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase' }}>
                          ACTION: {log.action}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                        User / Officer: <strong>{log.user_id}</strong>
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 2 }}>
                        {log.details || 'Standard access'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
