import { useState, useEffect } from 'react'
import axios from 'axios'
import { Camera, Wifi, WifiOff, Plus } from 'lucide-react'

const API = 'http://localhost:8000/api/v1'

export default function CamerasPage({ liveAlerts }) {
  const [cameras, setCameras] = useState([])

  const fetchCameras = async () => {
    try {
      const r = await axios.get(`${API}/cameras`)
      setCameras(r.data)
    } catch (_) {}
  }

  useEffect(() => {
    fetchCameras()
    const t = setInterval(fetchCameras, 8000)
    return () => clearInterval(t)
  }, [])

  const getCameraAlerts = (camId) =>
    liveAlerts.filter(a => a.camera_id === camId && a.status === 'new')

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Cameras</h1>
          <p className="page-subtitle">Registered camera feeds and status</p>
        </div>
        <button className="btn btn-primary"><Plus size={14} /> Add Camera</button>
      </div>

      {cameras.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <Camera size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p style={{ color: 'var(--text-muted)' }}>No cameras registered yet.</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 6 }}>
            Start the pipeline — it auto-registers the camera on first run.
          </p>
        </div>
      )}

      <div className="camera-grid">
        {cameras.map(cam => {
          const activeAlerts = getCameraAlerts(cam.id)
          const hasAlert = activeAlerts.length > 0
          return (
            <div key={cam.id} className={`camera-feed ${hasAlert ? 'alert-active' : ''}`}>
              <div className="camera-feed-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="camera-status-dot"
                    style={{ background: cam.status === 'online' ? 'var(--alert-ok)' : 'var(--alert-high)' }}
                  />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>{cam.name}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {hasAlert && (
                    <span className="alert-severity-badge badge-high">
                      {activeAlerts.length} ALERT{activeAlerts.length > 1 ? 'S' : ''}
                    </span>
                  )}
                  {cam.status === 'online'
                    ? <Wifi size={14} color="var(--alert-ok)" />
                    : <WifiOff size={14} color="var(--alert-high)" />
                  }
                </div>
              </div>

              <div className="camera-screen">
                {hasAlert && (
                  <div className="alert-overlay">
                    ⚠ {activeAlerts[0]?.rule_type?.toUpperCase()}
                  </div>
                )}
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {cam.status === 'online' ? '🎥 Live feed' : '⛔ Offline'}
                </span>
              </div>

              <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                  {cam.id}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {cam.source_url}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
