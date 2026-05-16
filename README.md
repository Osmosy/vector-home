# 🏠 Vector Home v2

> Умный дом на CPU. Без облака, без API-ключей, без интернета.
> 52 инструмента, RU+EN команды, веб-панель, Home Assistant.

## Архитектура

```
Голос / Текст
      ↓
┌─────────────┐    ┌──────────────┐
│   Router v2  │───→│   Parser v2  │
│ regex + Ollama│   │ GPT-2 124M  │
│  95 правил    │   │ 53 инструм.  │
│  100% EN/RU  │   │              │
└──────┬──────┘    └──────┬───────┘
       │                   │
       └───────┬───────────┘
               ↓
       ┌───────────────┐
       │   HA Bridge    │
       │ 53→HA mapping  │
       │ RU→EN translate│
       └───────┬───────┘
               ↓
        Home Assistant
```

## 52 инструмента

| Домен | Инструменты |
|-------|------------|
| 💡 Свет | `turn_on_light`, `turn_off_light`, `dim_light`, `blink_light`, `set_light_color`, `set_light_scene`, `set_light_temperature_k`, `query_light_state` |
| 🌡️ Климат | `set_temperature`, `query_temperature`, `set_thermostat`, `set_ac_mode`, `set_fan_speed`, `set_humidity_target`, `toggle_humidifier`, `toggle_dehumidifier`, `query_humidity` |
| 🪟 Шторы | `open_curtains`, `close_curtains`, `raise_blinds`, `lower_blinds`, `set_blinds_position`, `set_blinds_angle` |
| 🤖 Пылесос | `vacuum_start`, `stop_vacuum`, `dock_vacuum` |
| 🔒 Безопасность | `lock_door`, `unlock_door`, `query_door_status`, `arm_alarm_system`, `disarm_alarm_system`, `query_alarm_status`, `trigger_panic_alarm` |
| 🎵 Медиа | `play_music`, `stop_music`, `pause_music`, `play_radio_station`, `set_volume`, `mute_audio`, `turn_on_tv`, `turn_off_tv`, `set_tv_channel`, `set_tv_volume` |
| 🌿 Сад | `start_irrigation_zone`, `stop_irrigation_zone`, `query_soil_moisture` |
| 📡 Сенсоры | `query_air_quality`, `set_motion_sensitivity` |
| ⏰ Будильник | `set_alarm`, `cancel_alarm` |
| 🎬 Сцены | `activate_scene` |
| 🔌 Розетки | `toggle_outlet` |

## Быстрый старт

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt

# Тесты
python -m pytest tests/ -v                  # 130/130 ✓

# API сервер (порт 8126)
python -m src.api

# Веб-панель: http://localhost:8126/panel

# CLI
python -m src.pipeline "turn on the lights in the living room"
python -m src.pipeline "включи свет в гостиной"

# Голосовой пайплайн (нужен faster-whisper)
python -m src.voice --interactive
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `HA_URL` | URL Home Assistant | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | (пусто = dry run) |
| `VH_PORT` | Порт API сервера | `8126` |
| `GPT2_REPO` | Путь к gpt2-tool-call | `../gpt2-tool-call` |

## Точность роутера

| Набор | Точность |
|-------|---------|
| EN команды | 100% |
| RU команды | 100% |
| Порядок правил | ✓ (query до set, dim до off, thermostat до AC) |
| `\b` баг для кириллицы | ✗ исправлен |

## Структура проекта

```
vector-home/
├── src/
│   ├── router.py        # Regex роутер v2, 95 правил, EN+RU
│   ├── parser.py        # GPT-2 124M, 53 инструмента, fuzzy match
│   ├── pipeline.py     # Полный пайплайн: router→parser→HA
│   ├── api.py           # FastAPI + WebSocket + /panel
│   ├── ha_bridge.py     # 53 tool → HA mapping, RU→EN
│   └── voice.py         # STT→router→parser→HA→TTS
├── static/
│   ├── index.html       # Веб-панель — 8 групп устройств
│   ├── style.css        # Тёмная тема
│   └── app.js           # WebSocket + голосовой ввод
├── data/
│   ├── tools_spec_v2.json  # 52 инструмента + none
│   ├── train_dataset_v2.json  # 1000 примеров
│   └── test_dataset_v2.json   # Тестовый сплит
├── tests/
│   └── test_router.py   # 130 тестов: router, HA bridge, parser spec
├── docs/
│   └── SPEC.md          # Техническое задание v2
└── models/              # GPT-2 weights (git-lfs)
```

## Веб-панель

Доступна на `http://localhost:8126/panel`:

- 💡 Свет, 🌡️ Климат, 🪟 Шторы, 🤖 Пылесос, 🔒 Безопасность, 🎵 Медиа, 🌿 Сад, ⚡ Другое
- Текстовый ввод команд (RU+EN)
- 🎤 Голосовой ввод (Web Speech API)
- WebSocket для real-time обновлений
- История команд

## Home Assistant

Для реального управления устройствами:

1. Создайте Long-Lived Access Token в HA (`/profile/security`)
2. Установите переменные:

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="ваш_токен"
```

3. Запустите API с флагом `--live`:

```bash
python -m src.api --live
# или через pipeline:
python -m src.pipeline --live "turn on the lights"
```

Без токена — dry run режим (логирует, не отправляет в HA).

## Fallback на Ollama

Роутер использует regex-правила (100% точность на тестах). Если regex не находит совпадение — fallback на Qwen3:8B через Ollama:

```bash
# Убедитесь что Ollama запущена
ollama serve
ollama pull qwen3:8b    # или qwen3:7b для минимум
```

## Отличие от barometech/smart-home-gpt2

| | Vector Home v2 | smart-home-gpt2 |
|---|---|---|
| Роутер | Regex+fallback, 100% EN/RU | GPT-2 124M, multi-tool 71.7% |
| Парсер | GPT-2 124M, single-tool | GPT-2 124M, multi-tool |
| Инструментов | 52 | 100 |
| Голос | faster-whisper medium | faster-whisper medium |
| Веб-панель | ✓ (WebSocket) | ✗ |
| HA интеграция | ✓ (53 mapping) | Эмулятор |
| Тесты | 130 pytest | — |
| Русский | ✓ нативно | ✓ через translate |

## Лицензия

MIT