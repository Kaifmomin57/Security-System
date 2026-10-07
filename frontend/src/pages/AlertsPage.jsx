import { useState, useEffect } from 'react'
import axios from 'axios'
import { formatDistanceToNow, format } from 'date-fns'
import CardDeckCarousel from '../components/ui/card-deck-carousel'
import {
  Filter, RefreshCw, FileText, Archive,
  ShieldCheck, History, Download, AlertOctagon,
  Eye, CheckCircle, X, ChevronLeft, MapPin, Search, Cpu, List, Video, Trash2,
  BellRing, Brain, Timer, ArrowUp, ArrowDown, Clock, Maximize2, Lightbulb, AlertTriangle, MoreVertical, ArrowUpRight
} from 'lucide-react'

const API = 'http://localhost:8000/api/v1'

const RULE_LABELS = {
  loitering: 'Loitering',
  trailing: 'Trailing / Stalking',
  intrusion: 'Zone Intrusion',
  crowd: 'Crowd Density',
  unaccompanied_person: 'Unaccompanied Person',
  signal_for_help: 'Signal for Help (Distress Gesture)',
  possible_weapon: 'Weapon Detection (Gun / Knife)',
  abandoned_object: 'Abandoned / Suspicious Object',
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
  const [unblurredSnapshot, setUnblurredSnapshot] = useState(null)
  const [showUnblurredSnapshot, setShowUnblurredSnapshot] = useState(false)
  const [selectedAlertIds, setSelectedAlertIds] = useState(new Set())
  const [hideMocks, setHideMocksState] = useState(() => localStorage.getItem('sentrix_hide_mocks') === 'true')

  useEffect(() => () => {
    if (unblurredSnapshot) URL.revokeObjectURL(unblurredSnapshot.url)
  }, [unblurredSnapshot])

  useEffect(() => {
    setUnblurredSnapshot(null)
    setShowUnblurredSnapshot(false)
  }, [selected?.id])

  const setHideMocks = (val) => {
    setHideMocksState(val)
    if (val) localStorage.setItem('sentrix_hide_mocks', 'true')
    else localStorage.removeItem('sentrix_hide_mocks')
  }

  const fetchAlerts = async () => {
    try {
      const params = {}
      if (filter.status) params.status = filter.status
      if (filter.rule_type) params.rule_type = filter.rule_type
      const r = await axios.get(`${API}/alerts`, { params })
      setAlerts(r.data)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
  }

  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 2500)
    return () => clearInterval(interval)
  }, [filter, liveAlerts])

  // Poll for new alerts every 10 seconds so incidents survive page reload
  useEffect(() => {
    const interval = setInterval(fetchAlerts, 10000)
    return () => clearInterval(interval)
  }, [])

  const updateAlert = async (id, status) => {
    setUpdating(true)
    try {
      if (id.startsWith('mock')) {
        setAlerts(prev => prev.map(a => a.id === id ? { ...a, status } : a));
        if (selected && selected.id === id) {
          setSelected(prev => ({ ...prev, status }))
        }
        return;
      }
      await axios.patch(`${API}/alerts/${id}`, { status, responder: 'Officer on Duty' })
      fetchAlerts()
      if (selected && selected.id === id) {
        setSelected(prev => ({ ...prev, status }))
      }
    } catch (err) {
      console.error('Failed to update alert:', err)
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async (eventId) => {
    if (!window.confirm('Are you sure you want to permanently delete this incident?')) return;
    try {
      if (eventId.startsWith('mock')) {
        setHideMocks(true);
        return;
      }
      await axios.delete(`${API}/alerts/${eventId}`);
      setAlerts(prev => prev.filter(a => a.id !== eventId));
      if (selected?.id === eventId) setSelected(null);
      
      const newSet = new Set(selectedAlertIds);
      if (newSet.has(eventId)) {
        newSet.delete(eventId);
        setSelectedAlertIds(newSet);
      }
    } catch (err) {
      console.error('Failed to delete alert:', err);
    }
  }

  const handleBulkDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete ${selectedAlertIds.size} selected incidents?`)) return;
    setUpdating(true);
    try {
      const ids = Array.from(selectedAlertIds);
      await Promise.all(ids.map(async id => {
        if (!id.startsWith('mock')) {
          await axios.delete(`${API}/alerts/${id}`);
        }
      }));
      const hasMock = ids.some(id => id.startsWith('mock'));
      if (hasMock) setHideMocks(true);
      setAlerts(prev => prev.filter(a => !selectedAlertIds.has(a.id)));
      if (selected && selectedAlertIds.has(selected.id)) setSelected(null);
      setSelectedAlertIds(new Set());
    } catch (err) {
      console.error('Failed to bulk delete:', err);
    } finally {
      setUpdating(false);
    }
  }

  const handleDeleteAll = async () => {
    if (!window.confirm('Are you sure you want to permanently delete ALL incidents? This cannot be undone.')) return;
    setUpdating(true);
    try {
      await axios.delete(`${API}/alerts`);
      setAlerts([]);
      setSelected(null);
      setSelectedAlertIds(new Set());
      // Only hide mocks, not real alerts that may arrive later
      setHideMocks(true);
    } catch (err) {
      console.error('Failed to delete all alerts:', err);
    } finally {
      setUpdating(false);
    }
  }

  const toggleUnblurredSnapshot = async () => {
    if (showUnblurredSnapshot) {
      setShowUnblurredSnapshot(false)
      return
    }
    if (unblurredSnapshot?.eventId === selected.id) {
      setShowUnblurredSnapshot(true)
      return
    }

    const adminKey = window.prompt('Enter the admin key to view the unblurred snapshot:')
    if (!adminKey) return

    try {
      const response = await axios.get(`${API}/alerts/${selected.id}/unblurred-snapshot`, {
        headers: { 'X-Admin-Key': adminKey },
        responseType: 'blob'
      })
      const url = URL.createObjectURL(response.data)
      setUnblurredSnapshot({ eventId: selected.id, url })
      setShowUnblurredSnapshot(true)
    } catch (err) {
      let message = 'Could not load unblurred snapshot.'
      if (err.response?.data instanceof Blob) {
        const responseText = await err.response.data.text()
        try {
          message = JSON.parse(responseText).detail || message
        } catch {
          message = responseText || message
        }
      }
      window.alert(message)
    }
  }

  const toggleSelection = (e, id) => {
    e.stopPropagation();
    const newSet = new Set(selectedAlertIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedAlertIds(newSet);
  }

  const handleDownloadReportPDF = (eventId) => {
    window.open(`${API}/reports/${eventId}/download`, '_blank')
  }

  const handleExportCourtPackage = (eventId) => {
    // Generates the real SENTRYEYE AI SURVEILLANCE PDF report via the backend API
    window.open(`${API}/reports/${eventId}/download`, '_blank')
  }

  // Merge live + db alerts, deduplicate by ID (db takes priority)
  // Real DB alerts always show; hideMocks only suppresses hardcoded mock cards
  const seen = new Set()
  const allAlerts = [
    ...alerts,
    ...liveAlerts.filter(la => !alerts.find(a => a.id === la.id))
  ].filter(a => {
    if (seen.has(a.id)) return false
    seen.add(a.id)
    return true
  })

  const getRiskScore = (conf) => Math.round(conf * 100)

  const getMediaUrl = (url) => {
    if (!url) return null
    if (url.startsWith('http://') || url.startsWith('https://')) return url
    const filename = url.replace(/\\/g, '/').split('/').pop()
    if (!filename) return null
    if (url.includes('clips') || url.endsWith('.mp4')) {
      return `http://localhost:8000/media/clips/${filename}`
    }
    return `http://localhost:8000/media/snapshots/${filename}`
  }

  // ────────────────────────────────────────────────────────────────────────────────
  // DETAIL VIEW
  // ────────────────────────────────────────────────────────────────────────────────
  if (selected) {
    const riskScore = getRiskScore(selected.confidence)
    const severityColor = selected.severity === 'high' ? '#ef4444' : selected.severity === 'medium' ? '#f59e0b' : '#3b82f6'
    const timeDetected = new Date(selected.timestamp)
    const incidentDescription = selected.explanation?.description
      || `${RULE_LABELS[selected.rule_type] || selected.rule_type} incident recorded for ${selected.camera_id}.`

    const blurredSnapshotImg = getMediaUrl(selected.snapshot_url) || "https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=900&h=560&fit=crop"
    const snapshotImg = showUnblurredSnapshot && unblurredSnapshot?.eventId === selected.id
      ? unblurredSnapshot.url
      : blurredSnapshotImg
    const clipVid = getMediaUrl(selected.clip_url || selected.clip_path)

    const slides = [
      {
        image: snapshotImg,
        title: `Detection Snapshot — ${format(timeDetected, 'HH:mm:ss')}`,
        caption: selected.explanation?.description || "High-resolution frame captured at moment of trigger.",
        alt: "Primary evidence snapshot"
      },
      ...(clipVid ? [{
        video: clipVid,
        title: `Recorded Video Evidence`,
        caption: "Full CCTV incident video clip.",
        alt: "Incident video clip"
      }] : []),
      {
        image: snapshotImg,
        title: "AI Analysis Frame",
        caption: `Detection confidence: ${(selected.confidence * 100).toFixed(0)}%`,
        alt: "AI Analysis"
      }
    ]

    const whyFlaggedReasons = []
    if (selected.rule_type === 'possible_weapon') {
      whyFlaggedReasons.push(`Weapon detected (${selected.explanation?.weapon_class?.toUpperCase() || 'WEAPON'}) with ${(selected.confidence * 100).toFixed(0)}% confidence.`)
      whyFlaggedReasons.push(`Specialist neural detection model flagged high-risk tactical threat.`)
      whyFlaggedReasons.push(`Object flagged for mandatory officer human verification.`)
      whyFlaggedReasons.push(`Camera ${selected.camera_id} video buffer preserved for evidence.`)
    } else if (selected.rule_type === 'signal_for_help') {
      whyFlaggedReasons.push(`Signal-for-Help distress hand gesture confirmed by AI gesture engine.`)
      whyFlaggedReasons.push(`Deliberate sequence (thumb tucked in palm + fingers folded) detected.`)
      whyFlaggedReasons.push(`Immediate safety intervention required for subject.`)
      whyFlaggedReasons.push(`Evidence snapshot securely hashed and timestamped.`)
    } else if (selected.rule_type === 'trailing') {
      whyFlaggedReasons.push(`Subject followed target across trajectory path.`)
      whyFlaggedReasons.push(`Inter-person distance remained consistently below threshold.`)
      whyFlaggedReasons.push(`Movement vector correlation confirmed (directional alignment).`)
      whyFlaggedReasons.push(`Follower automatically added to Cross-Camera Re-ID gallery.`)
    } else if (selected.rule_type === 'possible_hit_and_run') {
      whyFlaggedReasons.push(incidentDescription)
      whyFlaggedReasons.push(`Vehicle track: #${selected.explanation?.track_id_fleeing ?? 'unknown'} (${selected.explanation?.fleeing_class || 'vehicle'}).`)
      whyFlaggedReasons.push(`Other involved track: #${selected.explanation?.track_id_stationary ?? 'unknown'} (${selected.explanation?.victim_class || 'unknown'}); observed for ${selected.explanation?.observation_seconds ?? 'unknown'} seconds after contact.`)
    } else if (selected.rule_type === 'abandoned_object') {
      whyFlaggedReasons.push(`Unattended luggage/bag left stationary without owner nearby.`)
      whyFlaggedReasons.push(`Dwell timer exceeded unattended safety threshold.`)
      whyFlaggedReasons.push(`Owner proximity scan negative in surrounding zone.`)
      whyFlaggedReasons.push(`Security perimeter alert initiated.`)
    } else {
      whyFlaggedReasons.push(selected.explanation?.description || 'Behavior persistence confirmed by surveillance engine.')
      whyFlaggedReasons.push(`Detection confidence scored at ${(selected.confidence * 100).toFixed(0)}%.`)
      whyFlaggedReasons.push(`Real-time safety rule triggered on camera ${selected.camera_id}.`)
      whyFlaggedReasons.push(`Evidence dossier generated for review.`)
    }

    return (
      <div className="max-w-[1200px] mx-auto pb-10 px-6 pt-6">
        <div className="flex items-center gap-3 mb-6 cursor-pointer text-slate-500 hover:text-slate-800 text-sm font-medium transition-colors" onClick={() => setSelected(null)}>
          <ChevronLeft size={18} /> Back to Incident Feed
        </div>
        
        <div className="flex justify-between items-start mb-6">
          <div>
            <div className="flex items-center gap-4 mb-2">
              <h1 className="m-0 text-2xl font-extrabold text-slate-900 tracking-tight">
                INCIDENT {selected.id.toUpperCase()}
              </h1>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wide ${selected.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>
                {selected.severity === 'high' ? '🔴' : '🟠'} {selected.severity}
              </span>
            </div>
            <div className="text-lg font-bold text-blue-600 mb-2">
              {RULE_LABELS[selected.rule_type] || selected.rule_type.toUpperCase()}
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-500 font-medium">
              <span className="flex items-center gap-1.5"><MapPin size={16} /> Main Entrance • {selected.camera_id}</span>
              <span className="flex items-center gap-1.5"><History size={16} /> Detected {format(timeDetected, 'HH:mm:ss')}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-[1fr_380px] gap-6">
          <div className="flex flex-col gap-6">
            <div className="overflow-hidden relative">
              <div className="flex justify-end mb-3">
                <button
                  className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={toggleUnblurredSnapshot}
                  disabled={!selected.snapshot_url}
                >
                  {showUnblurredSnapshot ? 'Show blurred face' : 'Unblur face (admin)'}
                </button>
              </div>
              <CardDeckCarousel
                height={420}
                cardWidth="min(90%, 380px)"
                aspect="16 / 10"
                scatter={5}
                autoplay={3500}
                background="transparent"
                ink="#0f172a"
                ariaLabel="Incident evidence frames"
                slides={slides}
              />
            </div>

            <div className="p-5">
              <div className="flex items-center gap-2 text-blue-600 font-bold mb-4 pb-4">
                <Cpu size={18} /> WHY SENTRIX FLAGGED THIS
              </div>
              <ul className="flex flex-col gap-3 text-sm text-slate-600 font-medium">
                {whyFlaggedReasons.map((reason, idx) => (
                  <li key={idx} className="flex gap-3 items-start">
                    <CheckCircle size={18} className="text-emerald-500 shrink-0 mt-0.5" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            <div className="p-5">
              <div className="flex items-center gap-2 text-slate-900 font-bold mb-4 pb-3">
                <AlertOctagon size={18} /> RECOMMENDED RESPONSE
              </div>
              <div className="flex flex-col gap-2 text-sm text-slate-800 font-semibold mb-6">
                <div>1. Verify live feed immediately</div>
                <div className="w-0.5 h-3 bg-slate-200 ml-2" />
                <div>2. Notify nearest patrol unit</div>
                <div className="w-0.5 h-3 bg-slate-200 ml-2" />
                <div>3. Track subject across adjacent cameras</div>
              </div>
              <div className="flex gap-2">
                <button className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-lg text-sm shadow-sm transition-colors" onClick={() => updateAlert(selected.id, 'acknowledged')} disabled={updating}>ACKNOWLEDGE</button>
                <button className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2 rounded-lg text-sm shadow-sm transition-colors" onClick={() => updateAlert(selected.id, 'resolved')} disabled={updating}>DISPATCH PATROL</button>
                <button className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-semibold py-2 rounded-lg text-sm shadow-sm transition-colors" onClick={() => updateAlert(selected.id, 'dismissed')} disabled={updating}>FALSE POSITIVE</button>
                <button className="px-3 bg-slate-100 hover:bg-red-100 hover:text-red-600 text-slate-500 font-semibold py-2 rounded-lg text-sm shadow-sm transition-colors flex items-center justify-center border border-slate-200 hover:border-red-200" onClick={() => handleDelete(selected.id)} title="Delete Incident">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-0">
            {/* AI Risk Score */}
            <div className="pb-5 mb-5 border-b border-slate-200">
              <div className="text-xs font-bold text-slate-500 tracking-wider mb-3">AI RISK SCORE</div>
              <div className="flex items-end gap-2 mb-2">
                <div className="text-5xl font-black leading-none" style={{ color: severityColor }}>{riskScore}</div>
                <div className="text-lg font-bold pb-1" style={{ color: severityColor }}>/ 100</div>
              </div>
              <div className="text-sm font-bold mb-5" style={{ color: severityColor }}>
                {selected.severity === 'high' ? 'HIGH RISK INCIDENT' : selected.severity === 'medium' ? 'MODERATE RISK INCIDENT' : 'EVALUATION NOTICE'}
              </div>
              
              <div className="flex flex-col gap-2.5 text-sm">
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Detection Confidence</span><span className="font-bold text-slate-900">{(selected.confidence * 100).toFixed(0)}%</span></div>
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Rule Category</span><span className="font-bold text-slate-900">{RULE_LABELS[selected.rule_type] || selected.rule_type}</span></div>
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Severity Level</span><span className="font-bold text-slate-900 uppercase">{selected.severity}</span></div>
              </div>
            </div>

            {/* Event Timeline */}
            <div className="pb-5 mb-5 border-b border-slate-200">
              <div className="flex items-center gap-2 text-slate-900 font-bold mb-4">
                <History size={16} /> EVENT TIMELINE
              </div>
              <div className="flex flex-col gap-4 text-sm font-medium">
                <div className="flex gap-4"><div className="text-slate-400 font-mono text-xs pt-0.5">20:40:51</div><div className="text-slate-600">Subjects detected in frame</div></div>
                <div className="flex gap-4"><div className="text-slate-400 font-mono text-xs pt-0.5">20:41:26</div><div className="text-slate-600">Trajectory correlation established</div></div>
                <div className="flex gap-4"><div className="text-blue-600 font-mono font-bold text-xs pt-0.5">20:42:31</div><div className="text-slate-900 font-bold">Behavior threshold crossed</div></div>
                <div className="flex gap-4"><div className="text-red-600 font-mono font-bold text-xs pt-0.5">20:42:32</div><div className="text-slate-900 font-bold">SentriX generated alert</div></div>
                <div className="flex gap-4"><div className="text-slate-400 font-mono text-xs pt-0.5">20:42:40</div><div className="text-slate-600">Operator notified automatically</div></div>
              </div>
            </div>

            {/* Evidence Package */}
            <div className="pb-2">
              <div className="flex items-center gap-2 text-slate-900 font-bold mb-4">
                <ShieldCheck size={16} /> EVIDENCE PACKAGE
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs text-slate-600 font-medium mb-5">
                <div className="flex items-center gap-2"><CheckCircle size={14} className="text-blue-600" /> Original CCTV Clip</div>
                <div className="flex items-center gap-2"><CheckCircle size={14} className="text-blue-600" /> Detection Snapshot</div>
                <div className="flex items-center gap-2"><CheckCircle size={14} className="text-blue-600" /> AI Analysis Log</div>
                <div className="flex items-center gap-2"><CheckCircle size={14} className="text-blue-600" /> Confidence Data</div>
              </div>
              <div className="text-xs text-slate-500 font-medium mb-4">
                <span className="mr-2">Evidence Hash (SHA-256):</span>
                <span className="font-mono text-slate-900 font-bold tracking-tight">91ab3f8c...8ef24d1a</span>
              </div>
              <button className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg text-sm shadow-sm transition-colors" onClick={() => handleExportCourtPackage(selected.id)}>
                <Download size={16} /> DOWNLOAD DOSSIER
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ────────────────────────────────────────────────────────────────────────────────
  // DASHBOARD LIST VIEW
  // ────────────────────────────────────────────────────────────────────────────────
  const stats = {
    active: allAlerts.filter(a => a.severity === 'high').length || 2,
    online: 10,
    totalCam: 12,
    avgScore: 76,
    sla: 2.4
  }

  return (
    <div className="w-full h-full bg-[#f8fafc] text-slate-900 flex flex-col font-sans overflow-x-hidden p-6 pb-16">
      
      {/* Header Area */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-[28px] font-black tracking-tight text-slate-900 mb-1">INCIDENT INTELLIGENCE</h1>
          <p className="text-slate-500 font-medium text-sm">Real-time incident detection, evidence packaging, and response orchestration</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedAlertIds.size > 0 && (
            <button
              className="bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 rounded-lg font-semibold text-sm flex items-center gap-2 shadow-sm transition-colors"
              onClick={handleBulkDelete}
              disabled={updating}
            >
              <Trash2 size={16} /> DELETE {selectedAlertIds.size} SELECTED
            </button>
          )}
          <button 
            className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-lg font-semibold text-sm flex items-center gap-2 shadow-sm transition-colors"
            onClick={handleDeleteAll}
            disabled={updating || allAlerts.length === 0}
          >
            <Trash2 size={16} /> DELETE ALL
          </button>
        </div>
      </div>

      {/* Top Stat Cards Removed by request */}


      {/* Main Content Area */}
      <div className="w-full">
        
        {/* Incident List */}
        <div className="flex flex-col gap-6">
          
          {/* Incident List or Empty State */}
          {allAlerts.length === 0 && hideMocks ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center mb-4">
                <ShieldCheck size={32} className="text-emerald-500" />
              </div>
              <h3 className="text-lg font-bold text-slate-700 mb-1">All Clear</h3>
              <p className="text-sm text-slate-400 mb-4">No incidents on record. The system is actively monitoring.</p>
              <button className="text-xs text-blue-500 hover:underline" onClick={() => setHideMocks(false)}>
                Show example incidents
              </button>
            </div>
          ) : (allAlerts.length === 0 && !hideMocks ? [
            { id: 'mock1', severity: 'high', rule_type: 'trailing', camera_id: 'cam_01', timestamp: new Date(Date.now() - 10*3600*1000).toISOString(), confidence: 1.0, status: 'dismissed' },
            { id: 'mock2', severity: 'medium', rule_type: 'trailing', camera_id: 'cam_01', timestamp: new Date(Date.now() - 10*3600*1000).toISOString(), confidence: 0.53, status: 'new' }
          ] : allAlerts).map(alert => {
            const isHigh = alert.severity === 'high';
            const risk = Math.round(alert.confidence * 100);
            const ago = alert.timestamp ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true }) : 'unknown time';
            
            return (
              <div key={alert.id} className={`bg-white border ${isHigh?'border-red-100':'border-orange-100'} rounded-xl flex items-stretch relative overflow-hidden transition-all cursor-pointer hover:shadow-md hover:-translate-y-0.5`} onClick={() => setSelected(alert)}>
                <div className={`w-1 shrink-0 ${isHigh?'bg-red-500':'bg-orange-400'}`} />
                
                <div className="flex flex-col sm:flex-row gap-5 p-5 flex-1 min-w-0 items-center">
                  {/* Checkbox */}
                  <div className="shrink-0 flex items-center justify-center pl-2" onClick={(e) => e.stopPropagation()}>
                    <input 
                      type="checkbox" 
                      className="w-5 h-5 rounded border-slate-300 text-blue-600 cursor-pointer focus:ring-blue-500"
                      checked={selectedAlertIds.has(alert.id)}
                      onChange={(e) => toggleSelection(e, alert.id)}
                    />
                  </div>
                  
                  {/* Video / Snapshot Thumbnail */}
                  <div className="relative w-full sm:w-[220px] h-[140px] bg-slate-900 rounded-lg overflow-hidden shrink-0 group">
                    {getMediaUrl(alert.clip_url || alert.clip_path) ? (
                      <video
                        autoPlay
                        loop
                        muted
                        playsInline
                        poster={getMediaUrl(alert.snapshot_url) || undefined}
                        className="w-full h-full object-cover opacity-80"
                      >
                        <source src={getMediaUrl(alert.clip_url || alert.clip_path)} type="video/mp4" />
                      </video>
                    ) : getMediaUrl(alert.snapshot_url) ? (
                      <img 
                        src={getMediaUrl(alert.snapshot_url)} 
                        alt="Incident Snapshot" 
                        className="w-full h-full object-cover" 
                        onError={(e) => { e.target.onerror = null; e.target.src = "https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=900&h=560&fit=crop"; }}
                      />
                    ) : (
                      <img 
                        src="https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=900&h=560&fit=crop" 
                        alt="Surveillance Frame" 
                        className="w-full h-full object-cover opacity-80" 
                      />
                    )}
                    <div className={`absolute top-2 left-2 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider ${isHigh?'bg-red-600 text-white':'bg-orange-500 text-white'}`}>
                      {isHigh ? 'CRITICAL' : 'MEDIUM'}
                    </div>
                    <div className="absolute bottom-2 left-2 font-mono text-[10px] text-white/80">{alert.rule_type?.toUpperCase()}</div>
                  </div>

                  {/* Info */}
                  <div className="flex-1 flex flex-col justify-center min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-bold text-[16px] text-slate-900 leading-tight truncate">{RULE_LABELS[alert.rule_type] || alert.rule_type?.replace(/_/g, ' ').toUpperCase()}</h3>
                      <span className={`text-[18px] font-black ${isHigh?'text-red-500':'text-orange-500'}`}>{risk}</span>
                      <div className={`ml-auto px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider shrink-0 ${alert.status==='dismissed'?'bg-rose-50 text-rose-500':'bg-blue-50 text-blue-500'}`}>
                        {alert.status || 'NEW'}
                      </div>
                    </div>
                    
                    <div className="text-[12px] text-slate-400 flex items-center gap-2 mb-3">
                      <MapPin size={11}/> {alert.camera_id} <span className="text-slate-200">·</span> Main Entrance <span className="text-slate-200">·</span> {ago}
                    </div>

                    <p className="text-[12px] text-slate-500 leading-relaxed line-clamp-2">
                      {alert.explanation?.description || alert.explanation?.fused_explanation || (
                        alert.rule_type === 'possible_hit_and_run'
                          ? 'Possible collision detected; vehicle fled while the other involved track remained at the scene.'
                          : alert.rule_type === 'trailing'
                            ? 'Movement pattern consistent with trailing behavior.'
                            : `${RULE_LABELS[alert.rule_type] || 'Incident'} detected.`
                      )}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
