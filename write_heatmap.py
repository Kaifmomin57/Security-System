import os

heatmap_content = """import { useState, useEffect } from 'react'
import axios from 'axios'
import { Flame, RefreshCw, Crosshair, Map, Shield } from 'lucide-react'

const Voxel = ({ x, y, h, heat, name }) => {
  const size = 40;
  const s = 34; // block size (leaves a 6px gap for roads/alleys)
  const isRoad = h === 0;
  
  // Base colors
  const bColor = isRoad ? [20, 25, 35] : [30, 41, 59];
  const hColor = [239, 68, 68]; // Police Red

  // Calculate mixed color based on heat (0.0 to 1.0)
  const r = Math.floor(bColor[0] + (hColor[0] - bColor[0]) * heat);
  const g = Math.floor(bColor[1] + (hColor[1] - bColor[1]) * heat);
  const b = Math.floor(bColor[2] + (hColor[2] - bColor[2]) * heat);

  const cTop = `rgb(${r}, ${g}, ${b})`;
  const cRight = `rgb(${r * 0.7}, ${g * 0.7}, ${b * 0.7})`;
  const cFront = `rgb(${r * 0.5}, ${g * 0.5}, ${b * 0.5})`;

  return (
    <div
      title={name + (heat > 0 ? ` (Risk Level: ${(heat * 100).toFixed(0)}%)` : '')}
      style={{
        position: 'absolute',
        left: x * size,
        top: y * size,
        width: s,
        height: s,
        transformStyle: 'preserve-3d',
        transition: 'all 0.5s ease',
        cursor: 'pointer'
      }}
    >
      {/* Top Face */}
      <div style={{
        position: 'absolute', width: s, height: s,
        background: cTop,
        transform: `translateZ(${h}px)`,
        border: isRoad ? 'none' : '1px solid rgba(255,255,255,0.05)',
        boxShadow: heat > 0 ? `0 0 ${40 * heat}px rgba(239,68,68,${heat})` : 'none',
        transition: 'all 0.5s ease',
      }} />

      {/* Front Face */}
      {!isRoad && (
        <div style={{
          position: 'absolute', left: 0, top: s, width: s, height: h,
          background: cFront,
          transformOrigin: 'top',
          transform: 'rotateX(-90deg)',
          transition: 'all 0.5s ease',
        }} />
      )}

      {/* Right Face */}
      {!isRoad && (
        <div style={{
          position: 'absolute', left: s, top: 0, width: h, height: s,
          background: cRight,
          transformOrigin: 'left',
          transform: 'rotateY(90deg)',
          transition: 'all 0.5s ease',
        }} />
      )}
    </div>
  );
}

export default function PatrolHeatmapPage() {
  const [rotation, setRotation] = useState(-45);
  const [pulse, setPulse] = useState(0);

  // Animate the heat pulse
  useEffect(() => {
    const i = setInterval(() => setPulse(p => p === 0 ? 1 : 0), 2000);
    return () => clearInterval(i);
  }, []);

  // Generate a mock city block map (10x10)
  // height 0 = road, >0 = building
  const mapData = [];
  for (let y = 0; y < 12; y++) {
    for (let x = 0; x < 12; x++) {
      const isRoad = x % 4 === 0 || y % 4 === 0;
      let h = isRoad ? 0 : 20 + Math.random() * 80;
      let heat = 0;

      // Create a specific "hotspot" at the East Entrance / Station Road
      if (x > 6 && x < 10 && y > 6 && y < 10) {
        heat = 0.5 + Math.random() * 0.5; // High heat
        if (pulse === 1) heat *= 1.2; // pulse effect
        if (heat > 1) heat = 1;
      }
      // Another minor hotspot
      if (x > 1 && x < 3 && y > 1 && y < 3) {
        heat = 0.2 + Math.random() * 0.3;
      }

      mapData.push({ x, y, h, heat, isRoad, name: isRoad ? 'Road' : `Block ${x}-${y}` });
    }
  }

  return (
    <div style={{ paddingBottom: 40, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Map size={24} color="var(--brand-blue)" />
            3D LIVE THREAT MAP
          </h1>
          <p className="page-subtitle">
            Real-time voxel cartography & pixelated risk topography engine.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn btn-ghost" onClick={() => setRotation(r => r - 45)}>
            <RefreshCw size={14} /> Rotate View
          </button>
          <button className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Crosshair size={14} /> Auto-Target Hotspots
          </button>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', perspective: '1200px', overflow: 'hidden', minHeight: '600px', background: 'radial-gradient(circle at center, #0a1020 0%, #030508 100%)', borderRadius: '12px', border: '1px solid var(--border)', marginTop: 24, position: 'relative' }}>
        
        {/* The 3D World */}
        <div style={{
          width: 12 * 40,
          height: 12 * 40,
          transformStyle: 'preserve-3d',
          transform: `rotateX(60deg) rotateZ(${rotation}deg) translateY(-50px)`,
          transition: 'transform 1s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          {mapData.map((v, i) => (
            <Voxel key={i} {...v} />
          ))}
        </div>

        {/* HUD Overlay */}
        <div style={{ position: 'absolute', top: 20, left: 20, background: 'rgba(6, 10, 18, 0.8)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.2)', backdropFilter: 'blur(10px)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '1px', marginBottom: 12 }}>LIVE SCAN METRICS</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{ width: 12, height: 12, background: 'var(--alert-high)', borderRadius: '2px', boxShadow: '0 0 10px red' }} />
            <div style={{ fontSize: '0.85rem', color: 'white', fontWeight: 600 }}>Critical Threat Zone (East)</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 12, height: 12, background: 'var(--alert-medium)', borderRadius: '2px' }} />
            <div style={{ fontSize: '0.85rem', color: 'white', fontWeight: 600 }}>Elevated Activity (West)</div>
          </div>
        </div>

        <div style={{ position: 'absolute', bottom: 20, right: 20, background: 'linear-gradient(90deg, rgba(37, 99, 235, 0.2), rgba(239, 68, 68, 0.2))', padding: '16px 24px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.4)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 40, height: 40, background: 'rgba(239, 68, 68, 0.2)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fca5a5' }}>
            <Shield size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.85rem', color: 'white', fontWeight: 700 }}>AI RECOMMENDATION</div>
            <div style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>Deploy SRT to Block 8-8 (East Entrance).</div>
          </div>
        </div>
      </div>
    </div>
  )
}
"""

with open('frontend/src/pages/PatrolHeatmapPage.jsx', 'w', encoding='utf-8') as f:
    f.write(heatmap_content)

print("PatrolHeatmapPage rewritten with 3D isometric city simulation.")
