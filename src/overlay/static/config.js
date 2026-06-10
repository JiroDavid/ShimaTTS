async function loadConfig() {
  const res = await fetch('/config/data');
  if (!res.ok) return;
  const cfg = await res.json();
  Object.entries(cfg).forEach(([key, value]) => {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = value;
  });
}

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
