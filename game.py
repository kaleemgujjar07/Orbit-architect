"""
Orbit Architect — game logic: scoring, random events, Monte Carlo.

Scoring is weighted /1000:
  science 30%, budget 20%, mass/power margins 20%,
  data return 15%, lifetime/reliability 15%.
Difficulty adds a bonus (easy 0, normal +50, hard +100) before capping at 1000.
"""
import random
from engine import evaluate_design

GRADES = [(900, "S"), (800, "A"), (700, "B"), (600, "C"), (500, "D"), (0, "F")]

def grade_for(score):
    for threshold, g in GRADES:
        if score >= threshold:
            return g
    return "F"

# 12 random events. impact is scaled by the design's margins:
# a healthy margin absorbs the hit, a thin margin turns it into a failure.
EVENTS = [
    {"id": "solar_storm", "name": "Solar Storm", "prob_per_month": 0.02,
     "text": "A solar storm bathes the spacecraft in charged particles.",
     "health_hit": 12, "margin": "radiation"},
    {"id": "micrometeorite", "name": "Micrometeorite Impact", "prob_per_month": 0.015,
     "text": "A micrometeorite strikes a solar panel.",
     "health_hit": 10, "margin": "power"},
    {"id": "gyro_failure", "name": "Gyro Failure", "prob_per_month": 0.01,
     "text": "A reaction wheel / gyro degrades; pointing wobbles.",
     "health_hit": 14, "margin": "mass"},
    {"id": "ground_outage", "name": "Ground Station Outage", "prob_per_month": 0.025,
     "text": "A ground station goes offline for a week; data is queued.",
     "health_hit": 6, "margin": "data"},
    {"id": "launch_delay", "name": "Launch Delay", "prob_per_month": 0.005,
     "text": "Weather / range delay pushes launch by a month (cost +$2M).",
     "health_hit": 4, "margin": "budget"},
    {"id": "battery_degrade", "name": "Battery Degradation", "prob_per_month": 0.015,
     "text": "Battery capacity fades faster than modelled.",
     "health_hit": 9, "margin": "power"},
    {"id": "thermal_spike", "name": "Thermal Spike", "prob_per_month": 0.012,
     "text": "A heater fails; an instrument runs cold for a month.",
     "health_hit": 10, "margin": "thermal"},
    {"id": "comms_dropout", "name": "Comms Dropout", "prob_per_month": 0.02,
     "text": "Deep-space link drops; a month of data is partly lost.",
     "health_hit": 8, "margin": "data"},
    {"id": "discovery", "name": "Surprise Discovery", "prob_per_month": 0.015,
     "text": "The instruments spot something unexpected — bonus science!",
     "health_hit": -10, "margin": "science"},
    {"id": "prop_leak", "name": "Propellant Leak", "prob_per_month": 0.008,
     "text": "A small propellant leak reduces the delta-v reserve.",
     "health_hit": 15, "margin": "mass"},
    {"id": "software_bug", "name": "Software Glitch", "prob_per_month": 0.015,
     "text": "A flight-software bug needs a patch uploaded from Earth.",
     "health_hit": 7, "margin": "budget"},
    {"id": "dust_storm", "name": "Dust Storm (Mars) / Cloud Surge", "prob_per_month": 0.012,
     "text": "Dust / clouds cut solar power for a month.",
     "health_hit": 11, "margin": "power"},
]

def score_design(ev):
    """Weighted score /1000 from an evaluate_design() result."""
    # science: 0-300
    s_science = min(100.0, ev["science_pct"]) * 3.0
    # budget: full marks if <=80% of cap, sliding to 0 at 100%+
    used = ev["budget_used_pct"]
    s_budget = max(0.0, min(100.0, (100 - used) / 20 * 100)) * 2.0 if used > 80 else 200.0
    # margins: power margin (clamped 0-30%) + mass margin (0-30%) -> 0-200
    pm = max(0.0, min(30.0, ev["power_margin_pct"])) / 30 * 100
    mm = max(0.0, min(30.0, ev["mass_margin_pct"])) / 30 * 100
    s_margin = (pm + mm) / 2 * 2.0
    # data: 0-150
    s_data = min(100.0, ev["data_returned_pct"]) * 1.5
    # lifetime/reliability: 0-150
    s_life = min(100.0, ev["lifetime_pct"]) * 0.75 + ev["reliability"] * 75
    total = s_science + s_budget + s_margin + s_data + s_life
    # failed hard checks cap the score — a design that cannot fly cannot score high
    failed = [c for c in ev["checks"] if not c["ok"]]
    if failed:
        total = min(total, 600 - 40 * len(failed))
    return round(max(0.0, min(1000.0, total)), 1)

def _margin_factor(ev, margin_key):
    """0.4 (thin margin, event hits hard) .. 1.0 (healthy margin, absorbs it)."""
    if margin_key == "power":
        m = ev["power_margin_pct"]
    elif margin_key == "mass":
        m = ev["mass_margin_pct"]
    elif margin_key == "data":
        m = ev["data_returned_pct"]
    elif margin_key == "budget":
        m = 100 - ev["budget_used_pct"]
    elif margin_key == "radiation":
        m = (1 - ev["orbit"]["radiation"]) * 100
    elif margin_key == "thermal":
        m = (1 - ev["orbit"]["thermal_risk"]) * 100
    else:
        m = 50.0
    return 0.4 + 0.6 * max(0.0, min(100.0, m)) / 100.0

def simulate_mission(ev, design, seed=42, log_events=True):
    """Month-by-month simulation. Returns report dict."""
    rng = random.Random(seed)
    diff = design.get("difficulty", "normal")
    from data import DIFFICULTY
    rate = DIFFICULTY[diff]["event_rate"]
    months = ev["lifetime_months"]
    health = 100.0
    data_returned_gb = 0.0
    science_earned = 0.0
    log = []
    for month in range(1, months + 1):
        # baseline monthly data / science
        data_returned_gb += ev["data_downlinked_gb_day"] * 30
        science_earned += ev["science_eff"] / months * (health / 100.0)
        for event in EVENTS:
            if rng.random() < event["prob_per_month"] * rate:
                factor = _margin_factor(ev, event["margin"])
                hit = event["health_hit"] * factor
                health -= hit
                if log_events:
                    log.append({"month": month, "event": event["name"],
                                "text": event["text"],
                                "health_change": round(-hit, 1)})
                if health <= 0:
                    break
        if health <= 0:
            log.append({"month": month, "event": "MISSION LOST",
                        "text": "Spacecraft health reached zero.", "health_change": 0})
            break
    health = max(0.0, health)
    base_score = score_design(ev)
    # Simulation scales the design score by health / survival
    sim_score = base_score * (0.35 + 0.65 * health / 100.0)
    if health <= 0:
        sim_score *= 0.4
    sim_score += DIFFICULTY[diff]["score_bonus"]
    sim_score = round(max(0.0, min(1000.0, sim_score)), 1)
    success = health > 50 and ev["all_checks_pass"]
    partial = health > 0 and not success
    verdict = "SUCCESS" if success else ("PARTIAL SUCCESS" if partial else "MISSION FAILED")
    reasons = []
    for c in ev["checks"]:
        reasons.append(("OK  " if c["ok"] else "FAIL") + " — " + c["name"] + ": " + c["detail"])
    reasons.append(f"Final health {health:.0f}% after {len(log)} events over {months} planned months.")
    if health <= 0:
        reasons.append("The spacecraft was lost before the mission ended.")
    elif not ev["all_checks_pass"]:
        reasons.append("One or more hard budgets failed, capping the score.")
    return {
        "score": sim_score, "grade": grade_for(sim_score), "verdict": verdict,
        "health_pct": round(health, 1), "months_flown": month,
        "data_returned_gb": round(data_returned_gb, 1),
        "science_earned": round(science_earned, 1),
        "success": success, "events": log, "reasons": reasons,
        "design_score": base_score,
    }

def monte_carlo(ev, design, n=200, seed=1234):
    """Run n seeded simulations. Returns success probability, mean, P10/P90."""
    scores = []
    successes = 0
    for i in range(n):
        r = simulate_mission(ev, design, seed=seed + i, log_events=False)
        scores.append(r["score"])
        if r["success"]:
            successes += 1
    scores.sort()
    def pct(p):
        return scores[min(n - 1, max(0, int(p * n)))]
    return {
        "n": n, "success_probability": round(successes / n, 3),
        "mean_score": round(sum(scores) / n, 1),
        "p10": scores[int(0.10 * n)], "p90": scores[int(0.90 * n)],
        "min_score": scores[0], "max_score": scores[-1],
    }

def team_roles(n_players):
    """Roles for solo / 2-4 player team play."""
    from data import ROLES
    order = ["director", "engineer", "science", "comms"]
    if n_players <= 1:
        return [{"player": 1, "role": "director", "title": ROLES["director"]}]
    return [{"player": i + 1, "role": order[i], "title": ROLES[order[i]]}
            for i in range(min(4, n_players))]

def full_run(design, data, seed=42):
    """One call the API uses: evaluate + simulate + Monte Carlo."""
    ev = evaluate_design(design, data)
    sim = simulate_mission(ev, design, seed=seed)
    mc = monte_carlo(ev, design, n=200, seed=seed + 1000)
    return {"evaluation": ev, "simulation": sim, "monte_carlo": mc,
            "roles": team_roles(design.get("team_size", 1))}
