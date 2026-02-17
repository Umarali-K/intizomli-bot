from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard() -> str:
    return """
<!doctype html>
<html lang='uz'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Intizomli Admin Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 0; background: #0b1220; color: #e6edf8; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 18px; }
    .card { background:#111c31; border:1px solid #2a3b5f; border-radius:12px; padding:12px; margin-bottom:12px; }
    .row { display:flex; gap:8px; flex-wrap:wrap; }
    input, button { padding:10px; border-radius:8px; border:1px solid #30466f; background:#0d1930; color:#e6edf8; }
    button { cursor:pointer; background:#1d4ed8; border-color:#1d4ed8; }
    table { width:100%; border-collapse: collapse; }
    th, td { border-bottom:1px solid #243656; padding:6px; text-align:left; font-size:13px; }
    .muted { color:#9fb3d4; }
  </style>
</head>
<body>
<div class='wrap'>
  <div class='card'>
    <h2>Admin Dashboard</h2>
    <div class='row'>
      <input id='base' value='' placeholder='Base URL (https://...up.railway.app)' style='min-width:340px'>
      <input id='token' value='' placeholder='ADMIN_API_TOKEN' style='min-width:260px'>
      <button onclick='loadAll()'>Yuklash</button>
    </div>
    <p class='muted'>Token client tomonda ishlatiladi. Ishonchli admin qurilmada oching.</p>
  </div>

  <div class='card'><h3>Overview</h3><pre id='overview'></pre></div>
  <div class='card'><h3>Hisobot yubormaganlar</h3><table><thead><tr><th>Ism</th><th>Username</th><th>TG ID</th></tr></thead><tbody id='missedBody'></tbody></table></div>
  <div class='card'><h3>Top 10</h3><table><thead><tr><th>#</th><th>Ism</th><th>Ball</th><th>Streak</th></tr></thead><tbody id='lbBody'></tbody></table></div>
</div>
<script>
async function req(path){
  const base = document.getElementById('base').value.trim();
  const token = document.getElementById('token').value.trim();
  const r = await fetch(base + path, {headers:{'x-admin-token':token}});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

async function loadAll(){
  try{
    const [ov, missed, lb] = await Promise.all([
      req('/v1/admin/analytics/overview?days=14'),
      req('/v1/admin/reports/missed'),
      fetch(document.getElementById('base').value.trim() + '/v1/app/leaderboard?limit=10').then(r=>r.json())
    ]);
    document.getElementById('overview').textContent = JSON.stringify(ov, null, 2);

    const mb = document.getElementById('missedBody');
    mb.innerHTML = (missed.items || []).map(x => `<tr><td>${x.full_name || '-'}</td><td>${x.username || '-'}</td><td>${x.tg_user_id}</td></tr>`).join('');

    const lbBody = document.getElementById('lbBody');
    lbBody.innerHTML = (lb.items || []).map(x => `<tr><td>${x.rank}</td><td>${x.name}</td><td>${x.rating_points}</td><td>${x.streak}</td></tr>`).join('');
  }catch(e){
    alert(e.message || e);
  }
}
</script>
</body>
</html>
"""
