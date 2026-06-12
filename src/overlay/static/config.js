let defaultClientId = '';
let customClientId = '';
let libraryFiles = [];

const $ = id => document.getElementById(id);
const field = name => document.querySelector(`[name="${name}"]`);

function showStatus(msg, type) {
  const status = $('status');
  status.textContent = msg;
  status.className = `status ${type}`;
}

// --- Theme ---

const themeToggle = $('theme-toggle');
themeToggle.checked = document.documentElement.dataset.theme === 'dark';
themeToggle.addEventListener('change', () => {
  const theme = themeToggle.checked ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('shima-theme', theme);
});

// --- Twitch avatar ---

async function loadAvatar(token, clientId) {
  if (!token || !clientId) return;
  try {
    const res = await fetch('https://api.twitch.tv/helix/users', {
      headers: { 'Authorization': 'Bearer ' + token, 'Client-Id': clientId },
    });
    if (!res.ok) return;
    const users = (await res.json()).data;
    if (users && users[0] && users[0].profile_image_url) {
      $('avatar').src = users[0].profile_image_url;
      $('avatar').classList.remove('hidden');
    }
  } catch (err) { /* offline or expired token - just skip the avatar */ }
}

// --- Config load/save ---

async function loadConfig() {
  const res = await fetch('/config/data');
  if (!res.ok) return;
  const cfg = await res.json();

  ['channel_name', 'reward_name'].forEach(k => {
    if (field(k) && cfg[k] !== undefined) field(k).value = cfg[k];
  });
  $('twitch_token_hidden').value = cfg.twitch_token || '';
  $('voice_sample_hidden').value = cfg.voice_sample || '';
  $('overlay_gif_hidden').value = cfg.overlay_gif || '';
  customClientId = cfg.twitch_client_id || '';

  if (cfg.tts_template) {
    $('prefix-toggle').checked = true;
    $('prefix-fields').classList.remove('hidden');
    field('tts_template').value = cfg.tts_template;
  }

  defaultClientId = cfg.default_client_id || '';
  updateLoginStatus(cfg.twitch_token, cfg.channel_name);
  loadAvatar(cfg.twitch_token, customClientId || defaultClientId);

  const isNew = !cfg.twitch_token || !cfg.voice_sample || !cfg.overlay_gif;
  $('setup-guide').open = isNew;

  const complete = cfg.twitch_token && cfg.channel_name && cfg.reward_name
    && cfg.voice_sample && cfg.overlay_gif;
  updateTestSection(Boolean(complete), cfg.channel_name);

  renderGalleries();
}

function updateLoginStatus(token, channelName) {
  const statusEl = $('login-status');
  const btnEl = $('login-btn');
  const autoLabel = $('channel-auto-label');
  if (token) {
    statusEl.textContent = channelName ? `Connected as @${channelName}` : 'Connected';
    statusEl.className = 'login-status connected';
    btnEl.textContent = 'Re-login with Twitch';
    autoLabel.style.display = 'none';
    $('logout-btn').classList.remove('hidden');
  } else {
    statusEl.textContent = 'Not connected';
    statusEl.className = 'login-status not-connected';
    btnEl.textContent = 'Login with Twitch';
    autoLabel.style.display = '';
    $('logout-btn').classList.add('hidden');
    $('avatar').classList.add('hidden');
  }
}

$('login-btn').addEventListener('click', () => {
  const clientId = customClientId || defaultClientId;
  if (!clientId) {
    showStatus('No Twitch client ID configured - set twitch_client_id in config.json.', 'error');
    return;
  }
  const redirectUri = encodeURIComponent('http://localhost:7878/auth/callback');
  const scope = encodeURIComponent('channel:read:redemptions');
  const url = `https://id.twitch.tv/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=token&scope=${scope}&state=${encodeURIComponent(clientId)}`;
  window.open(url, '_blank');

  const poll = setInterval(async () => {
    let cfg;
    try {
      const res = await fetch('/config/data');
      if (!res.ok) return;
      cfg = await res.json();
    } catch (err) {
      return; // server briefly down while switching setup/running mode
    }
    if (cfg.twitch_token) {
      clearInterval(poll);
      $('twitch_token_hidden').value = cfg.twitch_token;
      if (cfg.channel_name) field('channel_name').value = cfg.channel_name;
      updateLoginStatus(cfg.twitch_token, cfg.channel_name);
      loadAvatar(cfg.twitch_token, customClientId || defaultClientId);
      clearFieldError('twitch_token');
      if (cfg.channel_name) clearFieldError('channel_name');
      showStatus('Twitch connected!', 'success');
    }
  }, 1500);
});

$('logout-btn').addEventListener('click', async () => {
  if (!confirm('Logout of Twitch? TTS alerts will stop until you log back in.')) return;
  try {
    const res = await fetch('/auth/logout', { method: 'POST' });
    if (!res.ok) {
      showStatus('Logout failed - check the log.', 'error');
      return;
    }
  } catch (err) {
    showStatus('Logout error: ' + err.message, 'error');
    return;
  }
  $('twitch_token_hidden').value = '';
  updateLoginStatus('', '');
  updateTestSection(false, '');
  showStatus('Logged out of Twitch. Login again whenever you\'re ready.', 'success');
});

// --- File libraries ---

function formatSize(bytes) {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return bytes + ' B';
}

function formatTime(s) {
  if (!isFinite(s)) return '-:--';
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
}

async function loadFiles() {
  const res = await fetch('/files');
  if (!res.ok) return;
  libraryFiles = (await res.json()).files;
  renderGalleries();
}

async function deleteFile(f) {
  if (!confirm(`Delete ${f.name}?`)) return;
  const res = await fetch('/files/' + encodeURIComponent(f.name), { method: 'DELETE' });
  if (res.ok) {
    if ($('voice_sample_hidden').value === f.path) $('voice_sample_hidden').value = '';
    if ($('overlay_gif_hidden').value === f.path) $('overlay_gif_hidden').value = '';
    showStatus(`${f.name} deleted.`, 'success');
    loadFiles();
  } else {
    showStatus('Delete failed.', 'error');
  }
}

function renderGalleries() {
  renderVoiceGallery();
  renderGifGallery();
}

// One shared registry so starting a sample pauses the others
const players = [];

function stopOtherPlayers(current) {
  players.forEach(p => { if (p.audio !== current && !p.audio.paused) p.audio.pause(); });
}

const PLAY_SVG = '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 2.5v11l9-5.5z" fill="currentColor"/></svg>';
const PAUSE_SVG = '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor"/></svg>';

function buildAudioPlayer(f) {
  const wrap = document.createElement('div');
  wrap.className = 'player';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'player-btn';
  btn.innerHTML = PLAY_SVG;

  const track = document.createElement('div');
  track.className = 'player-track';
  const fill = document.createElement('div');
  fill.className = 'player-fill';
  track.appendChild(fill);

  const time = document.createElement('span');
  time.className = 'player-time';
  time.textContent = '-:--';

  const audio = new Audio();
  audio.preload = 'none';
  audio.src = '/files/' + encodeURIComponent(f.name);
  players.push({ audio });

  btn.addEventListener('click', e => {
    e.stopPropagation();
    if (audio.paused) {
      stopOtherPlayers(audio);
      audio.play();
    } else {
      audio.pause();
    }
  });
  audio.addEventListener('play', () => { btn.innerHTML = PAUSE_SVG; });
  audio.addEventListener('pause', () => { btn.innerHTML = PLAY_SVG; });
  audio.addEventListener('loadedmetadata', () => { time.textContent = formatTime(audio.duration); });
  audio.addEventListener('timeupdate', () => {
    if (audio.duration) fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
    time.textContent = formatTime(audio.duration ? audio.duration - audio.currentTime : NaN);
  });
  audio.addEventListener('ended', () => {
    fill.style.width = '0%';
    time.textContent = formatTime(audio.duration);
  });
  track.addEventListener('click', e => {
    e.stopPropagation();
    if (!audio.duration) return;
    const rect = track.getBoundingClientRect();
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
  });

  wrap.appendChild(btn);
  wrap.appendChild(track);
  wrap.appendChild(time);
  return wrap;
}

function buildDeleteBtn(f) {
  const del = document.createElement('button');
  del.type = 'button';
  del.className = 'card-delete';
  del.title = `Delete ${f.name}`;
  del.textContent = '×';
  del.addEventListener('click', e => {
    e.stopPropagation();
    deleteFile(f);
  });
  return del;
}

function externalNote(el, path, libPaths) {
  if (path && !libPaths.includes(path)) {
    el.textContent = `Currently using an external file: ${path}`;
    el.classList.remove('hidden');
  } else {
    el.classList.add('hidden');
  }
}

function renderVoiceGallery() {
  const gallery = $('voice-gallery');
  players.length = 0;
  gallery.innerHTML = '';
  const voices = libraryFiles.filter(f => f.kind === 'audio');
  const selected = $('voice_sample_hidden').value;

  if (voices.length === 0) {
    gallery.innerHTML = '<div class="lib-empty">No voice samples yet - upload one above.</div>';
  }
  voices.forEach(f => {
    const card = document.createElement('div');
    card.className = 'voice-card' + (f.path === selected ? ' selected' : '');

    const top = document.createElement('div');
    top.className = 'card-top';
    const name = document.createElement('span');
    name.className = 'card-name';
    name.textContent = f.name;
    const size = document.createElement('span');
    size.className = 'card-size';
    size.textContent = formatSize(f.size);
    top.appendChild(name);
    top.appendChild(size);
    if (f.path === selected) {
      const badge = document.createElement('span');
      badge.className = 'selected-badge';
      badge.textContent = '✓ selected';
      top.appendChild(badge);
    }
    top.appendChild(buildDeleteBtn(f));

    card.appendChild(top);
    card.appendChild(buildAudioPlayer(f));
    card.addEventListener('click', () => {
      $('voice_sample_hidden').value = f.path;
      clearFieldError('voice_sample');
      renderVoiceGallery();
      showStatus(`Voice: ${f.name} - hit Save & Start to apply.`, 'info');
    });
    gallery.appendChild(card);
  });

  externalNote($('voice-external'), selected, voices.map(f => f.path));
}

function renderGifGallery() {
  const gallery = $('gif-gallery');
  gallery.innerHTML = '';
  const gifs = libraryFiles.filter(f => f.kind === 'gif');
  const selected = $('overlay_gif_hidden').value;

  if (gifs.length === 0) {
    gallery.innerHTML = '<div class="lib-empty">No GIFs yet - upload one above.</div>';
  }
  gifs.forEach(f => {
    const card = document.createElement('div');
    card.className = 'gif-card' + (f.path === selected ? ' selected' : '');

    const img = document.createElement('img');
    img.loading = 'lazy';
    img.src = '/files/' + encodeURIComponent(f.name);
    img.alt = f.name;
    card.appendChild(img);

    if (f.path === selected) {
      const badge = document.createElement('span');
      badge.className = 'selected-badge gif-badge';
      badge.textContent = '✓';
      card.appendChild(badge);
    }
    card.appendChild(buildDeleteBtn(f));

    const name = document.createElement('div');
    name.className = 'gif-name';
    name.textContent = f.name;
    card.appendChild(name);

    card.addEventListener('click', () => {
      $('overlay_gif_hidden').value = f.path;
      clearFieldError('overlay_gif');
      renderGifGallery();
      showStatus(`Alert GIF: ${f.name} - hit Save & Start to apply.`, 'info');
    });
    gallery.appendChild(card);
  });

  externalNote($('gif-external'), selected, gifs.map(f => f.path));
}

async function uploadTo(endpoint, inputEl, autoSelectField) {
  const file = inputEl.files[0];
  if (!file) return;
  showStatus(`Uploading ${file.name}...`, 'info');
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await fetch(endpoint, { method: 'POST', body: formData });
    if (res.ok) {
      const data = await res.json();
      $(autoSelectField).value = data.path;
      showStatus(`${file.name} uploaded and selected - hit Save & Start to apply.`, 'success');
      await loadFiles();
    } else {
      const err = await res.json().catch(() => ({}));
      showStatus(err.detail || 'Upload failed.', 'error');
    }
  } catch (err) {
    showStatus('Upload error: ' + err.message, 'error');
  }
  inputEl.value = '';
}

$('voice_upload').addEventListener('change', () =>
  uploadTo('/upload/voice', $('voice_upload'), 'voice_sample_hidden'));
$('gif_upload').addEventListener('change', () =>
  uploadTo('/upload/gif', $('gif_upload'), 'overlay_gif_hidden'));

// --- Required-field validation ---

const REQUIRED = [
  { key: 'twitch_token', label: 'Twitch login', target: () => $('login-btn') },
  { key: 'channel_name', label: 'Channel Name', target: () => field('channel_name') },
  { key: 'reward_name', label: 'Reward Name', target: () => field('reward_name') },
  { key: 'voice_sample', label: 'Voice sample', target: () => $('voice-gallery') },
  { key: 'overlay_gif', label: 'Alert GIF', target: () => $('gif-gallery') },
];

function clearFieldErrors() {
  document.querySelectorAll('.req-msg').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.field-invalid').forEach(el => el.classList.remove('field-invalid'));
}

function clearFieldError(key) {
  const msg = $(`err-${key}`);
  if (msg) msg.classList.add('hidden');
  const req = REQUIRED.find(r => r.key === key);
  if (req) req.target().classList.remove('field-invalid');
}

function validateRequired(data) {
  clearFieldErrors();
  const missing = REQUIRED.filter(r => !data[r.key]);
  if (missing.length === 0) return true;

  missing.forEach(r => {
    const msg = $(`err-${r.key}`);
    if (msg) msg.classList.remove('hidden');
    r.target().classList.add('field-invalid');
  });

  const names = missing.map(r => r.label).join(', ');
  showStatus(`Almost there! Still needed: ${names}`, 'error');

  const first = missing[0].target();
  first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  if (first.tagName === 'INPUT') setTimeout(() => first.focus({ preventScroll: true }), 450);
  return false;
}

['channel_name', 'reward_name'].forEach(k =>
  field(k).addEventListener('input', () => clearFieldError(k)));

// --- Test & Preview ---

function updateTestSection(complete, channelName) {
  const section = $('test-section');
  if (!complete) {
    section.classList.add('hidden');
    return;
  }
  const wasHidden = section.classList.contains('hidden');
  section.classList.remove('hidden');
  $('pv-username').textContent = '@' + (channelName || 'you');
  $('pv-gif').src = '/overlay-gif?' + Date.now();
  if (wasHidden) replayPreview();
}

function replayPreview() {
  const alert = $('pv-alert');
  alert.classList.remove('pv-animate');
  void alert.offsetWidth;
  alert.classList.add('pv-animate');
}

$('replay-preview').addEventListener('click', replayPreview);
$('pv-gif').addEventListener('error', () => { $('pv-gif').style.display = 'none'; });
$('pv-gif').addEventListener('load', () => { $('pv-gif').style.display = ''; });

$('send-test-alert').addEventListener('click', async () => {
  const btn = $('send-test-alert');
  btn.disabled = true;
  try {
    const res = await fetch('/test/alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: field('channel_name').value.trim() || 'shima',
        message: 'This is a test alert from ShimaTTS!',
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.connections > 0) {
        showStatus(`Test alert sent to ${data.connections} connected overlay${data.connections > 1 ? 's' : ''}!`, 'success');
      } else {
        showStatus('Test sent, but no overlay is connected - add the browser source in OBS first (see the setup guide).', 'error');
      }
      replayPreview();
    } else {
      showStatus('Could not send test alert.', 'error');
    }
  } catch (err) {
    showStatus('Test alert error: ' + err.message, 'error');
  }
  btn.disabled = false;
});

// --- Custom prefix toggle ---

$('prefix-toggle').addEventListener('change', () => {
  $('prefix-fields').classList.toggle('hidden', !$('prefix-toggle').checked);
});

// --- Save / quit ---

const form = $('config-form');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const data = {
    twitch_token: $('twitch_token_hidden').value,
    channel_name: field('channel_name').value.trim(),
    reward_name: field('reward_name').value.trim(),
    voice_sample: $('voice_sample_hidden').value,
    overlay_gif: $('overlay_gif_hidden').value,
    tts_template: $('prefix-toggle').checked ? field('tts_template').value.trim() : '',
  };

  if (!validateRequired(data)) return;

  if (data.tts_template && !data.tts_template.includes('{message}')) {
    showStatus('Custom prefix must contain {message} - otherwise nothing gets spoken.', 'error');
    field('tts_template').classList.add('field-invalid');
    field('tts_template').scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }
  field('tts_template').classList.remove('field-invalid');

  try {
    const res = await fetch('/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      const json = await res.json();
      $('save-btn').textContent = 'Saved!';
      setTimeout(() => { $('save-btn').textContent = 'Save & Start'; }, 2500);
      $('saved-banner').classList.remove('hidden');
      setTimeout(() => $('saved-banner').classList.add('hidden'), 6000);
      if (json.complete) {
        $('saved-banner').textContent = '✓ Config saved - ShimaTTS is running, go stream!';
        updateTestSection(true, data.channel_name);
        $('test-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else {
      showStatus('Save failed - check the log.', 'error');
    }
  } catch (err) {
    showStatus('Error: ' + err.message, 'error');
  }
});

$('quit-btn').addEventListener('click', async () => {
  if (!confirm('Quit ShimaTTS? TTS alerts will stop until you start it again.')) return;
  try {
    await fetch('/app/quit', { method: 'POST' });
  } catch (err) { /* server dies before responding - expected */ }
  document.body.innerHTML = '<div style="display:flex;height:90vh;align-items:center;justify-content:center;color:#888;font-family:Segoe UI,sans-serif;font-size:18px">ShimaTTS has been closed. You can close this window.</div>';
});

loadConfig();
loadFiles();
