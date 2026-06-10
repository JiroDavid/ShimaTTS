async function loadConfig() {
  const res = await fetch('/config/data');
  if (!res.ok) return;
  const cfg = await res.json();
  Object.entries(cfg).forEach(([key, value]) => {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = value;
  });
  updateLoginStatus(cfg.twitch_token, cfg.channel_name);
}

function updateLoginStatus(token, channelName) {
  const statusEl = document.getElementById('login-status');
  const btnEl    = document.getElementById('login-btn');
  const autoLabel = document.getElementById('channel-auto-label');
  if (token) {
    statusEl.textContent = channelName ? `Connected as @${channelName}` : 'Connected';
    statusEl.className = 'login-status connected';
    btnEl.textContent  = 'Re-login with Twitch';
    autoLabel.style.display = 'none';
  } else {
    statusEl.textContent = 'Not connected';
    statusEl.className   = 'login-status not-connected';
    btnEl.textContent    = 'Login with Twitch';
    autoLabel.style.display = '';
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
  const url = `https://id.twitch.tv/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=token&scope=${scope}&state=${encodeURIComponent(clientId)}`;
  window.open(url, '_blank');

  const poll = setInterval(async () => {
    const res = await fetch('/config/data');
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg.twitch_token) {
      clearInterval(poll);
      document.getElementById('twitch_token_hidden').value = cfg.twitch_token;
      if (cfg.channel_name) {
        document.querySelector('[name="channel_name"]').value = cfg.channel_name;
      }
      updateLoginStatus(cfg.twitch_token, cfg.channel_name);
      showStatus('Twitch connected!', 'success');
    }
  }, 1500);
});

// File pickers
async function uploadFile(inputId, pathFieldName, endpoint) {
  const file = document.getElementById(inputId).files[0];
  if (!file) return;
  showStatus('Uploading...', 'info');
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await fetch(endpoint, { method: 'POST', body: formData });
    if (res.ok) {
      const data = await res.json();
      document.querySelector(`[name="${pathFieldName}"]`).value = data.path;
      showStatus('File uploaded.', 'success');
    } else {
      showStatus('Upload failed.', 'error');
    }
  } catch (err) {
    showStatus('Upload error: ' + err.message, 'error');
  }
}

document.getElementById('voice_pick').addEventListener('change', () =>
  uploadFile('voice_pick', 'voice_sample', '/upload/voice'));

document.getElementById('gif_pick').addEventListener('change', () =>
  uploadFile('gif_pick', 'overlay_gif', '/upload/gif'));

const form   = document.getElementById('config-form');
const status = document.getElementById('status');

function showStatus(msg, type) {
  status.textContent = msg;
  status.className = `status ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

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
      document.getElementById('save-btn').textContent = 'Saved!';
      document.getElementById('saved-banner').classList.remove('hidden');
      document.getElementById('saved-banner').scrollIntoView({ behavior: 'smooth' });
    } else {
      showStatus('Save failed - check the console.', 'error');
    }
  } catch (err) {
    showStatus('Error: ' + err.message, 'error');
  }
});

loadConfig();
