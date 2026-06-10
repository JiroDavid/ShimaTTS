const alertEl = document.getElementById('alert');
const gifEl   = document.getElementById('gif');
const userEl  = document.getElementById('username');
const msgEl   = document.getElementById('message');

let hideTimer = null;

function showAlert(username, message, durationMs) {
  if (hideTimer) clearTimeout(hideTimer);

  gifEl.src = '/overlay-gif?' + Date.now(); // bust GIF loop cache
  userEl.textContent = '@' + username;
  msgEl.textContent  = message;

  alertEl.classList.remove('hidden', 'fade-out');

  hideTimer = setTimeout(() => {
    alertEl.classList.add('fade-out');
    setTimeout(() => alertEl.classList.add('hidden'), 650);
  }, durationMs);
}

function connect() {
  const ws = new WebSocket('ws://' + location.host + '/ws');

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    showAlert(data.username, data.message, data.duration_ms);
  };

  ws.onclose = () => setTimeout(connect, 2000);
  ws.onerror = () => ws.close();
}

connect();
