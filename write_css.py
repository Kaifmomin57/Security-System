import os

css_content = """/* ═══════════════════════════════════════════════════════════════
   SentryEye — GOVERNMENT/POLICE ENTERPRISE UI (LIGHT THEME)
   Clean, authoritative, high-contrast, and professional
   ═══════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

/* ─── CSS Variables ─────────────────────────────────────────── */
:root {
  /* Crisp, clean backgrounds */
  --bg-void:       #f0f2f5;
  --bg-primary:    #ffffff;
  --bg-secondary:  #f8fafc;
  --bg-card:       #ffffff;
  --bg-glass:      rgba(255, 255, 255, 0.95);

  /* Borders and dividers */
  --border:        #e2e8f0;
  --border-glow:   #cbd5e1;
  --border-hot:    #fca5a5;

  /* Official Police/Gov Palette */
  --brand-navy:    #0f172a;
  --brand-blue:    #1d4ed8;
  --brand-light:   #eff6ff;

  --neon-blue:     #2563eb;
  --neon-cyan:     #0284c7;
  --neon-purple:   #7c3aed;
  --neon-red:      #dc2626;
  --neon-orange:   #ea580c;
  --neon-green:    #16a34a;

  /* Alert Severity Colors (High contrast on light mode) */
  --alert-low:     #d97706;
  --alert-medium:  #ea580c;
  --alert-high:    #dc2626;
  --alert-ok:      #059669;

  /* Text Colors */
  --text-primary:  #0f172a;
  --text-secondary:#334155;
  --text-muted:    #64748b;

  --radius:        10px;
  --radius-sm:     6px;
  --radius-xs:     4px;
  
  /* Subdued drop shadows for a material look */
  --shadow:        0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-hover:  0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
  --shadow-hot:    0 0 15px rgba(220, 38, 38, 0.2);

  --transition:    all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ─── Reset ──────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }

body {
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg-void);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* ─── Scrollbar ──────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* ─── Layout ─────────────────────────────────────────────────── */
.app-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  grid-template-rows: 64px 1fr;
  min-height: 100vh;
}

/* ─── Sidebar (Dark authoritative navy look to anchor the design) ────────────────── */
.sidebar {
  grid-column: 1;
  grid-row: 1 / -1;
  background: var(--brand-navy);
  color: #f1f5f9;
  padding: 0 12px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  box-shadow: 2px 0 10px rgba(0,0,0,0.1);
  z-index: 100;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 12px;
  font-size: 1.15rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 12px;
}

.sidebar-logo .logo-icon {
  width: 32px; height: 32px;
  background: var(--brand-blue);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(29, 78, 216, 0.4);
}

.sidebar-logo .logo-dot {
  width: 8px; height: 8px;
  background: #34d399;
  border-radius: 50%;
  margin-left: auto;
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.6);
}

.sidebar-section-label {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: #94a3b8;
  padding: 16px 12px 6px;
  margin-top: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  color: #cbd5e1;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  transition: var(--transition);
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.nav-item.active {
  background: var(--brand-blue);
  color: #ffffff;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(29, 78, 216, 0.3);
}

/* ─── Topbar ─────────────────────────────────────────────────── */
.topbar {
  grid-column: 2;
  grid-row: 1;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  position: sticky;
  top: 0;
  z-index: 50;
}

.topbar-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.ws-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.ws-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--alert-ok);
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.2);
}
.ws-dot.offline { background: var(--alert-high); box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.2); }

/* ─── Main Content ───────────────────────────────────────────── */
.main-content {
  grid-column: 2;
  grid-row: 2;
  padding: 32px;
  overflow-y: auto;
}

/* ─── Cards ──────────────────────────────────────────────────── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow);
  transition: var(--transition);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.card-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ─── Stats Grid ─────────────────────────────────────────────── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; bottom: 0;
  width: 4px;
}

.stat-card.blue::before  { background: var(--brand-blue); }
.stat-card.orange::before { background: var(--alert-medium); }
.stat-card.red::before   { background: var(--alert-high); }
.stat-card.green::before { background: var(--alert-ok); }

.stat-value {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
  margin: 12px 0 4px;
  letter-spacing: -1px;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

/* ─── Alert Feed ─────────────────────────────────────────────── */
.alert-feed { display: flex; flex-direction: column; gap: 12px; }

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  transition: var(--transition);
  cursor: pointer;
}

.alert-item:hover {
  box-shadow: var(--shadow-hover);
  border-color: #cbd5e1;
  transform: translateY(-2px);
}

.alert-item.severity-high   { border-left: 4px solid var(--alert-high); background: #fef2f2; }
.alert-item.severity-medium { border-left: 4px solid var(--alert-medium); background: #fff7ed; }
.alert-item.severity-low    { border-left: 4px solid var(--alert-low); background: #fefce8; }

.alert-severity-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-high   { background: #fee2e2; color: #b91c1c; }
.badge-medium { background: #ffedd5; color: #c2410c; }
.badge-low    { background: #fef9c3; color: #a16207; }
.badge-new    { background: #dbeafe; color: #1d4ed8; }

.alert-meta { flex: 1; }
.alert-title { font-size: 0.95rem; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.alert-sub   { font-size: 0.8rem; color: var(--text-secondary); }

.alert-time {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
}

/* ─── Camera Grid ────────────────────────────────────────────── */
.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
}

.camera-feed {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  position: relative;
}

.camera-feed.alert-active {
  border: 2px solid var(--alert-high);
  box-shadow: var(--shadow-hot);
}

.camera-feed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.85rem;
}

.camera-status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--alert-ok);
  box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.2);
}

.camera-screen {
  width: 100%;
  aspect-ratio: 16/9;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  position: relative;
}

.camera-screen img { width: 100%; height: 100%; object-fit: cover; }

.alert-overlay {
  position: absolute;
  top: 12px; right: 12px;
  background: var(--alert-high);
  color: white;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.4);
}

/* ─── Buttons ────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
  transition: var(--transition);
}

.btn-primary {
  background: var(--brand-blue);
  color: white;
  box-shadow: 0 2px 4px rgba(29, 78, 216, 0.2);
}
.btn-primary:hover {
  background: #1e40af;
  box-shadow: 0 4px 6px rgba(29, 78, 216, 0.3);
}

.btn-danger {
  background: #fef2f2;
  color: var(--alert-high);
  border-color: #fecaca;
}
.btn-danger:hover { background: #fee2e2; }

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border);
}
.btn-ghost:hover { background: var(--bg-secondary); color: var(--text-primary); }

.btn-success {
  background: #ecfdf5;
  color: var(--alert-ok);
  border-color: #a7f3d0;
}
.btn-success:hover { background: #d1fae5; }

/* ─── Table ──────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); }

table { width: 100%; border-collapse: collapse; font-size: 0.85rem; background: var(--bg-primary); }

th {
  text-align: left;
  padding: 14px 16px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: 0.7rem;
  border-bottom: 1px solid var(--border);
}

td {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  vertical-align: middle;
}

tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-secondary); }

/* ─── Page Header ────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32px;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--brand-navy);
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-top: 6px;
}

/* ─── Confidence Bar ─────────────────────────────────────────── */
.conf-bar {
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  width: 100px;
  overflow: hidden;
}
.conf-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--brand-blue);
}

/* ─── Detail Modal ───────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: var(--bg-primary);
  border-radius: var(--radius);
  padding: 32px;
  width: 90%;
  max-width: 760px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  position: relative;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

/* ─── Utilities & Layout tweaks ──────────────────────────────── */
.text-mono { font-family: 'JetBrains Mono', monospace; }
.text-muted { color: var(--text-muted); }
"""

with open('frontend/src/index.css', 'w', encoding='utf-8') as f:
    f.write(css_content)

print("CSS successfully written to index.css")
