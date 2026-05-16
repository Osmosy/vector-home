# Vector Home v2 — Быстрый старт

> Управляй умным домом голосом или текстом. Без облака, без GPU, без API-ключей.

---

## Что это?

Vector Home — твой личный ассистент для умного дома. Говоришь по-русски или по-английски — он понимает. Всё работает на твоём компьютере, никуда ничего не отправляет.

```
"Включи свет в гостиной"  →  2 секунды  →  💡 Свет горит
"Set temperature to 22"  →  2 секунды  →  🌡️ 22°C
"Поставь будильник на 7"  →  2 секунды  →  ⏰ Будильник установлен
```

## 52 инструмента, 8 доменов

| Домен | 🔧 | Что умеет | Пример EN | Пример RU |
|:------|---:|:----------|:----------|:----------|
| 💡 Свет | 8 | Включить, выключить, приглушить, цвет, сцена, мигнуть, температура, статус | `turn on the lights` | `включи свет в гостиной` |
| 🌡️ Климат | 9 | Температура, термостат, кондиционер, вентилятор, влажность, увлажнитель, осушитель | `set temperature to 22°C` | `установи 22 градуса` |
| 🪟 Шторы | 6 | Открыть/закрыть шторы и жалюзи, позиция, угол наклона | `open the curtains` | `открой шторы` |
| 🤖 Пылесос | 3 | Запустить, остановить, отправить на базу | `vacuum the office` | `пропылесось кухню` |
| 🔒 Безопасность | 7 | Замок (открыть/закрыть/статус), сигнализация (поставить/снять/статус), тревога | `lock the front door` | `запри входную дверь` |
| 🎵 Медиа | 10 | Музыка, радио, громкость, без звука, ТВ (вкл/выкл/канал/громкость) | `play jazz in the kitchen` | `включи музыку на кухне` |
| 🌿 Сад | 3 | Полив (вкл/выкл), влажность почвы | `start irrigation zone 1` | `включи полив газона` |
| 📡 Другое | 6 | Будильник, сцены, розетки, качество воздуха, датчик движения | `wake me up at 07:30` | `поставь будильник на 7 утра` |

---

## Установка

### Требования

| | Минимум | Рекомендуется |
|---|---------|---------------|
| CPU | Любой x86_64 | 4+ ядра |
| RAM | 600 MB (только парсер) | 6 GB (с Qwen3 fallback) |
| Диск | 1.5 GB | 2 GB |
| GPU | Не нужен | — |
| Python | 3.10+ | 3.12 |
| Интернет | Не нужен | Для Ollama fallback |

### Шаг 1. Клонирование

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt
```

### Шаг 2. Проверка

```bash
# 130 тестов — все должны пройти ✓
python -m pytest tests/test_router.py -v
```

### Шаг 3. Запуск

```bash
# API-сервер (порт 8126) + веб-панель
python -m src.api

# CLI — текстовая команда
python -m src.pipeline "turn on the lights in the living room"
python -m src.pipeline "включи свет в гостиной"

# CLI — интерактивный режим
python -m src.pipeline --interactive

# Голос (нужен faster-whisper)
python -m src.voice --interactive
```

---

## Веб-панель управления

Открой **http://localhost:8126/panel** — тёмная тема, 8 вкладок с устройствами.

Что видишь на экране:

- **Шапка** — логотип «Vector Home v2», статус-бар (зелёные/красные точки: WebSocket, Home Assistant, счётчик инструментов)
- **Строка ввода** — текстовое поле + кнопка «▶» отправить + кнопка «🎤» голосовой ввод (Web Speech API)
- **Результат** — карточка с разобранной командой: название инструмента, аргументы, HA-вызов, задержка
- **Вкладки устройств** — 8 кнопок: 💡 Свет · 🌡️ Климат · 🪟 Шторы · 🤖 Пылесос · 🔒 Безопасность · 🎵 Медиа · 🌿 Сад · 📡 Другое
- **Карточки** — при клике на вкладку появляются карточки с иконками, названиями и привязанными командами. Нажал карточку — команда ушла
- **История** — список последних команд: текст → инструмент → время. Можно кликнуть строку, чтобы повторить
- **Подвал** — версия, количество инструментов, статус подключения

---

## Примеры команд

### Свет (8 инструментов)

```bash
# Включить
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "turn on the lights in the living room"}'

# Выключить (по-русски)
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "выключи свет на кухне"}'

# Приглушить
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "dim the lights to 30%"}'

# Цвет
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "set the light color to red"}'
```

### Климат (9 инструментов)

```bash
# Температура
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "установи 22 градуса в спальне"}'

# Кондиционер
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "set AC to cool mode"}'

# Влажность
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "какая влажность?"}'
```

### Шторы (6 инструментов)

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "открой шторы"}'

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "set blinds to 50%"}'
```

### Пылесос (3 инструмента)

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "пропылесось кухню"}'

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "dock the vacuum"}'
```

### Безопасность (7 инструментов)

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "запри входную дверь"}'

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "arm the alarm"}'

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "тревога!"}'
```

### Медиа (10 инструментов)

```bash
# Музыка
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "play jazz in the kitchen"}'

# Радио
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "включи радио"}'

# ТВ
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "включи телевизор"}'

# Громкость
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "set volume to 50%"}'
```

### Сад (3 инструмента)

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "включи полив газона"}'

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "what is the soil moisture?"}'
```

### Будильники, сцены, розетки и датчики (6 инструментов)

```bash
# Будильник
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "поставь будильник на 7 утра"}'

# Сцена
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "activate movie night"}'

# Розетка
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "toggle the outlet"}'

# Качество воздуха
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "качество воздуха?"}'
```

---

## Формат ответа v2

Каждая команда возвращает JSON с полем `ha_call` — это готовый вызов для Home Assistant:

```json
{
  "tool": "turn_on_light",
  "arguments": {"room": "living_room"},
  "ha_call": {
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.living_room",
    "service_data": {}
  },
  "latency_s": 0.3,
  "used_fallback": false
}
```

### Примеры ответов

**Включить свет (EN):**
```bash
# Запрос
curl -s -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "turn on the lights in the living room"}'

# Ответ
{
  "tool": "turn_on_light",
  "arguments": {"room": "living_room"},
  "ha_call": {
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.living_room"
  },
  "latency_s": 0.2,
  "used_fallback": false
}
```

**Установить температуру (RU):**
```bash
# Запрос
curl -s -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "поставь 22 градуса в спальне"}'

# Ответ
{
  "tool": "set_temperature",
  "arguments": {"room": "bedroom", "temperature_c": 22},
  "ha_call": {
    "domain": "climate",
    "service": "set_temperature",
    "entity_id": "climate.bedroom",
    "service_data": {"temperature": 22}
  },
  "latency_s": 0.4,
  "used_fallback": false
}
```

**Запереть дверь (RU):**
```bash
# Запрос
curl -s -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "запри входную дверь"}'

# Ответ
{
  "tool": "lock_door",
  "arguments": {"door": "front_door"},
  "ha_call": {
    "domain": "lock",
    "service": "lock",
    "entity_id": "lock.front_door"
  },
  "latency_s": 0.1,
  "used_fallback": false
}
```

**Не распознано:**
```json
{
  "tool": "none",
  "arguments": {},
  "ha_call": null,
  "latency_s": 0,
  "used_fallback": false
}
```

> 💡 Русские названия комнат автоматически переводятся: `гостиная` → `living_room`, `спальня` → `bedroom`, `кухня` → `kitchen` и т.д.

---

## Подключение к Home Assistant

### Шаг 1. Установи Home Assistant

Если ещё не установлен — см. [HA Installation](https://www.home-assistant.io/installation/). Рекомендуемый вариант: Home Assistant OS на Raspberry Pi или мини-ПК.

### Шаг 2. Создай Long-Lived Access Token

1. Открой HA → Профиль (левое меню, внизу) → Безопасность
2. Прокрути до «Долгосрочные токены доступа»
3. Нажми «Создать токен»
4. Назови: `Vector Home`
5. Скопируй токен (показывается один раз!)

### Шаг 3. Запусти с live-режимом

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_token_here"

# Live-режим — команды реально выполняются в HA
python -m src.api --live

# Или через CLI
python -m src.pipeline --live "turn on the lights in the living room"
```

### Шаг 4. Переименуй entity_id

Чтобы Vector Home находил устройства, переименуй entity_id в HA:

**Свет:** `light.living_room`, `light.bedroom`, `light.kitchen`, `light.bathroom`

**Климат:** `climate.bedroom`, `climate.living_room_ac`

**Замки:** `lock.front_door`, `lock.back_door`

**Медиа:** `media_player.kitchen`, `media_player.bedroom_tv`

См. полный список маппингов в [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md).

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|:-----------|:---------|:------------|
| `HA_URL` | Адрес Home Assistant | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | пусто = dry run |
| `VH_PORT` | Порт API-сервера | `8126` |
| `GPT2_REPO` | Путь к gpt2-tool-call | `../gpt2-tool-call` |

---

## API-эндпоинты

| Метод | Путь | Описание |
|:------|:-----|:---------|
| `POST` | `/command` | Обработка текстовой команды |
| `GET` | `/health` | Статус системы |
| `GET` | `/tools` | Список 52 инструментов |
| `GET` | `/entities?domain=light` | Сущности HA (с фильтром) |
| `POST` | `/ha/call` | Прямой вызов HA |
| `GET` | `/history?limit=20` | История команд |
| `WS` | `/ws` | WebSocket (real-time) |
| `GET` | `/panel` | Веб-панель управления |

---

## Оборудование

Подробный гайд по выбору и настройке железа — в [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md).

**Кратко — бюджетный набор (~4 300 ₽):**

- 4× Yeelight Color (лампочки) — 2 400 ₽
- 1× Sonoff TH Elite + DHT22 (термостат) — 1 000 ₽
- 1× Sonoff S31 (розетка) — 500 ₽
- 1× Sonoff SV (реле для замка) — 400 ₽

**Оптимальный набор (~16 200 ₽):** + Nuki Smart Lock, BT-колонка

**Продвинутый (~41 800 ₽):** + Роборок S6, Google Nest Mini, 6 лампочек, 2 термостата

---

## Устранение неполадок

### Команды не распознаются

1. Проверь, что сервер запущен: `curl http://localhost:8126/health`
2. Попробуй простые команды: `turn on the lights`, `включи свет`
3. Проверь кодировку: русские буквы в UTF-8

### HA не отвечает

1. Проверь `HA_URL` — открой `http://homeassistant.local:8123` в браузере
2. Проверь `HA_TOKEN` — создай новый, если старый не работает
3. В dry run-режиме (без токена) команды парсятся, но не отправляются в HA

### Устройство не подключается к Wi-Fi

1. Убедись, что Wi-Fi 2.4 ГГц (не 5 ГГц!)
2. Введи пароль правильно (особые символы, регистр)
3. Перезагрузи роутер
4. Поднеси устройство ближе к роутеру

### ESPHome устройство не подключается после прошивки

1. Проверь SSID и пароль в YAML-конфиге
2. Подключись к Fallback AP (точка доступа с именем устройства)
3. Открой http://192.168.4.1
4. Введи правильные данные Wi-Fi
5. Если не помогло — перепрошей через USB-UART

### Home Assistant не видит устройство

1. Убедись, что устройство в той же сети
2. Перезагрузи HA: Настройки → Система → Перезагрузка
3. Проверь IP устройства в роутере (DHCP-таблица)
4. Добавь интеграцию вручную по IP

---

## Архитектура

```
Голос / Текст
      ↓
┌─────────────┐    ┌──────────────┐
│   Router v2  │───→│   Parser v2  │
│ 95 правил    │    │ GPT-2 124M  │
│ 100% EN/RU   │    │  52 инструм. │
└──────┬──────┘    └──────┬───────┘
       │                   │
       └───────┬───────────┘
               ↓
       ┌───────────────┐
       │   HA Bridge    │
       │ 52→HA маппинг  │
       │ RU→EN переводу│
       └──────┬───────┘
               ↓
        Home Assistant
```

**Router v2** — 95 regex-правил для 52 интентов, EN+RU, 100% точность. Fallback на Qwen3:8B (Ollama) для неоднозначных команд.

**Parser v2** — GPT-2 124M, single-tool парсинг, ~2 с/cоманду на CPU, 600 MB RAM.

**HA Bridge** — 52 инструмента → Home Assistant service calls. Автоматический перевод русских названий комнат, дверей, сцен и режимов кондиционера.

---

## Что дальше?

- 📄 [SPEC.md](SPEC.md) — техническое задание (подробная архитектура)
- 🔧 [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md) — выбор оборудования, ESPHome, инструкции
- 🧪 `python -m pytest tests/test_router.py -v` — запуск тестов

---

<div align="center">

Built by [Osmosy](https://github.com/Osmosy) · Powered by [gpt2-tool-call](https://github.com/barometech/gpt2-tool-call)

</div>