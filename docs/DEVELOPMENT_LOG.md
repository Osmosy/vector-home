# Vector Home — Хроника разработки

## Суть проекта

Оффлайновый стек управления умным домом на CPU. Голос или текст → keyword router → GPT-2 124M parser → Home Assistant. Без облака, без GPU, без API-ключей, без интернета. Поддержка русского и английского языков.

Основа — репозиторий [barometech/gpt2-tool-call](https://github.com/barometech/gpt2-tool-call): GPT-2 124M (2019), дотюненный под tool calling. Мы адаптировали его под домен умного дома и добавили русский язык.

---

## Phase 0: Foundation

### Клонирование и подготовка

- Клонирован репозиторий `gpt2-tool-call`, скачаны веса через `git lfs pull`
- Изучена архитектура: Full FT (124M, 475 МБ) и Adapter (250K, 1 МБ)
- Нативный контекст GPT-2 = 1024 токена (архитектурный лимит)
- Инференс: чистый torch + safetensors, без зависимости от transformers

### Генерация EN датасета

- 658 примеров: 628 single-tool + 30 irrelevance
- 12 инструментов: turn_on/off_light, set/query_temperature, lock/unlock_door, play/stop_music, set/cancel_alarm, activate_scene, vacuum_start
- Формат: `{"prompt": "...", "completion": "{\"name\": \"...\", \"arguments\": {...}}"}`
- Комнаты: living room, bedroom, kitchen, bathroom, office, garage, hallway
- Двери: front door, back door, garage door
- Сцены: movie night, morning, night, party, romantic, away, focus
- Музыка: jazz, rock, pop, classical, lo-fi

### EN SFT обучение

- Чекпоинт: `gpt2_ha_best.pt` (475 МБ)
- AdamW, lr=1e-5, batch=1, grad_accum=4, PAD=512, 1 эпоха
- Время: 24 минуты на 4 потоках CPU
- Loss: 1.6 → 0.3 за первые 100 шагов
- Валидация: **12/12 = 100%** на single-tool командах
- Step 100 checkpoint: `gpt2_ha_step100.pt` (475 МБ)
- Финальный чекпоинт: `gpt2_ha_final.pt` — overfitted, показал 92%, забракован

---

## Phase 1: Router

### Keyword/regex классификатор намерений

- `HomeRouter` — ~100 regex правил, EN + RU
- Нулевая RAM, нулевая задержка — чистый regex
- Порядок правил важен: более специфичные паттерны идут первыми
- Lights OFF перед Lights ON (чтобы «turn off» не совпало с «turn on»)
- Query temperature перед Set temperature

### STT-нормализация

- Router приводит вход к lowercase, убирает пунктуацию
- Добавлены `-ing` формы для всех EN паттернов: «turning on», «switching off», «locking» и т.д.
- Причина: Whisper STT часто выдаёт «Turning on the lights» вместо «Turn on the lights»

### Fix для кириллицы

- `\b` (word boundary) не работает с кириллицей в Python regex
- Заменено на `.{0,5}` (non-greedy) для всех RU паттернов
- Пример: `(?:какая|сколько).{0,5}(?:температур)` вместо `\b(какая|сколько)\b.*\b(температур)\b`

### Fallback

- При отсутствии мача роутера — fallback на Ollama Qwen3:8B
- Ollama уже развёрнут на localhost:11434
- Multi-intent и ambiguous запросы направляются к fallback

### Валидация роутера

- **44/44 = 100%**: 22 EN + 22 RU команды
- Все 12 intents покрыты на обоих языках

---

## Phase 2: Integration

### HomeParser (GPT-2 124M Full FT)

- `parser.py` — инференс GPT-2 с tool spec в промпте
- `parse(utterance, tool_name)` — single-tool режим
- Промпт: `SYSTEM: [tool spec] USER: [utterance] ASSISTANT: <functioncall>`
- Модель получает spec конкретного инструмента от роутера → нет проблемы multi-tool
- Greedy decode, MAX_GEN_TOKENS=80, остановка по `}`
- `name` из результата принудительно заменяется на `tool_name` от роутера
- **Критический инсайт**: `parse()` требует `tool_name` от роутера. Без правильного tool spec модель получает `none({})`. Это не баг — это архитектура single-tool режима.

### HABridge (REST API)

- `ha_bridge.py` — HTTP API к Home Assistant
- Маппинг tool_name → HA service call (domain, service, entity_id)
- Entity discovery через GET /api/states
- Dry-run по умолчанию (VH_DRY_RUN=1)
- `build_service_call()` — синхронный, для тестов
- `call_service()` — async, для production

### FastAPI endpoint

- `api.py` — HTTP сервер на порту 8126 (VH_PORT env)
- Endpoints: POST /command, GET /health, GET /tools, GET /entities, POST /ha/call
- CORS включён
- Dry-run по умолчанию

### Pipeline

- `pipeline.py` — CLI pipeline: utterance → router → parser → HA bridge
- Синхронный, для тестов и отладки

---

## Phase 3: Voice

### STT (faster-whisper)

- Модель: tiny (~75 МБ, offline)
- Latency: ~0.5s загрузка, ~3.5s транскрипция
- Работает на CPU

### TTS (edge-tts + Piper)

- **edge-tts**: онлайн, Microsoft голоса, бесплатно
- **Piper**: оффлайн, ~61 МБ на голос
  - EN: `en_US-lessac-medium.onnx`
  - RU: `ru_RU-dmitri-medium.onnx`
- Piper установлен как бинарник в `/usr/local/bin/piper`
- Голоса скачаны в `models/voices/`

### Автоопределение языка

- `voice.py` проверяет наличие кириллицы в аргументах парсера
- Если кириллица найдена → RU голос (dmitri), RU шаблон ответа
- Иначе → EN голос (lessac), EN шаблон ответа
- RU шаблоны: «Включаю свет в {room}», «Температура установлена на {temp}°C» и т.д.

### Замкнутый контур

- `process_voice()` — audio → STT → router → parser → HA → TTS → audio
- Latency: ~7-8s end-to-end на CPU

---

## Phase 4: RU SFT

### Генерация RU датасета

- `data/train_dataset_ru.json` — 695 примеров
  - 480 RU tool-calling примеров
  - 25 RU irrelevance примеров
  - 190 EN stability примеров (для предотвращения catastrophic forgetting)
- RU значения комнат: гостиная, спальня, кухня, ванная, кабинет, прихожая, гараж, детская, коридор
- RU двери: входная дверь, задняя дверь, гаражная дверь, балконная дверь
- RU сцены: кинотеатр, утро, ночь, вечеринка, романтика, отъезд, фокус
- RU музыка: джаз, рок, поп, классика, лоу-фай

### RU SFT обучение

- Стартовый чекпоинт: `gpt2_ha_best.pt` (EN FT, не base GPT-2)
- LR=5e-6 (ниже чем EN 1e-5, чтобы сохранить EN навыки)
- 173 шага, 24.5 мин CPU на 4 потоках
- Loss: 0.249 → 0.002
- Step 100 validation: 10.5/12 = 88%
- Final validation (20 samples): 19/20 = 95%
- Чекпоинты: `gpt2_ha_ru_step100.pt`, `gpt2_ha_ru_best.pt` (498 МБ)

### HA WebSocket

- `ha_ws.py` — async WebSocket клиент к HA
- Auth: `auth_required` → отправка токена → `auth_ok`
- `subscribe_events()` → `state_changed`
- Auto-reconnect с exponential backoff (1→2→4→…≤30s)
- `on_state_change()` — маппинг HA events в человекочитаемые строки
- `_ha_url_to_ws()` — http:// → ws://, https:// → wss://

### Проблема RU→EN маппинга и фикс падежей

**Проблема**: Модель выдаёт русские аргументы в косвенных падежах:
- «включи свет в гостиной» → `room: "гостиной"` (предложный падеж)
- «пропылесось кухню» → `room: "кухню"` (винительный падеж)
- «установи температуру в спальне» → `room: "спальне"` (предложный падеж)
- «запри входную дверь» → `door: "дверь"` (модель потеряла прилагательное «входная»)

Старый `_normalize()` использовал точное совпадение (`t == ru`) с маппингом только в именительном падеже. Ни одна из форм не маппилась → entity_id содержал кириллицу.

**Решение**: `RU_ROOM_MAP_EXT` / `RU_DOOR_MAP_EXT` / `RU_SCENE_MAP_EXT` / `RU_MUSIC_MAP_EXT` — расширенные маппинги со всеми падежными формами:

| Именительный | Предложный | Дательный | Винительный | → HA entity |
|---|---|---|---|---|
| гостиная | гостиной | — | гостиную | living_room |
| спальня | спальне | — | спальню | bedroom |
| кухня | кухне | — | кухню | kitchen |
| ванная | ванной | — | ванную | bathroom |

Дополнительно:
- `"дверь"` → `"front_door"` — дефолт для голого существительного без прилагательного
- `"входная"` / `"входную"` → `"front_door"` — модель иногда теряет «дверь»
- Условие `ru in t` для частичного совпадения

### Полная pipeline-валидация

**12/12 RU = 100%** через router → parser → HA bridge normalize:

| Команда | Tool | HA Entity |
|---------|------|-----------|
| включи свет в гостиной | turn_on_light | light.living_room |
| выключи свет на кухне | turn_off_light | light.kitchen |
| установи температуру 22 в спальне | set_temperature | climate.bedroom |
| какая температура в ванной | query_temperature | sensor.bathroom_temperature |
| запри входную дверь | lock_door | lock.front_door |
| открой заднюю дверь | unlock_door | lock.back_door |
| включи джаз на кухне | play_music | media_player.kitchen |
| останови музыку в гостиной | stop_music | media_player.living_room |
| поставь будильник на 07:30 | set_alarm | input_datetime.alarm |
| отмени будильник | cancel_alarm | input_boolean.alarm |
| включи сцену кинотеатр | activate_scene | scene.movie_night |
| пропылесось кухню | vacuum_start | vacuum.robot |

**4/4 EN = 100%** — EN capability сохранена после RU SFT.

---

## Итоговые метрики

| Метрика | Значение |
|---------|----------|
| RU pipeline accuracy | 12/12 = 100% |
| EN pipeline accuracy | 12/12 = 100% (EN stability: 4/4 = 100%) |
| Router accuracy | 44/44 = 100% |
| Parser latency | 1.5–5s/команда CPU |
| RAM (parser only) | ~600 МБ |
| RAM (parser + Ollama fallback) | ~6 ГБ |
| Диск (модели) | 475 МБ (EN) + 498 МБ (RU) |
| Диск (голоса Piper) | 61 МБ × 2 |
| EN SFT время | 24 мин CPU |
| RU SFT время | 24.5 мин CPU |
| Оффлайн | ✅ Полный стек работает без интернета |

## Файловая структура

```
vector-home/
├── src/
│   ├── router.py              # HomeRouter — regex intent classifier, RU/EN, ~100 правил
│   ├── parser.py              # HomeParser — GPT-2 FT inference (single-tool mode)
│   ├── pipeline.py            # CLI pipeline (utterance → HA)
│   ├── api.py                 # FastAPI server (port 8126)
│   ├── ha_bridge.py           # HABridge — REST API + RU→EN entity mapping (с падежами)
│   ├── ha_ws.py               # HAWebSocketClient — real-time events, auto-reconnect
│   ├── voice.py               # VoicePipeline — STT → TTS, auto language, Piper + edge-tts
│   ├── train_ha.py            # EN SFT training script (658 examples)
│   ├── train_ha_ru.py         # RU SFT training script (695 examples, starts from EN FT)
│   └── generate_ru_dataset.py # RU dataset generator
├── data/
│   ├── train_dataset.json     # 658 EN examples
│   ├── train_dataset_ru.json  # 695 RU+EN examples
│   └── tools_spec.json        # 12 tool definitions
├── models/
│   ├── gpt2_ha_best.pt        # EN Full FT (475 МБ, 100% accuracy)
│   ├── gpt2_ha_ru_best.pt    # RU+EN Full FT (498 МБ, 100% pipeline)
│   ├── gpt2_ha_step100.pt     # EN step 100 checkpoint
│   ├── gpt2_ha_ru_step100.pt  # RU step 100 checkpoint
│   ├── gpt2_ha_final.pt       # EN overfitted (92%, забракован)
│   └── voices/
│       ├── en_US-lessac-medium.onnx      # Piper EN voice (61 МБ)
│       ├── en_US-lessac-medium.onnx.json
│       ├── ru_RU-dmitri-medium.onnx      # Piper RU voice (61 МБ)
│       └── ru_RU-dmitri-medium.onnx.json
├── docs/
│   ├── SPEC.md                # Техническое задание
│   ├── DEVELOPMENT_LOG.md     # Этот файл
│   └── USER_GUIDE.md          # Руководство по эксплуатации
└── requirements.txt
```