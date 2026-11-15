# Orbit Architect - Space Mission Design Game

**NASA Space Apps Challenge 2026 · Challenge: Space Mission Design Game · Universal Event**


- **Real orbital mechanics** (`engine.py`): period `T=2π√(a³/μ)`, circular velocity,
  Hohmann transfer Δv, escape velocity, inclination-change cost.
  μ Earth 398600.4418, Moon 4902.80066, Mars 42828.375 km³/s², etc.
- **Tsiolkovsky rocket equation**: Δv = Isp·g₀·ln(m₀/mf), propellant sized from
  the mission's required Δv, checked against the launch vehicle's payload capacity.
- **Power budget**: solar power by inverse-square law `P ∝ 1/d²`, eclipse fraction
  by orbit, battery usable energy (Ah·V·DoD), power margin.
- **Link budget**: Friis free-space path loss, received power, SNR margin,
  ground-station passes/day, downlink capacity vs data generated.
- **Mass budget**: dry + payload + propellant, 20% contingency, launch-vehicle check.
- **Thermal / radiation risk** by orbit, feeding reliability.
- **Game** (`game.py`): 3 difficulty levels, solo + 2–4 player team roles
  (Mission Director, Spacecraft Engineer, Science Lead, Comms & Operations),
  scoring /1000 weighted science 30% / budget 20% / margins 20% / data 15% /
  lifetime 15%, 12 random events whose impact depends on your margins,
  **Monte Carlo: 200 seeded simulations** reporting success probability,
  mean score, P10/P90.
- **Content** (`data.py`): 8 missions, 8 spacecraft buses, 14 instruments,
  8 launch vehicles (Falcon 9, Atlas V, Ariane 6, Vulcan, H-IIA, PSLV,
  Electron, SLS-style heavy), 6 orbits.

## How to run

```bash
pip install -r requirements.txt   # nothing to install — stdlib only
python3 test_engine.py            # tests, must pass
python3 app.py                    # starts the server
# open http://127.0.0.1:5000

## API

- `GET  /api/health` — status
- `GET  /api/data` — missions, buses, instruments, launch vehicles, orbits
- `POST /api/design` — `{"design": {...}}` → evaluation + score /1000 + grade
- `POST /api/simulate` — `{"design": {...}, "seed": 42}` → evaluation + month-by-month simulation + Monte Carlo
- `POST /api/montecarlo` — `{"design": {...}, "n": 200}` → success probability, mean, P10/P90

Sample design (also in `app.py`):

```json
{"mission_id": "earth_observer", "bus_id": "small_sat",
 "instrument_ids": ["camera_vis", "multispectral", "radiometer"],
 "launch_vehicle_id": "falcon9", "orbit_id": "sso600",
 "difficulty": "normal", "team_size": 1}
```

## Files

```
app.py            stdlib web server + API
engine.py         real physics: orbits, Tsiolkovsky, power, link, mass
data.py           8 missions, 8 buses, 14 instruments, 8 launch vehicles, 6 orbits
game.py           scoring, 12 events, Monte Carlo, team roles
test_engine.py    9 tests — run with: python3 test_engine.py
templates/index.html
static/style.css  dark mission-control UI
static/game.js    calls the Python API, canvas orbit diagram, HUD, report
requirements.txt  stdlib only
```
