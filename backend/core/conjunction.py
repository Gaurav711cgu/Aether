"""
conjunction.py
--------------
High-performance conjunction assessment using KD-Tree spatial indexing.
Avoids O(N²) brute-force by first filtering with bounding sphere queries,
then running precise TCA propagation only on candidate pairs.

Pipeline:
  1. Build KD-Tree over all debris positions
  2. For each satellite, query debris within a 50km radius
  3. For each candidate pair, compute TCA via propagation
  4. Flag conjunctions below D_CRIT (100m)
"""

import numpy as np
from scipy.spatial import KDTree
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .physics import (
    propagate, time_of_closest_approach,
    plan_evasion_maneuver, plan_recovery_maneuver,
    D_CRIT, SK_BOX, rtn_to_eci, eci_to_lla
)


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class CDM:
    """Conjunction Data Message."""
    sat_id: str
    deb_id: str
    tca_seconds: float          # seconds from now
    tca_timestamp: datetime
    miss_distance_km: float
    probability: float          # simplified estimate
    sat_state: np.ndarray
    deb_state: np.ndarray

    @property
    def is_critical(self) -> bool:
        return self.miss_distance_km < D_CRIT

    @property
    def risk_level(self) -> str:
        if self.miss_distance_km < D_CRIT:
            return "CRITICAL"
        elif self.miss_distance_km < 1.0:
            return "RED"
        elif self.miss_distance_km < 5.0:
            return "YELLOW"
        return "GREEN"


@dataclass
class ScheduledManeuver:
    burn_id: str
    satellite_id: str
    burn_time: datetime
    dv_eci: np.ndarray          # ΔV in ECI (km/s)
    burn_type: str              # EVASION | RECOVERY | GRAVEYARD
    cdm_id: Optional[str] = None


# ── Conjunction Assessor ───────────────────────────────────────────────────────

class ConjunctionAssessor:
    """
    High-performance conjunction assessment engine.
    Uses KD-Tree for O(N log N) screening.
    """

    # Pre-screening radius: propagate up to ~50km approach zone
    SCREEN_RADIUS = 50.0    # km
    HORIZON       = 86400.0 # 24 hours

    def __init__(self):
        self._debris_positions: np.ndarray = np.empty((0, 3))
        self._debris_states: Dict[str, np.ndarray] = {}
        self._debris_ids: List[str] = []
        self._kdtree: Optional[KDTree] = None
        self._active_cdms: List[CDM] = []

    def update_debris(self, debris_states: Dict[str, np.ndarray]):
        """Rebuild KD-Tree with latest debris positions."""
        self._debris_states = debris_states
        self._debris_ids = list(debris_states.keys())
        if not self._debris_ids:
            self._kdtree = None
            return
        self._debris_positions = np.array([
            debris_states[d][:3] for d in self._debris_ids
        ])
        self._kdtree = KDTree(self._debris_positions)

    def assess(
        self,
        sat_states: Dict[str, np.ndarray],
        sim_time: datetime
    ) -> List[CDM]:
        """
        Run full conjunction assessment for all satellites.
        Returns list of CDMs sorted by miss distance.
        """
        if self._kdtree is None or not sat_states:
            return []

        cdms = []
        for sat_id, sat_state in sat_states.items():
            sat_pos = sat_state[:3]

            # Stage 1: KD-Tree coarse screen — find debris within SCREEN_RADIUS
            candidate_indices = self._kdtree.query_ball_point(
                sat_pos, self.SCREEN_RADIUS
            )
            if not candidate_indices:
                continue

            # Stage 2: Propagate candidates and find TCA
            for idx in candidate_indices:
                deb_id = self._debris_ids[idx]
                deb_state = self._debris_states[deb_id]

                tca_s, miss_dist = time_of_closest_approach(
                    sat_state, deb_state,
                    t_horizon=self.HORIZON,
                    dt=30.0
                )

                if miss_dist < self.SCREEN_RADIUS:
                    prob = self._collision_probability(miss_dist)
                    cdm = CDM(
                        sat_id=sat_id,
                        deb_id=deb_id,
                        tca_seconds=tca_s,
                        tca_timestamp=sim_time + timedelta(seconds=tca_s),
                        miss_distance_km=miss_dist,
                        probability=prob,
                        sat_state=sat_state.copy(),
                        deb_state=deb_state.copy(),
                    )
                    cdms.append(cdm)

        cdms.sort(key=lambda c: c.miss_distance_km)
        self._active_cdms = cdms
        return cdms

    def _collision_probability(self, miss_dist: float) -> float:
        """Simplified Pc estimate based on miss distance."""
        if miss_dist <= D_CRIT:
            return 1.0
        elif miss_dist < 1.0:
            return 0.8 * np.exp(-miss_dist)
        elif miss_dist < 5.0:
            return 0.1 * np.exp(-miss_dist / 2)
        return max(0.0, 0.01 * np.exp(-miss_dist / 10))

    @property
    def active_cdms(self) -> List[CDM]:
        return self._active_cdms

    def get_cdms_for_sat(self, sat_id: str) -> List[CDM]:
        return [c for c in self._active_cdms if c.sat_id == sat_id]


# ── Ground Station LOS ────────────────────────────────────────────────────────

GROUND_STATIONS = [
    {"id": "GS-001", "name": "ISTRAC_Bengaluru",     "lat": 13.0333,  "lon":  77.5167, "elev_m": 820,  "min_el": 5.0},
    {"id": "GS-002", "name": "Svalbard",              "lat": 78.2297,  "lon":  15.4077, "elev_m": 400,  "min_el": 5.0},
    {"id": "GS-003", "name": "Goldstone",             "lat": 35.4266,  "lon": -116.890, "elev_m": 1000, "min_el": 10.0},
    {"id": "GS-004", "name": "Punta_Arenas",          "lat": -53.1500, "lon": -70.9167, "elev_m": 30,   "min_el": 5.0},
    {"id": "GS-005", "name": "IIT_Delhi",             "lat": 28.5450,  "lon":  77.1926, "elev_m": 225,  "min_el": 15.0},
    {"id": "GS-006", "name": "McMurdo",               "lat": -77.8463, "lon": 166.6682, "elev_m": 10,   "min_el": 5.0},
]


def gs_ecef(gs: dict) -> np.ndarray:
    """Convert ground station lat/lon/alt to ECEF (approx ECI for our purposes)."""
    from .physics import RE
    lat = np.radians(gs["lat"])
    lon = np.radians(gs["lon"])
    alt = gs["elev_m"] / 1000.0   # km
    r = RE + alt
    return np.array([
        r * np.cos(lat) * np.cos(lon),
        r * np.cos(lat) * np.sin(lon),
        r * np.sin(lat)
    ])


def satellite_has_los(sat_pos_eci: np.ndarray, gst: float = 0.0) -> Tuple[bool, List[str]]:
    """
    Check if satellite has line-of-sight to at least one ground station.
    Returns (has_los, list_of_visible_station_ids).
    """
    visible = []
    for gs in GROUND_STATIONS:
        gs_pos = gs_ecef(gs)
        # Vector from GS to satellite
        to_sat = sat_pos_eci - gs_pos
        to_sat_norm = to_sat / np.linalg.norm(to_sat)
        gs_up = gs_pos / np.linalg.norm(gs_pos)
        # Elevation angle
        el = np.degrees(np.arcsin(np.dot(to_sat_norm, gs_up)))
        if el >= gs["min_el"]:
            visible.append(gs["id"])
    return len(visible) > 0, visible
