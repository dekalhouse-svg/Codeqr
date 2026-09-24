const API_BASE_URL = window.QR_API_BASE_URL || 'http://127.0.0.1:5000';
const form = document.getElementById('loginForm');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const error = document.getElementById('error');
const setupLink = document.getElementById('setupLink');

async function status() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/setup/status`);
    const data = await response.json();
    if (setupLink) setupLink.style.display = data.admin_exists ? 'none' : 'block';
  } catch (e) {
    if (setupLink) setupLink.style.display = 'block';
    if (error) error.textContent = 'Backend inaccessible. Vérifiez que Flask est lancé.';
  }
}

status();

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  error.textContent = '';

  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: usernameInput.value.trim(),
        password: passwordInput.value
      })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Erreur serveur (${response.status})`);

    localStorage.setItem('qr_dekal_admin_token', data.token);
    localStorage.setItem('qr_dekal_admin_name', data.username);
    window.location.href = 'dashboard.html';
  } catch (err) {
    error.textContent = `Connexion impossible : ${err.message}`;
  }
});
