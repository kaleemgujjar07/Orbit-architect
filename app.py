"""
Orbit Architect — web app (Python stdlib only, no Flask needed).

Team PyInTheSky, NASA Space Apps Challenge 2026.
Run:  python3 app.py        then open http://127.0.0.1:5000
API:
  GET  /api/health     -> {"status": "ok", ...}
  GET  /api/data       -> missions, buses, instruments, launch vehicles, orbits
  POST /api/design     -> {"design": {...}} -> evaluation + score
  POST /api/simulate   -> {"design": {...}, "seed": 42} -> full run
  POST /api/montecarlo -> {"design": {...}, "n": 200} -> Monte Carlo stats
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import data as DATA
import engine
from game import full_run, grade_for, score_design

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "5000"))

DATA_DICTS = {
    "missions": DATA.MISSIONS, "buses": DATA.BUSES,
    "instruments": DATA.INSTRUMENTS, "launch_vehicles": DATA.LAUNCH_VEHICLES,
    "orbits": DATA.ORBITS, "difficulty": DATA.DIFFICULTY, "roles": DATA.ROLES,
}

SAMPLE_DESIGN = {
    "mission_id": "earth_observer", "bus_id": "small_sat",
    "instrument_ids": ["camera_vis", "multispectral", "radiometer"],
    "launch_vehicle_id": "falcon9", "orbit_id": "sso600",
    "difficulty": "normal", "team_size": 1,
}


def _jsonable(obj):
    """Convert evaluation dicts to plain JSON-safe structures."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _validate_design(d):
    required = ["mission_id", "bus_id", "launch_vehicle_id", "orbit_id"]
    for k in required:
        if k not in d:
            raise ValueError(f"missing field: {k}")
    if d["mission_id"] not in DATA.MISSIONS:
        raise ValueError(f"unknown mission_id: {d['mission_id']}")
    if d["bus_id"] not in DATA.BUSES:
        raise ValueError(f"unknown bus_id: {d['bus_id']}")
    if d["launch_vehicle_id"] not in DATA.LAUNCH_VEHICLES:
        raise ValueError(f"unknown launch_vehicle_id: {d['launch_vehicle_id']}")
    if d["orbit_id"] not in DATA.ORBITS:
        raise ValueError(f"unknown orbit_id: {d['orbit_id']}")
    for i in d.get("instrument_ids", []):
        if i not in DATA.INSTRUMENTS:
            raise ValueError(f"unknown instrument_id: {i}")
    d.setdefault("instrument_ids", [])
    d.setdefault("difficulty", "normal")
    d.setdefault("team_size", 1)
    return d


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep console clean

    def _send_json(self, obj, status=200):
        body = json.dumps(_jsonable(obj)).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def _find_file(self, *candidates):
        """Return the first candidate path that exists.

        Supports both layouts:
          * normal: templates/index.html, static/game.js
          * flat GitHub upload: index.html, game.js, style.css at repo root
          * nested: orbit-architect-python/templates/index.html, ...
        """
        for rel in candidates:
            full = os.path.join(BASE, rel)
            if os.path.isfile(full):
                return full
        raise FileNotFoundError(candidates[0])

    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p in ("/", "/index.html"):
                full = self._find_file(
                    os.path.join("templates", "index.html"),
                    "index.html",
                    os.path.join("orbit-architect-python", "templates", "index.html"),
                )
                self._send_file(full, "text/html")
            elif p.startswith("/static/"):
                name = p[len("/static/"):]
                safe = os.path.basename(name)
                full = self._find_file(
                    os.path.join("static", safe),
                    safe,
                    os.path.join("orbit-architect-python", "static", safe),
                )
                ctype = "text/css" if safe.endswith(".css") else \
                    "application/javascript" if safe.endswith(".js") else "text/plain"
                self._send_file(full, ctype)
            elif p == "/api/health":
                self._send_json({"status": "ok", "app": "Orbit Architect",
                                 "team": "PyInTheSky", "sample_design": SAMPLE_DESIGN})
            elif p == "/api/data":
                self._send_json(DATA_DICTS)
            else:
                self._send_json({"error": "not found"}, 404)
        except FileNotFoundError:
            self._send_json({"error": "file not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            body = self._read_json()
            design = _validate_design(dict(body.get("design", SAMPLE_DESIGN)))
            if p == "/api/design":
                ev = engine.evaluate_design(design, DATA_DICTS)
                s = score_design(ev)
                self._send_json({"evaluation": ev, "score": s, "grade": grade_for(s)})
            elif p == "/api/simulate":
                result = full_run(design, DATA_DICTS, seed=int(body.get("seed", 42)))
                self._send_json(result)
            elif p == "/api/montecarlo":
                from game import monte_carlo
                ev = engine.evaluate_design(design, DATA_DICTS)
                mc = monte_carlo(ev, design, n=int(body.get("n", 200)),
                                 seed=int(body.get("seed", 1234)))
                self._send_json(mc)
            else:
                self._send_json({"error": "not found"}, 404)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


if __name__ == "__main__":
    # Bind 0.0.0.0 so cloud hosts like Render can reach the app.
    # Locally it is still http://127.0.0.1:PORT — PORT comes from the
    # environment on Render/Railway, and defaults to 5000 locally.
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, PORT), Handler)
    print(f"Orbit Architect — PyInTheSky")
    print(f"Open http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
