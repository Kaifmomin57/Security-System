import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Flame,
  Calendar,
  Filter,
  Download,
  Clock,
  MapPin,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  Shield,
  Layers
} from 'lucide-react'

const API = 'http://localhost:8000/api/v1'

const RULE_LABELS = {
  all: 'All Violation Types',
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

export default function PatrolHeatmapPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('zones') // 'zones' | 'cameras'
  const [filterRule, setFilterRule] = useState('all')
  const [filterCamera, setFilterCamera] = useState('all')
  const [selectedCell, setSelectedCell] = useState(null)

  const fetchHeatmap = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filterRule !== 'all') params.rule_type = filterRule
      if (filterCamera !== 'all') params.camera_id = filterCamera
      const res = await axios.get(`${API}/analytics/heatmap`, { params })
      setData(res.data)
    } catch (err) {
      console.error('Failed to load heatmap data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHeatmap()
  }, [filterRule, filterCamera])

  const handleExportCSV = () => {
    const params = new URLSearchParams()
    if (filterRule !== 'all') params.append('rule_type', filterRule)
    if (filterCamera !== 'all') params.append('camera_id', filterCamera)
    window.open(`${API}/analytics/heatmap/export?${params.toString()}`, '_blank')
  }

  // Color intensity calculation
  const getCellColor = (count, maxCount) => {
    if (!count || count === 0) return 'rgba(255, 255, 255, 0.02)'
    const ratio = Math.min(1.0, count / Math.max(1, maxCount))
    if (ratio < 0.25) return 'rgba(56, 189, 248, 0.25)' // sky blue
    if (ratio < 0.5) return 'rgba(234, 179, 8, 0.45)'  // amber
    if (ratio < 0.75) return 'rgba(249, 115, 22, 0.7)' // orange
    return 'rgba(239, 68, 68, 0.9)'                     // police red
  }

  const items = (data && (viewMode === 'zones' ? data.zones : data.cameras)) || []
  const maxIncidentInGrid = items.reduce((max, it) => Math.max(max, ...it.hourly_counts), 1)

  return (
    <div style={{ paddingBottom: 40 }}>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'linear-gradient(135deg, #ef4444, #991b1b)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 15px rgba(239, 68, 68, 0.4)'
            }}>
              <Flame size={20} color="#fff" />
            </div>
            <div>
              <h1 className="page-title" style={{ margin: 0 }}>Historical Incident Heatmap</h1>
              <p className="page-subtitle" style={{ margin: 0 }}>
                Hourly risk density analytics for data-informed police patrol deployment (FR 1)
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={fetchHeatmap} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={handleExportCSV}
            style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#2563eb' }}
          >
            <Download size={14} /> Export Patrol CSV
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 20 }}>
          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 8, background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#60a5fa' }}>
              <TrendingUp size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Total Incidents</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)' }}>{data.summary.total_incidents}</div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 8, background: 'rgba(239, 68, 68, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f87171' }}>
              <Clock size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Peak Risk Hour</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--alert-high)' }}>
                {String(data.summary.peak_hour).padStart(2, '0')}:00 – {String(data.summary.peak_hour + 1).padStart(2, '0')}:00
              </div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 8, background: 'rgba(245, 158, 11, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fbbf24' }}>
              <MapPin size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Highest Risk Zone</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 170 }}>
                {data.summary.peak_zone}
              </div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 8, background: 'rgba(168, 85, 247, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c084fc' }}>
              <AlertTriangle size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Primary Violation</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                {RULE_LABELS[data.summary.peak_rule] || data.summary.peak_rule.replace('_', ' ')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter & View Controls */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Filter size={14} color="var(--text-muted)" />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Filters:</span>
        </div>

        {/* Rule Filter */}
        <select
          value={filterRule}
          onChange={e => setFilterRule(e.target.value)}
          style={{
            background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            color: 'var(--text-primary)', borderRadius: 6, padding: '6px 12px',
            fontSize: '0.8rem', cursor: 'pointer',
          }}
        >
          {Object.entries(RULE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>

        {/* View Mode Toggle */}
        <div style={{ display: 'flex', background: 'var(--bg-secondary)', borderRadius: 6, padding: 3, border: '1px solid var(--border)' }}>
          <button
            onClick={() => setViewMode('zones')}
            style={{
              padding: '4px 12px', borderRadius: 4, border: 'none', cursor: 'pointer',
              fontSize: '0.75rem', fontWeight: 600,
              background: viewMode === 'zones' ? '#2563eb' : 'transparent',
              color: viewMode === 'zones' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            By Monitored Zone
          </button>
          <button
            onClick={() => setViewMode('cameras')}
            style={{
              padding: '4px 12px', borderRadius: 4, border: 'none', cursor: 'pointer',
              fontSize: '0.75rem', fontWeight: 600,
              background: viewMode === 'cameras' ? '#2563eb' : 'transparent',
              color: viewMode === 'cameras' ? '#fff' : 'var(--text-secondary)',
            }}
          >
            By Camera Feed
          </button>
        </div>

        {/* Color Legend */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          <span>Low Risk</span>
          <div style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(56, 189, 248, 0.4)' }} />
          <div style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(234, 179, 8, 0.6)' }} />
          <div style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(249, 115, 22, 0.8)' }} />
          <div style={{ width: 12, height: 12, borderRadius: 2, background: 'rgba(239, 68, 68, 1)' }} />
          <span>High Risk (Dispatch Patrol)</span>
        </div>
      </div>

      {/* Heatmap Matrix Table */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--border)', minWidth: 160 }}>
                  {viewMode === 'zones' ? 'Zone / Area Name' : 'Camera ID'}
                </th>
                {Array.from({ length: 24 }).map((_, h) => (
                  <th key={h} style={{ textAlign: 'center', padding: '8px 4px', borderBottom: '1px solid var(--border)', minWidth: 28, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono' }}>
                    {String(h).padStart(2, '0')}
                  </th>
                ))}
                <th style={{ textAlign: 'center', padding: '8px 8px', borderBottom: '1px solid var(--border)', minWidth: 60 }}>
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={26} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    No incident records match the selected filter.
                  </td>
                </tr>
              ) : (
                items.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.03)' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Shield size={12} color="#3b82f6" />
                        {viewMode === 'zones' ? row.zone_name : row.camera_name}
                      </div>
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                        {viewMode === 'zones' ? `Cam: ${row.camera_id}` : `ID: ${row.camera_id}`}
                      </span>
                    </td>
                    {row.hourly_counts.map((count, h) => {
                      const bg = getCellColor(count, maxIncidentInGrid)
                      return (
                        <td
                          key={h}
                          onClick={() => setSelectedCell({ name: viewMode === 'zones' ? row.zone_name : row.camera_name, hour: h, count })}
                          style={{
                            textAlign: 'center',
                            padding: 0,
                            height: 34,
                            background: bg,
                            cursor: count > 0 ? 'pointer' : 'default',
                            transition: 'all 0.15s ease',
                            border: '1px solid rgba(0,0,0,0.2)',
                            position: 'relative'
                          }}
                          title={`${viewMode === 'zones' ? row.zone_name : row.camera_name} at ${h}:00 — ${count} incident(s)`}
                        >
                          {count > 0 && (
                            <span style={{
                              fontWeight: 700,
                              fontSize: '0.7rem',
                              color: count > 2 ? '#ffffff' : 'var(--text-primary)',
                              textShadow: '0 1px 2px rgba(0,0,0,0.8)'
                            }}>
                              {count}
                            </span>
                          )}
                        </td>
                      )
                    })}
                    <td style={{ textAlign: 'center', padding: '8px 8px', fontWeight: 700, color: row.total_incidents > 0 ? '#f87171' : 'var(--text-muted)' }}>
                      {row.total_incidents}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Patrol Recommendation Banner */}
      {data && data.summary.total_incidents > 0 && (
        <div style={{
          marginTop: 20,
          background: 'linear-gradient(90deg, rgba(37, 99, 235, 0.1), rgba(239, 68, 68, 0.1))',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: 8,
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 16
        }}>
          <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(59, 130, 246, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#60a5fa', flexShrink: 0 }}>
            <Shield size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Tactical Patrol Recommendation
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>
              Deploy patrol units to <strong>{data.summary.peak_zone}</strong> between <strong>{String(data.summary.peak_hour).padStart(2, '0')}:00 and {String(data.summary.peak_hour + 1).padStart(2, '0')}:00</strong>. Historical data indicates a significant spike in <strong>{RULE_LABELS[data.summary.peak_rule] || data.summary.peak_rule}</strong> alerts during this time window.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
