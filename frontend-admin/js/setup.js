const API_BASE_URL = window.QR_API_BASE_URL || 'http://127.0.0.1:5000';
const form = document.getElementById('setupForm');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const confirmInput = document.getElementById('confirm');
const error = document.getElementById('error');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  error.textContent = '';

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const confirm = confirmInput.value;

  if (password !== confirm) {
    error.textContent = 'Les mots de passe ne correspondent pas.';
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/setup/admin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Erreur serveur (${response.status})`);

    alert(data.message || 'Administrateur créé avec succès.');
    window.location.href = 'login.html';
  } catch (err) {
    error.textContent = `Impossible de créer le compte : ${err.message}. Vérifiez que le backend est démarré et que l'URL API est correcte.`;
  }
});
