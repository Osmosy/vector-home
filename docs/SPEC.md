# Vector Home v2 — Техническое задание

## Суть проекта

Оффлайновый стек управления умным домом на CPU: голос/текст → router → SLM-parser → Home Assistant.
**v2**: 53 инструмента, веб-панель управления, мерж с barometech/smart-home-gpt2.

Без облака, без GPU, без API-ключей.

## Архитектура

```
Голос/Текст  ──►  Web Panel (React)
        │               │
        ▼               ▼
┌──────────────────────────────┐
│          Router v2           │  keyword/regex (0 RAM, 53+ intents)
│     215 rules, RU + EN       │  fallback → Qwen3:8B (Ollama)
└──────────┬───────────────────┘
           │
           ├─ hit ──► GPT-2 124M Full FT (600 MB RAM)
           │           single-tool parser → JSON
           │
           ├─ miss ──► Qwen3:8B (5 GB RAM, Ollama)
           │           multi-intent / ambiguous
           │
           └─ ambiguous ──► clarify (возврат пользователю)

           │
           ▼
┌──────────────────┐      ┌──────────────────┐
│ Home Assistant    │◄────►│ HA WebSocket      │
│ REST API          │      │ (real-time events)│
└──────────────────┘      └──────────────────┘

           │
           ▼
┌──────────────────┐
│ Voice Pipeline    │  STT (Whisper) → TTS (Piper / edge-tts)
└──────────────────┘

           │
           ▼
┌──────────────────┐
│  Web Dashboard    │  FastAPI + React SPA (порт 8126)
│  /panel           │  Управление устройствами, мониторинг, история
└──────────────────┘
```

## Компоненты

### 1. Router v2 (intent classifier)
- 215 regex правил для 53 интентов, RU/EN
- Порядок правил критичен: специфичные → общие
- `\b` НЕ используется для кириллицы (Python regex баг)
- Fallback на Qwen3:8B при промахе
- Валидация: 87/95 = 92% (цель: 95%+)

### 2. Parser (GPT-2 124M Full FT)
- База: gpt2-tool-call (barometech/gpt2-tool-call)
- Full FT под домен умного дома: `gpt2_ha_best.pt`
- RU SFT: `gpt2_ha_ru_best.pt` (mixed EN+RU)
- v2: `smart_home_v2.pt` (barometech, merged dataset)
- Single-tool: 100% EN, 95% RU
- Инференс: ~2s/команда на CPU
- RAM: ~600 MB

### 3. Fallback solver (Qwen3:8B via Ollama)
- Multi-intent команды
- Ambiguous запросы
- localhost:11434

### 4. Home Assistant bridge (REST + WebSocket)
- `ha_bridge.py` — 53 tool → HA service call маппинг
- `ha_ws.py` — real-time state_changed events, auto-reconnect
- RU→EN маппинг имён комнат/дверей/сцен
- Entity discovery через `/api/states`

### 5. HTTP API + Web Dashboard (FastAPI)
- **API**:
  - `POST /command` — текстовая команда → router → parser → HA
  - `GET /health` — статус всех компонентов
  - `GET /tools` — список 53 инструментов
  - `GET /entities` — сущности HA (с фильтром по домену)
  - `POST /ha/call` — прямой вызов HA
  - `GET /history` — последние N команд (in-memory)
  - `WS /ws` — WebSocket для real-time обновлений панели
- **Dashboard** (`/panel`):
  - React SPA, встроена в FastAPI (static files)
  - Управление устройствами по группам (свет, климат, безопасность...)
  - Командная строка (ввод текста/голоса)
  - История команд с результатами
  - Статус HA подключений
  - Мобильный адаптивный дизайн

### 6. Voice Pipeline
- **STT**: faster-whisper (tiny/medium)
- **TTS**: Piper (offline) / edge-tts (online)
- Полный контур: `voice.py process_voice()`

## Датасет v2

### Объединённый (train_dataset_v2.json)
- 1000 примеров после дедупликации
- Источники: 658 EN (оригинал) + 695 RU (оригинал) + 773 barometech (отфильтрованные)
- 53 инструмента (12 оригинальных + 41 новых из barometech)
- Формат: single-tool prompt → JSON

### tools_spec_v2.json
- 53 определения инструментов с параметрами
- Группы: light (8), climate (8), covers (6), vacuum (3), security (7),
  media (7), garden (3), sensors (3), alarms (2), scenes (1), outlets (1), thermostat (1), door (3), humidity (3)

## Поддерживаемые команды (53 инструмента)

### 💡 Свет (8)
| Tool | EN | RU |
|------|----|----|
| turn_on_light | turn on the lights in the living room | включи свет в гостиной |
| turn_off_light | turn off garage lights | выключи свет на кухне |
| dim_light | dim the lights in the bedroom | приглуши свет в спальне |
| blink_light | blink the lights | мигни светом |
| set_light_color | set the light color to red | сделай свет синий |
| set_light_scene | activate mood lighting | включи сцену кино |
| set_light_temperature_k | warm white in the bedroom | тёплый свет в спальне |
| query_light_state | is the light on? | включен ли свет? |

### 🌡️ Климат (8)
| Tool | EN | RU |
|------|----|----|
| set_temperature | set bedroom to 22 degrees | поставь 22 градуса |
| query_temperature | what is the temperature? | какая температура? |
| set_thermostat | set thermostat to heat mode | термостат на обогрев |
| set_ac_mode | set AC to cool mode | кондиционер режим охлаждения |
| set_fan_speed | set fan to high | скорость вентилятора |
| set_humidity_target | set humidity to 50% | влажность 50% |
| toggle_humidifier | turn on humidifier | включи увлажнитель |
| toggle_dehumidifier | turn on dehumidifier | включи осушитель |
| query_humidity | what's the humidity? | какая влажность? |

### 🪟 Шторы/жалюзи (6)
| Tool | EN | RU |
|------|----|----|
| open_curtains | open the curtains | открой шторы |
| close_curtains | close the curtains | закрой шторы |
| raise_blinds | raise the blinds | подними жалюзи |
| lower_blinds | lower the blinds | опусти жалюзи |
| set_blinds_position | set blinds to 50% | жалюзи на 50% |
| set_blinds_angle | tilt blinds to 45° | наклон жалюзи 45° |

### 🤖 Пылесос (3)
| Tool | EN | RU |
|------|----|----|
| vacuum_start | vacuum the office | пропылесось кухню |
| stop_vacuum | stop the vacuum | останови пылесос |
| dock_vacuum | dock the vacuum | пылесос на базу |

### 🔒 Безопасность (7)
| Tool | EN | RU |
|------|----|----|
| lock_door | lock the front door | запри входную дверь |
| unlock_door | unlock the back door | открой замок |
| query_door_status | is the door locked? | дверь заперта? |
| arm_alarm_system | arm the alarm | поставь сигнализацию |
| disarm_alarm_system | disarm the alarm | сними сигнализацию |
| query_alarm_status | what's the alarm status? | статус сигнализации? |
| trigger_panic_alarm | panic alarm! | тревога! |

### 🎵 Медиа (7)
| Tool | EN | RU |
|------|----|----|
| play_music | play jazz in the kitchen | включи джаз |
| stop_music | stop music | останови музыку |
| pause_music | pause the music | пауза |
| play_radio_station | play radio jazz fm | включи радио |
| set_volume | set volume to 50% | громкость 50% |
| mute_audio | mute the audio | выключи звук |
| turn_on_tv | turn on the tv | включи телевизор |
| turn_off_tv | turn off the tv | выключи телевизор |
| set_tv_channel | set tv channel to 5 | переключи канал |
| set_tv_volume | set tv volume to 30 | громкость тв |

### 🌿 Сад (3)
| Tool | EN | RU |
|------|----|----|
| start_irrigation_zone | start irrigation zone 1 | включи полив |
| stop_irrigation_zone | stop irrigation zone 3 | выключи полив |
| query_soil_moisture | what's the soil moisture? | влажность почвы? |

### 📡 Сенсоры (3)
| Tool | EN | RU |
|------|----|----|
| query_air_quality | what's the air quality? | качество воздуха? |
| set_motion_sensitivity | set motion sensitivity to high | чувствительность датчика |
| query_humidity | what's the humidity? | какая влажность? |

### ⏰ Будильник (2)
| Tool | EN | RU |
|------|----|----|
| set_alarm | wake me up at 07:30 | поставь будильник |
| cancel_alarm | cancel the alarm | отмени будильник |

### 🎬 Сцены (1)
| Tool | EN | RU |
|------|----|----|
| activate_scene | activate movie night | включи сцену кино |

### 🔌 Розетки (1)
| Tool | EN | RU |
|------|----|----|
| toggle_outlet | toggle the outlet | включи розетку |

## Веб-панель управления (/panel)

### Функциональность
- **Панель устройств**: карточки устройства по группам (свет, климат, ...)
- **Командная строка**: ввод текстовой команды с живым результатом
- **История команд**: список последних N команд с результатами (in-memory)
- **Статус системы**: HA подключение, router/parser/bridge статусы
- **WebSocket**: real-time обновления при выполнении команд

### Техническое решение
- FastAPI раздаёт статические файлы из `static/`
- React SPA собирается в `static/` (или чистый HTML+JS без сборки для простоты)
- CSS: тёмная тема, адаптивная верстка, иконки по группам
- WebSocket через `/ws` endpoint для push-обновлений

## Требования

### Минимальные
- CPU-only (без GPU)
- RAM: ≤1 GB для stack без fallback, ≤6 GB с Qwen3
- Диск: ≤2 GB (модели + голоса + данные)
- Оффлайн: полная работоспособность без интернета
- Python 3.10+

### Целевые
- Latency router: <10ms
- Latency parser: <3s (CPU)
- Router accuracy: ≥95% (v2 target)
- Parser accuracy EN: 100%, RU: ≥90%

## Этапы

### Phase 0: Foundation ✅
- [x] Клонировать gpt2-tool-call, скачать веса
- [x] Сгенерировать EN датасет (658 примеров)
- [x] SFT EN: 12/12 = 100%

### Phase 1: Router ✅
- [x] Keyword/regex router v1: 12 intents, 44 команды = 100%

### Phase 2: Integration ✅
- [x] FastAPI API endpoint (порт 8126)
- [x] HA REST bridge + WebSocket
- [x] RU→EN маппинг entity

### Phase 3: Voice ✅
- [x] STT + TTS pipeline
- [x] Замкнутый контур: голос → HA → голос

### Phase 4: RU SFT ✅
- [x] RU датасет: 695 примеров
- [x] RU SFT: 95% accuracy

### Phase 5: v2 Merge 🔄
- [x] Merge barometech/smart-home-gpt2 dataset (1500 примеров)
- [x] Router v2: 53 intents, 215 правил
- [x] tools_spec_v2.json: 53 инструмента
- [x] train_dataset_v2.json: 1000 примеров (merged + dedup)
- [ ] Починить router_v2: 92% → 95%+ (8 failing RU+EN tests)
- [ ] Обновить parser.py под tools_spec_v2
- [ ] Обновить pipeline.py под router_v2
- [ ] Обновить api.py + веб-панель
- [ ] Обновить ha_bridge.py: 53 tool → HA mapping
- [ ] Обновить voice.py под router_v2

### Phase 6: Web Dashboard 🔄
- [ ] FastAPI: `/panel` раздаёт static HTML+JS
- [ ] Dashboard UI: карточки устройств по группам
- [ ] Командная строка в панели
- [ ] История команд (`/history` endpoint)
- [ ] WebSocket `/ws` для real-time
- [ ] Статус системы в панели

### Phase 7: Real HA (отложено)
- [ ] Подключение к реальному HA
- [ ] Тестирование на реальных entity
- [ ] WebSocket подписка на state_changed

## Известные ограничения

1. GPT-2 context = 1024 токена. PI > 4x ломает качество.
2. Multi-tool без fallback = 8% (architecture limit).
3. Router v2: `\b` не работает с кириллицей в Python regex → убрано.
4. 53 инструмента — потолок для keyword/regex router, дальнейшее расширение → fallback на LLM.

## Файловая структура v2

```
vector-home/
├── src/
│   ├── router.py            # HomeRouter v2 — 53 intents, 215 rules, RU+EN
│   ├── parser.py             # HomeParser — GPT-2 inference (tools_spec_v2)
│   ├── pipeline.py           # process() — router → parser → HA bridge
│   ├── api.py                # FastAPI server + WebSocket (/panel, /ws)
│   ├── ha_bridge.py          # HABridge — 53 tools → HA service calls
│   ├── ha_ws.py              # HA WebSocket client
│   ├── voice.py              # VoicePipeline
│   ├── train_ha.py           # EN SFT
│   ├── train_ha_ru.py        # RU SFT
│   └── generate_ru_dataset.py # RU dataset generator (53 tools)
├── static/                   # Web dashboard (HTML+CSS+JS, no build step)
│   ├── index.html            # Dashboard SPA
│   ├── style.css             # Dark theme, responsive
│   └── app.js                # Dashboard logic + WebSocket
├── data/
│   ├── tools_spec.json       # v1: 12 tools (legacy)
│   ├── tools_spec_v2.json    # v2: 53 tools
│   ├── train_dataset.json    # v1: 658 EN
│   ├── train_dataset_ru.json # v1: 695 RU
│   └── train_dataset_v2.json # v2: 1000 merged
├── models/
│   ├── gpt2_ha_best.pt       # EN FT
│   ├── gpt2_ha_ru_best.pt    # RU+EN FT
│   └── voices/               # Piper voices
├── tests/
│   └── test_router_v2.py     # Router unit tests
├── docs/
│   ├── SPEC.md               # Это ТЗ
│   ├── QUICK_START.md
│   ├── USER_GUIDE.md
│   └── HARDWARE_GUIDE.md
└── requirements.txt
```

## Лог эксперимента

| Что | Результат |
|-----|-----------|
| EN single-tool (12 команд) | 12/12 = 100% |
| RU single-tool (20 команд) | 19/20 = 95% |
| Router v1 (44 команды) | 44/44 = 100% |
| Router v2 (95 команд, 53 интента) | 87/95 = 92% |
| v2 merged dataset | 1000 примеров (658+695+773, dedup) |
| v2 tools | 53 (12 orig + 41 barometech) |