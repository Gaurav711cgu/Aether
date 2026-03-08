"""
main.py
-------
FastAPI application exposing all required ACM endpoints.
Runs on port 8000, binds to 0.0.0.0.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os

from core.constellation import ConstellationManager

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("aether.api")

# ── Global ACM Instance ────────────────────────────────────────────────────────
acm: Optional[ConstellationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global acm
    logger.info("🚀 Initializing Autonomous Constellation Manager...")
    acm = ConstellationManager()
    logger.info("✅ ACM online. Fleet initialized.")
    yield
    logger.info("Shutting down ACM.")


app = FastAPI(
    title="Project AETHER — Autonomous Constellation Manager",
    description="GNSS Orbital Debris Avoidance & Constellation Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend if built
frontend_path = "/app/frontend/dist"
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ── Request / Response Models ──────────────────────────────────────────────────

class Vector3(BaseModel):
    x: float
    y: float
    z: float


class TelemetryObject(BaseModel):
    id: str
    type: str   # DEBRIS | SATELLITE
    r: Vector3
    v: Vector3


class TelemetryRequest(BaseModel):
    timestamp: str
    objects: List[TelemetryObject]


class BurnCommand(BaseModel):
    burn_id: str
    burnTime: str
    deltaV_vector: Vector3
    burn_type: str = "MANUAL"


class ManeuverRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: List[BurnCommand]


class StepRequest(BaseModel):
    step_seconds: float


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "online", "service": "AETHER ACM", "version": "1.0.0"}


@app.post("/api/telemetry")
async def ingest_telemetry(req: TelemetryRequest):
    """Ingest high-frequency telemetry updates."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    ts = datetime.fromisoformat(req.timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
    objects = [o.dict() for o in req.objects]
    result = acm.ingest_telemetry(ts, objects)
    return result


@app.post("/api/maneuver/schedule")
async def schedule_maneuver(req: ManeuverRequest):
    """Schedule a maneuver sequence for a satellite."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    sequence = []
    for burn in req.maneuver_sequence:
        sequence.append({
            "burn_id": burn.burn_id,
            "burnTime": burn.burnTime,
            "deltaV_vector": burn.deltaV_vector.dict(),
            "burn_type": burn.burn_type,
        })
    result = acm.schedule_maneuver(req.satelliteId, sequence)
    if result.get("status") == "REJECTED":
        raise HTTPException(400, result.get("reason"))
    return result


@app.post("/api/simulate/step")
async def simulate_step(req: StepRequest):
    """Advance simulation by step_seconds."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    if req.step_seconds <= 0 or req.step_seconds > 86400:
        raise HTTPException(400, "step_seconds must be between 1 and 86400")
    t0 = time.perf_counter()
    result = acm.simulate_step(req.step_seconds)
    elapsed = time.perf_counter() - t0
    result["computation_time_ms"] = round(elapsed * 1000, 1)
    return result


@app.get("/api/visualization/snapshot")
async def get_snapshot():
    """Optimized snapshot for frontend rendering."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    return acm.get_snapshot()


@app.get("/api/satellites")
async def list_satellites():
    """List all satellites with full state."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    return {
        "satellites": [s.to_dict() for s in acm.satellites.values()],
        "timestamp": acm.sim_time.isoformat() + "Z",
    }


@app.get("/api/satellites/{sat_id}")
async def get_satellite(sat_id: str):
    """Get detailed state for a single satellite."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    if sat_id not in acm.satellites:
        raise HTTPException(404, f"Satellite {sat_id} not found")
    sat = acm.satellites[sat_id]
    data = sat.to_dict()
    data["maneuver_log"] = sat.maneuver_log[-20:]
    data["trajectory"] = acm.get_satellite_trajectory(sat_id, minutes=90)
    return data


@app.get("/api/conjunctions")
async def get_conjunctions():
    """Get all active Conjunction Data Messages."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    return {
        "timestamp": acm.sim_time.isoformat() + "Z",
        "cdm_count": len(acm.active_cdms),
        "cdms": [{
            "sat_id": c.sat_id,
            "deb_id": c.deb_id,
            "tca_seconds": round(c.tca_seconds, 1),
            "tca_timestamp": c.tca_timestamp.isoformat() + "Z",
            "miss_distance_km": round(c.miss_distance_km, 4),
            "probability": round(c.probability, 4),
            "risk_level": c.risk_level,
            "is_critical": c.is_critical,
        } for c in acm.active_cdms[:100]],
    }


@app.get("/api/maneuvers/queue")
async def get_maneuver_queue():
    """Get pending maneuver queue (Gantt data)."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    return {
        "queued": [{
            "burn_id": m.burn_id,
            "satellite_id": m.satellite_id,
            "burn_time": m.burn_time.isoformat() + "Z",
            "dv_mag_ms": round(float(sum(m.dv_eci**2)**0.5) * 1000, 2),
            "burn_type": m.burn_type,
        } for m in acm.maneuver_queue],
        "executed_count": acm.total_maneuvers_executed,
    }


@app.get("/api/fleet/stats")
async def fleet_stats():
    """Fleet-wide health and performance metrics."""
    if acm is None:
        raise HTTPException(503, "ACM not initialized")
    return {
        "timestamp": acm.sim_time.isoformat() + "Z",
        **acm._fleet_stats(),
        "total_collisions": acm.total_collisions,
    }


@app.get("/api/ground_stations")
async def ground_stations():
    """List ground station network."""
    from core.conjunction import GROUND_STATIONS
    return {"stations": GROUND_STATIONS}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
