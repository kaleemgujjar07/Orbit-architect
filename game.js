// Orbit Architect frontend — all physics runs in Python (engine.py).
// This file only renders data from /api/data, /api/design, /api/simulate, /api/montecarlo.
let DATA = null;
const state = { mission_id: 'earth_observer', bus_id: 'small_sat', instrument_ids: ['camera_vis','multispectral','radiometer'], launch_vehicle_id: 'falcon9', orbit_id: 'sso600', difficulty: 'normal', team_size: 4 };
const $ = id => document.getElementById(id);
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : undefined});
  const j = await r.json(); if (!r.ok) throw new Error(j.error || 'API error'); return j;
}
function opt(el, items, fmt) { el.innerHTML = Object.entries(items).map(([k,v]) => `<option value="${k}">${fmt ? fmt(v) : v.name}</option>`).join(''); }
function cardList(el, items, selected, onPick, fmt) {
  el.innerHTML = Object.entries(items).map(([k,v]) => `<div class="card ${selected.includes(k)?'sel':''}" data-k="${k}"><b>${v.name}</b><small>${fmt(v)}</small></div>`).join('');
  el.querySelectorAll('.card').forEach(c => c.onclick = () => onPick(c.dataset.k));
}
function drawOrbit() {
  const c = $('orbit-canvas'), ctx = c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height);
  const o = DATA.orbits[state.orbit_id]; const cx=260, cy=130;
  ctx.fillStyle='#fbbf24'; ctx.beginPath(); ctx.arc(60,130,14,0,7); ctx.fill();
  ctx.fillStyle='#38bdf8'; ctx.beginPath(); ctx.arc(cx,cy,26,0,7); ctx.fill();
  ctx.strokeStyle='#8fa3c4'; ctx.setLineDash([5,5]);
  const rad = o.altitude_km ? 55 + Math.min(90, o.altitude_km/500) : 95;
  ctx.beginPath(); ctx.arc(cx,cy,rad,0,7); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(cx+rad,cy,6,0,7); ctx.fill();
  ctx.fillStyle='#e6eefc'; ctx.font='13px sans-serif';
  ctx.fillText(o.name, 14, 24); ctx.fillText('alt ' + (o.altitude_km||'—') + ' km · ' + o.data_rate_mbps + ' Mbps', 14, 240);
}
function bar(label, pct, text, invert=false) {
  const p = Math.max(0, Math.min(100, pct)); const cls = p > 80 ? (invert?'bad':'') : p > 60 ? 'warn' : '';
  return `<div class="bar"><label><span>${label}</span><span>${text}</span></label><div class="track"><div class="fill ${cls}" style="width:${p}%"></div></div></div>`;
}
function renderEval(ev, score, grade) {
  $('hud-cost').textContent = '$' + ev.cost_m + 'M';
  $('hud-cost-sub').textContent = ev.budget_used_pct + '% of $' + ev.budget_cap_m + 'M cap';
  $('hud-mass').textContent = ev.mass_kg + ' kg';
  $('hud-mass-sub').textContent = 'margin ' + ev.mass_margin_pct + '% · LV cap';
  $('hud-power').textContent = ev.power_margin_pct + '%';
  $('hud-power-sub').textContent = ev.power_generated_w + ' W gen vs ' + ev.power_consumed_w + ' W used';
  $('hud-data').textContent = ev.data_returned_pct + '%';
  $('hud-data-sub').textContent = ev.data_downlinked_gb_day + ' / ' + ev.data_generated_gb_day + ' GB/day';
  $('hud-science').textContent = ev.science_pct + '%';
  $('hud-science-sub').textContent = ev.science_eff + ' / ' + ev.mission.science_target + ' science pts';
  $('hud-score').textContent = score + ' / 1000';
  $('hud-grade').textContent = 'Grade ' + grade;
  $('bars').innerHTML =
    bar('Budget used', ev.budget_used_pct, ev.budget_used_pct+'%', true) +
    bar('Science', ev.science_pct, ev.science_pct+'%') +
    bar('Data returned', ev.data_returned_pct, ev.data_returned_pct+'%') +
    bar('Lifetime', ev.lifetime_pct, ev.lifetime_pct+'%') +
    bar('Power margin (capped)', Math.max(0,ev.power_margin_pct), ev.power_margin_pct+'%');
  $('checks').innerHTML = ev.checks.map(c => `<li class="${c.ok?'ok':'fail'}">${c.ok?'✓':'✗'} ${c.name} — ${c.detail}</li>`).join('');
  $('orbit-info').textContent = `${ev.orbit.name} · ${ev.passes_per_pass ?? ''} passes/day: ${ev.passes_per_day} · link margin ${ev.link.margin_db} dB · FSPL ${ev.link.fspl_db} dB · eclipse ${(ev.eclipse_fraction*100).toFixed(0)}%`;
}
async function evaluate() {
  const r = await api('/api/design', {design: state});
  renderEval(r.evaluation, r.score, r.grade); return r;
}
async function launch() {
  $('log').innerHTML = '<li>Launching… simulation running in Python.</li>';
  const r = await api('/api/simulate', {design: state, seed: 42});
  renderEval(r.evaluation, r.simulation.score, r.simulation.grade);
  const s = r.simulation;
  $('log').innerHTML = s.events.length ? s.events.map(e => `<li><b>Month ${e.month} — ${e.event}</b> (${e.health_change} health)<br>${e.text}</li>`).join('') : '<li>No random events this run — clean mission.</li>';
  $('report').innerHTML = `<div class="big">${s.grade} · ${s.score}/1000 — ${s.verdict}</div>
    <p>Health ${s.health_pct}% · ${s.months_flown} months flown · ${s.data_returned_gb} GB returned · science ${s.science_earned}</p>
    <p><b>Why:</b></p><ul>${s.reasons.map(x=>`<li>${x}</li>`).join('')}</ul>
    <p>Monte Carlo (200 runs): success probability <b>${r.monte_carlo.success_probability}</b>, mean ${r.monte_carlo.mean_score}, P10 ${r.monte_carlo.p10}, P90 ${r.monte_carlo.p90}. Change the design and refly.</p>`;
  $('mc').innerHTML = `<p>Success probability <b>${r.monte_carlo.success_probability}</b> · mean ${r.monte_carlo.mean_score} · P10 ${r.monte_carlo.p10} · P90 ${r.monte_carlo.p90} · min ${r.monte_carlo.min_score} · max ${r.monte_carlo.max_score} (n=${r.monte_carlo.n})</p>`;
}
async function init() {
  DATA = await api('/api/data');
  opt($('mission'), DATA.missions); opt($('lv'), DATA.launch_vehicles); opt($('orbit'), DATA.orbits);
  $('mission').value = state.mission_id; $('lv').value = state.launch_vehicle_id; $('orbit').value = state.orbit_id;
  const refresh = () => {
    $('mission-desc').textContent = DATA.missions[state.mission_id].objective + ' · Δv ' + DATA.missions[state.mission_id].required_dv_m_s + ' m/s · lifetime ' + DATA.missions[state.mission_id].lifetime_months + ' mo';
    cardList($('buses'), DATA.buses, [state.bus_id], k => { state.bus_id = k; refresh(); }, v => `${v.dry_mass_kg} kg · ${v.cost_m}$M · Isp ${v.isp_s}s`);
    cardList($('instruments'), DATA.instruments, state.instrument_ids, k => {
      state.instrument_ids = state.instrument_ids.includes(k) ? state.instrument_ids.filter(x=>x!==k) : [...state.instrument_ids, k].slice(0,5); refresh();
    }, v => `${v.mass_kg} kg · ${v.power_w} W · ${v.science} sci`);
    const roles = ['Mission Director','Spacecraft Engineer','Science Lead','Comms & Operations'];
    $('roles').innerHTML = state.team_size <= 1 ? 'Solo: you are the Mission Director.' : 'Team roles: ' + roles.slice(0, state.team_size).join(' · ');
    drawOrbit();
  };
  $('mission').onchange = e => { state.mission_id = e.target.value; refresh(); };
  $('lv').onchange = e => { state.launch_vehicle_id = e.target.value; refresh(); };
  $('orbit').onchange = e => { state.orbit_id = e.target.value; refresh(); };
  $('difficulty').onchange = e => { state.difficulty = e.target.value; };
  $('team-size').onchange = e => { state.team_size = +e.target.value; refresh(); };
  $('btn-eval').onclick = () => evaluate().catch(e => alert(e.message));
  $('btn-launch').onclick = () => launch().catch(e => alert(e.message));
  $('btn-mc').onclick = async () => { const r = await api('/api/montecarlo', {design: state, n: 200}); $('mc').innerHTML = `<p>Success probability <b>${r.success_probability}</b> · mean ${r.mean_score} · P10 ${r.p10} · P90 ${r.p90} · min ${r.min_score} · max ${r.max_score} (n=${r.n})</p>`; };
  refresh(); evaluate().catch(()=>{});
}
init();
