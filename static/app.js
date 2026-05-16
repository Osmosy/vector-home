/* Vector Home v2 — Dashboard Logic */

const API = '';
let ws = null;
let currentGroup = 'light';
let history = [];

// ── Device definitions (matching 53 tools) ──────────────────────────
const DEVICES = {
  light: [
    { icon: '💡', name: 'Включить свет', cmd: 'turn on the lights in the living room', tool: 'turn_on_light' },
    { icon: '🌑', name: 'Выключить свет', cmd: 'turn off the lights in the bedroom', tool: 'turn_off_light' },
    { icon: '🔅', name: 'Приглушить свет', cmd: 'dim the lights to 30%', tool: 'dim_light' },
    { icon: '🔴', name: 'Цвет света', cmd: 'set the light color to red', tool: 'set_light_color' },
    { icon: '🌅', name: 'Тёплый свет', cmd: 'set color temperature to 2700 kelvin', tool: 'set_light_temperature_k' },
    { icon: '🎬', name: 'Сцена света', cmd: 'activate mood lighting', tool: 'set_light_scene' },
    { icon: '✨', name: 'Мигнуть светом', cmd: 'blink the lights', tool: 'blink_light' },
    { icon: '❓', name: 'Состояние света', cmd: 'is the light on?', tool: 'query_light_state' },
  ],
  climate: [
    { icon: '🌡️', name: 'Установить температуру', cmd: 'set temperature to 22 degrees', tool: 'set_temperature' },
    { icon: '🌡️', name: 'Какая температура?', cmd: 'what is the temperature?', tool: 'query_temperature' },
    { icon: '🔧', name: 'Термостат', cmd: 'set the thermostat to heat mode', tool: 'set_thermostat' },
    { icon: '❄️', name: 'Кондиционер', cmd: 'set AC to cool mode', tool: 'set_ac_mode' },
    { icon: '🌀', name: 'Вентилятор', cmd: 'set fan speed to high', tool: 'set_fan_speed' },
    { icon: '💧', name: 'Целевая влажность', cmd: 'set humidity target to 50%', tool: 'set_humidity_target' },
    { icon: '💨', name: 'Увлажнитель', cmd: 'turn on the humidifier', tool: 'toggle_humidifier' },
    { icon: '🌵', name: 'Осушитель', cmd: 'turn on the dehumidifier', tool: 'toggle_dehumidifier' },
    { icon: '💧', name: 'Какая влажность?', cmd: 'what is the humidity?', tool: 'query_humidity' },
  ],
  covers: [
    { icon: '🪟', name: 'Открыть шторы', cmd: 'open the curtains', tool: 'open_curtains' },
    { icon: '🪟', name: 'Закрыть шторы', cmd: 'close the curtains', tool: 'close_curtains' },
    { icon: '☀️', name: 'Поднять жалюзи', cmd: 'raise the blinds', tool: 'raise_blinds' },
    { icon: '🌙', name: 'Опустить жалюзи', cmd: 'lower the blinds', tool: 'lower_blinds' },
    { icon: '📐', name: 'Позиция жалюзи', cmd: 'set blinds position to 50%', tool: 'set_blinds_position' },
    { icon: '🔄', name: 'Угол жалюзи', cmd: 'tilt blinds to 45 degrees', tool: 'set_blinds_angle' },
  ],
  vacuum: [
    { icon: '🤖', name: 'Пылесос', cmd: 'vacuum the living room', tool: 'vacuum_start' },
    { icon: '⏹️', name: 'Остановить', cmd: 'stop the vacuum', tool: 'stop_vacuum' },
    { icon: '🔌', name: 'На базу', cmd: 'dock the vacuum', tool: 'dock_vacuum' },
  ],
  security: [
    { icon: '🔒', name: 'Запереть дверь', cmd: 'lock the front door', tool: 'lock_door' },
    { icon: '🔓', name: 'Открыть замок', cmd: 'unlock the front door', tool: 'unlock_door' },
    { icon: '❓', name: 'Дверь заперта?', cmd: 'is the front door locked?', tool: 'query_door_status' },
    { icon: '🚨', name: 'Поставить сигнализацию', cmd: 'arm the alarm system', tool: 'arm_alarm_system' },
    { icon: '✅', name: 'Снять сигнализацию', cmd: 'disarm the alarm system', tool: 'disarm_alarm_system' },
    { icon: '❓', name: 'Статус сигнализации', cmd: 'what is the alarm status?', tool: 'query_alarm_status' },
    { icon: '🆘', name: 'Тревога!', cmd: 'panic alarm!', tool: 'trigger_panic_alarm' },
  ],
  media: [
    { icon: '🎵', name: 'Включить музыку', cmd: 'play jazz in the kitchen', tool: 'play_music' },
    { icon: '⏹️', name: 'Остановить', cmd: 'stop the music', tool: 'stop_music' },
    { icon: '⏸️', name: 'Пауза', cmd: 'pause the music', tool: 'pause_music' },
    { icon: '📻', name: 'Радио', cmd: 'play radio station jazz fm', tool: 'play_radio_station' },
    { icon: '🔊', name: 'Громкость', cmd: 'set volume to 50%', tool: 'set_volume' },
    { icon: '🔇', name: 'Без звука', cmd: 'mute the audio', tool: 'mute_audio' },
    { icon: '📺', name: 'Включить ТВ', cmd: 'turn on the tv', tool: 'turn_on_tv' },
    { icon: '📺', name: 'Выключить ТВ', cmd: 'turn off the tv', tool: 'turn_off_tv' },
    { icon: '📺', name: 'Канал ТВ', cmd: 'set tv channel to 5', tool: 'set_tv_channel' },
  ],
  garden: [
    { icon: '💧', name: 'Полив вкл', cmd: 'start irrigation zone 1', tool: 'start_irrigation_zone' },
    { icon: '🛑', name: 'Полив выкл', cmd: 'stop irrigation zone 1', tool: 'stop_irrigation_zone' },
    { icon: '🌱', name: 'Влажность почвы', cmd: 'what is the soil moisture?', tool: 'query_soil_moisture' },
  ],
  other: [
    { icon: '⏰', name: 'Будильник', cmd: 'set alarm for 07:30', tool: 'set_alarm' },
    { icon: '❌', name: 'Отменить будильник', cmd: 'cancel the alarm', tool: 'cancel_alarm' },
    { icon: '🎬', name: 'Сцена', cmd: 'activate movie night scene', tool: 'activate_scene' },
    { icon: '🔌', name: 'Розетка', cmd: 'toggle the outlet', tool: 'toggle_outlet' },
    { icon: '💨', name: 'Качество воздуха', cmd: 'what is the air quality?', tool: 'query_air_quality' },
    { icon: '📡', name: 'Датчик движения', cmd: 'set motion sensitivity to high', tool: 'set_motion_sensitivity' },
  ],
};

// ── Init ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  renderDevices(currentGroup);
  setupTabs();
  setupCommandInput();
  setupVoice();
  connectWebSocket();
  fetchHistory();
});

// ── WebSocket ────────────────────────────────────────────────────────

function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    document.getElementById('ws-status').className = 'dot connected';
    document.getElementById('connection-info').textContent = 'Connected';
  };

  ws.onclose = () => {
    document.getElementById('ws-status').className = 'dot disconnected';
    document.getElementById('connection-info').textContent = 'Disconnected';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'command') {
        addHistoryItem(msg.data);
      }
    } catch (e) {}
  };
}

// ── Devices ──────────────────────────────────────────────────────────

function setupTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentGroup = btn.dataset.group;
      renderDevices(currentGroup);
    });
  });
}

function renderDevices(group) {
  const grid = document.getElementById('devices-grid');
  const devices = DEVICES[group] || [];
  grid.innerHTML = devices.map(d => `
    <div class="device-card" data-cmd="${escapeHtml(d.cmd)}">
      <div class="icon">${d.icon}</div>
      <div class="name">${d.name}</div>
    </div>
  `).join('');

  grid.querySelectorAll('.device-card').forEach(card => {
    card.addEventListener('click', () => {
      const cmd = card.dataset.cmd;
      document.getElementById('cmd-input').value = cmd;
      sendCommand(cmd);
    });
  });
}

// ── Command Input ────────────────────────────────────────────────────

function setupCommandInput() {
  const input = document.getElementById('cmd-input');
  const sendBtn = document.getElementById('cmd-send');

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCommand(input.value);
  });
  sendBtn.addEventListener('click', () => sendCommand(input.value));
}

async function sendCommand(text) {
  if (!text.trim()) return;

  const resultDiv = document.getElementById('cmd-result');
  resultDiv.className = 'result-card';
  resultDiv.innerHTML = '⏳ Processing...';

  try {
    const resp = await fetch(`${API}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.trim() }),
    });

    if (!resp.ok) {
      resultDiv.innerHTML = `❌ Error: ${resp.status} ${resp.statusText}`;
      resultDiv.className = 'result-card error';
      return;
    }

    const data = await resp.json();
    displayResult(data);
  } catch (err) {
    resultDiv.innerHTML = `❌ Network error: ${err.message}`;
    resultDiv.className = 'result-card error';
  }
}

function displayResult(data) {
  const div = document.getElementById('cmd-result');
  div.className = 'result-card';

  const tool = data.tool || 'none';
  const args = data.arguments || {};
  const ha = data.ha_service || {};
  const latency = data.latency_s ? `${data.latency_s.toFixed(1)}s` : '';
  const fallback = data.used_fallback ? ' (fallback→Ollama)' : '';

  let html = `<span class="tool-name">${tool}</span>${fallback}`;
  html += `<span class="args">(${formatArgs(args)})</span>`;
  if (latency) html += ` <span class="latency">${latency}</span>`;
  if (ha && ha.domain) {
    html += `<br><span class="ha-call">HA: ${ha.domain}.${ha.service}(${ha.entity_id || ''})</span>`;
  }
  if (data.ha_result) {
    const hr = data.ha_result;
    if (hr.dry_run) html += `<br><span class="latency">${hr.message || 'DRY RUN'}</span>`;
    else if (hr.success) html += `<br><span style="color:var(--success)">✓ executed</span>`;
    else if (hr.error) html += `<br><span style="color:var(--danger)">✗ ${hr.error}</span>`;
  }

  div.innerHTML = html;
}

function formatArgs(args) {
  return Object.entries(args).map(([k, v]) => `${k}=${v}`).join(', ') || 'no args';
}

// ── Voice Input ───────────────────────────────────────────────────────

function setupVoice() {
  const btn = document.getElementById('cmd-voice');
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    btn.style.display = 'none';
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.lang = 'ru-RU';
  recognition.continuous = false;
  recognition.interimResults = false;

  let isListening = false;

  btn.addEventListener('click', () => {
    if (isListening) {
      recognition.stop();
      btn.classList.remove('recording');
      isListening = false;
    } else {
      recognition.start();
      btn.classList.add('recording');
      isListening = true;
    }
  });

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    document.getElementById('cmd-input').value = text;
    sendCommand(text);
    btn.classList.remove('recording');
    isListening = false;
  };

  recognition.onerror = () => {
    btn.classList.remove('recording');
    isListening = false;
  };

  recognition.onend = () => {
    btn.classList.remove('recording');
    isListening = false;
  };
}

// ── History ───────────────────────────────────────────────────────────

async function fetchHistory() {
  try {
    const resp = await fetch(`${API}/history?limit=20`);
    const data = await resp.json();
    history = data.history || [];
    renderHistory();
  } catch (e) {
    // silently fail
  }
}

function renderHistory() {
  const list = document.getElementById('history-list');
  if (history.length === 0) {
    list.innerHTML = '<p class="empty">Нет команд</p>';
    return;
  }

  list.innerHTML = history.slice().reverse().map((h, i) => {
    const result = h.result || {};
    const isError = result.tool === 'none' || result.error;
    const ts = h.timestamp ? new Date(h.timestamp).toLocaleTimeString('ru-RU') : '';
    return `<div class="history-item${isError ? ' error' : ''}" onclick="reuseCommand('${escapeHtml(h.text)}')">
      <span class="cmd">${escapeHtml(h.text)}</span>
      <span class="tool">${result.tool || '?'}</span>
      <span class="time">${ts}</span>
    </div>`;
  }).join('');
}

function addHistoryItem(entry) {
  history.push(entry);
  if (history.length > 50) history.shift();
  renderHistory();
}

function reuseCommand(text) {
  document.getElementById('cmd-input').value = text;
  sendCommand(text);
}

document.getElementById('clear-history').addEventListener('click', () => {
  history = [];
  renderHistory();
});

// ── Utils ─────────────────────────────────────────────────────────────

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}