# 🛰️ Project AETHER
### Autonomous Constellation Manager
**National Space Hackathon 2026 | IIT Delhi**
**Team: DEBUG THUGS | C.V. Raman Global University**
**Contact: gauravnayak711@gmail.com**

---

## Overview

AETHER is a high-performance **Autonomous Constellation Manager (ACM)** for orbital debris avoidance and constellation management. It autonomously protects a 50-satellite LEO constellation from 10,000+ tracked debris objects using ML-grade spatial indexing, real-time orbital mechanics, and a mission-control grade visualization dashboard.

```
Telemetry Stream (debris + satellites)
           │
           ▼
  KD-Tree Spatial Index ──── O(N log N) conjunction screening
           │
           ▼
   RK4 + J2 Propagator ──── TCA calculation for candidate pairs
           │
           ▼
  Autonomous Maneuver Planner
  ├── Evasion burn (RTN prograde/retrograde, min ΔV)
  └── Recovery burn (Hohmann transfer back to slot)
           │
           ▼
  Ground Station LOS Check ──── Tsiolkovsky fuel tracking
           │
           ▼
   FastAPI REST (port 8000) ──── Orbital Insight Dashboard
```

---

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Physics Engine | NumPy + SciPy | RK4 propagator, J2 perturbation |
| Spatial Index | scipy.spatial.KDTree | O(N log N) conjunction detection |
| Backend API | FastAPI + Uvicorn | All 5 required endpoints |
| Frontend | React + Canvas API | 60 FPS dashboard, 10K+ debris |
| Deployment | Docker (ubuntu:22.04) | Port 8000 |

---

## Quick Start

### Docker (Recommended)
```bash
git clone https://github.com/YOUR_USERNAME/project-aether
cd project-aether
docker build -t aether .
docker run -p 8000:8000 aether
# Open http://localhost:8000
```

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (separate terminal)
cd frontend
npm install && npm run dev
# Open http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/telemetry` | Ingest satellite/debris state vectors |
| POST | `/api/maneuver/schedule` | Schedule evasion/recovery burns |
| POST | `/api/simulate/step` | Advance simulation clock |
| GET  | `/api/visualization/snapshot` | Optimized frontend snapshot |
| GET  | `/api/conjunctions` | Active CDM warnings |
| GET  | `/api/fleet/stats` | Fleet health metrics |
| GET  | `/api/satellites/{id}` | Per-satellite detail + trajectory |
| GET  | `/api/maneuvers/queue` | Pending maneuver Gantt data |

---

## Physics Implementation

### Orbital Propagation
RK4 integration of the full J2-perturbed equations of motion:

```
d²r/dt² = -(μ/|r|³)r + a_J2
```

Where `a_J2` accounts for Earth's equatorial bulge (J2 = 1.08263×10⁻³).

### Conjunction Detection — O(N log N)
1. Build **KD-Tree** over all debris positions (rebuilt each telemetry update)
2. Query satellites against 50km bounding sphere — eliminates 99.9% of pairs
3. Precise RK4 TCA propagation only on candidates
4. CDMs issued for miss distance < 100m (D_crit)

### Autonomous Evasion
- RTN frame prograde/retrograde burn (most fuel-efficient)
- ΔV capped at 15 m/s per burn (DV_MAX)
- 600s thruster cooldown enforced
- Recovery Hohmann transfer scheduled automatically

### Fuel Tracking (Tsiolkovsky)
```
Δm = m_current × (1 - exp(-|ΔV| / (Isp × g0)))
```
- Isp = 300s, g0 = 9.80665 m/s²
- EOL threshold: fuel < 5% → graveyard orbit scheduled

---

## Dashboard Modules

| Module | Description |
|--------|-------------|
| 🌍 Ground Track | Mercator map, terminator line, 90-min trail, debris cloud |
| 🎯 Bullseye Plot | Polar conjunction proximity view, risk color-coded |
| ⛽ Fleet Health | Per-satellite fuel gauges, ΔV vs collisions chart |
| 📅 Gantt Timeline | Maneuver schedule with cooldown visualization |
| 📡 Sat Inspector | Click any satellite for detail, trajectory, maneuver log |

---

## Ground Station Network

| ID | Location | Min Elevation |
|----|----------|--------------|
| GS-001 | ISTRAC Bengaluru | 5° |
| GS-002 | Svalbard | 5° |
| GS-003 | Goldstone | 10° |
| GS-004 | Punta Arenas | 5° |
| GS-005 | IIT Delhi | 15° |
| GS-006 | McMurdo | 5° |

---

## Evaluation Targets

| Criterion | Weight | Our Approach |
|-----------|--------|-------------|
| Safety Score | 25% | KD-Tree + RK4 TCA → autonomous evasion before D_crit breach |
| Fuel Efficiency | 20% | Prograde RTN burns (min ΔV), Tsiolkovsky exact tracking |
| Constellation Uptime | 15% | Fast Hohmann recovery burns, 10km box monitoring |
| Algorithmic Speed | 15% | KD-Tree O(N log N), vectorized NumPy propagation |
| UI/UX | 15% | Canvas 60fps, all 4 required dashboard modules |
| Code Quality | 10% | Modular, documented, maneuver logging |
