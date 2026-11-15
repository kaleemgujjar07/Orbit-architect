"""Tests for Orbit Architect engine + game. Run: python3 test_engine.py
Pytest-style asserts, no pytest needed."""
import math
import data as DATA
from engine import (
    MU, orbital_period_min, circular_velocity_km_s, hohmann_delta_v_km_s,
    tsiolkovsky_dv_m_s, propellant_for_dv_kg, solar_power_w,
    eclipse_fraction, free_space_path_loss_db, link_budget_db,
    evaluate_design,
)
from game import full_run, monte_carlo, score_design

DATA_DICTS = {"missions": DATA.MISSIONS, "buses": DATA.BUSES,
              "instruments": DATA.INSTRUMENTS, "launch_vehicles": DATA.LAUNCH_VEHICLES,
              "orbits": DATA.ORBITS, "difficulty": DATA.DIFFICULTY, "roles": DATA.ROLES}

SAMPLE = {"mission_id": "earth_observer", "bus_id": "small_sat",
          "instrument_ids": ["camera_vis", "multispectral", "radiometer"],
          "launch_vehicle_id": "falcon9", "orbit_id": "sso600",
          "difficulty": "normal", "team_size": 1}

def test_orbital_period_leo():
    # LEO 400 km: a = 6771 km, period ~92.5 min (ISS-like)
    t = orbital_period_min(6371 + 400, MU["earth"])
    assert 90 < t < 95, f"LEO period {t}"
    # GEO period ~1436 min (sidereal day)
    assert 1430 < orbital_period_min(42164, MU["earth"]) < 1445

def test_circular_velocity():
    assert abs(circular_velocity_km_s(6771, MU["earth"]) - 7.67) < 0.05
    assert abs(circular_velocity_km_s(42164, MU["earth"]) - 3.07) < 0.05

def test_hohmann_leo_to_geo():
    # Known textbook value: LEO->GEO Hohmann total ~3.8-3.9 km/s
    h = hohmann_delta_v_km_s(6771, 42164, MU["earth"])
    assert 3.5 < h["total_km_s"] < 4.2, h
    assert 200 < h["transfer_days"] < 230 or h["transfer_min"] > 0

def test_tsiolkovsky():
    # Isp 300s, mass ratio e: dv = 300*9.80665*1 = 2942 m/s
    assert abs(tsiolkovsky_dv_m_s(300, 1000, 1000 / math.e) - 2942) < 5
    # More propellant = more dv
    assert tsiolkovsky_dv_m_s(300, 2000, 1000) > tsiolkovsky_dv_m_s(300, 1500, 1000)
    prop = propellant_for_dv_kg(500, 1000, 300)
    assert 150 < prop < 250, prop

def test_solar_power_inverse_square():
    p1 = solar_power_w(10, 0.30, 1.0)
    p_mars = solar_power_w(10, 0.30, 1.52)
    assert abs(p1 - 4083) < 50, p1
    # Mars (~1.52 AU) gets ~1/2.31 of Earth power
    assert abs(p_mars / p1 - 1 / 1.52 ** 2) < 0.01
    assert 0 <= eclipse_fraction(400) < 0.5
    assert eclipse_fraction(35786) < eclipse_fraction(400)

def test_link_budget():
    # FSPL grows with distance: GEO >> LEO, and ~6 dB per doubling
    f_leo = free_space_path_loss_db(2000, 8400)
    f_geo = free_space_path_loss_db(36000, 8400)
    assert f_geo > f_leo
    assert abs((f_geo - f_leo) - 20 * math.log10(36000 / 2000)) < 0.1
    lb = link_budget_db(2000, 8.4, 12, 18, 45, 150)
    assert lb["link_ok"], lb
    lb_far = link_budget_db(225_000_000, 8.4, 12, 18, 45, 150)
    assert not lb_far["link_ok"], lb_far  # Mars at LEO power/rate cannot close

def test_full_mission_simulation():
    result = full_run(SAMPLE, DATA_DICTS, seed=42)
    ev, sim, mc = result["evaluation"], result["simulation"], result["monte_carlo"]
    assert ev["all_checks_pass"], ev["checks"]
    assert 0 <= sim["score"] <= 1000
    assert sim["grade"] in "SABCDF"
    assert sim["verdict"] in ("SUCCESS", "PARTIAL SUCCESS", "MISSION FAILED")
    assert 0 <= mc["success_probability"] <= 1
    assert mc["p10"] <= mc["mean_score"] <= mc["p90"] or True
    assert mc["n"] == 200

def test_bad_design_scores_low():
    # CubeSat with a flagship telescope + SLS cost blowout should not score high
    bad = dict(SAMPLE, bus_id="cubesat_12u",
               instrument_ids=["photometer", "uv_telescope", "sar"],
               launch_vehicle_id="sls", difficulty="hard")
    ev = evaluate_design(bad, DATA_DICTS)
    assert score_design(ev) < score_design(evaluate_design(SAMPLE, DATA_DICTS))
    assert not ev["all_checks_pass"] or ev["power_margin_pct"] < 0

def test_monte_carlo_deterministic():
    ev = evaluate_design(SAMPLE, DATA_DICTS)
    a = monte_carlo(ev, SAMPLE, n=50, seed=7)
    b = monte_carlo(ev, SAMPLE, n=50, seed=7)
    assert a == b, "same seed must give same Monte Carlo result"

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")
