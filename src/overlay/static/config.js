async function loadConfig() {
  const res = await fetch('/config/data');
  if (!res.ok) return;
  const cfg = await res.json();
  Object.entries(cfg).forEach(([key, value]) => {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = value;
  });
  updateLoginStatus(cfg.twitch_token);
}

function updateLoginStatus(token) {
  const statusEl = document.getElementById('login-status');
  const btnEl = document.getElementById('login-btn');
  if (token) {
    statusEl.textContent = 'Connected';
    statusEl.className = 'login-status connected';
    btnEl.textContent = 'Re-login with Twitch';
  } else {
    statusEl.textContent = 'Not connected';
    statusEl.className = 'login-status not-connected';
    btnEl.textContent = 'Login with Twitch';
  }
}

document.getElementById('login-btn').addEventListener('click', () => {
  const clientId = document.querySelector('[name="twitch_client_id"]').value.trim();
  if (!clientId) {
    showStatus('Enter your Client ID first.', 'error');
    return;
  }
  const port = document.querySelector('[name="port"]').value || '7878';
  const redirectUri = encodeURIComponent(`http://localhost:${port}/auth/callback`);
  const scope = encodeURIComponent('channel:read:redemptions');
  const url = `https://id.twitch.tv/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=token&scope=${scope}`;
  window.open(url, '_blank');

  // Poll for token after login window opens
  const poll = setInterval(async () => {
    const res = await fetch('/config/data');
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg.twitch_token) {
      clearInterval(poll);
      document.getElementById('twitch_token_hidden').value = cfg.twitch_token;
      updateLoginStatus(cfg.twitch_token);
      showStatus('Twitch connected!', 'success');
    }
  }, 1500);
});

const form   = document.getElementById('config-form');
const status = document.getElementById('status');

function showStatus(msg, type) {
  status.textContent = msg;
  status.className = `status ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  showStatus('Saving...', 'info');

  const numericFields = ['max_message_length', 'port'];
  const data = {};
  new FormData(form).forEach((v, k) => {
    data[k] = numericFields.includes(k) ? parseInt(v, 10) : v;
  });

  try {
    const res = await fetch('/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      showStatus('Saved! ShimaTTS will apply your settings.', 'success');
    } else {
      showStatus('Save failed - check the console.', 'error');
    }
  } catch (err) {
    showStatus('Error: ' + err.message, 'error');
  }
});

loadConfig();
