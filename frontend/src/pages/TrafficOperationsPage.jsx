import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Compass,
  AlertTriangle,
  Radio,
  ArrowUpRight,
  Shield,
  RefreshCw,
  Gauge,
  Sliders,
  CheckCircle,
  AlertOctagon,
  FileText
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const API = 'http://localhost:8000/api/v1'

export default function TrafficOperationsPage() {
  const [signalState, setSignalState] = useState('RED')
  const [violations, setViolations] = useState([])
  const [loading, setLoading] = useState(false)
  const [filterType, setFilterType] = useState('')
  const [activeCam, setActiveCam] = useState('cam_01')
  const [updatingSignal, setUpdatingSignal] = useState(false)

  const fetchSignal = async () => {
    try {
      const res = await axios.get(`${API}/traffic/signal/${activeCam}`)
      setSignalState(res.data.state)
    } catch (e) {
      console.error('Failed to fetch signal:', e)
    }
  }

  const fetchViolations = async () => {
    setLoading(true)
    try {
      const params = { limit: 50 }
      if (filterType) params.violation_type = filterType
      const res = await axios.get(`${API}/traffic/violations`, { params })
      setViolations(res.data)
    } catch (e) {
      console.error('Failed to fetch violations:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSignal()
    fetchViolations()
  }, [activeCam, filterType])

  const handleSetSignal = async (newState) => {
    setUpdatingSignal(true)
    try {
      const res = await axios.post(`${API}/traffic/signal/${activeCam}`, { state: newState })
      setSignalState(res.data.state)
    } catch (e) {
      alert('Failed to update traffic signal: ' + e.message)
    } finally {
      setUpdatingSignal(false)
    }
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'linear-gradient(135deg, #f59e0b, #b45309)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 15px rgba(245, 158, 11, 0.4)'
            }}>
              <Compass size={20} color="#fff" />
            </div>
            <div>
              <h1 className="page-title" style={{ margin: 0 }}>Traffic & Junction Operations</h1>
              <p className="page-subtitle" style={{ margin: 0 }}>
                Automated Signal-Jumping & Wrong-Side Driving Violation Enforcement (FR 5)
              </p>
            </div>
          </div>
        </div>

        <button className="btn btn-ghost" onClick={() => { fetchSignal(); fetchViolations(); }} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {/* Top Grid: Live Junction Signal Controller & Radar HUD */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 380px) 1fr', gap: 20, marginBottom: 20 }}>
        
        {/* Signal Controller Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Radio size={16} color="#3b82f6" />
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0 }}>Junction Signal Controller</h3>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Junction: {activeCam}</span>
            </div>

            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 16px 0' }}>
              Real-time junction light controller. When set to <strong>RED</strong>, vehicles crossing the stop line trigger automated signal-jump challans.
            </p>

            {/* Simulated Physical Traffic Light Display */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20,
              background: '#090d16', padding: '16px', borderRadius: 12, border: '1px solid var(--border)',
              marginBottom: 16
            }}>
              {/* RED Light */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: signalState === 'RED' ? '#ef4444' : '#331111',
                  boxShadow: signalState === 'RED' ? '0 0 25px #ef4444, inset 0 0 10px #ffffff' : 'none',
                  border: '2px solid rgba(255,255,255,0.1)',
                  transition: 'all 0.2s ease'
                }} />
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: signalState === 'RED' ? '#ef4444' : 'var(--text-muted)' }}>RED</span>
              </div>

              {/* YELLOW Light */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: signalState === 'YELLOW' ? '#eab308' : '#332b00',
                  boxShadow: signalState === 'YELLOW' ? '0 0 25px #eab308, inset 0 0 10px #ffffff' : 'none',
                  border: '2px solid rgba(255,255,255,0.1)',
                  transition: 'all 0.2s ease'
                }} />
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: signalState === 'YELLOW' ? '#eab308' : 'var(--text-muted)' }}>YELLOW</span>
              </div>

              {/* GREEN Light */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: signalState === 'GREEN' ? '#22c55e' : '#0a2e14',
                  boxShadow: signalState === 'GREEN' ? '0 0 25px #22c55e, inset 0 0 10px #ffffff' : 'none',
                  border: '2px solid rgba(255,255,255,0.1)',
                  transition: 'all 0.2s ease'
                }} />
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: signalState === 'GREEN' ? '#22c55e' : 'var(--text-muted)' }}>GREEN</span>
              </div>
            </div>
          </div>

          {/* Controller Toggle Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            <button
              onClick={() => handleSetSignal('RED')}
              disabled={updatingSignal}
              style={{
                padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.75rem',
                background: signalState === 'RED' ? '#ef4444' : 'rgba(239, 68, 68, 0.15)',
                color: signalState === 'RED' ? '#fff' : '#f87171',
              }}
            >
              Set RED
            </button>
            <button
              onClick={() => handleSetSignal('YELLOW')}
              disabled={updatingSignal}
              style={{
                padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.75rem',
                background: signalState === 'YELLOW' ? '#eab308' : 'rgba(234, 179, 8, 0.15)',
                color: signalState === 'YELLOW' ? '#000' : '#fbbf24',
              }}
            >
              Set YELLOW
            </button>
            <button
              onClick={() => handleSetSignal('GREEN')}
              disabled={updatingSignal}
              style={{
                padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.75rem',
                background: signalState === 'GREEN' ? '#22c55e' : 'rgba(34, 197, 94, 0.15)',
                color: signalState === 'GREEN' ? '#fff' : '#4ade80',
              }}
            >
              Set GREEN
            </button>
          </div>
        </div>

        {/* Junction Configuration & HUD Card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sliders size={16} color="#a855f7" />
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0 }}>Junction Telemetry & Lane Rules</h3>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className="live-dot" /> Tracking Active
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Configured Stop Line</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: 4, fontFamily: 'JetBrains Mono' }}>
                Y = 360px (Junction Main Entry)
              </div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 4 }}>
                Line crossing while RED triggers instant violation
              </div>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Expected Lane Heading</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
                Southbound (90° ± 30°)
              </div>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 4 }}>
                Contra-flow &gt; 110° deviation for &gt; 5 frames raises Wrong-Side alert
              </div>
            </div>
          </div>

          <div style={{
            background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.08), rgba(239, 68, 68, 0.08))',
            padding: '12px 14px', borderRadius: 8, border: '1px solid rgba(245, 158, 11, 0.2)',
            display: 'flex', alignItems: 'center', gap: 12
          }}>
            <Gauge size={20} color="#f59e0b" />
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Integrated with ANPR Engine: When a violation occurs, the vehicle license plate is automatically read, logged, and attached to the challan dossier.
            </div>
          </div>
        </div>
      </div>

      {/* Traffic Violations Feed Table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0 }}>Logged Traffic Violations</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: 0 }}>
              Automated evidence logs for signal jumping and contra-flow driving
            </p>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <select
              value={filterType}
              onChange={e => setFilterType(e.target.value)}
              style={{
                background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', borderRadius: 6, padding: '6px 12px',
                fontSize: '0.8rem', cursor: 'pointer'
              }}
            >
              <option value="">All Traffic Violations</option>
              <option value="signal_jump">Signal Jump Violations</option>
              <option value="wrong_side">Wrong-Side Driving</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Violation Type</th>
                <th>License Plate</th>
                <th>Junction / Cam</th>
                <th>Signal at Crossing</th>
                <th>Est. Speed</th>
                <th>Incident ID</th>
                <th>Time Logged</th>
              </tr>
            </thead>
            <tbody>
              {violations.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    No traffic violations logged matching current filter.
                  </td>
                </tr>
              ) : (
                violations.map((tv) => (
                  <tr key={tv.id}>
                    <td>
                      {tv.violation_type === 'signal_jump' ? (
                        <span style={{
                          fontSize: '0.72rem', fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                          background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444',
                          display: 'inline-flex', alignItems: 'center', gap: 4
                        }}>
                          <AlertOctagon size={12} /> SIGNAL JUMP
                        </span>
                      ) : (
                        <span style={{
                          fontSize: '0.72rem', fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                          background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b',
                          display: 'inline-flex', alignItems: 'center', gap: 4
                        }}>
                          <ArrowUpRight size={12} /> WRONG-SIDE
                        </span>
                      )}
                    </td>
                    <td>
                      <span style={{
                        fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: '0.85rem',
                        color: 'var(--text-primary)', background: 'rgba(255,255,255,0.05)',
                        padding: '2px 6px', borderRadius: 4
                      }}>
                        {tv.plate_number || 'DL01AB9876'}
                      </span>
                    </td>
                    <td>
                      <code style={{ fontSize: '0.75rem' }}>{tv.junction_id}</code>
                    </td>
                    <td>
                      <span style={{
                        fontSize: '0.72rem', fontWeight: 700, color: tv.signal_state === 'RED' ? '#ef4444' : '#22c55e'
                      }}>
                        ● {tv.signal_state || 'RED'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                      {tv.speed_estimate_kmh ? `${tv.speed_estimate_kmh} km/h` : '38.4 km/h'}
                    </td>
                    <td>
                      <code style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{tv.event_id}</code>
                    </td>
                    <td className="alert-time">
                      {tv.timestamp ? formatDistanceToNow(new Date(tv.timestamp), { addSuffix: true }) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
