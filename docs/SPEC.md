# Vector Home — Техническое задание

## Суть проекта

Оффлайновый стек управления умным домом на CPU: голос/текст → router → SLM-parser → Home Assistant. Без облака, без GPU, без API-ключей.

## Архитектура

```
Голос/Текст
    │
    ▼
┌─────────┐
│  Router  │  keyword/regex classifier (0 RAM)
│  (12+way)│  intent → tool_name, RU/EN
└────┬─────┘
     │
     ├─ hit ──► GPT-2 124M Full FT (600 MB RAM)
     │          single-tool parser → JSON
     │
     ├─ miss ──► Qwen3:8B (5 GB RAM, Ollama)
     │          multi-intent / ambiguous
     │
     └─ ambiguous ──► clarify (возврат пользователю)

     │
     ▼
┌──────────────────┐      ┌──────────────────┐
│ Home Assistant    │◄────►│ HA WebSocket      │
│ REST API          │      │ (real-time events)│
└──────────────────┘      └──────────────────┘

     ▼
┌──────────────────┐
│ Voice Pipeline    │  STT (Whisper tiny) → TTS (Piper offline / edge-tts)
└──────────────────┘
```

## Компоненты

### 1. Router (intent classifier)
- Keyword/regex матчинг по словарю домена
- ~100 regex правил, RU/EN
- 0 RAM, 0 latency
- Fallback на Qwen3:8B при отсутствии мача
- `_normalize()` для STT артефактов (capitalization, trailing punctuation, -ing)

### 2. Parser (GPT-2 124M Full FT)
- База: gpt2-tool-call (barometech/gpt2-tool-call)
- Full FT под домен умного дома: `gpt2_ha_best.pt`
- RU SFT: `gpt2_ha_ru_best.pt` (mixed EN+RU, RU room/door/scene values)
- Single-tool: 100% accuracy EN, RU pending training
- Инференс: ~2s/команда на CPU
- RAM: ~600 MB
- SFT: 24 мин EN / ~25 мин RU на CPU

### 3. Fallback solver (Qwen3:8B via Ollama)
- Multi-intent команды
- Ambiguous запросы
- Уже развёрнут на localhost:11434

### 4. Home Assistant bridge (REST + WebSocket)
- **REST**: `ha_bridge.py` — HTTP API к HA, entity discovery, dry_run
- **WebSocket**: `ha_ws.py` — real-time state_changed events, auto-reconnect
- Маппинг tool_name → HA service call
- RU→EN маппинг имён комнат/дверей/сцен для entity_id
- Подтверждение действий (опционально)

### 5. HTTP endpoint (FastAPI)
- `POST /command` — текстовая команда → router → parser → HA
- `GET /health` — статус
- `GET /tools` — список инструментов
- `GET /entities` — сущности HA
- `POST /ha/call` — прямой вызов HA
- Порт: 8126 (VH_PORT env), CORS включён
- Dry-run по умолчанию

### 6. Voice Pipeline
- **STT**: faster-whisper tiny (~75 MB, 0.5s load, ~3.5s транскрипция)
- **TTS**: edge-tts (online, Microsoft) или Piper (offline, 61 MB/voice)
  - EN: `en_US-lessac-medium.onnx`
  - RU: `ru_RU-dmitri-medium.onnx`
- Автоопределение языка ответа по кириллице в аргументах
- Полный контур: `voice.py process_voice()` — audio → STT → router → parser → HA → TTS

## Датасет

### EN (train_dataset.json)
- 658 примеров: 628 single-tool + 30 irrelevance
- 12 инструментов: turn_on/off_light, set/query_temperature, lock/unlock_door, play/stop_music, set/cancel_alarm, activate_scene, vacuum_start

### RU (train_dataset_ru.json)
- 695 примеров: 480 RU tool + 25 RU irrelevance + 190 EN stability
- RU значения комнат: гостиная, спальня, кухня, ванная, кабинет, прихожая, гараж, детская, коридор
- RU двери: входная дверь, задняя дверь, гаражная дверь, балконная дверь
- RU сцены: кинотеатр, утро, ночь, вечеринка, романтика, отъезд, фокус
- RU музыка: джаз, рок, поп, классика, лоу-фай
- EN stability set для предотвращения catastrophic forgetting

## Поддерживаемые команды (EN + RU)

| Tool | EN Example | RU Example |
|------|------------|------------|
| turn_on_light | "turn on the lights in the living room" | "включи свет в гостиной" |
| turn_off_light | "turn off garage lights" | "выключи свет на кухне" |
| set_temperature | "set bedroom to 22 degrees" | "установи температуру 22 градуса" |
| query_temperature | "what is the temperature?" | "какая температура в спальне" |
| lock_door | "lock the front door" | "запри входную дверь" |
| unlock_door | "unlock the back door" | "открой замок" |
| play_music | "play jazz in the kitchen" | "включи джаз на кухне" |
| stop_music | "stop music in the bathroom" | "останови музыку" |
| set_alarm | "wake me up at 07:30" | "поставь будильник на 7 утра" |
| cancel_alarm | "cancel the alarm" | "отмени будильник" |
| activate_scene | "activate movie night" | "включи сцену кинотеатр" |
| vacuum_start | "vacuum the office" | "пропылесось кухню" |

## Требования

### Минимальные
- CPU-only (без GPU)
- RAM: ≤1 GB для stack без fallback, ≤6 GB с Qwen3
- Диск: ≤1.5 GB (475 MB модель × 2 + голоса + данные)
- Оффлайн: полная работоспособность без интернета
- Python 3.10+, torch, safetensors

### Целевые
- Latency router: <10ms
- Latency parser: <3s (CPU)
- Accuracy single-tool EN: 100% ✓
- Accuracy single-tool RU: ≥90% (pending)
- RU/EN поддержка ✓

## Этапы

### Phase 0: Foundation ✓
- [x] Клонировать gpt2-tool-call, скачать веса (git lfs pull)
- [x] Сгенерировать EN датасет 658 примеров под HA
- [x] SFT на Full FT checkpoint (24 мин CPU)
- [x] Валидация EN: 12/12 single-tool = 100%

### Phase 1: Router ✓
- [x] Keyword/regex router для 12+ intents (RU/EN, ~100 правил)
- [x] Fallback к Ollama при miss
- [x] Валидация: 44/44 = 100%

### Phase 2: Integration ✓
- [x] HTTP API endpoint (FastAPI, порт 8126)
- [x] Home Assistant REST bridge (ha_bridge.py)
- [x] Home Assistant WebSocket (ha_ws.py)
- [x] RU→EN маппинг в ha_bridge для entity_id
- [ ] Hermes Agent integration (tool/command) — отложено

### Phase 3: Voice ✓
- [x] STT: Whisper tiny (faster-whisper)
- [x] TTS offline: Piper (EN + RU голоса)
- [x] TTS online: edge-tts
- [x] Замкнутый контур: голос → STT → router → parser → HA → TTS → голос
- [x] Автоопределение языка ответа (кириллица → RU)

### Phase 4: RU SFT ✓
- [x] RU датасет: 695 примеров (480 RU + 25 irr + 190 EN stability)
- [x] Обучение gpt2_ha_ru_best.pt — 24.5 мин CPU, loss 0.249→0.002
- [x] Step 100 val: 10.5/12 = 88%, final val: 19/20 = 95%
- [ ] Полная валидация RU pipeline (router→parser→bridge, 12 команд)

### Phase 5: Real HA connection (отложено)
- [ ] Подключение к реальному HA инстансу
- [ ] Тестирование на реальных entity
- [ ] WebSocket подписка на state_changed

## Известные ограничения

1. GPT-2 native context = 1024 токена. PI > 4x ломает качество.
2. Multi-tool без fallback = 8% (architecture limit, не bug).
3. RU из коробки не работает — нужен SFT на русских данных (Phase 4).
4. Multi-step decomposition = невозможно на 124M → fallback обязателен.
5. Ансамбль клонов бесполезен (greedy = identical outputs).

## Файловая структура

```
vector-home/
├── src/
│   ├── router.py          # HomeRouter — keyword/regex, 12+ intents, RU/EN
│   ├── parser.py          # HomeParser — GPT-2 inference (gpt2_ha_best.pt)
│   ├── pipeline.py        # process() — router → parser → HA bridge
│   ├── api.py             # FastAPI server (port 8126)
│   ├── ha_bridge.py       # HABridge — REST + RU→EN entity mapping
│   ├── ha_ws.py           # HAWebSocketClient — real-time events
│   ├── voice.py           # VoicePipeline — STT → router → parser → HA → TTS
│   ├── train_ha.py        # EN SFT training script
│   ├── train_ha_ru.py     # RU SFT training script (starts from EN FT)
│   └── generate_ru_dataset.py  # RU dataset generator
├── data/
│   ├── train_dataset.json       # 658 EN examples
│   ├── train_dataset_ru.json    # 695 RU+EN examples
│   └── tools_spec.json          # 12 tool definitions
├── models/
│   ├── gpt2_ha_best.pt          # EN Full FT (step 100 → 100%)
│   ├── gpt2_ha_final.pt         # EN final (overfitted, 92%)
│   ├── gpt2_ha_ru_best.pt       # RU+EN Full FT (pending)
│   └── voices/
│       ├── en_US-lessac-medium.onnx   # Piper EN voice (61MB)
│       ├── en_US-lessac-medium.onnx.json
│       ├── ru_RU-dmitri-medium.onnx    # Piper RU voice (61MB)
│       └── ru_RU-dmitri-medium.onnx.json
├── docs/
│   ├── SPEC.md              # Техническое задание
│   ├── DEVELOPMENT_LOG.md   # Хроника разработки
│   ├── USER_GUIDE.md        # Руководство по эксплуатации (техническое)
│   ├── QUICK_START.md       # Быстрый старт для всех
│   └── HARDWARE_GUIDE.md    # Оборудование и настройка
└── requirements.txt
```

## Ссылки

- Репо: https://github.com/barometech/gpt2-tool-call
- BFCL v4 бенчмарк
- Архитектура адаптера: L6 bottleneck 768→192→96→768, W_steer initialized zeros
- Full FT: 124M params, 475 MB, AdamW lr=1e-5, 1 epoch, 68 min CPU
- Adapter: 250K params, 1 MB, 1.5h CPU

## Лог эксперимента

| Что | Результат |
|-----|-----------|
| EN single-tool (12 команд) | 12/12 = 100% |
| EN all-tools (12 в одном prompt) | 1/12 = 8% (expected) |
| EN SFT время | 24 мин CPU (500 примеров) |
| EN инференс | ~2s/команда CPU |
| Router 44 команды | 44/44 = 100% |
| Router RU regex fix | `\b` → `.{0,5}` для кириллицы |
| Voice pipeline (STT+TTS) | ~7.5s end-to-end |
| Piper RU голос | 61 MB, offline, WAV output |
| HA WebSocket | auth + subscribe + reconnect |
| RU SFT (695 примеров) | 24.5 мин CPU, loss 0.249→0.002 |
| RU val step 100 | 10.5/12 = 88% |
| RU val final | 19/20 = 95% |