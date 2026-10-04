import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Car,
  ShieldAlert,
  Search,
  Plus,
  Trash2,
  CheckCircle,
  AlertOctagon,
  RefreshCw,
  Camera,
  UploadCloud,
  FileCheck,
  Zap
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const API = 'http://localhost:8000/api/v1'

export default function ANPRWatchlistPage() {
  const [watchlist, setWatchlist] = useState([])
  const [plateReads, setPlateReads] = useState([])
  const [loading, setLoading] = useState(false)
  const [filterMatchedOnly, setFilterMatchedOnly] = useState(false)

  // Add Watchlist Modal state
  const [newPlate, setNewPlate] = useState('')
  const [newReason, setNewReason] = useState('Reported Stolen')
  const [addingOfficer, setAddingOfficer] = useState('Control Room Officer')
  const [isAdding, setIsAdding] = useState(false)

  // Interactive Test Scanner state
  const [testPlateInput, setTestPlateInput] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [scanning, setScanning] = useState(false)

  const fetchWatchlist = async () => {
    try {
      const res = await axios.get(`${API}/watchlist`)
      setWatchlist(res.data)
    } catch (e) {
      console.error('Failed to load watchlist:', e)
    }
  }

  const fetchPlateReads = async () => {
    setLoading(true)
    try {
      const params = { limit: 50 }
      if (filterMatchedOnly) params.matched = true
      const res = await axios.get(`${API}/plate-reads`, { params })
      setPlateReads(res.data)
    } catch (e) {
      console.error('Failed to load plate reads:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWatchlist()
    fetchPlateReads()
  }, [filterMatchedOnly])

  const handleAddToWatchlist = async (e) => {
    e.preventDefault()
    if (!newPlate.trim()) return
    setIsAdding(true)
    try {
      await axios.post(`${API}/watchlist`, {
        plate_number: newPlate.trim(),
        reason: newReason,
        added_by: addingOfficer,
      })
      setNewPlate('')
      fetchWatchlist()
    } catch (err) {
      alert('Failed to add plate to watchlist: ' + (err.response?.data?.detail || err.message))
    } finally {
      setIsAdding(false)
    }
  }

  const handleDeleteWatchlist = async (plateNumber) => {
    if (!confirm(`Remove plate ${plateNumber} from watchlist?`)) return
    try {
      await axios.delete(`${API}/watchlist/${plateNumber}`)
      fetchWatchlist()
    } catch (err) {
      alert('Failed to remove plate: ' + err.message)
    }
  }

  const handleTestScan = async () => {
    setScanning(true)
    setScanResult(null)
    try {
      const res = await axios.post(`${API}/anpr/scan`, {
        plate_number: testPlateInput.trim() || 'DL01AB9876',
        camera_id: 'cam_01',
      })
      setScanResult(res.data)
      fetchPlateReads()
    } catch (err) {
      alert('Plate scan failed: ' + err.message)
    } finally {
      setScanning(false)
    }
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)'
            }}>
              <Car size={20} color="#fff" />
            </div>
            <div>
              <h1 className="page-title" style={{ margin: 0 }}>ANPR & Watchlist Intercept System</h1>
              <p className="page-subtitle" style={{ margin: 0 }}>
                Automatic Number Plate Recognition & Flagged Vehicle Watchlist Matching (FR 3)
              </p>
            </div>
          </div>
        </div>

        <button className="btn btn-ghost" onClick={() => { fetchWatchlist(); fetchPlateReads(); }} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh Feeds
        </button>
      </div>

      {/* Grid Layout: Left Column = Watchlist & Scanner, Right Column = Live Plate OCR Feed */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 420px) 1fr', gap: 20 }}>
        
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Add Plate Form */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <ShieldAlert size={16} color="#ef4444" />
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0 }}>Add Vehicle to Hotlist / Watchlist</h3>
            </div>

            <form onSubmit={handleAddToWatchlist} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  License Plate Number
                </label>
                <input
                  type="text"
                  placeholder="e.g. DL01AB9876"
                  value={newPlate}
                  onChange={e => setNewPlate(e.target.value.toUpperCase())}
                  style={{
                    width: '100%', padding: '8px 12px', background: 'var(--bg-secondary)',
                    border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                    fontFamily: 'JetBrains Mono', fontWeight: 600, fontSize: '0.85rem'
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Flag Reason / Crime Category
                </label>
                <select
                  value={newReason}
                  onChange={e => setNewReason(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 12px', background: 'var(--bg-secondary)',
                    border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                    fontSize: '0.8rem'
                  }}
                >
                  <option value="Reported Stolen (FIR Recorded)">Reported Stolen (FIR Recorded)</option>
                  <option value="Wanted Suspect / Fleeing Vehicle">Wanted Suspect / Fleeing Vehicle</option>
                  <option value="Hit-and-Run Intercept Alert">Hit-and-Run Intercept Alert</option>
                  <option value="Unregistered / Fake Plate Series">Unregistered / Fake Plate Series</option>
                  <option value="VIP Escort / Priority Surveillance">VIP Escort / Priority Surveillance</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  Investigating Unit / Officer
                </label>
                <input
                  type="text"
                  value={addingOfficer}
                  onChange={e => setAddingOfficer(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 12px', background: 'var(--bg-secondary)',
                    border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                    fontSize: '0.8rem'
                  }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isAdding}
                style={{ marginTop: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, background: '#dc2626' }}
              >
                <Plus size={14} /> {isAdding ? 'Flagging...' : 'Add to Active Watchlist'}
              </button>
            </form>
          </div>

          {/* Interactive OCR Plate Scanner Test */}
          <div className="card" style={{ border: '1px solid rgba(59, 130, 246, 0.3)', background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9))' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Zap size={16} color="#60a5fa" />
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0 }}>ANPR Live Scan Simulator</h3>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 12px 0' }}>
              Test plate recognition and trigger instant high-severity watchlist alert:
            </p>

            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                type="text"
                placeholder="DL01AB9876"
                value={testPlateInput}
                onChange={e => setTestPlateInput(e.target.value.toUpperCase())}
                style={{
                  flex: 1, padding: '8px 12px', background: 'var(--bg-secondary)',
                  border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)',
                  fontFamily: 'JetBrains Mono', fontSize: '0.85rem'
                }}
              />
              <button
                className="btn btn-primary"
                onClick={handleTestScan}
                disabled={scanning}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <Camera size={14} /> {scanning ? 'Scanning...' : 'Scan'}
              </button>
            </div>

            {scanResult && (
              <div style={{
                borderRadius: 6, padding: '10px 12px',
                background: scanResult.matched ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
                border: `1px solid ${scanResult.matched ? '#ef4444' : '#22c55e'}`
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: '0.9rem', color: '#fff' }}>
                    {scanResult.plate_number}
                  </span>
                  <span style={{
                    fontSize: '0.68rem', fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                    background: scanResult.matched ? '#ef4444' : '#22c55e', color: '#fff'
                  }}>
                    {scanResult.matched ? '🚨 WATCHLIST HIT' : '✔ CLEAR'}
                  </span>
                </div>
                {scanResult.matched && (
                  <div style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: 4 }}>
                    Reason: <strong>{scanResult.reason}</strong>
                  </div>
                )}
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
                  Confidence: {(scanResult.ocr_confidence * 100).toFixed(0)}% • Action: {scanResult.action}
                </div>
              </div>
            )}
          </div>

          {/* Active Watchlist Table */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0 }}>Active Watchlist ({watchlist.length})</h3>
            </div>

            <div style={{ maxHeight: 220, overflowY: 'auto' }}>
              {watchlist.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  No vehicles currently watchlisted.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {watchlist.map((w) => (
                    <div
                      key={w.plate_number}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6,
                        borderLeft: '3px solid #ef4444'
                      }}
                    >
                      <div>
                        <div style={{ fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                          {w.plate_number}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#f87171' }}>{w.reason}</div>
                      </div>
                      <button
                        onClick={() => handleDeleteWatchlist(w.plate_number)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
                        title="Remove from watchlist"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Live Plate Reads Log */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0 }}>Live OCR Plate Reads Feed</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: 0 }}>
                Real-time number plate stream across all junction and gate cameras
              </p>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={filterMatchedOnly}
                  onChange={e => setFilterMatchedOnly(e.target.checked)}
                />
                Watchlist Hits Only
              </label>
            </div>
          </div>

          <div className="table-wrap" style={{ flex: 1 }}>
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>License Plate</th>
                  <th>Camera ID</th>
                  <th>OCR Confidence</th>
                  <th>Reason / Category</th>
                  <th>Time Detected</th>
                </tr>
              </thead>
              <tbody>
                {plateReads.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                      No license plate reads recorded yet.
                    </td>
                  </tr>
                ) : (
                  plateReads.map((pr) => (
                    <tr key={pr.id} style={{ background: pr.matched ? 'rgba(239, 68, 68, 0.05)' : 'transparent' }}>
                      <td>
                        {pr.matched ? (
                          <span style={{
                            fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                            background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', border: '1px solid #ef4444',
                            display: 'inline-flex', alignItems: 'center', gap: 4
                          }}>
                            <AlertOctagon size={12} /> HIT
                          </span>
                        ) : (
                          <span style={{
                            fontSize: '0.7rem', fontWeight: 600, padding: '3px 8px', borderRadius: 4,
                            background: 'rgba(34, 197, 94, 0.1)', color: '#22c55e',
                            display: 'inline-flex', alignItems: 'center', gap: 4
                          }}>
                            <CheckCircle size={12} /> OK
                          </span>
                        )}
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: '0.85rem',
                          color: pr.matched ? '#fca5a5' : 'var(--text-primary)',
                          background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4
                        }}>
                          {pr.plate_number}
                        </span>
                      </td>
                      <td>
                        <code style={{ fontSize: '0.75rem' }}>{pr.camera_id}</code>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div className="conf-bar" style={{ width: 60 }}>
                            <div
                              className="conf-fill"
                              style={{
                                width: `${pr.ocr_confidence * 100}%`,
                                background: pr.ocr_confidence > 0.8 ? 'var(--accent-emerald)' : 'var(--alert-medium)'
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                            {(pr.ocr_confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td style={{ fontSize: '0.75rem', color: pr.matched ? '#ef4444' : 'var(--text-secondary)' }}>
                        {pr.reason || 'General Vehicle Passage'}
                      </td>
                      <td className="alert-time">
                        {pr.timestamp ? formatDistanceToNow(new Date(pr.timestamp), { addSuffix: true }) : '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
