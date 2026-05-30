# Vector Home v2 — Техническое задание (полная спецификация)

> **Версия:** 2.0.0  
> **Дата:** 2026-05-16  
> **Статус:** Все фазы 0–6 завершены ✅

---

## 1. Суть проекта

**Vector Home v2** — оффлайновый стек управления умным домом на CPU.  
Конвейер: **голос/текст → Router → Parser → HA Bridge → Home Assistant**.

Без облака · Без GPU · Без API-ключей

**Ключевые метрики v2:**

| Метрика | Значение |
|---------|----------|
| Инструментов | 52 (+ `none`) |
|Router правила | 95 |
| Router точность | **95/95 = 100%** EN+RU |
| Тестов pytest | **130 ✓** |
| Языки | EN + RU (нативно) |
| Порог \b для кириллицы | ✅ Исправлен |
| HA маппингов | 53 tool → HA service call |

---

## 2. Архитектура

```
Голос / Текст  ──►  Web Dashboard (/panel)
       │                   │
       ▼                   ▼
┌──────────────────────────────────────┐
│            Router v2                │
│  95 regex правил, 0 RAM, <1 ms      │
│  100% EN+RU, fallback → Qwen3:8B   │
└──────────┬───────────────────────────┘
           │ hit
           ▼
┌──────────────────┐
│  Parser v2       │  GPT-2 124M (smart_home_v2.pt)
│  Single-tool     │  Fuzzy match, 53-tool spec
│  ~2 s/команда    │  1024 токена контекст
└──────────┬───────┘
           │ JSON {name, arguments}
           ▼
┌──────────────────┐
│  HA Bridge v2     │  53 tool → HA mapping
│  RU → EN маппинг │  комнаты/двери/сцены/AC режимы
│  REST + WebSocket │  entity discovery
└──────────┬───────┘
           │
           ▼
    Home Assistant
    (REST API /api/services)

           │
           ▼
┌──────────────────┐
│  API v2           │  FastAPI + WebSocket
│  POST /command    │  GET /panel, /history, /tools
│  WS  /ws          │  real-time push
└──────────────────┘

           │
           ▼
┌──────────────────────────────────────┐
│  Voice Pipeline                      │
│  STT (faster-whisper) → Router →     │
│  Parser → HA → TTS (Piper/edge-tts) │
└──────────────────────────────────────┘
```

---

## 3. Компоненты

### 3.1 Router v2 — классификатор интентов

**Файл:** `src/router.py`  
**Класс:** `HomeRouter`

| Параметр | Значение |
|----------|----------|
| Тип | Keyword/regex (re.IGNORECASE) |
| Правила | **95** raw rules в `_ROUTER_RULES_RAW` |
| Интенты | 53 (52 инструмента + `none`) |
| Языки | EN + RU, нативно |
| RAM | 0 (чистый regex) |
| Latency | < 1 ms / команда |
| Точность | **95/95 = 100%** (TEST_CASES) |
| Fallback | Qwen3:8B через Ollama (`localhost:11434`) |

**Критические решения:**

1. **Порядок правил (ORDER MATTERS):** Специфичные шаблоны расположены раньше общих. Блоки приоритета:
   - Block 1: query_light, set_light_temperature_k, dim_light, blink_light, set_light_color, set_light_scene (ambiguous patterns)
   - Block 2: TV (перед generic turn_on/off)
   - Block 3: Radio (перед play_music)
   - Block 4: Pause (перед stop_music), Mute (перед set_volume)
   - Block 5: Cancel_alarm (перед Disarm_alarm_system)
   - Block 6: Set_alarm (перед generic «set»)
   - Block 7: Blinds angle (перед set_temperature — «degrees»)
   - Block 9: Outlet (перед generic turn_on/off)
   - Block 10: Humidifier/Dehumidifier (перед generic turn_on/off)

2. **`\b` НЕ используется для кириллицы** — Python regex `re.IGNORECASE` некорректно обрабатывает `\b` для Unicode-символов (кириллица). Все RU-паттерны используют bare text без `\b`. EN-подстроки вроде `irrigat` тоже без `\b`.

3. **Fallback на Ollama:** При промахе всех regex правил (результат `none`, `confident=False`) вызывается `route_with_fallback()` → POST `/v1/chat/completions` к Qwen3:8B. Модель получает список всех 53 интентов и возвращает один.

**Метод:**
```python
route(utterance: str) -> Tuple[str, bool]
# Returns: (tool_name, confident)
# "none"/False → no match
```

**Нормализация:**
- lower().strip()
- Удаление конечных `.!?`
- Замена `'s ` → ` is `

---

### 3.2 Parser v2 — GPT-2 124M

**Файл:** `src/parser.py`  
**Класс:** `HomeParser`

| Параметр | Значение |
|----------|----------|
| Модель | GPT-2 124M (gpt2-tool-call) |
| Веса | `models/smart_home_v2.pt` (fallback: `gpt2_ha_best.pt`) |
| Контекст | **1024 токена** |
| Max генерация | 80 токенов |
| Тип инференса | Single-tool (router предвыбирает инструмент) |
| Fuzzy match | 15 алиасов (turn_on_lights → turn_on_light и т.д.) |
| Validation | Аргументы фильтруются по spec инструмента |
| Latency CPU | ~2 s/команда |
| RAM | ~600 MB |

**Конфигурация:**
- Файл спеки инструментов: `data/tools_spec_v2.json` (53 инструмента)
- Prompt format: `SYSTEM: You are a helpful assistant...\n<spec>\n\nUSER: <utterance>\n\nASSISTANT: <functioncall> `
- Генерация: greedy decoding (argmax), остановка по `}`
- Переопределение имени инструмента: router name имеет приоритет над GPT-2 output

**Fuzzy match (FUZZY_TOOLS_MAP):**
```python
"start_vacuum_cleaner" → "vacuum_start"
"turn_on_lights"       → "turn_on_light"
"set_thermostat_mode"  → "set_thermostat"
"set_ac_temperature"   → "set_ac_mode"
"turn_on_music"        → "play_music"
...
```
Также работает prefix match: `turn_on_ligh` → `turn_on_light`.

---

### 3.3 HA Bridge v2 — маппинг на Home Assistant

**Файл:** `src/ha_bridge.py`  
**Класс:** `HABridge`

#### 3.3.1 Маппинги

**`HA_ENTITY_MAP`** — 53 записи: tool_name → (HA_domain, entity_template)

```python
"turn_on_light"     → ("light",    "light.{room}")
"set_temperature"    → ("climate",  "climate.{room}")
"open_curtains"      → ("cover",    "cover.{room}_curtains")
"lock_door"          → ("lock",     "lock.{door}")
"play_music"         → ("media_player", "media_player.{room}")
"start_irrigation_zone" → ("switch", "switch.irrigation_zone_{zone}")
...
```

**`HA_SERVICE_MAP`** — 53 записи: tool_name → (domain, service, service_data_template)

```python
"turn_on_light"          → ("light", "turn_on", {})
"set_temperature"        → ("climate", "set_temperature", {"temperature": "{temperature_c}"})
"set_ac_mode"            → ("climate", "set_hvac_mode", {"hvac_mode": "{mode}"})
"set_blinds_position"    → ("cover", "set_cover_position", {"position": "{position}"})
"play_radio_station"     → ("media_player", "play_media",
                             {"media_content_id": "{station}", "media_content_type": "music"})
...
```

**Query-инструменты** (возвращают состояние, не вызывают сервис):
```python
QUERY_TOOLS = {
    "query_temperature", "query_light_state", "query_humidity",
    "query_door_status", "query_alarm_status", "query_soil_moisture",
    "query_air_quality",
}
```

#### 3.3.2 RU → EN маппинг

**Комнаты** (`RU_ROOM_MAP`, 14 записей):
```python
"гостиная" → "living_room"    "спальня" → "bedroom"
"кухня"    → "kitchen"         "ванная"  → "bathroom"
"кабинет"  → "office"          "прихожая" → "hallway"
"гараж"    → "garage"          "детская"  → "nursery"
"коридор"  → "hall"            "подвал"  → "basement"
"чердак"   → "attic"           "столовая" → "dining_room"
"гостевая" → "guest_room"      "кладовая" → "storage"
```

**Двери** (`RU_DOOR_MAP`, 5 записей):
```python
"входная"  → "front_door"      "задняя"    → "back_door"
"гаражная" → "garage_door"     "балконная"  → "balcony_door"
"подвальная" → "basement_door"
```

**Сцены** (`RU_SCENE_MAP`, 16 записей):
```python
"кино" → "movie"     "ночь" → "night"     "утро" → "morning"
"вечеринка" → "party" "романтик" → "romantic"
"фокус" → "focus"     "отпуск" → "away"
...
```

**AC режимы** (`RU_AC_MODE_MAP`, 14 записей):
```python
"охлаждение" → "cool"   "обогрев" → "heat"   "авто" → "auto"
"сушка" → "dry"         "вентиляция" → "fan_only"
...
```

#### 3.3.3 Entity discovery

Метод `list_entities(domain=None)` — GET `/api/states` async через httpx.

#### 3.3.4 Dry run mode

При отсутствии `HA_TOKEN` или `dry_run=True` — возвращает лог вызова без реального обращения к HA.

---

### 3.4 API v2 — FastAPI + WebSocket

**Файл:** `src/api.py`  
**Порт:** 8126 (env `VH_PORT`)

#### Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/command` | Текстовая команда → router → parser → HA |
| `GET` | `/health` | Статус системы (router, parser, HA bridge) |
| `GET` | `/tools` | Список 53 инструментов с описаниями |
| `GET` | `/entities?domain=` | Сущности HA (опционально по домену) |
| `POST` | `/ha/call` | Прямой вызов HA service |
| `GET` | `/history?limit=20` | История последних команд (in-memory, max 100) |
| `WS` | `/ws` | WebSocket: real-time push + приём команд |
| `GET` | `/panel` | Web Dashboard (serves static/index.html) |

#### Data models

```python
class CommandRequest(BaseModel):
    text: str
    live: bool = False   # True → реальный HA вызов

class CommandResponse(BaseModel):
    tool: str
    arguments: dict
    ha_service: Optional[dict] = None
    latency_s: float = 0
    used_fallback: bool = False
    ha_result: Optional[dict] = None
```

#### WebSocket протокол

- **Init:** При подключении отправляется `{"type": "init", "tools_count": 53, "history": [...]}`
- **Command:** Клиент отправляет `/command <text>` → сервер возвращает результат
- **Broadcast:** При POST `/command` результат пушится всем WebSocket-клиентам
- **Ping/Pong:** Клиент шлёт `ping` → сервер отвечает `{"type": "pong"}`

---

### 3.5 Web Dashboard

**Директория:** `static/` (раздаётся через FastAPI `/static` и `/panel`)

Файлы:
- `index.html` — SPA с 8 группами устройств
- `style.css` — Тёмная тема, адаптивная верстка
- `app.js` — WebSocket + голосовой ввод (Web Speech API)

#### Группы устройств (8)

| # | Группа | Иконка | Инструменты |
|---|--------|--------|-------------|
| 1 | Свет | 💡 | turn_on_light, turn_off_light, dim_light, blink_light, set_light_color, set_light_scene, set_light_temperature_k, query_light_state |
| 2 | Климат | 🌡️ | set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, set_humidity_target, toggle_humidifier, toggle_dehumidifier, query_humidity |
| 3 | Шторы/жалюзи | 🪟 | open_curtains, close_curtains, raise_blinds, lower_blinds, set_blinds_position, set_blinds_angle |
| 4 | Пылесос | 🤖 | vacuum_start, stop_vacuum, dock_vacuum |
| 5 | Безопасность | 🔒 | lock_door, unlock_door, query_door_status, arm_alarm_system, disarm_alarm_system, query_alarm_status, trigger_panic_alarm |
| 6 | Медиа | 🎵 | play_music, stop_music, pause_music, play_radio_station, set_volume, mute_audio, turn_on_tv, turn_off_tv, set_tv_channel, set_tv_volume |
| 7 | Сад | 🌿 | start_irrigation_zone, stop_irrigation_zone, query_soil_moisture |
| 8 | Другое | ⚡ | set_alarm, cancel_alarm, activate_scene, toggle_outlet, query_air_quality, set_motion_sensitivity |

#### Функции Dashboard

- **Командная строка**: текстовый ввод + кнопка отправки
- **Голосовой ввод**: 🎤 кнопка, Web Speech API (browser native)
- **История команд**: список результатов (scrollable, clearable)
- **Статусы**: WebSocket подключение (dot green/red), HA подключение (dot green/red)
- **Real-time**: WebSocket push новых результатов
- **Dark theme**: CSS variables, адаптивная верстка (mobile-first)

---

### 3.6 Voice Pipeline

**Файл:** `src/voice.py`  
**Класс:** `VoicePipeline`

| Компонент | Реализация |
|-----------|-----------|
| STT | faster-whisper (tiny/base/medium) |
| TTS | Piper (offline, ~20MB/voice) или edge-tts (online) |
| Языки | EN + RU (автоопределение по кириллице в аргументах) |

**Контур:** Audio → STT → text → Router → Parser → HA → format_response → TTS → audio

---

### 3.7 Pipeline

**Файл:** `src/pipeline.py`  
**Функция:** `process(utterance, router, parser, ha, verbose=True)`

```
1. Router.route(utterance) → (tool_name, confident)
2. При miss → Router.route_with_fallback(utterance) → Ollama Qwen3:8B
3. Parser.parse(utterance, tool_name) → {name, arguments, _latency_s}
4. HABridge.build_service_call(tool_name, arguments) → HA service call
5. call_ha_sync(tool_name, arguments) → HA REST API (при non-dry-run)
```

---

## 4. 52 инструмента по 8 доменам

| Домен | Кол-во | Инструменты |
|-------|--------|-------------|
| 💡 Свет | 8 | turn_on_light, turn_off_light, dim_light, blink_light, set_light_color, set_light_scene, set_light_temperature_k, query_light_state |
| 🌡️ Климат | 9 | set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, set_humidity_target, toggle_humidifier, toggle_dehumidifier, query_humidity |
| 🪟 Шторы/жалюзи | 6 | open_curtains, close_curtains, raise_blinds, lower_blinds, set_blinds_position, set_blinds_angle |
| 🤖 Пылесос | 3 | vacuum_start, stop_vacuum, dock_vacuum |
| 🔒 Безопасность | 7 | lock_door, unlock_door, query_door_status, arm_alarm_system, disarm_alarm_system, query_alarm_status, trigger_panic_alarm |
| 🎵 Медиа | 10 | play_music, stop_music, pause_music, play_radio_station, set_volume, mute_audio, turn_on_tv, turn_off_tv, set_tv_channel, set_tv_volume |
| 🌿 Сад | 3 | start_irrigation_zone, stop_irrigation_zone, query_soil_moisture |
| 📡 Другое | 6 | set_alarm, cancel_alarm, activate_scene, toggle_outlet, query_air_quality, set_motion_sensitivity |

**Итого: 52 инструмента + `none` (нерознанное) = 53 интента в Router**

---

## 5. Датасет v2

### 5.1 tools_spec_v2.json

- **53 определения** инструментов с типами параметров
- Формат: `{name, description, parameters: {param_name: {type, description}}}`
- Версия: `_version: "2.0"`

### 5.2 train_dataset_v2.json

- **1000 примеров** (merged + dedup)
- Источники: 658 EN (оригинал) + 695 RU (оригинал) + 773 barometech (отфильтрованные)
- Формат: single-tool prompt → JSON

### 5.3 test_dataset_v2.json

- Разделение для валидации модели parser'а

---

## 6. Этапы (фазы 0–6 — все завершены ✅)

| Фаза | Описание | Статус |
|------|----------|--------|
| 0 | **Foundation** — клонирование gpt2-tool-call, EN SFT, 12/12=100% | ✅ |
| 1 | **Router v2** — 95 regex rules, 100% EN/RU, \b fix для кириллицы | ✅ |
| 2 | **Integration** — FastAPI API, HA Bridge, WebSocket, RU→EN маппинг | ✅ |
| 3 | **Voice** — STT (faster-whisper) + TTS (Piper/edge-tts), замкнутый контур | ✅ |
| 4 | **Web Dashboard** — 8 групп устройств, голосовой ввод, тёмная тема, WebSocket | ✅ |
| 5 | **RU SFT + v2 Merge** — RU датасет 695 примеров, merged 1000 примеров, 53 инструмента | ✅ |
| 6 | **v2 Release** — Router v2 95/95=100%, Parser v2 (smart_home_v2.pt), 130 pytest | ✅ |

---

## 7. Экспериментальный лог

| Что | Результат |
|-----|-----------|
| EN single-tool (12 команд) | 12/12 = **100%** |
| RU single-tool (20 команд) | 19/20 = 95% |
| Router v1 (44 команды) | 44/44 = **100%** |
| **Router v2 (95 команд, 53 интента)** | **95/95 = 100%** |
| v2 merged dataset | 1000 примеров (658+695+773, dedup) |
| v2 tools | 53 (12 orig + 41 barometech) |
| **pytest (router + bridge + regressions)** | **130/130 ✓** |
| Cyrillic `\b` regression | ✅ Исправлен (все RU-паттерны без `\b`) |
| Rule ordering (query→set, dim→off, thermostat→AC) | ✅ Все корректны |

---

## 8. Известные ограничения

1. **`\b` для кириллицы** — ✅ **Исправлено** в v2. Все RU-паттерны используют bare text без `\b`. EN-подстроки типа `irrigat` тоже без `\b`.

2. **53 инструмента — потолок для regex router** — Дальнейшее расширение количества интентов потребует перехода на fallback (Qwen3:8B) как основной классификатор, т.к. regex-правила становятся неуправляемыми при >60 интентах.

3. **GPT-2 context = 1024 токена** — Prompt с более чем ~4 инструментами одновременно переполняет контекст. Single-tool routing (через Router) — единственный надёжный режим. Multi-tool без fallback даёт ~8% точности.

4. **Оффлайн-only при CPU** — Ollama fallback (Qwen3:8B) требует ~5 GB RAM и GPU/долгий CPU вывод. Без Ollama недоступен multi-intent fallback.

5. **HA_entity_map использует шаблоны** — Entity ID вида `light.{room}` требуют точного совпадения комнаты с HA entity. При несовпадении — dry run вернёт шаблон без реального вызова.

6. **In-memory history** — Командная история хранится в RAM (max 100 записей), при перезапуске API теряется.

---

## 9. Файловая структура v2

```
vector-home/
├── src/
│   ├── router.py                # HomeRouter v2 — 95 rules, 53 intents, EN+RU
│   ├── parser.py                # HomeParser — GPT-2 124M, fuzzy match, 53-tool spec
│   ├── pipeline.py              # process() — router → parser → HA bridge
│   ├── api.py                   # FastAPI + WebSocket + /panel + /history
│   ├── ha_bridge.py             # HABridge — 53 mappings, RU→EN (rooms/doors/scenes/AC modes)
│   └── voice.py                 # VoicePipeline — STT → pipeline → TTS
├── static/
│   ├── index.html               # Web Dashboard — 8 device groups, voice input
│   ├── style.css                # Dark theme, responsive
│   └── app.js                   # WebSocket real-time + voice input (Web Speech API)
├── data/
│   ├── tools_spec_v2.json       # 53 tool definitions
│   ├── train_dataset_v2.json    # 1000 merged training examples
│   └── test_dataset_v2.json     # Test split
├── models/
│   ├── smart_home_v2.pt          # GPT-2 v2 weights (barometech merged)
│   ├── gpt2_ha_best.pt           # GPT-2 v1 EN FT weights
│   ├── gpt2_ha_ru_best.pt        # GPT-2 v1 RU+EN FT weights
│   └── voices/                    # Piper voice models
├── tests/
│   └── test_router.py            # 130 pytest tests (routing, regressions, bridge)
├── docs/
│   ├── SPEC.md                   # Это ТЗ (ru)
│   └── HARDWARE_GUIDE.md
├── assets/
│   └── logo-original.png
├── requirements.txt
└── README.md
```

---

## 10. Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|---------------|
| `HA_URL` | URL Home Assistant | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | (пусто = dry run) |
| `VH_PORT` | Порт API сервера | `8126` |
| `GPT2_REPO` | Путь к gpt2-tool-call | `../gpt2-tool-call` |

### Зависимости

**Минимальные (CPU-only):**
```
torch (CPU)
fastapi
uvicorn
httpx
pydantic
```

**Опциональные:**
```
faster-whisper    # голосовой ввод
edge-tts          # TTS (online)
piper-tts         # TTS (offline)
ollama            # fallback классификатор (Qwen3:8B)
```

### Системные требования

| | Минимум | Рекомендуется |
|---|---------|---------------|
| CPU | Любой x86_64 | 4+ ядра |
| RAM | 600 MB (только parser) | 6 GB (с Qwen3 fallback) |
| Диск | 1.5 GB | 2 GB |
| GPU | Не требуется | — |
| Python | 3.10+ | 3.12 |
| Интернет | Не требуется | Для Ollama fallback |

---

## 11. Быстрый старт

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt

# Тесты (130/130 ✓)
python -m pytest tests/ -v

# API сервер (порт 8126) + web dashboard
python -m src.api

# CLI текстовая команда
python -m src.pipeline "turn on the lights in the living room"
python -m src.pipeline "включи свет в гостиной"

# Голос (требуется faster-whisper)
python -m src.voice --interactive

# Live Home Assistant
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_token"
python -m src.api --live
```

---

## 12. Тестирование

```bash
python -m pytest tests/test_router.py -v
```

**Покрытие:**

| Категория | Кол-во тестов | Описание |
|-----------|---------------|---------|
| TEST_CASES parametrize | 95 | Все 95 router test cases |
| Cyrillic `\b` regression | 8 | RU паттерны без `\b` boundary |
| Rule ordering | ≥ 10 | Приоритет специфичных правил перед общими |
| HA bridge mappings | ≥ 10 | 53 tool → HA service call |
| Parser spec validation | ≥ 7 | tools_spec_v2 load + fuzzy match |
| **Итого** | **130** | |

---

## 13. Отличия от barometech/smart-home-gpt2

| | Vector Home v2 | smart-home-gpt2 |
|---|---|---|
| Router | Regex+fallback, 100% EN/RU | GPT-2 124M, multi-tool 71.7% |
| Parser | GPT-2 124M, single-tool | GPT-2 124M, multi-tool |
| Инструментов | 52 (+none=53 intents) | 100 |
| Голос | faster-whisper medium | faster-whisper medium |
| Dashboard | ✅ (WebSocket, dark theme) | ❌ |
| HA integration | ✅ (53 mapping, RU→EN) | Эмулятор только |
| Тесты | 130 pytest | — |
| Русский язык | ✅ нативно | ✅ через translate |
| `\b` bug | ✅ Исправлен | — |

---

## 14. HA Service Call Mapping (подробно)

### 💡 Свет (8 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| turn_on_light | light | turn_on | light.{room} | — |
| turn_off_light | light | turn_off | light.{room} | — |
| dim_light | light | turn_on | light.{room} | brightness_pct={brightness} |
| blink_light | light | turn_on | light.{room} | flash=short |
| set_light_color | light | turn_on | light.{room} | color_name={color} |
| set_light_scene | scene | turn_on | scene.{scene} | — |
| set_light_temperature_k | light | turn_on | light.{room} | kelvin={temperature} |
| query_light_state | sensor | — | sensor.{room}_light | (query) |

### 🌡️ Климат (9 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| set_temperature | climate | set_temperature | climate.{room} | temperature={temperature_c} |
| query_temperature | sensor | — | sensor.{room}_temperature | (query) |
| set_thermostat | climate | set_hvac_mode | climate.{room} | hvac_mode={mode} |
| set_ac_mode | climate | set_hvac_mode | climate.{room}_ac | hvac_mode={mode} |
| set_fan_speed | fan | set_percentage | fan.{room} | percentage={speed_pct} |
| set_humidity_target | humidifier | set_humidity | humidifier.{room} | humidity={humidity_pct} |
| toggle_humidifier | humidifier | toggle | humidifier.{room} | — |
| toggle_dehumidifier | humidifier | toggle | dehumidifier.{room} | — |
| query_humidity | sensor | — | sensor.{room}_humidity | (query) |

### 🪟 Шторы/жалюзи (6 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| open_curtains | cover | open_cover | cover.{room}_curtains | — |
| close_curtains | cover | close_cover | cover.{room}_curtains | — |
| raise_blinds | cover | open_cover | cover.{room}_blinds | — |
| lower_blinds | cover | close_cover | cover.{room}_blinds | — |
| set_blinds_position | cover | set_cover_position | cover.{room}_blinds | position={position} |
| set_blinds_angle | cover | set_cover_tilt_position | cover.{room}_blinds | tilt_position={angle} |

### 🤖 Пылесос (3 инструмента)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| vacuum_start | vacuum | start | vacuum.robot | — |
| stop_vacuum | vacuum | stop | vacuum.robot | — |
| dock_vacuum | vacuum | return_to_base | vacuum.robot | — |

### 🔒 Безопасность (7 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| lock_door | lock | lock | lock.{door} | — |
| unlock_door | lock | unlock | lock.{door} | — |
| query_door_status | sensor | — | sensor.{door}_lock_status | (query) |
| arm_alarm_system | alarm_control_panel | alarm_arm_away | alarm_control_panel.home | code={code} |
| disarm_alarm_system | alarm_control_panel | alarm_disarm | alarm_control_panel.home | code={code} |
| query_alarm_status | sensor | — | sensor.alarm_status | (query) |
| trigger_panic_alarm | alarm_control_panel | alarm_trigger | alarm_control_panel.home | — |

### 🎵 Медиа (10 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| play_music | media_player | media_play | media_player.{room} | — |
| stop_music | media_player | media_stop | media_player.{room} | — |
| pause_music | media_player | media_pause | media_player.{room} | — |
| play_radio_station | media_player | play_media | media_player.{room} | content_id={station}, type=music |
| set_volume | media_player | volume_set | media_player.{room} | volume_level={volume_pct} |
| mute_audio | media_player | volume_mute | media_player.{room} | is_volume_muted=true |
| turn_on_tv | media_player | turn_on | media_player.{room}_tv | — |
| turn_off_tv | media_player | turn_off | media_player.{room}_tv | — |
| set_tv_channel | media_player | play_media | media_player.{room}_tv | content_id=channel_{channel_number} |
| set_tv_volume | media_player | volume_set | media_player.{room}_tv | volume_level={volume_pct} |

### 🌿 Сад (3 инструмента)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| start_irrigation_zone | switch | turn_on | switch.irrigation_zone_{zone} | — |
| stop_irrigation_zone | switch | turn_off | switch.irrigation_zone_{zone} | — |
| query_soil_moisture | sensor | — | sensor.soil_moisture_zone_{zone} | (query) |

### 📡 Другое (6 инструментов)

| Tool | HA Domain | HA Service | Entity Template | Service Data |
|------|-----------|------------|-----------------|--------------|
| set_alarm | input_datetime | set_datetime | input_datetime.alarm | time={time} |
| cancel_alarm | input_boolean | turn_off | input_boolean.alarm | — |
| activate_scene | scene | turn_on | scene.{scene} | — |
| toggle_outlet | switch | toggle | switch.{room}_outlet | — |
| query_air_quality | sensor | — | sensor.{room}_air_quality | (query) |
| set_motion_sensitivity | number | set_value | number.{room}_motion_sensitivity | value={level} |

---

## 15. RU → EN маппинги (полный список)

### Комнаты (14)

| RU | EN |
|----|-----|
| гостиная | living_room |
| спальня | bedroom |
| кухня | kitchen |
| ванная | bathroom |
| кабинет | office |
| прихожая | hallway |
| гараж | garage |
| детская | nursery |
| коридор | hall |
| подвал | basement |
| чердак | attic |
| столовая | dining_room |
| гостевая | guest_room |
| кладовая | storage |

### Двери (5)

| RU | EN |
|----|-----|
| входная | front_door |
| задняя | back_door |
| гаражная | garage_door |
| балконная | balcony_door |
| подвальная | basement_door |

### Сцены (16)

| RU | EN |
|----|-----|
| кино / кинотеатр | movie |
| ночь / ночи / ночной | night |
| утро / утра / утренний | morning |
| вечеринка / пати | party |
| романтик / романтический | romantic |
| фокус / рабочий | focus |
| отпуск / отсутствие | away |
| гость | guest |

### AC режимы (14)

| RU | EN |
|----|-----|
| охлаждение / охлажд / холод | cool |
| обогрев / обогр / тепло / гре / нагрев | heat |
| авто / автоматический | auto |
| сушка / сух / осушение | dry |
| вентиляция / вентил / проветривание | fan_only |

---

## 16. Router v2 — полная таблица приоритетов

### Блок 1: Конфликтующие интенты (query перед set, dim перед off и т.д.)

| # | Приоритет | Интент | EN пример | RU пример |
|---|-----------|--------|-----------|-----------|
| 1 | query→set | query_light_state | is the light on? | включен ли свет? |
| 2 | temp_k→color | set_light_temperature_k | warm white in bedroom | тёплый свет |
| 3 | dim→off | dim_light | dim the lights | приглуши свет |
| 4 | blink→on | blink_light | blink the lights | мигни светом |
| 5 | color→scene | set_light_color | make the lights blue | сделай свет синий |
| 6 | scene→general | set_light_scene | activate mood lighting | включи сцену кино |

### Блок 2: TV перед generic light on/off

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 7 | turn_on_tv | turn on the tv | включи телевизор |
| 8 | turn_off_tv | turn off the tv | выключи телевизор |
| 9 | set_tv_channel | switch channel on tv | переключи канал |
| 10 | set_tv_volume | set tv volume to 30 | громкость телевизора |

### Блок 3: Radio перед play_music

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 11 | play_radio_station | play radio jazz fm | включи радио |

### Блок 4: Pause перед stop, Mute перед volume

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 12 | pause_music | pause the music | пауза музыки |
| 13 | mute_audio | mute the audio | выключи звук |

### Блок 5: Cancel_alarm перед Disarm

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 14 | cancel_alarm | cancel the alarm | отмени будильник |

### Блок 6: Set_alarm перед generic set

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 15 | set_alarm | wake me up at 07:30 | поставь будильник на 7 утра |

### Блок 7: Blinds angle перед temperature (degrees)

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 16 | set_blinds_angle | tilt the blinds to 45 degrees | наклон жалюзи 45° |
| 17 | set_blinds_position | set blinds to 50% | жалюзи на 50% |

### Блок 9: Outlet перед generic turn on/off

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 18 | toggle_outlet | toggle the outlet | включи розетку |

### Блок 10: Humidifier перед generic

| # | Интент | EN пример | RU пример |
|---|--------|-----------|-----------|
| 19 | toggle_humidifier | turn on the humidifier | включи увлажнитель |
| 20 | toggle_dehumidifier | turn on the dehumidifier | включи осушитель |

### Общие интенты (после всех приоритетных блоков)

Остальные 73 правила покрывают: turn_on/off_light, set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, query/set_humidity, covers, vacuum, security, music, volume, irrigation, sensors, scenes, alarms.

---

## 17. Тест-кейсы Router (95 примеров)

### 💡 Свет (21)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 1 | turn on the lights in the living room | turn_on_light |
| 2 | turn off garage lights | turn_off_light |
| 3 | light up the bedroom | turn_on_light |
| 4 | switch off the bedroom light | turn_off_light |
| 5 | включи свет в гостиной | turn_on_light |
| 6 | выключи свет на кухне | turn_off_light |
| 7 | погаси свет в ванной | turn_off_light |
| 8 | dim the lights in the bedroom | dim_light |
| 9 | dim light to 30% | dim_light |
| 10 | приглуши свет в спальне | dim_light |
| 11 | blink the lights | blink_light |
| 12 | flash the bedroom light | blink_light |
| 13 | set the light color to red in the kitchen | set_light_color |
| 14 | make the lights blue | set_light_color |
| 15 | сделай свет синий на кухне | set_light_color |
| 16 | set the light scene to movie | set_light_scene |
| 17 | activate mood lighting | set_light_scene |
| 18 | set light color temperature to 4000 kelvin | set_light_temperature_k |
| 19 | warm white in the bedroom | set_light_temperature_k |
| 20 | is the light on in the kitchen? | query_light_state |
| 21 | включен ли свет в спальне | query_light_state |

### 🌡️ Климат (18)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 22 | set the bedroom to 22 degrees | set_temperature |
| 23 | what is the temperature in the bedroom? | query_temperature |
| 24 | how warm is it in the living room | query_temperature |
| 25 | make it 20 celsius in the office | set_temperature |
| 26 | какая температура в спальне | query_temperature |
| 27 | установи температуру 22 градуса в гостиной | set_temperature |
| 28 | set the thermostat to 72 and heat mode | set_thermostat |
| 29 | термостат на охлаждение 20 градусов | set_thermostat |
| 30 | set AC to cool mode | set_ac_mode |
| 31 | кондиционер режим охлаждения | set_ac_mode |
| 32 | set the fan speed to high | set_fan_speed |
| 33 | increase fan speed in the bedroom | set_fan_speed |
| 34 | set humidity target to 50 percent | set_humidity_target |
| 35 | what's the humidity in the bedroom? | query_humidity |
| 36 | какая влажность на кухне | query_humidity |
| 37 | turn on the humidifier | toggle_humidifier |
| 38 | включи увлажнитель | toggle_humidifier |
| 39 | turn on the dehumidifier | toggle_dehumidifier |

### 🪟 Шторы/жалюзи (9)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 40 | open the curtains in the bedroom | open_curtains |
| 41 | close the curtains | close_curtains |
| 42 | открой шторы в гостиной | open_curtains |
| 43 | закрой шторы | close_curtains |
| 44 | raise the blinds | raise_blinds |
| 45 | lower the blinds in the kitchen | lower_blinds |
| 46 | опусти жалюзи | lower_blinds |
| 47 | set blinds position to 50% | set_blinds_position |
| 48 | tilt the blinds to 45 degrees | set_blinds_angle |

### 🤖 Пылесос (6)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 49 | vacuum the office | vacuum_start |
| 50 | start the robot vacuum | vacuum_start |
| 51 | пропылесось кухню | vacuum_start |
| 52 | stop the vacuum | stop_vacuum |
| 53 | dock the vacuum | dock_vacuum |
| 54 | пылесос на базу | dock_vacuum |

### 🔒 Безопасность (10)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 55 | lock the front door | lock_door |
| 56 | unlock the back door | unlock_door |
| 57 | запри входную дверь | lock_door |
| 58 | is the front door locked? | query_door_status |
| 59 | arm the alarm system | arm_alarm_system |
| 60 | поставь сигнализацию | arm_alarm_system |
| 61 | disarm the alarm | disarm_alarm_system |
| 62 | cancel the 06:00 alarm | cancel_alarm |
| 63 | what's the alarm status? | query_alarm_status |
| 64 | panic alarm! | trigger_panic_alarm |

### 🎵 Медиа (12)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 65 | play jazz playlist in the kitchen | play_music |
| 66 | stop music in the bathroom | stop_music |
| 67 | pause the music | pause_music |
| 68 | play radio station jazz fm | play_radio_station |
| 69 | set volume to 50% | set_volume |
| 70 | mute the audio | mute_audio |
| 71 | turn on the tv in the living room | turn_on_tv |
| 72 | turn off the tv | turn_off_tv |
| 73 | set tv channel to 5 | set_tv_channel |
| 74 | set tv volume to 30 | set_tv_volume |
| 75 | включи музыку на кухне | play_music |
| 76 | останови музыку в гостиной | stop_music |

### 🌿 Сад (4)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 77 | start irrigation zone 1 | start_irrigation_zone |
| 78 | включи полив газона | start_irrigation_zone |
| 79 | stop irrigation zone 3 | stop_irrigation_zone |
| 80 | what's the soil moisture level? | query_soil_moisture |

### 📡 Сенсоры (2)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 81 | what's the air quality in the living room? | query_air_quality |
| 82 | set motion sensitivity to high | set_motion_sensitivity |

### ⏰ Будильник (3)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 83 | wake me up at 07:30 | set_alarm |
| 84 | поставь будильник на 7 утра | set_alarm |
| 85 | отмени будильник | cancel_alarm |

### 🎬 Сцены (5)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 86 | activate movie night scene | activate_scene |
| 87 | switch to away mode | activate_scene |
| 88 | night mode | activate_scene |
| 89 | включи сцену кинотеатр | activate_scene |
| 90 | режим ночи | activate_scene |

### 🔌 Розетки (2)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 91 | toggle the outlet in the kitchen | toggle_outlet |
| 92 | включи розетку | toggle_outlet |

### 🚫 Edge cases (3)

| # | Фраза | Ожидаемый интент |
|---|-------|-----------------|
| 93 | what's the weather outside | none |
| 94 | tell me a joke | none |
| 95 | (дополнительно из regressions) | varies |

---

_Документация Vector Home v2. Все фазы 0–6 завершены. Router: 95/95=100%. Тестов: 130.._
---

## 8. Рекомендованное оборудование (v2.1)

### Базовая платформа

| Компонент | Модель | Цена |
|-----------|--------|------|
| Хост | Raspberry Pi 5 (8 ГБ) | ~$80 |
| Хаб | Home Assistant Yellow / Green | ~$100 |
| Микрофон | USB-микрофон / PS3 Eye | ~$10 |
| Динамик | Любой с 3.5mm / Bluetooth | ~$20 |

### WiFi-сенсинг (рекомендация)

**RuView** — WiFi как пространственное зрение. Без камер, без носимых устройств.

| Компонент | Модель | Цена | Что даёт |
|-----------|--------|------|---------|
| Чип | ESP32-S3 | $9 | CSI-сбор |
| Прошивка | RuView (61K звёзд) | Бесплатно | Presence, дыхание, пульс, поза, падение, счёт людей |
| Стандарт | IEEE 802.11bf-2025 | В будущем | WiFi-сенсинг в каждом роутере |

**Что заменяет:** PIR-датчики, камеры присутствия, носимые устройства.

**Интеграция:** ESP32-S3 → CSI → RuView → MQTT → Home Assistant → Vector Home GPT-2.

### Традиционные сенсоры

| Сенсор | Протокол | Цена |
|--------|---------|------|
| PIR движения | Zigbee | ~$10 |
| Дверной/оконный | Zigbee | ~$8 |
| Температура/влажность | Zigbee | ~$12 |
| Освещённость | Zigbee | ~$10 |
| Датчик дыма | Zigbee | ~$25 |

### Источники

- RuView: WiFi-сенсинг, 61K звёзд, ESP32-S3 $9
- IEEE 802.11bf-2025: стандарт WiFi-сенсинга (2025)
- CMU DensePose from WiFi: академический предшественник

---

## 9. Голосовой стек (v2.2)

**Vector Voice** — голосовой слой на базе Moonshine Voice. Замена Whisper + Piper + Router.

### Установка

```bash
pip install moonshine-voice
```

### Компоненты

| Компонент | Было | Стало |
|-----------|------|-------|
| STT | Whisper (faster-whisper) | Moonshine STT — выше точность, ниже задержка |
| TTS | Piper | Moonshine TTS — русский язык из коробки |
| Intent | Router (GPT-2 + regex) | Moonshine Intent — семантический matching |
| Diarization | Нет | Moonshine — кто говорит |

### Модели

| Модель | Размер | Где |
|--------|--------|-----|
| tiny | 26 МБ | Raspberry Pi 5 |
| small | ~100 МБ | Десктоп |
| base | ~300 МБ | Сервер |

### Интеграция

```python
from moonshine_voice import MicTranscriber, IntentRecognizer

transcriber = MicTranscriber(language="ru")
recognizer = IntentRecognizer()

for text in transcriber.stream():
    intent = recognizer.match(text, actions=ACTION_LIST)
    if intent:
        ha_bridge.execute(intent)
```

### Источник

- Vector Voice: https://github.com/Osmosy/vector-voice
- Moonshine Voice: https://github.com/moonshine-ai/moonshine (8.3K+ звёзд)
