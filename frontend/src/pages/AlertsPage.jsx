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
  const [selectedAlertIds, setSelectedAlertIds] = useState(new Set())

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
      if (!eventId.startsWith('mock')) {
        await axios.delete(`${API}/alerts/${eventId}`);
      }
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
      setAlerts(prev => prev.filter(a => !selectedAlertIds.has(a.id)));
      if (selected && selectedAlertIds.has(selected.id)) setSelected(null);
      setSelectedAlertIds(new Set());
    } catch (err) {
      console.error('Failed to bulk delete:', err);
    } finally {
      setUpdating(false);
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

  const allAlerts = [
    ...liveAlerts.filter(la => !alerts.find(a => a.id === la.id)),
    ...alerts
  ]

  const getRiskScore = (conf) => Math.round(conf * 100)

  // ────────────────────────────────────────────────────────────────────────────────
  // DETAIL VIEW (UNCHANGED logic, tweaked classes for consistency)
  // ────────────────────────────────────────────────────────────────────────────────
  if (selected) {
    const riskScore = getRiskScore(selected.confidence)
    const severityColor = selected.severity === 'high' ? '#ef4444' : selected.severity === 'medium' ? '#f59e0b' : '#3b82f6'
    const timeDetected = new Date(selected.timestamp)

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
              <CardDeckCarousel
                height={420}
                cardWidth="min(90%, 380px)"
                aspect="16 / 10"
                scatter={5}
                autoplay={3500}
                background="transparent"
                ink="#0f172a"
                ariaLabel="Incident evidence frames"
                slides={[
                  {
                    ...(selected.clip_path ? { video: `http://localhost:8000${selected.clip_path}` } : { image: selected.snapshot_url ? `http://localhost:8000${selected.snapshot_url}` : "https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=900&h=560&fit=crop" }),
                    title: `Evidence Proof — ${format(timeDetected, 'HH:mm:ss')}`,
                    caption: selected.clip_path ? "Full incident video recording." : "Primary detection frame triggered by SentriX.",
                    alt: "Primary evidence"
                  },
                  {
                    image: selected.snapshot_url ? `http://localhost:8000${selected.snapshot_url}` : "https://images.unsplash.com/photo-1584433144859-1fc3ab64a957?w=900&h=560&fit=crop",
                    title: "Detection Snapshot",
                    caption: "High-res snapshot at moment of trigger.",
                    alt: "Snapshot frame"
                  },
                  {
                    image: "https://images.unsplash.com/photo-1555099962-4199c345e5dd?w=900&h=560&fit=crop",
                    title: "AI Analysis",
                    caption: "Behavior persistence confirmed across zones.",
                    alt: "Tertiary CCTV frame"
                  }
                ]}
              />
            </div>

            <div className="p-5">
              <div className="flex items-center gap-2 text-blue-600 font-bold mb-4 pb-4">
                <Cpu size={18} /> WHY SENTRIX FLAGGED THIS
              </div>
              <ul className="flex flex-col gap-3 text-sm text-slate-600 font-medium">
                <li className="flex gap-3 items-start"><CheckCircle size={18} className="text-emerald-500 shrink-0 mt-0.5" /> Same individual followed target across 3 operational zones.</li>
                <li className="flex gap-3 items-start"><CheckCircle size={18} className="text-emerald-500 shrink-0 mt-0.5" /> Inter-person distance remained consistently below 4.2m.</li>
                <li className="flex gap-3 items-start"><CheckCircle size={18} className="text-emerald-500 shrink-0 mt-0.5" /> Behavior persisted for 126 seconds uninterrupted.</li>
                <li className="flex gap-3 items-start"><CheckCircle size={18} className="text-emerald-500 shrink-0 mt-0.5" /> Matching trajectory detected traversing restricted area.</li>
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
              <div className="text-sm font-bold mb-5" style={{ color: severityColor }}>HIGH RISK INCIDENT</div>
              
              <div className="flex flex-col gap-2.5 text-sm">
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Detection Confidence</span><span className="font-bold text-slate-900">94%</span></div>
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Behavior Persistence</span><span className="font-bold text-slate-900">89%</span></div>
                <div className="flex justify-between items-center"><span className="text-slate-500 font-medium">Trajectory Correlation</span><span className="font-bold text-slate-900">92%</span></div>
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
        {selectedAlertIds.size > 0 && (
          <button 
            className="bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 rounded-lg font-semibold text-sm flex items-center gap-2 shadow-sm transition-colors"
            onClick={handleBulkDelete}
            disabled={updating}
          >
            <Trash2 size={16} /> DELETE {selectedAlertIds.size} SELECTED
          </button>
        )}
      </div>

      {/* Top Stat Cards Removed by request */}


      {/* Main Content Area */}
      <div className="w-full">
        
        {/* Incident List */}
        <div className="flex flex-col gap-6">
          
          {/* FAKE CARDS TO MATCH SCREENSHOT IF API EMPTY, ELSE MAP OVER ALERTS */}
          {(allAlerts.length === 0 ? [
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
                  
                  {/* Video Thumbnail */}
                  <div className="relative w-full sm:w-[220px] h-[140px] bg-slate-900 rounded-lg overflow-hidden shrink-0 group">
                    <video autoPlay loop muted playsInline className="w-full h-full object-cover opacity-80">
                      <source src="https://assets.mixkit.co/videos/preview/mixkit-people-walking-in-a-busy-street-23849-large.mp4" type="video/mp4" />
                    </video>
                    <div className={`absolute top-2 left-2 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider ${isHigh?'bg-red-600 text-white':'bg-orange-500 text-white'}`}>
                      {isHigh ? 'CRITICAL' : 'MEDIUM'}
                    </div>
                    <div className="absolute bottom-2 left-2 font-mono text-[10px] text-white/80">{isHigh?'00:32':'00:28'}</div>
                  </div>

                  {/* Info */}
                  <div className="flex-1 flex flex-col justify-center min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-bold text-[16px] text-slate-900 leading-tight truncate">{RULE_LABELS[alert.rule_type] || 'Trailing / Stalking'}</h3>
                      <span className={`text-[18px] font-black ${isHigh?'text-red-500':'text-orange-500'}`}>{risk}</span>
                      <div className={`ml-auto px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider shrink-0 ${alert.status==='dismissed'?'bg-rose-50 text-rose-500':'bg-blue-50 text-blue-500'}`}>
                        {alert.status || 'NEW'}
                      </div>
                    </div>
                    
                    <div className="text-[12px] text-slate-400 flex items-center gap-2 mb-3">
                      <MapPin size={11}/> {alert.camera_id} <span className="text-slate-200">·</span> Riverside Plaza <span className="text-slate-200">·</span> {ago}
                    </div>

                    <p className="text-[12px] text-slate-500 leading-relaxed line-clamp-2">
                      {isHigh ? 'Movement pattern consistent with stalking behavior. Subject followed target across zones.' : 'Moderate risk — consistent proximity and matching movement direction detected.'}
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
