const API_BASE_URL = window.QR_API_BASE_URL || 'http://127.0.0.1:5000';
const token = localStorage.getItem('qr_dekal_admin_token');
if (!token) window.location.href = 'login.html';

document.getElementById('adminName').textContent = localStorage.getItem('qr_dekal_admin_name') || '';
const headers = {'Authorization': 'Bearer ' + token};

async function api(path, opt = {}) {
  const requestHeaders = {...headers, ...(opt.headers || {})};
  if (!(opt.body instanceof FormData) && !requestHeaders['Content-Type']) requestHeaders['Content-Type'] = 'application/json';
  const r = await fetch(API_BASE_URL + path, {...opt, headers: requestHeaders});
  const d = await r.json().catch(() => ({}));
  if (r.status === 401) {
    localStorage.removeItem('qr_dekal_admin_token');
    localStorage.removeItem('qr_dekal_admin_name');
    window.location.href = 'login.html?expired=1';
    throw new Error('Session expirée ou invalide.');
  }
  if (!r.ok) throw new Error(d.error || `Erreur serveur (${r.status})`);
  return d;
}

async function verifySession() {
  try { await api('/api/admin/me'); }
  catch (e) { console.error(e); throw e; }
}

async function load() {
  try {
    const [s,u,q,a] = await Promise.all([
      api('/api/admin/stats'), api('/api/admin/users'), api('/api/admin/qr'), api('/api/admin/ads')
    ]);
    totalUsers.textContent = s.total_users;
    activeUsers.textContent = s.active_users;
    totalQr.textContent = s.total_qr;
    usersBody.innerHTML = u.users.map(x => `<tr><td>${escapeHtml(x.user_code)}</td><td>${new Date(x.first_seen).toLocaleString()}</td><td>${new Date(x.last_seen).toLocaleString()}</td></tr>`).join('');
    qrBody.innerHTML = q.qr_codes.map(x => `<tr><td>${escapeHtml(x.user_code)}</td><td>${escapeHtml(x.content)}</td><td>${new Date(x.created_at).toLocaleString()}</td></tr>`).join('');
    renderChart(s.daily_qr);
    renderAds(a.ads);
  } catch (e) { console.error(e); }
}

function escapeHtml(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
function renderChart(rows) { const max = Math.max(1, ...rows.map(x => x.count)); chart.innerHTML = rows.length ? rows.map(x => `<div class="bar" style="height:${Math.max(4,x.count/max*160)}px"><span>${x.day.slice(5)}</span></div>`).join('') : '<span class="muted">Aucune génération enregistrée.</span>'; }
function renderAds(ads) {
  adsBody.innerHTML = ads.map(a => `<tr><td>${escapeHtml(a.title)}</td><td>${a.media_type === 'video' ? '🎬 Vidéo' : '🖼️ Image'}</td><td>${a.active ? 'Active' : 'Inactive'}</td><td>${a.media_url ? `<a href="${API_BASE_URL + a.media_url}" target="_blank">Voir</a>` : '—'}</td><td><button onclick="toggleAd(${a.id},${!a.active})">${a.active ? 'Désactiver' : 'Activer'}</button> <button onclick="deleteAd(${a.id})">Supprimer</button></td></tr>`).join('');
}

window.toggleAd = async (id, active) => { const rows = await api('/api/admin/ads'); const a = rows.ads.find(x => x.id === id); if (!a) return; await api('/api/admin/ads/' + id, {method:'PUT', body:JSON.stringify({...a, active})}); load(); };
window.deleteAd = async id => { if (confirm('Supprimer cette publicité ?')) { await api('/api/admin/ads/' + id, {method:'DELETE'}); load(); } };

adForm.addEventListener('submit', async e => {
  e.preventDefault();
  const file = adMedia.files[0];
  if (!file) { adMessage.textContent = 'Choisissez une image ou une vidéo.'; return; }
  adMessage.textContent = 'Importation en cours...';
  const fd = new FormData();
  fd.append('title', adTitle.value.trim());
  fd.append('target_url', adUrl.value.trim());
  fd.append('start_at', adStart.value);
  fd.append('end_at', adEnd.value);
  fd.append('active', adActive.checked ? '1' : '0');
  fd.append('media', file);
  try {
    await api('/api/admin/ads', {method:'POST', body:fd});
    adForm.reset(); adActive.checked = true; adMessage.textContent = 'Publicité ajoutée.'; load();
  } catch (e) { adMessage.textContent = e.message; }
});

logout.onclick = () => { localStorage.removeItem('qr_dekal_admin_token'); localStorage.removeItem('qr_dekal_admin_name'); window.location.href='login.html'; };

(async () => { await verifySession(); await load(); })();
