"""
constellation.py
----------------
Central state manager for the entire constellation.
Tracks all satellites, debris, fuel budgets, maneuver queues,
station-keeping status, and uptime metrics.
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from threading import Lock

from .physics import (
    propagate, rk4_step, apply_burn, fuel_consumed,
    eci_to_lla, state_to_elements, orbital_period,
    M_DRY, M_FUEL0, DV_MAX, COOLDOWN, SK_BOX, FUEL_EOL,
    plan_evasion_maneuver, plan_recovery_maneuver, MU
)
from .conjunction import (
    ConjunctionAssessor, CDM, ScheduledManeuver,
    satellite_has_los, GROUND_STATIONS
)

logger = logging.getLogger("aether.constellation")


# ── Satellite State ─────────────────────────────────────────────────────────────

@dataclass
class SatelliteState:
    sat_id: str
    state: np.ndarray               # [x,y,z,vx,vy,vz] ECI (km, km/s)
    nominal_state: np.ndarray       # Ideal unperturbed slot
    fuel_kg: float = M_FUEL0
    status: str = "NOMINAL"         # NOMINAL | EVADING | RECOVERING | EOL
    last_burn_time: Optional[datetime] = None
    collisions_avoided: int = 0
    total_dv_used: float = 0.0
    outage_seconds: float = 0.0
    maneuver_log: List[dict] = field(default_factory=list)

    @property
    def mass_kg(self) -> float:
        return M_DRY + self.fuel_kg

    @property
    def fuel_fraction(self) -> float:
        return self.fuel_kg / M_FUEL0

    @property
    def is_eol(self) -> bool:
        return self.fuel_fraction <= FUEL_EOL

    @property
    def in_station_keeping_box(self) -> bool:
        drift = np.linalg.norm(self.state[:3] - self.nominal_state[:3])
        return drift <= SK_BOX

    @property
    def drift_km(self) -> float:
        return float(np.linalg.norm(self.state[:3] - self.nominal_state[:3]))

    def can_burn(self, sim_time: datetime) -> bool:
        if self.last_burn_time is None:
            return True
        return (sim_time - self.last_burn_time).total_seconds() >= COOLDOWN

    def to_dict(self) -> dict:
        lat, lon, alt = eci_to_lla(self.state[:3])
        return {
            "id": self.sat_id,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt_km": round(alt, 2),
            "fuel_kg": round(self.fuel_kg, 3),
            "fuel_pct": round(self.fuel_fraction * 100, 1),
            "status": self.status,
            "drift_km": round(self.drift_km, 3),
            "in_box": self.in_station_keeping_box,
            "dv_used": round(self.total_dv_used, 4),
            "collisions_avoided": self.collisions_avoided,
        }


# ── Constellation Manager ───────────────────────────────────────────────────────

class ConstellationManager:
    """
    Central ACM brain. Thread-safe state management.
    """

    SIGNAL_LATENCY = 10.0   # seconds

    def __init__(self):
        self._lock = Lock()
        self.sim_time: datetime = datetime.utcnow()
        self.satellites: Dict[str, SatelliteState] = {}
        self.debris: Dict[str, np.ndarray] = {}
        self.maneuver_queue: List[ScheduledManeuver] = []
        self.executed_maneuvers: List[ScheduledManeuver] = []
        self.assessor = ConjunctionAssessor()
        self.active_cdms: List[CDM] = []
        self.total_collisions = 0
        self.total_maneuvers_executed = 0
        self._init_constellation()
        logger.info("ConstellationManager initialized")

    def _init_constellation(self):
        """Initialize 50 satellites in LEO constellation (Walker-like)."""
        n_planes = 5
        n_per_plane = 10
        base_alt = 550.0    # km above surface
        a = 6378.137 + base_alt
        inc_deg = 53.0

        sat_idx = 0
        for plane in range(n_planes):
            raan = plane * 360.0 / n_planes
            for slot in range(n_per_plane):
                ta = slot * 360.0 / n_per_plane
                state = self._keplerian_to_state(
                    a=a, e=0.0001, i=np.radians(inc_deg),
                    raan=np.radians(raan), argp=0.0, ta=np.radians(ta)
                )
                sat_id = f"SAT-P{plane+1}-{slot+1:02d}"
                self.satellites[sat_id] = SatelliteState(
                    sat_id=sat_id,
                    state=state.copy(),
                    nominal_state=state.copy(),
                )
                sat_idx += 1

        logger.info(f"Initialized {len(self.satellites)} satellites")
        self._init_debris_field()

    def _init_debris_field(self, n_debris: int = 500):
        """Initialize debris field with TLE-like randomized orbits."""
        rng = np.random.default_rng(42)
        for i in range(n_debris):
            alt = rng.uniform(400, 700)
            a = 6378.137 + alt
            inc = np.radians(rng.uniform(0, 98))
            raan = np.radians(rng.uniform(0, 360))
            ta = np.radians(rng.uniform(0, 360))
            e = rng.uniform(0, 0.01)
            state = self._keplerian_to_state(a, e, inc, raan, 0.0, ta)
            self.debris[f"DEB-{i+1:05d}"] = state
        self.assessor.update_debris(self.debris)
        logger.info(f"Initialized {n_debris} debris objects")

    def _keplerian_to_state(self, a, e, i, raan, argp, ta) -> np.ndarray:
        """Convert Keplerian elements to ECI state vector."""
        p = a * (1 - e**2)
        r_mag = p / (1 + e * np.cos(ta))

        # Position in perifocal frame
        r_pf = r_mag * np.array([np.cos(ta), np.sin(ta), 0.0])
        v_pf = np.sqrt(MU / p) * np.array([-np.sin(ta), e + np.cos(ta), 0.0])

        # Rotation matrix: perifocal → ECI
        cos_O, sin_O = np.cos(raan), np.sin(raan)
        cos_i, sin_i = np.cos(i),    np.sin(i)
        cos_w, sin_w = np.cos(argp), np.sin(argp)

        R = np.array([
            [cos_O*cos_w - sin_O*sin_w*cos_i, -cos_O*sin_w - sin_O*cos_w*cos_i,  sin_O*sin_i],
            [sin_O*cos_w + cos_O*sin_w*cos_i, -sin_O*sin_w + cos_O*cos_w*cos_i, -cos_O*sin_i],
            [sin_w*sin_i,                       cos_w*sin_i,                        cos_i      ],
        ])
        return np.concatenate([R @ r_pf, R @ v_pf])

    # ── Telemetry Ingestion ─────────────────────────────────────────────────────

    def ingest_telemetry(self, timestamp: datetime, objects: List[dict]) -> dict:
        """Process incoming telemetry. Updates debris and satellite states."""
        with self._lock:
            updated_debris = {}
            updated_sats = {}
            for obj in objects:
                oid = obj["id"]
                r = obj["r"]; v = obj["v"]
                state = np.array([r["x"], r["y"], r["z"],
                                   v["x"], v["y"], v["z"]])
                if obj["type"] == "DEBRIS":
                    self.debris[oid] = state
                    updated_debris[oid] = state
                elif obj["type"] == "SATELLITE":
                    if oid in self.satellites:
                        self.satellites[oid].state = state
                    updated_sats[oid] = state

            # Rebuild KD-tree if debris updated
            if updated_debris:
                self.assessor.update_debris(self.debris)

        return {
            "status": "ACK",
            "processed_count": len(objects),
            "active_cdm_warnings": len([c for c in self.active_cdms
                                         if c.risk_level in ("RED", "CRITICAL")])
        }

    # ── Maneuver Scheduling ─────────────────────────────────────────────────────

    def schedule_maneuver(self, sat_id: str, maneuver_sequence: List[dict]) -> dict:
        """Validate and queue a maneuver sequence."""
        with self._lock:
            if sat_id not in self.satellites:
                return {"status": "REJECTED", "reason": f"Unknown satellite {sat_id}"}

            sat = self.satellites[sat_id]
            mass = sat.mass_kg
            scheduled = []

            for burn in maneuver_sequence:
                burn_time = datetime.fromisoformat(
                    burn["burnTime"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
                dv = burn["deltaV_vector"]
                dv_eci = np.array([dv["x"], dv["y"], dv["z"]])
                dv_mag = np.linalg.norm(dv_eci)

                # Validate LOS
                has_los, _ = satellite_has_los(sat.state[:3])
                if not has_los:
                    return {"status": "REJECTED", "reason": "No ground station LOS"}

                # Validate fuel
                dm = fuel_consumed(mass, dv_mag)
                if dm > sat.fuel_kg:
                    return {"status": "REJECTED", "reason": "Insufficient fuel"}

                # Validate ΔV limit
                if dv_mag > DV_MAX:
                    return {"status": "REJECTED", "reason": f"ΔV {dv_mag:.4f} exceeds {DV_MAX} km/s limit"}

                mass -= dm
                m = ScheduledManeuver(
                    burn_id=burn["burn_id"],
                    satellite_id=sat_id,
                    burn_time=burn_time,
                    dv_eci=dv_eci,
                    burn_type=burn.get("burn_type", "MANUAL"),
                )
                self.maneuver_queue.append(m)
                scheduled.append(m)

            return {
                "status": "SCHEDULED",
                "validation": {
                    "ground_station_los": True,
                    "sufficient_fuel": True,
                    "projected_mass_remaining_kg": round(mass, 2),
                }
            }

    # ── Simulation Step ─────────────────────────────────────────────────────────

    def simulate_step(self, step_seconds: float) -> dict:
        """Advance simulation by step_seconds. Execute maneuvers, propagate orbits."""
        with self._lock:
            substep = 30.0
            t_elapsed = 0.0
            collisions = 0
            maneuvers_exec = 0

            while t_elapsed < step_seconds:
                dt = min(substep, step_seconds - t_elapsed)
                new_time = self.sim_time + timedelta(seconds=dt)

                # Execute scheduled maneuvers in this window
                due = [m for m in self.maneuver_queue
                       if self.sim_time <= m.burn_time <= new_time]
                for m in due:
                    if m.satellite_id in self.satellites:
                        sat = self.satellites[m.satellite_id]
                        new_state, new_mass = apply_burn(
                            sat.state, m.dv_eci, sat.mass_kg)
                        dv_mag = np.linalg.norm(m.dv_eci)
                        sat.state = new_state
                        sat.fuel_kg = new_mass - M_DRY
                        sat.last_burn_time = m.burn_time
                        sat.total_dv_used += dv_mag
                        sat.maneuver_log.append({
                            "burn_id": m.burn_id,
                            "time": m.burn_time.isoformat(),
                            "dv_mag": round(dv_mag * 1000, 3),   # m/s
                            "type": m.burn_type,
                            "fuel_remaining_kg": round(sat.fuel_kg, 3),
                        })
                        self.maneuver_queue.remove(m)
                        self.executed_maneuvers.append(m)
                        maneuvers_exec += 1

                # Propagate all objects
                for sat in self.satellites.values():
                    sat.state = rk4_step(sat.state, dt)
                    sat.nominal_state = rk4_step(sat.nominal_state, dt)

                    # Update status
                    if not sat.in_station_keeping_box:
                        sat.outage_seconds += dt
                        if sat.status == "NOMINAL":
                            sat.status = "EVADING"
                    else:
                        if sat.status in ("EVADING", "RECOVERING"):
                            sat.status = "NOMINAL"

                    # EOL check
                    if sat.is_eol and sat.status != "EOL":
                        sat.status = "EOL"
                        self._schedule_graveyard(sat)

                for deb_id in list(self.debris.keys()):
                    self.debris[deb_id] = rk4_step(self.debris[deb_id], dt)

                self.sim_time = new_time
                t_elapsed += dt

            # Rebuild KD-tree after propagation
            self.assessor.update_debris(self.debris)

            # Run conjunction assessment
            sat_states = {s.sat_id: s.state for s in self.satellites.values()
                          if s.status != "EOL"}
            self.active_cdms = self.assessor.assess(sat_states, self.sim_time)

            # Auto-plan evasion for critical conjunctions
            for cdm in self.active_cdms:
                if cdm.is_critical:
                    collisions += 1
                    self._auto_evade(cdm)

            self.total_collisions += collisions
            self.total_maneuvers_executed += maneuvers_exec

            return {
                "status": "STEP_COMPLETE",
                "new_timestamp": self.sim_time.isoformat() + "Z",
                "collisions_detected": collisions,
                "maneuvers_executed": maneuvers_exec,
            }

    def _auto_evade(self, cdm: CDM):
        """Automatically plan and queue evasion + recovery maneuver pair."""
        sat = self.satellites.get(cdm.sat_id)
        if not sat or not sat.can_burn(self.sim_time):
            return
        has_los, _ = satellite_has_los(sat.state[:3])
        if not has_los:
            return

        dv_evade = plan_evasion_maneuver(
            cdm.sat_state, cdm.deb_state, cdm.tca_seconds)
        burn_time = self.sim_time + timedelta(seconds=self.SIGNAL_LATENCY + 60)

        # Schedule evasion
        evasion = ScheduledManeuver(
            burn_id=f"AUTO_EVADE_{cdm.sat_id}_{cdm.deb_id}",
            satellite_id=cdm.sat_id,
            burn_time=burn_time,
            dv_eci=dv_evade,
            burn_type="EVASION",
            cdm_id=f"{cdm.sat_id}_{cdm.deb_id}",
        )
        self.maneuver_queue.append(evasion)
        sat.status = "EVADING"
        sat.collisions_avoided += 1

        # Schedule recovery 90 min later
        dv_recover = plan_recovery_maneuver(sat.state, sat.nominal_state)
        recovery = ScheduledManeuver(
            burn_id=f"AUTO_RECOVER_{cdm.sat_id}",
            satellite_id=cdm.sat_id,
            burn_time=burn_time + timedelta(seconds=COOLDOWN + 60),
            dv_eci=dv_recover,
            burn_type="RECOVERY",
        )
        self.maneuver_queue.append(recovery)
        sat.status = "RECOVERING"
        logger.info(f"Auto-evasion scheduled for {cdm.sat_id} vs {cdm.deb_id}")

    def _schedule_graveyard(self, sat: SatelliteState):
        """Schedule final deorbit to graveyard orbit for EOL satellite."""
        dv_deorbit = np.array([0.0, -0.050, 0.0])   # Retrograde 50 m/s
        burn_time = self.sim_time + timedelta(seconds=30)
        m = ScheduledManeuver(
            burn_id=f"GRAVEYARD_{sat.sat_id}",
            satellite_id=sat.sat_id,
            burn_time=burn_time,
            dv_eci=dv_deorbit,
            burn_type="GRAVEYARD",
        )
        self.maneuver_queue.append(m)
        logger.info(f"Graveyard maneuver scheduled for EOL satellite {sat.sat_id}")

    # ── Visualization Snapshot ──────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Optimized snapshot for frontend visualization."""
        with self._lock:
            sats = [s.to_dict() for s in self.satellites.values()]

            # Compact debris: [ID, lat, lon, alt]
            debris_cloud = []
            for did, state in list(self.debris.items())[:2000]:   # cap at 2000 for perf
                lat, lon, alt = eci_to_lla(state[:3])
                debris_cloud.append([did, round(lat, 2), round(lon, 2), round(alt, 1)])

            cdm_list = [{
                "sat_id": c.sat_id,
                "deb_id": c.deb_id,
                "tca_s": round(c.tca_seconds, 1),
                "miss_km": round(c.miss_distance_km, 3),
                "risk": c.risk_level,
            } for c in self.active_cdms[:50]]

            return {
                "timestamp": self.sim_time.isoformat() + "Z",
                "satellites": sats,
                "debris_cloud": debris_cloud,
                "active_cdms": cdm_list,
                "fleet_stats": self._fleet_stats(),
            }

    def _fleet_stats(self) -> dict:
        sats = list(self.satellites.values())
        nominal = sum(1 for s in sats if s.status == "NOMINAL")
        total_fuel = sum(s.fuel_kg for s in sats)
        total_dv = sum(s.total_dv_used for s in sats)
        return {
            "total_satellites": len(sats),
            "nominal": nominal,
            "evading": sum(1 for s in sats if s.status == "EVADING"),
            "recovering": sum(1 for s in sats if s.status == "RECOVERING"),
            "eol": sum(1 for s in sats if s.status == "EOL"),
            "total_fuel_kg": round(total_fuel, 2),
            "total_dv_km_s": round(total_dv, 4),
            "active_cdms": len(self.active_cdms),
            "collisions_avoided": sum(s.collisions_avoided for s in sats),
            "uptime_pct": round(nominal / max(len(sats), 1) * 100, 1),
        }

    def get_satellite_trajectory(self, sat_id: str, minutes: int = 90) -> List[dict]:
        """Compute future ground track for visualization."""
        if sat_id not in self.satellites:
            return []
        state = self.satellites[sat_id].state.copy()
        track = []
        dt = 60.0  # 1 minute steps
        for _ in range(minutes):
            state = rk4_step(state, dt)
            lat, lon, alt = eci_to_lla(state[:3])
            track.append({"lat": round(lat, 3), "lon": round(lon, 3), "alt": round(alt, 1)})
        return track
