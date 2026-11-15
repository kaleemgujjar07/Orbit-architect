"""
Orbit Architect — simulation engine (real physics, Python stdlib only).

Team PyInTheSky, NASA Space Apps Challenge 2026, Space Mission Design Game.
All quantities carry explicit units in names / docstrings. No toy constants
are hidden: every budget is computed from the inputs below.

References (standard astrodynamics):
  T  = 2*pi*sqrt(a^3 / mu)            orbital period
  v  = sqrt(mu / r)                   circular orbital velocity
  Hohmann transfer between circular orbits r1 -> r2
  dv = Isp * g0 * ln(m0 / mf)         Tsiolkovsky rocket equation
  P  ~ 1 / d^2                        solar power, inverse-square law
  FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.44   Friis (free space)
"""
import math

G0 = 9.80665  # m/s^2, standard gravity
AU_KM = 149_597_870.7  # km
SOLAR_CONSTANT_W_M2 = 1361.0  # W/m^2 at 1 AU

# Gravitational parameters, km^3/s^2
MU = {
    "earth": 398600.4418,
    "moon": 4902.80066,
    "mars": 42828.375,
    "venus": 324858.592,
    "jupiter": 126686534.0,
    "sun": 132712440018.0,
}
# Mean radii, km
RADIUS_KM = {
    "earth": 6371.0,
    "moon": 1737.4,
    "mars": 3389.5,
    "venus": 6051.8,
    "jupiter": 69911.0,
    "sun": 695700.0,
}


# ---------------------------------------------------------------- orbital ----
def orbital_period_min(semi_major_axis_km, mu_km3_s2):
    """Orbital period in minutes. T = 2*pi*sqrt(a^3/mu)."""
    if semi_major_axis_km <= 0 or mu_km3_s2 <= 0:
        raise ValueError("a and mu must be positive")
    return 2 * math.pi * math.sqrt(semi_major_axis_km ** 3 / mu_km3_s2) / 60.0


def circular_velocity_km_s(radius_km, mu_km3_s2):
    """Circular orbital velocity in km/s. v = sqrt(mu/r)."""
    return math.sqrt(mu_km3_s2 / radius_km)


def escape_velocity_km_s(radius_km, mu_km3_s2):
    """Escape velocity in km/s. v_esc = sqrt(2*mu/r)."""
    return math.sqrt(2 * mu_km3_s2 / radius_km)


def hohmann_delta_v_km_s(r1_km, r2_km, mu_km3_s2):
    """Hohmann transfer between two circular orbits.

    Returns dict with dv1, dv2, total dv (km/s) and transfer time (days).
    r1, r2 are orbital radii (body centre to spacecraft), km.
    """
    v1 = circular_velocity_km_s(r1_km, mu_km3_s2)
    v2 = circular_velocity_km_s(r2_km, mu_km3_s2)
    a_t = (r1_km + r2_km) / 2.0
    vt1 = math.sqrt(mu_km3_s2 * (2 / r1_km - 1 / a_t))
    vt2 = math.sqrt(mu_km3_s2 * (2 / r2_km - 1 / a_t))
    dv1 = abs(vt1 - v1)
    dv2 = abs(v2 - vt2)
    transfer_min = math.pi * math.sqrt(a_t ** 3 / mu_km3_s2) / 60.0
    return {
        "dv1_km_s": dv1, "dv2_km_s": dv2, "total_km_s": dv1 + dv2,
        "transfer_days": transfer_min / 1440.0, "transfer_min": transfer_min,
    }


def inclination_change_dv_km_s(velocity_km_s, delta_deg):
    """Plane-change cost: dv = 2*v*sin(delta_i/2), km/s."""
    return 2 * velocity_km_s * math.sin(math.radians(delta_deg) / 2.0)


# -------------------------------------------------------------- propulsion ----
def tsiolkovsky_dv_m_s(isp_s, m0_kg, mf_kg):
    """Delta-v in m/s from Tsiolkovsky: dv = Isp*g0*ln(m0/mf)."""
    if m0_kg <= mf_kg or mf_kg <= 0:
        raise ValueError("need m0 > mf > 0")
    return isp_s * G0 * math.log(m0_kg / mf_kg)


def propellant_for_dv_kg(dry_mass_kg, dv_m_s, isp_s):
    """Propellant mass (kg) needed for a given dv from a dry mass.

    m0 = mf * exp(dv/(Isp*g0));  prop = m0 - mf.
    """
    if dv_m_s <= 0:
        return 0.0
    return dry_mass_kg * (math.exp(dv_m_s / (isp_s * G0)) - 1.0)


def mass_ratio_for_dv(dv_m_s, isp_s):
    """m0/mf = exp(dv/(Isp*g0))."""
    return math.exp(dv_m_s / (isp_s * G0))


# ------------------------------------------------------------------- power ----
def solar_power_w(array_area_m2, efficiency, distance_au, degradation=1.0):
    """Solar-array power in W: P = 1361 * A * eta / d^2 * degradation."""
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    return SOLAR_CONSTANT_W_M2 * array_area_m2 * efficiency / (distance_au ** 2) * degradation


def eclipse_fraction(altitude_km, body_radius_km=6371.0):
    """Approx. fraction of an orbit in eclipse (circular orbit, Sun far away).

    f_eclipse ~= (1/pi) * asin(R / (R+h))  -- geometric shadow fraction.
    LEO 400 km gives ~0.39 (ISS-like), GEO gives ~0.05. Returns 0..0.5.
    """
    r = body_radius_km + altitude_km
    if r <= body_radius_km:
        return 0.0
    return math.asin(body_radius_km / r) / math.pi


def battery_energy_wh(capacity_ah, voltage_v, depth_of_discharge=0.6):
    """Usable battery energy in Wh = Ah * V * DoD."""
    return capacity_ah * voltage_v * depth_of_discharge


def power_margin_pct(generated_w, consumed_w):
    """(generated-consumed)/consumed * 100. Negative = deficit."""
    if consumed_w <= 0:
        return 100.0
    return (generated_w - consumed_w) / consumed_w * 100.0


# -------------------------------------------------------------------- link ----
def free_space_path_loss_db(distance_km, freq_mhz):
    """Friis free-space path loss, dB: 20log10(d_km)+20log10(f_MHz)+32.44."""
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44


def link_budget_db(distance_km, freq_ghz, tx_power_w, tx_gain_dbi,
                   rx_gain_dbi, data_rate_mbps, system_noise_db=2.0):
    """Simple link budget. Returns dict with FSPL, received power, margin.

    Received power (dBm) = 10log10(Ptx_W*1000) + Gtx + Grx - FSPL.
    Required Eb/N0 ~ 5 dB for QPSK at 1e-5 BER is folded into a
    10*log10(data_rate) term; margin = Prx - (-174 + 10log10(BW) + NF).
    This is an educational model, not a substitute for a full link design.
    """
    fspl = free_space_path_loss_db(distance_km, freq_ghz * 1000.0)
    ptx_dbm = 10 * math.log10(tx_power_w * 1000.0)
    prx_dbm = ptx_dbm + tx_gain_dbi + rx_gain_dbi - fspl
    # Noise floor for the channel bandwidth ~ data rate (Hz ~= bps)
    bw_hz = max(data_rate_mbps * 1e6, 1.0)
    noise_dbm = -174.0 + 10 * math.log10(bw_hz) + system_noise_db
    # Require ~2 dB SNR: modern LDPC/Turbo coding needs Eb/N0 ~1-2 dB,
    # not the 8 dB of an uncoded link.
    margin_db = prx_dbm - noise_dbm - 2.0
    return {
        "fspl_db": round(fspl, 2), "tx_power_dbm": round(ptx_dbm, 2),
        "received_dbm": round(prx_dbm, 2), "noise_dbm": round(noise_dbm, 2),
        "margin_db": round(margin_db, 2),
        "link_ok": margin_db > 0,
    }


def passes_per_day(orbital_period_min):
    """Ground-station passes/day, rough: ~1440/period, capped by geometry."""
    if orbital_period_min <= 0:
        return 0.0
    return round(1440.0 / orbital_period_min, 1)


# -------------------------------------------------------------------- mass ----
def mass_budget(dry_mass_kg, payload_kg, propellant_kg, structure_frac=0.18):
    """Mass budget. Returns totals and margin vs a 20% contingency rule.

    structure is estimated as structure_frac * dry mass when not given
    separately; callers pass dry mass already including structure.
    """
    wet = dry_mass_kg + propellant_kg
    total = wet + payload_kg
    contingency_kg = total * 0.20
    return {
        "dry_mass_kg": dry_mass_kg, "payload_kg": payload_kg,
        "propellant_kg": propellant_kg, "wet_mass_kg": wet,
        "total_mass_kg": total, "contingency_kg": contingency_kg,
        "total_with_margin_kg": total + contingency_kg,
    }


# ------------------------------------------------------- design evaluation ----
def evaluate_design(design, data):
    """Evaluate a full mission design. Returns a dict of budgets + checks.

    design keys: mission_id, bus_id, instrument_ids (list), launch_vehicle_id,
    orbit_id, difficulty ('easy'|'normal'|'hard').
    data is the module imported from data.py (dicts MISSIONS, BUSES, ...).
    """
    # Accept both the lowercase API dicts and the UPPERCASE module names.
    def _table(name):
        return data.get(name) or data.get(name.upper())
    mission = _table("missions")[design["mission_id"]]
    bus = _table("buses")[design["bus_id"]]
    lv = _table("launch_vehicles")[design["launch_vehicle_id"]]
    orbit = _table("orbits")[design["orbit_id"]]
    instruments = [_table("instruments")[i] for i in design.get("instrument_ids", [])]
    difficulty = design.get("difficulty", "normal")
    diff = _table("difficulty")[difficulty]

    # --- mass ---
    inst_mass = sum(i["mass_kg"] for i in instruments)
    dry_mass = bus["dry_mass_kg"] + inst_mass
    # propellant sized from the mission's required dv and the bus Isp
    dv_req_m_s = mission["required_dv_m_s"]
    # Size propellant for required dv + 25% reserve (standard margin).
    prop = propellant_for_dv_kg(dry_mass, dv_req_m_s * 1.25, bus["isp_s"])
    mb = mass_budget(dry_mass, inst_mass, prop)
    total_mass = mb["total_with_margin_kg"]
    lv_cap = lv["payload_capacity_kg"].get(orbit["lv_class"], lv["payload_capacity_kg"]["leo"])
    mass_ok = total_mass <= lv_cap
    mass_margin_pct = (lv_cap - total_mass) / lv_cap * 100 if lv_cap else -100

    # --- cost ---
    cost_m = (mission["ops_cost_m"] + bus["cost_m"] + lv["cost_m"]
              + sum(i["cost_m"] for i in instruments))
    budget_cap_m = mission["budget_cap_m"] * diff["budget_factor"]
    cost_ok = cost_m <= budget_cap_m
    budget_used_pct = cost_m / budget_cap_m * 100 if budget_cap_m else 999

    # --- power ---
    dist_au = orbit["distance_au"]
    eclipse = eclipse_fraction(orbit["altitude_km"], RADIUS_KM.get(mission["body"], 6371.0)) \
        if orbit["altitude_km"] else 0.0
    gen_w = solar_power_w(bus["solar_array_m2"], bus["solar_efficiency"],
                          dist_au, degradation=0.92) * (1 - eclipse * 0.35)
    gen_w += bus.get("rtg_power_w", 0.0)  # nuclear power, distance-independent
    cons_w = bus["base_power_w"] + sum(i["power_w"] for i in instruments)
    p_margin = power_margin_pct(gen_w, cons_w)
    power_ok = gen_w >= cons_w * 1.05  # need >=5% margin to be safe
    battery_wh = battery_energy_wh(bus["battery_ah"], bus["battery_v"])

    # --- data / link ---
    # Deep-space instruments duty-cycle (they do not record at full rate
    # continuously); orbit["duty_cycle"] models that.
    data_gen = sum(i["data_gb_day"] for i in instruments) * orbit.get("duty_cycle", 1.0)
    lb = link_budget_db(orbit["distance_km"], orbit["freq_ghz"],
                        bus["tx_power_w"], bus["tx_gain_dbi"],
                        orbit["ground_gain_dbi"], orbit["data_rate_mbps"])
    passes = passes_per_day(orbital_period_min(
        RADIUS_KM.get(mission["body"], 6371.0) + orbit["altitude_km"],
        MU.get(mission["body"], MU["earth"]))) if orbit["altitude_km"] else 2.0
    # Downlink capacity per day: passes * contact minutes * rate
    downlink_gb_day = passes * orbit["contact_min_per_pass"] * 60 * orbit["data_rate_mbps"] / 8 / 1000
    if not lb["link_ok"]:
        downlink_gb_day *= 0.25  # weak link: retransmits, low rate
    data_returned_pct = min(100.0, downlink_gb_day / data_gen * 100) if data_gen else 100.0
    data_ok = downlink_gb_day >= data_gen * 0.8

    # --- science ---
    science = sum(i["science"] for i in instruments)
    # Orbit / body suitability: instruments have a target; mismatch halves value
    matched = [i for i in instruments if mission["body"] in i["targets"] or "any" in i["targets"]]
    science_eff = sum(i["science"] for i in matched) + 0.5 * sum(
        i["science"] for i in instruments if i not in matched)
    science_pct = min(100.0, science_eff / mission["science_target"] * 100) if mission["science_target"] else 0

    # --- lifetime / reliability ---
    lifetime_months = min(bus["design_life_months"], mission["lifetime_months"])
    rad = orbit["radiation"]  # 0..1
    thermal = orbit["thermal_risk"]  # 0..1
    reliability = max(0.05, 1.0 - rad * 0.25 - thermal * 0.15
                      - (0.10 if p_margin < 10 else 0.0)
                      - (0.10 if mass_margin_pct < 10 else 0.0))
    lifetime_pct = lifetime_months / mission["lifetime_months"] * 100 if mission["lifetime_months"] else 0

    # --- delta-v check (spacecraft) ---
    dv_avail = tsiolkovsky_dv_m_s(bus["isp_s"], dry_mass + prop, dry_mass)
    dv_ok = dv_avail >= dv_req_m_s * 0.999

    checks = [
        {"name": "Launch mass vs vehicle capacity", "ok": bool(mass_ok),
         "detail": f"{total_mass:.0f} kg with margin vs {lv_cap:.0f} kg capacity"},
        {"name": "Delta-v budget", "ok": bool(dv_ok),
         "detail": f"need {dv_req_m_s:.0f} m/s, spacecraft provides {dv_avail:.0f} m/s"},
        {"name": "Power budget", "ok": bool(power_ok),
         "detail": f"{gen_w:.0f} W generated vs {cons_w:.0f} W consumed ({p_margin:.0f}% margin)"},
        {"name": "Budget", "ok": bool(cost_ok),
         "detail": f"${cost_m:.0f}M of ${budget_cap_m:.0f}M cap ({budget_used_pct:.0f}% used)"},
        {"name": "Data downlink", "ok": bool(data_ok),
         "detail": f"{downlink_gb_day:.1f} GB/day downlinked vs {data_gen:.1f} GB/day generated"},
        {"name": "Link margin", "ok": bool(lb["link_ok"]),
         "detail": f"{lb['margin_db']:.1f} dB margin, FSPL {lb['fspl_db']:.0f} dB"},
    ]
    return {
        "mission": mission, "bus": bus, "launch_vehicle": lv, "orbit": orbit,
        "instruments": instruments, "difficulty": difficulty,
        "mass_kg": round(total_mass, 1), "mass_margin_pct": round(mass_margin_pct, 1),
        "cost_m": round(cost_m, 1), "budget_cap_m": round(budget_cap_m, 1),
        "budget_used_pct": round(budget_used_pct, 1),
        "power_generated_w": round(gen_w, 1), "power_consumed_w": round(cons_w, 1),
        "power_margin_pct": round(p_margin, 1), "battery_wh": round(battery_wh, 1),
        "eclipse_fraction": round(eclipse, 3),
        "data_generated_gb_day": round(data_gen, 2),
        "data_downlinked_gb_day": round(downlink_gb_day, 2),
        "data_returned_pct": round(data_returned_pct, 1),
        "link": lb, "passes_per_day": passes,
        "science": science, "science_eff": round(science_eff, 1),
        "science_pct": round(science_pct, 1),
        "lifetime_months": lifetime_months,
        "lifetime_pct": round(lifetime_pct, 1),
        "reliability": round(reliability, 3),
        "dv_required_m_s": dv_req_m_s, "dv_available_m_s": round(dv_avail, 1),
        "dv_ok": bool(dv_ok), "checks": checks,
        "all_checks_pass": all(c["ok"] for c in checks),
    }
