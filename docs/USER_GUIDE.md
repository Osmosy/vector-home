# Vector Home — Руководство по эксплуатации

## Преимущества нашей версии

Vector Home — это не просто обёртка над GPT-2. Мы построили **завершённый офлайновый стек** для управления умным домом, который работает на обычном ноутбуке без интернета. Вот что отличает нашу реализацию от базового репозитория gpt2-tool-call:

### 1. Русский язык из коробки

Базовый gpt2-tool-call — только английский. Мы:
- Сгенерировали RU-датасет (695 примеров с русскими комнатами, дверями, сценами)
- Дотюнили модель, стартуя от EN-чекпоинта (не с нуля) — русская модель сохраняет английский
- Решили проблему падежей: модель выдаёт «гостиной», «кухне», «кухню» — HABridge маппит все формы в HA entity_id
- Автоопределение языка ответа: кириллица в args → русский голос + русские шаблоны

### 2. Завершённый pipeline, а не просто модель

Базовый репозиторий даёт модель и inference-скрипт. Мы построили полный стек:

```
Голос/Текст → Router → Parser → HABridge → Home Assistant
                                      ↓
                              HA WebSocket ← События реального времени
                                      ↓
                              Voice Pipeline → Голосовой ответ
```

Каждый компонент протестирован и работает. 12/12 команд = 100% на обоих языках.

### 3. Router решает главную проблему GPT-2

Базовая модель даёт 8% на multi-tool (12 функций в одном промпте). Это архитектурный лимит 124M модели — она не может выбирать из 12 инструментов.

Мы обошли это: **роутер** (regex, 0 RAM, 0ms) определяет intent → parser получает только один инструмент → 100% точность. Router + parser = 100%. Parser alone (multi-tool) = 8%.

### 4. Офлайновый голос

Полный контур: голос → Whisper STT → router → parser → HA → Piper TTS → голос. Всё на CPU, без интернета. Два языка (RU + EN голоса Piper по 61 МБ).

### 5. HA WebSocket для обратной связи

Не только команды в HA, но и события из HA: свет включился, температура изменилась, дверь открылась. WebSocket с auto-reconnect.

### 6. Дообучение за 24 минуты

Нужен新しい tool (например, «полей цветы»)? Генерируешь 500 примеров (любой LLM), запускаешь `train_ha_ru.py` — через 24 минуты на CPU новый чекпоинт готов. Без GPU, без облака.

---

## Установка

### Зависимости

```bash
pip3 install --break-system-packages torch safetensors numpy httpx uvicorn faster-whisper edge-tts
```

Piper TTS (опционально, для офлайн-голоса):
```bash
# Скачать бинарник
wget -q https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz
tar xf piper_linux_x86_64.tar.gz
sudo mv piper/piper /usr/local/bin/
rm -rf piper piper_linux_x86_64.tar.gz
```

### Репозиторий GPT-2

```bash
cd ~/projects
git clone https://github.com/barometech/gpt2-tool-call.git
cd gpt2-tool-call
git lfs pull   # Скачать веса базовой модели
```

### Vector Home

```bash
cd ~/projects
# Если репозиторий Vector Home уже склонирован —モデル доступны
# Модели: models/gpt2_ha_best.pt (EN), models/gpt2_ha_ru_best.pt (RU+EN)
```

---

## Запуск

### dry-run (без HA, для тестов)

```bash
cd ~/projects/vector-home
VH_PORT=8126 VH_DRY_RUN=1 python3 -m src.api
```

Сервер запускается на http://localhost:8126. Команды обрабатываются, HA не вызывается.

### С реальным Home Assistant

```bash
VH_PORT=8126 \
HA_URL=http://homeassistant.local:8123 \
HA_TOKEN=your_long_lived_access_token \
VH_DRY_RUN=0 \
python3 -m src.api
```

Dry-run отключён — команды реально отправляются в HA.

### HA_TOKEN: как получить

1. Открой Home Assistant в браузере
2. Настройки → Пользователи → Твой пользователь → Долгоживущие токены доступа
3. Создать токен → скопировать → подставить в HA_TOKEN

---

## API

### POST /command — обработка текстовой команды

```bash
# EN
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "turn on the lights in the living room"}'

# RU
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи свет в гостиной"}'
```

Ответ:
```json
{
  "tool": "turn_on_light",
  "arguments": {"room": "гостиной"},
  "ha_call": {
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.living_room"
  },
  "dry_run": true,
  "message": "[DRY RUN] Would call light.turn_on on light.living_room"
}
```

### GET /health

```bash
curl http://localhost:8126/health
# {"status": "ok", "model": "gpt2_ha_ru_best.pt", "dry_run": true}
```

### GET /tools

```bash
curl http://localhost:8126/tools
# Список 12 поддерживаемых инструментов
```

### GET /entities?domain=light

```bash
curl http://localhost:8126/entities?domain=light
# Список HA сущностей (требует HA_URL + HA_TOKEN)
```

### POST /ha/call — прямой вызов HA

```bash
curl -X POST http://localhost:8126/ha/call \
  -H 'Content-Type: application/json' \
  -d '{"domain": "light", "service": "turn_on", "entity_id": "light.living_room"}'
```

---

## Поддерживаемые команды

| Tool | EN | RU |
|------|----|----|
| turn_on_light | turn on the lights in the living room | включи свет в гостиной |
| turn_off_light | turn off garage lights | выключи свет на кухне |
| set_temperature | set bedroom to 22 degrees | установи температуру 22 градуса |
| query_temperature | what is the temperature? | какая температура в спальне |
| lock_door | lock the front door | запри входную дверь |
| unlock_door | unlock the back door | открой замок |
| play_music | play jazz in the kitchen | включи джаз на кухне |
| stop_music | stop music in the bathroom | останови музыку |
| set_alarm | wake me up at 07:30 | поставь будильник на 7 утра |
| cancel_alarm | cancel the alarm | отмени будильник |
| activate_scene | activate movie night | включи сцену кинотеатр |
| vacuum_start | vacuum the office | пропылесось кухню |

---

## Голосовой контур

### С Piper TTS (офлайн)

```bash
# RU голос
python3 -m src.voice recording.wav --tts piper --tts-voice ru

# EN голос
python3 -m src.voice recording.wav --tts piper --tts-voice en
```

### С edge-tts (онлайн)

```bash
python3 -m src.voice recording.wav --tts edge-tts
```

### Пайплайн

1. **STT**: faster-whisper (tiny) → распознаёт речь, ~~3.5s
2. **Router**: regex → определяет intent, 0ms
3. **Parser**: GPT-2 → извлекает аргументы, ~~3s
4. **HABridge**: маппит в HA entity, отправляет вызов
5. **TTS**: Piper (офлайн) или edge-tts (онлайн) → голосовой ответ
6. **Автоопределение языка**: кириллица в args → RU голос + RU шаблон ответа

Общая задержка: ~7-8s end-to-end на CPU.

---

## Маппинг русских имён в HA entity_id

Модель выдаёт русские аргументы в косвенных падежах. `HABridge._normalize()` автоматически маппит:

### Комнаты

| Модель выдаёт | HA entity |
|---|---|
| гостиная, гостиной, гостиную | living_room |
| спальня, спальне, спальню | bedroom |
| кухня, кухне, кухню | kitchen |
| ванная, ванной, ванную | bathroom |
| кабинет | office |
| прихожая, прихожей | hallway |
| гараж | garage |
| детская, детской | nursery |
| коридор | hall |

### Двери

| Модель выдаёт | HA entity |
|---|---|
| входная дверь, входную дверь, входная, входную, дверь | front_door |
| задняя дверь, заднюю дверь, задняя, заднюю | back_door |
| гаражная дверь, гаражную дверь, гаражная, гаражную | garage_door |
| балконная дверь, балконную дверь, балконная, балконную | balcony_door |

### Сцены

| Модель выдаёт | HA entity |
|---|---|
| кинотеатр | movie_night |
| утро | morning |
| ночь | night |
| вечеринка | party |
| романтика | romantic |
| отъезд | away |
| фокус | focus |

### Музыка

| Модель выдаёт | HA entity |
|---|---|
| джаз | jazz |
| рок | rock |
| поп | pop |
| классика | classical |
| лоу-фай | lo-fi |

---

## Добавление нового инструмента

### 1. Обновить tools_spec.json

Добавить определение инструмента в `data/tools_spec.json`:

```json
{
  "name": "water_plants",
  "description": "Water plants in a specific room",
  "parameters": {
    "type": "object",
    "properties": {
      "room": {"type": "string", "description": "Room with plants"}
    }
  }
}
```

### 2. Добавить правило в роутер

В `src/router.py` добавить regex:

```python
(r"\b(water|irrigate|watering)\b.*\b(plants?|flowers?)\b", "water_plants"),
(r"(?:полей|поливай|полив).{0,5}(?:цветы|растения|рассаду)", "water_plants"),
```

### 3. Сгенерировать примеры и дообучить

Сгенерировать ~500 примеров с помощью любой LLM и дообучить модель:
```bash
python3 src/train_ha_ru.py   # ~24 мин CPU
```

### 4. Добавить маппинг в HABridge

В `src/ha_bridge.py`:
```python
HA_ENTITY_MAP["water_plants"] = ("switch", "switch.plants_{room}")
```

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| VH_PORT | 8126 | Порт HTTP API |
| VH_DRY_RUN | 1 | 1=не отправлять команды в HA, 0=реальные вызовы |
| HA_URL | http://homeassistant.local:8123 | URL Home Assistant |
| HA_TOKEN | (пусто) | Long-lived access token |
| GPT2_REPO | ../gpt2-tool-call | Путь к репозиторию gpt2-tool-call |

---

## Модели

| Файл | Размер | Назначение | Точность |
|---|---|---|---|
| gpt2_ha_best.pt | 475 МБ | EN Full FT | 12/12 = 100% |
| gpt2_ha_ru_best.pt | 498 МБ | RU+EN Full FT | 12/12 RU + 4/4 EN = 100% |
| gpt2_ha_step100.pt | 475 МБ | EN checkpoint step 100 | 12/12 = 100% |
| gpt2_ha_ru_step100.pt | 498 МБ | RU checkpoint step 100 | 10.5/12 = 88% |
| gpt2_ha_final.pt | 475 МБ | EN overfitted | ❌ 92%, забракован |

### Выбор модели

Парсер загружает модель из пути, указанного в конструкторе:
```python
# RU модель (рекомендуется, содержит EN + RU)
parser = HomeParser(weights_path=Path("models/gpt2_ha_ru_best.pt"))

# EN модель (только английский)
parser = HomeParser(weights_path=Path("models/gpt2_ha_best.pt"))
```

RU модель (`gpt2_ha_ru_best.pt`) сохраняет EN capability — нет смысла использовать EN-модель, если нужна только английская команда.

---

## Известные ограничения

1. **Контекст**: GPT-2 = 1024 токена нативно. Position Interpolation > 4x ломает качество.
2. **Multi-tool без роутера**: 8% (архитектурный лимит 124M). Роутер решает эту проблему.
3. **Multi-step decomposition**: Невозможно на 124M → fallback на Ollama Qwen3:8B обязателен.
4. **Ансамбль клонов**: Бесполезен — greedy decode даёт идентичные выходы.
5. **Английский код**: Модель не умеет писать код, только tool calling.
6. **Двери**: Модель иногда теряет прилагательное («входная дверь» → `door: "дверь"`). HABridge маппит голое «дверь» в front_door как дефолт.

---

## Устранение неполадок

### `parse()` возвращает `none({})`

Причина: передан неверный `tool_name`. `parse(utterance, tool_name)` использует tool_name для формирования промпта — если tool не найден в `tools_spec.json`, модель не получает spec → возвращает none.

Решение: всегда запускать через router.route() → parser.parse().

### `entity_id` содержит кириллицу

Причина: `_normalize()` не нашёл маппинг для данного значения аргумента.

Решение: добавить форму в `RU_ROOM_MAP_EXT` / `RU_DOOR_MAP_EXT` в `ha_bridge.py`.

### Модель загружается долго (>30s)

Причина: GPT-2 загружает base weights + FT weights.

Решение: это нормально, загрузка одноразовая при старте сервера. Инференс ~3s/команду.

### Ollama fallback не работает

Причина: Ollama не запущен или модель не скачана.

Решение: `ollama serve` и `ollama pull qwen3:8b`.

### Piper TTS не найден

Причина: бинарник `piper` не в PATH.

Решение: `sudo ln -s /usr/local/bin/piper /usr/bin/piper` или указать полный путь.

---

## Архитектура (для разработчиков)

```
┌─────────────┐
│  Голос/Текст  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     miss → Ollama Qwen3:8B (fallback)
│   Router     │     ~100 regex rules, RU+EN, 0ms
│  (12+ way)   │     intent → tool_name
└──────┬──────┘
       │ tool_name
       ▼
┌─────────────┐
│   Parser     │     GPT-2 124M Full FT (~600 MB RAM)
│ (single-tool)│     prompt = tool_spec + utterance
└──────┬──────┘     greedy decode, ~3s/команда
       │ {name, arguments}
       ▼
┌─────────────┐     RU→EN entity mapping
│  HABridge    │     tool_name → domain.service(entity_id)
│  + WebSocket │     state_changed events → callback
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Home         │     REST API: POST /api/services/...
│ Assistant    │     WebSocket: ws://.../api/websocket
└─────────────┘
       │
       ▼ (response)
┌─────────────┐
│ Voice Pipeline│   STT (Whisper) → Router → Parser → HA → TTS (Piper)
└─────────────┘
```

### Поток обработки

1. Пользователь говорит или вводит команду
2. Router матчит regex → `(tool_name, confident=True)`
3. Parser формирует промпт с tool spec, генерирует JSON
4. HABridge маппит руские аргументы в HA entity_id (с падежами)
5. HABridge отправляет REST API вызов в HA (или dry-run)
6. HA WebSocket получает состояние в реальном времени
7. Voice pipeline формирует голосовой ответ на языке команды