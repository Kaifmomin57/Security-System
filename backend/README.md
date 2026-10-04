# SentryEye — Smart Suspicious Activity Detection System

> AI-powered CCTV surveillance with real-time alerts, PostgreSQL logging, GPU-accelerated detection, and a live React dashboard.

---

## 🚀 Quick Start (5 steps)

### Step 1 — Clone & enter project
```powershell
cd d:\security\sentryeye\backend
```

### Step 2 — Install PyTorch with CUDA (GTX 1650 → CUDA 12.1)
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 3 — Install Python dependencies
```powershell
cd d:\security\sentryeye\backend
pip install -r requirements.txt
```

### Step 4 — Configure environment
```powershell
cd d:\security\sentryeye\backend
Copy-Item .env.example .env
# Then edit .env with your PostgreSQL password + Telegram Bot token
```

### Step 5 — Set up PostgreSQL database
```sql
-- Run in psql:
CREATE DATABASE sentryeye;
CREATE USER sentryeye_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE sentryeye TO sentryeye_user;
```

---

## 🏃 Running the System

### Terminal 1 — Backend API
```powershell
cd d:\security\sentryeye\backend
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Detection Pipeline
```powershell
cd d:\security\sentryeye\backend
python pipeline.py
```

### Terminal 3 — React Dashboard
```powershell
cd d:\security\sentryeye\frontend
npm run dev
# Open http://localhost:5173
```

**Or run everything at once:**
```powershell
cd d:\security\sentryeye\backend
python run.py
```

---

## 📁 Project Structure
```
sentryeye/
├── backend/                  ← All Python code lives here
│   ├── ingestion/            Video stream reader (RTSP + file)
│   ├── detection/            YOLOv8 detector + DeepSORT tracker
│   ├── rules/                Behavior rules + fusion engine
│   ├── alerts/               Severity, Telegram, trust adjuster
│   ├── evidence/             SHA-256 file hashing
│   ├── privacy/              Face blur (Haar Cascade)
│   ├── storage/              PostgreSQL models + clip saver
│   ├── api/                  FastAPI routes + WebSocket
│   ├── baseline/             Adaptive baseline module
│   ├── config/               zones.yaml — per-camera zone config
│   ├── media/                snapshots/ and clips/
│   ├── pipeline.py           Main AI pipeline orchestrator
│   ├── run.py                Single-command launcher
│   ├── requirements.txt      Python dependencies
│   └── .env                  Your secrets (copy from .env.example)
└── frontend/                 ← React dashboard (Vite)
```

---

## 🔌 API Reference
| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/alerts` | GET | List alerts (filterable) |
| `/api/v1/alerts/{id}` | PATCH | Acknowledge / Resolve / Dismiss |
| `/api/v1/zones` | POST | Create zone polygon |
| `/api/v1/cameras` | GET | List cameras |
| `/api/v1/health` | GET | Pipeline FPS + uptime |
| `/ws/alerts` | WS | Live alert push |
| `/docs` | GET | Interactive Swagger UI |

---

## ⚙️ Key Configuration (.env)
| Variable | Default | Description |
|---|---|---|
| `YOLO_MODEL` | `yolov8s.pt` | Use `yolov8n.pt` for lower VRAM |
| `DEVICE` | `cuda` | GPU device |
| `FRAME_SKIP` | `2` | Process every 2nd frame |
| `LOITERING_THRESHOLD_SECONDS` | `60` | Seconds to trigger loitering |
| `FACE_BLUR_ENABLED` | `true` | Blur faces in saved clips |

---

## ✅ GPU Verification
```python
import torch
print(torch.cuda.is_available())         # True
print(torch.cuda.get_device_name(0))     # NVIDIA GeForce GTX 1650
```
