const alertEl = document.getElementById('alert');
const gifEl   = document.getElementById('gif');
const userEl  = document.getElementById('username');
const msgEl   = document.getElementById('message');

let hideTimer = null;

function fitMessage() {
  // The card is fixed-size: shrink the font until the text fits its box
  let size = 28;
  msgEl.style.fontSize = size + 'px';
  while (size > 13 && msgEl.scrollHeight > msgEl.clientHeight) {
    size -= 0.5;
    msgEl.style.fontSize = size + 'px';
  }
}

function showAlert(username, message, durationMs) {
  if (hideTimer) clearTimeout(hideTimer);

  gifEl.src = '/overlay-gif?' + Date.now(); // bust GIF loop cache
  userEl.textContent = '@' + username;
  msgEl.textContent  = message;

  alertEl.classList.remove('hidden', 'fade-out');
  fitMessage();

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
