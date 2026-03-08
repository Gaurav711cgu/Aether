"""
physics.py
----------
Core orbital mechanics engine.
- RK4 numerical integration
- J2 perturbation model
- RTN <-> ECI frame conversion
- Tsiolkovsky rocket equation fuel tracking
- Hohmann transfer / phasing maneuver planning
"""

import numpy as np
from typing import Tuple

# ── Physical Constants ─────────────────────────────────────────────────────────
MU      = 398600.4418       # Earth gravitational parameter (km³/s²)
RE      = 6378.137          # Earth radius (km)
J2      = 1.08263e-3        # J2 perturbation coefficient
G0      = 9.80665e-3        # Standard gravity (km/s²)  [converted from m/s²]
ISP     = 300.0             # Specific impulse (s)
M_DRY   = 500.0             # Dry mass (kg)
M_FUEL0 = 50.0              # Initial fuel mass (kg)
DV_MAX  = 0.015             # Max ΔV per burn (km/s = 15 m/s)
COOLDOWN = 600.0            # Thruster cooldown (s)
D_CRIT  = 0.100             # Conjunction threshold (km = 100 m)
SK_BOX  = 10.0              # Station-keeping radius (km)
FUEL_EOL = 0.05             # End-of-life fuel fraction → graveyard orbit


# ── J2 Acceleration ────────────────────────────────────────────────────────────

def j2_acceleration(r: np.ndarray) -> np.ndarray:
    """Compute J2 perturbation acceleration vector in ECI frame."""
    x, y, z = r
    r_mag = np.linalg.norm(r)
    factor = (3/2) * J2 * MU * RE**2 / r_mag**5
    common = 5 * z**2 / r_mag**2
    ax = factor * x * (common - 1)
    ay = factor * y * (common - 1)
    az = factor * z * (common - 3)
    return np.array([ax, ay, az])


def equations_of_motion(t: float, state: np.ndarray) -> np.ndarray:
    """
    Full equations of motion with J2.
    state = [x, y, z, vx, vy, vz]
    returns d(state)/dt
    """
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    a_gravity = -MU / r_mag**3 * r
    a_j2 = j2_acceleration(r)
    a_total = a_gravity + a_j2
    return np.concatenate([v, a_total])


# ── RK4 Integrator ─────────────────────────────────────────────────────────────

def rk4_step(state: np.ndarray, dt: float) -> np.ndarray:
    """Single RK4 integration step."""
    k1 = equations_of_motion(0, state)
    k2 = equations_of_motion(0, state + 0.5 * dt * k1)
    k3 = equations_of_motion(0, state + 0.5 * dt * k2)
    k4 = equations_of_motion(0, state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)


def propagate(state: np.ndarray, dt_total: float, dt_step: float = 10.0) -> np.ndarray:
    """
    Propagate state vector forward by dt_total seconds.
    Uses adaptive sub-stepping for accuracy.
    """
    remaining = dt_total
    current = state.copy()
    while remaining > 0:
        step = min(dt_step, remaining)
        current = rk4_step(current, step)
        remaining -= step
    return current


def propagate_history(state: np.ndarray, dt_total: float,
                      dt_step: float = 30.0) -> np.ndarray:
    """Returns array of states at each step (for trajectory visualization)."""
    steps = int(dt_total / dt_step)
    history = np.zeros((steps + 1, 6))
    history[0] = state
    for i in range(steps):
        history[i+1] = rk4_step(history[i], dt_step)
    return history


# ── RTN Frame ──────────────────────────────────────────────────────────────────

def eci_to_rtn_matrix(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    Compute rotation matrix from ECI to RTN frame.
    R: radial (r̂), T: transverse (v direction), N: normal (R×T)
    """
    R_hat = r / np.linalg.norm(r)
    N_hat = np.cross(r, v)
    N_hat /= np.linalg.norm(N_hat)
    T_hat = np.cross(N_hat, R_hat)
    return np.array([R_hat, T_hat, N_hat])   # rows = RTN unit vectors


def rtn_to_eci(dv_rtn: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Convert ΔV from RTN frame to ECI frame."""
    M = eci_to_rtn_matrix(r, v)
    return M.T @ dv_rtn   # inverse rotation = transpose


# ── Tsiolkovsky Rocket Equation ────────────────────────────────────────────────

def fuel_consumed(m_current: float, dv_mag: float) -> float:
    """
    Mass of propellant consumed for a given ΔV.
    ΔV in km/s, Isp × g0 in km/s.
    """
    ve = ISP * G0   # effective exhaust velocity (km/s)
    dm = m_current * (1 - np.exp(-dv_mag / ve))
    return dm


def apply_burn(state: np.ndarray, dv_eci: np.ndarray,
               m_current: float) -> Tuple[np.ndarray, float]:
    """
    Apply impulsive burn. Returns new state and new mass.
    dv_eci in km/s.
    """
    dv_mag = np.linalg.norm(dv_eci)
    if dv_mag == 0:
        return state, m_current
    dm = fuel_consumed(m_current, dv_mag)
    new_state = state.copy()
    new_state[3:] += dv_eci
    return new_state, m_current - dm


# ── Conjunction Detection ──────────────────────────────────────────────────────

def time_of_closest_approach(
    state_sat: np.ndarray,
    state_deb: np.ndarray,
    t_horizon: float = 86400.0,
    dt: float = 30.0
) -> Tuple[float, float]:
    """
    Find TCA and minimum miss distance between satellite and debris
    over t_horizon seconds using coarse scan + fine refinement.
    Returns (tca_seconds, min_distance_km).
    """
    min_dist = np.inf
    tca = 0.0
    s1, s2 = state_sat.copy(), state_deb.copy()

    t = 0.0
    while t <= t_horizon:
        dist = np.linalg.norm(s1[:3] - s2[:3])
        if dist < min_dist:
            min_dist = dist
            tca = t
        s1 = rk4_step(s1, dt)
        s2 = rk4_step(s2, dt)
        t += dt

    return tca, min_dist


# ── Maneuver Planning ──────────────────────────────────────────────────────────

def plan_evasion_maneuver(
    state_sat: np.ndarray,
    state_deb: np.ndarray,
    tca: float,
    dv_budget: float = 0.010   # km/s
) -> np.ndarray:
    """
    Plan minimum-fuel evasion maneuver in RTN frame.
    Uses prograde/retrograde burn (most fuel-efficient).
    Returns ΔV vector in ECI frame (km/s).
    """
    r, v = state_sat[:3], state_sat[3:]

    # Relative position at TCA
    s1 = propagate(state_sat, tca)
    s2 = propagate(state_deb, tca)
    rel_pos = s1[:3] - s2[:3]

    # Choose prograde or retrograde based on approach direction
    R_hat = r / np.linalg.norm(r)
    N_hat = np.cross(r, v); N_hat /= np.linalg.norm(N_hat)
    T_hat = np.cross(N_hat, R_hat)

    # Project approach vector onto T (transverse) direction
    approach_T = np.dot(rel_pos, T_hat)
    sign = 1.0 if approach_T >= 0 else -1.0

    # Clamp to DV_MAX
    dv_mag = min(dv_budget, DV_MAX)
    dv_rtn = np.array([0.0, sign * dv_mag, 0.0])   # Prograde/retrograde
    dv_eci = rtn_to_eci(dv_rtn, r, v)
    return dv_eci


def plan_recovery_maneuver(
    state_current: np.ndarray,
    state_nominal: np.ndarray
) -> np.ndarray:
    """
    Plan recovery burn to return satellite to nominal slot.
    Uses simplified Hohmann-like transfer.
    Returns ΔV in ECI (km/s).
    """
    r_cur = state_current[:3]
    v_cur = state_current[3:]
    r_nom = state_nominal[:3]

    # Simple correction: target the difference in velocity direction
    dr = r_nom - r_cur
    dv_correction = dr * 1e-4   # gentle nudge proportional to offset

    # Clamp magnitude
    mag = np.linalg.norm(dv_correction)
    if mag > DV_MAX:
        dv_correction = dv_correction / mag * DV_MAX

    return dv_correction


# ── ECI ↔ Lat/Lon/Alt ─────────────────────────────────────────────────────────

def eci_to_lla(r_eci: np.ndarray, gst: float = 0.0) -> Tuple[float, float, float]:
    """
    Convert ECI position to geodetic Lat/Lon/Alt.
    gst: Greenwich Sidereal Time (radians). Approximate as 0 for visualization.
    """
    x, y, z = r_eci
    # Rotate by GST to get ECEF
    x_ecef = x * np.cos(gst) + y * np.sin(gst)
    y_ecef = -x * np.sin(gst) + y * np.cos(gst)
    z_ecef = z

    lon = np.degrees(np.arctan2(y_ecef, x_ecef))
    r_xy = np.sqrt(x_ecef**2 + y_ecef**2)
    lat = np.degrees(np.arctan2(z_ecef, r_xy))
    alt = np.linalg.norm(r_eci) - RE
    return lat, lon, alt


# ── Orbital Elements ───────────────────────────────────────────────────────────

def state_to_elements(state: np.ndarray) -> dict:
    """Convert state vector to Keplerian orbital elements."""
    r = state[:3]; v = state[3:]
    r_mag = np.linalg.norm(r)
    v_mag = np.linalg.norm(v)

    h = np.cross(r, v)
    h_mag = np.linalg.norm(h)
    e_vec = np.cross(v, h) / MU - r / r_mag
    e = np.linalg.norm(e_vec)
    a = 1 / (2/r_mag - v_mag**2/MU)
    i = np.degrees(np.arccos(h[2] / h_mag))

    return {"a": a, "e": e, "i": i,
            "h": h_mag, "r": r_mag, "v": v_mag}


def orbital_period(a: float) -> float:
    """Orbital period in seconds given semi-major axis in km."""
    return 2 * np.pi * np.sqrt(a**3 / MU)
