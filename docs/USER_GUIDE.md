# Vector Home v2 — Руководство пользователя

> **Версия:** 2.0.0  
> **Дата:** 2026-05-16  
> **Языки:** 🇷🇺 Русский / 🇬🇧 English  
> **Статус:** Все фазы 0–6 завершены ✅

---

## Содержание

1. [Обзор](#1-обзор)
2. [52 команды по 8 доменам](#2-52-команды-по-8-доменам)
3. [RU→EN маппинг](#3-ruen-маппинг)
4. [API v2](#4-api-v2)
5. [Веб-панель управления](#5-веб-панель-управления)
6. [Parser: Fuzzy Match](#6-parser-fuzzy-match)
7. [Замечание о `\b` для кириллицы](#7-замечание-о-b-для-кириллицы)
8. [Тесты](#8-тесты)
9. [Установка и запуск](#9-установка-и-запуск)
10. [Подключение к Home Assistant](#10-подключение-к-home-assistant)
11. [Известные ограничения](#11-известные-ограничения)
12. [Устранение неполадок](#12-устранение-неполадок)

---

## 1. Обзор

**Vector Home v2** — оффлайновый стек управления умным домом на CPU.  
Конвейер: **голос/текст → Router → Parser → HA Bridge → Home Assistant**.

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
           │ ha_call
           ▼
    Home Assistant
    (REST API /api/services)
```

**Ключевые метрики:**

| Метрика | Значение |
|---------|----------|
| Инструментов | 52 (+ `none`) |
| Router правила | 95 |
| Router точность | **95/95 = 100%** EN+RU |
| Тестов pytest | **130 ✓** |
| Языки | EN + RU (нативно) |
| Порог `\b` для кириллицы | ✅ Исправлен |
| HA маппингов | 53 tool → HA service call |

---

## 2. 52 команды по 8 доменам

### 2.1 💡 Свет (8 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 1 | `turn_on_light` | Включить свет | `turn on the lights in the living room` | `включи свет в гостиной` |
| 2 | `turn_off_light` | Выключить свет | `turn off garage lights` | `выключи свет на кухне` |
| 3 | `dim_light` | Приглушить свет | `dim the lights to 30%` | `приглуши свет в спальне` |
| 4 | `blink_light` | Мигать светом | `blink the lights` | `моргни светом` |
| 5 | `set_light_color` | Установить цвет | `set the light color to red` | `поставь красный свет` |
| 6 | `set_light_scene` | Сцена освещения | `set light scene to romantic` | `включи сцену романтик` |
| 7 | `set_light_temperature_k` | Цветовая температура | `set light temperature to 4000 kelvin` | `установи тёплый свет 4000K` |
| 8 | `query_light_state` | Статус света | `is the light on in the kitchen?` | `включён ли свет на кухне?` |

### 2.2 🌡️ Климат (9 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 9 | `set_temperature` | Установить температуру | `set bedroom to 22 degrees` | `поставь 22 градуса в спальне` |
| 10 | `query_temperature` | Узнать температуру | `what is the temperature?` | `какая температура в спальне?` |
| 11 | `set_thermostat` | Режим термостата | `set thermostat to heat mode` | `термостат на обогрев` |
| 12 | `set_ac_mode` | Режим кондиционера | `set AC to cool mode` | `кондиционер на охлаждение` |
| 13 | `set_fan_speed` | Скорость вентилятора | `set fan speed to 50%` | `вентилятор на 50%` |
| 14 | `set_humidity_target` | Целевая влажность | `set humidity to 45%` | `установи влажность 45%` |
| 15 | `toggle_humidifier` | Вкл/выкл увлажнитель | `toggle the humidifier` | `включи увлажнитель` |
| 16 | `toggle_dehumidifier` | Вкл/выкл осушитель | `toggle the dehumidifier` | `включи осушитель` |
| 17 | `query_humidity` | Узнать влажность | `what's the humidity?` | `какая влажность на кухне?` |

### 2.3 🪟 Шторы/жалюзи (6 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 18 | `open_curtains` | Открыть шторы | `open the curtains` | `открой шторы` |
| 19 | `close_curtains` | Закрыть шторы | `close the curtains in the bedroom` | `закрой шторы в спальне` |
| 20 | `raise_blinds` | Поднять жалюзи | `raise the blinds` | `подними жалюзи` |
| 21 | `lower_blinds` | Опустить жалюзи | `lower the blinds` | `опусти жалюзи` |
| 22 | `set_blinds_position` | Позиция жалюзи (%) | `set blinds to 50%` | `жалюзи на 50%` |
| 23 | `set_blinds_angle` | Угол наклона жалюзи | `set blinds angle to 45 degrees` | `наклон жалюзи 45 градусов` |

### 2.4 🤖 Пылесос (3 инструмента)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 24 | `vacuum_start` | Запустить пылесос | `vacuum the office` | `пропылесось кухню` |
| 25 | `stop_vacuum` | Остановить пылесос | `stop the vacuum` | `останови пылесос` |
| 26 | `dock_vacuum` | Отправить на базу | `dock the vacuum` | `отправь пылесос на базу` |

### 2.5 🔒 Безопасность (7 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 27 | `lock_door` | Запереть дверь | `lock the front door` | `запри входную дверь` |
| 28 | `unlock_door` | Отпереть дверь | `unlock the back door` | `открой замок` |
| 29 | `query_door_status` | Статус двери | `is the front door locked?` | `заперта ли входная дверь?` |
| 30 | `arm_alarm_system` | Поставить на охрану | `arm the alarm` | `поставь сигнализацию` |
| 31 | `disarm_alarm_system` | Снять с охраны | `disarm the alarm` | `сними сигнализацию` |
| 32 | `query_alarm_status` | Статус сигнализации | `is the alarm armed?` | `сигнализация включена?` |
| 33 | `trigger_panic_alarm` | Тревога | `trigger panic alarm!` | `тревога!` |

### 2.6 🎵 Медиа (10 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 34 | `play_music` | Включить музыку | `play jazz in the kitchen` | `включи джаз на кухне` |
| 35 | `stop_music` | Остановить музыку | `stop music in the bathroom` | `останови музыку` |
| 36 | `pause_music` | Пауза | `pause music` | `поставь на паузу` |
| 37 | `play_radio_station` | Радиостанция | `play radio station BBC` | `включи радио` |
| 38 | `set_volume` | Громкость (%) | `set volume to 50%` | `громкость на 50%` |
| 39 | `mute_audio` | Без звука | `mute audio` | `выключи звук` |
| 40 | `turn_on_tv` | Включить ТВ | `turn on the TV` | `включи телевизор` |
| 41 | `turn_off_tv` | Выключить ТВ | `turn off the TV` | `выключи телевизор` |
| 42 | `set_tv_channel` | Канал ТВ | `set TV channel to 5` | `включи 5-й канал` |
| 43 | `set_tv_volume` | громкость ТВ | `set TV volume to 30%` | `громкость телека на 30%` |

### 2.7 🌿 Сад (3 инструмента)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 44 | `start_irrigation_zone` | Начать полив зоны | `start irrigation zone 1` | `включи полив газона` |
| 45 | `stop_irrigation_zone` | Остановить полив | `stop irrigation zone 2` | `выключи полив` |
| 46 | `query_soil_moisture` | Влажность почвы | `what is the soil moisture?` | `какая влажность почвы?` |

### 2.8 ⚡ Другое (6 инструментов)

| # | Инструмент | Описание | Пример EN | Пример RU |
|---|-----------|----------|-----------|-----------|
| 47 | `set_alarm` | Будильник | `wake me up at 07:30` | `поставь будильник на 7 утра` |
| 48 | `cancel_alarm` | Отменить будильник | `cancel the alarm` | `отмени будильник` |
| 49 | `activate_scene` | Сцена | `activate movie night` | `включи сцену кино` |
| 50 | `toggle_outlet` | Розетка | `toggle the outlet` | `включи розетку` |
| 51 | `query_air_quality` | Качество воздуха | `what's the air quality?` | `качество воздуха?` |
| 52 | `set_motion_sensitivity` | Чувствительность сенсора | `set motion sensitivity to high` | `чувствительность движения на максимум` |

**Итого: 52 инструмента + `none` (не распознано) = 53 интента в Router.**

---

## 3. RU→EN маппинг

HA Bridge автоматически переводит русские аргументы в entity_id Home Assistant.

### 3.1 Комнаты (`RU_ROOM_MAP`, 14 записей)

| Русский | English entity |
|---------|---------------|
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

Падежные формы обрабатываются автоматически: `гостиной` → `living_room`, `кухне` → `kitchen`, `спальне` → `bedroom`.

### 3.2 Двери (`RU_DOOR_MAP`, 5 записей)

| Русский | English entity |
|---------|---------------|
| входная | front_door |
| задняя | back_door |
| гаражная | garage_door |
| балконная | balcony_door |
| подвальная | basement_door |

### 3.3 Сцены (`RU_SCENE_MAP`, 16 записей)

| Русский | English entity |
|---------|---------------|
| кино, кинь, кинотеатр | movie |
| ночь, ночи, ночной | night |
| утро, утра, утренний | morning |
| вечеринка, пати, гость | party |
| романтик, романтический | romantic |
| фокус, рабочий | focus |
| отпуск, отсутствие | away |

### 3.4 AC режимы (`RU_AC_MODE_MAP`, 14 записей)

| Русский | English HVAC mode |
|---------|-------------------|
| охлаждение, охлажд, холод | **cool** |
| обогрев, обогр, тепло, гре, нагрев | **heat** |
| авто, автоматический | **auto** |
| сушка, сух, осушение | **dry** |
| вентиляция, вентил, проветривание | **fan_only** |

**Пример:** Команда `«кондиционер режим охлаждение»` → `set_ac_mode(mode="cool")`.

### 3.5 Covers: шторы → curtains, жалюзи → blinds

В HA entity_id шторы и жалюзи различаются суффиксом:

| Инструмент | HA domain | entity_template |
|-----------|-----------|-----------------|
| `open_curtains` / `close_curtains` | `cover` | `cover.{room}_curtains` |
| `raise_blinds` / `lower_blinds` / `set_blinds_position` / `set_blinds_angle` | `cover` | `cover.{room}_blinds` |

### 3.6 Garden: полив → irrigation

| Инструмент | HA domain | entity_template |
|-----------|-----------|-----------------|
| `start_irrigation_zone` / `stop_irrigation_zone` | `switch` | `switch.irrigation_zone_{zone}` |
| `query_soil_moisture` | `sensor` | `sensor.soil_moisture_zone_{zone}` |

Русские команды вида `«включи полив газона»` роутятся в `start_irrigation_zone`, парсер извлекает `zone`, HA Bridge подставляет в `switch.irrigation_zone_{zone}`.

### 3.7 Outlets: розетка → outlet

| Инструмент | HA domain | entity_template |
|-----------|-----------|-----------------|
| `toggle_outlet` | `switch` | `switch.{room}_outlet` |

Русские команды `«включи розетку»` и `«выключи розетку»` роутятся в `toggle_outlet` (toggle = переключить).

---

## 4. API v2

API-сервер работает на порту **8126** (переменная `VH_PORT`).

### 4.1 Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/command` | Текстовая команда → router → parser → HA |
| `GET` | `/health` | Статус системы (router, parser, HA bridge) |
| `GET` | `/tools` | Список 53 инструментов с описаниями |
| `GET` | `/entities?domain=` | Сущности HA (опциональный фильтр по домену) |
| `POST` | `/ha/call` | Прямой вызов HA service |
| `GET` | `/history?limit=20` | История последних команд (in-memory, max 100) |
| `WS` | `/ws` | WebSocket: real-time push + приём команд |
| `GET` | `/panel` | Web Dashboard (отдаёт static/index.html) |

### 4.2 POST /command

Основной эндпоинт. JSON-запрос:

```json
{
  "text": "включи свет в гостиной",
  "live": false
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | `string` | Текстовая команда (RU или EN) |
| `live` | `bool` | `true` → реальный вызов HA, `false` → dry run |

JSON-ответ:

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

| Поле | Тип | Описание |
|------|-----|----------|
| `tool` | `string` | Имя инструмента (52 инструмента или `none`) |
| `arguments` | `object` | Аргументы (комнаты, двери, температура и т.д.) |
| `ha_call` | `object\|null` | Готовый вызов для HA API (`domain`, `service`, `entity_id`, `service_data`) |
| `latency_s` | `float` | Время обработки (секунды) |
| `used_fallback` | `bool` | `true` = Qwen3:8B fallback использовался |

**Примеры:**

```bash
# Включить свет (RU)
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "включи свет в гостиной"}'

# Установить температуру (EN)
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "set bedroom to 22 degrees"}'

# Кондиционер на охлаждение (RU)
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"text": "кондиционер режим охлаждение"}'
```

### 4.3 GET /history

Возвращает историю последних обработанных команд. Параметр `limit` (по умолчанию 20, макс. 100).

```bash
curl http://localhost:8126/history?limit=10
```

Ответ — массив объектов:
```json
[
  {
    "timestamp": "2026-05-16T07:30:00",
    "text": "включи свет в гостиной",
    "tool": "turn_on_light",
    "arguments": {"room": "living_room"},
    "latency_s": 0.3
  }
]
```

> ⚠️ Хранится в RAM. При перезапуске сервера история теряется.

### 4.4 WS /ws

WebSocket для real-time взаимодействия.

**Подключение:**
```javascript
const ws = new WebSocket('ws://localhost:8126/ws');
```

**Протокол:**

| Направление | Сообщение | Описание |
|-------------|-----------|----------|
| Сервер → Клиент | `{"type": "init", "tools_count": 53, "history": [...]}` | При подключении |
| Клиент → Сервер | `/command <text>` | Текстовая команда |
| Сервер → Клиент | `{"type": "result", ...}` | Результат обработки |
| Сервер → Клиент | `{"type": "broadcast", ...}` | Push при POST /command от другого клиента |
| Клиент → Сервер | `ping` | Проверка соединения |
| Сервер → Клиент | `{"type": "pong"}` | Ответ на ping |

### 4.5 GET /panel

Отдаёт `static/index.html` — веб-панель управления. См. [раздел 5](#5-веб-панель-управления).

```bash
# Открыть в браузере
http://localhost:8126/panel
```

### 4.6 POST /ha/call (прямой вызов HA)

Для прямого управления HA без обработки NLP:

```bash
curl -X POST http://localhost:8126/ha/call \
  -H 'Content-Type: application/json' \
  -d '{
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.living_room"
  }'
```

---

## 5. Веб-панель управления

Открой **http://localhost:8126/panel** — тёмная тема, 8 вкладок с устройствами.

### 5.1 Структура панели

```
┌─────────────────────────────────────────────┐
│  Vector Home v2          🟢 WS  🟢 HA  53⚙  │
├─────────────────────────────────────────────┤
│  [ Введите команду...               ] [▶][🎤]│
├─────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐    │
│  │  Результат:                         │    │
│  │  tool: turn_on_light                │    │
│  │  args: {room: "living_room"}        │    │
│  │  ha_call: light.turn_on             │    │
│  │  latency: 0.3s                     │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  💡 Свет │ 🌡️ Климат │ 🪟 Шторы │ 🤖 Пылесос│
│  🔒 Охрана│ 🎵 Медиа  │ 🌿 Сад   │ ⚡ Другое │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │ 📋 История                         │    │
│  │ 13:02 включи свет → turn_on_light   │    │
│  │ 13:01 поставь 22° → set_temperature│    │
│  └─────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│  v2.0.0 · 53 tools · WebSocket: connected   │
└─────────────────────────────────────────────┘
```

### 5.2 8 групп устройств

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

### 5.3 Функции Dashboard

- **Командная строка** — текстовый ввод + кнопка отправки
- **Голосовой ввод** — кнопка 🎤, Web Speech API (браузерный SpeechRecognition)
- **Результат** — карточка с разобранной командой: инструмент, аргументы, HA-вызов, задержка
- **Вкладки устройств** — 8 кнопок с иконками. При клике появляются карточки с привязанными командами
- **История** — список последних команд, кликабельный для повтора
- **Статусы** — точки: WebSocket (зелёная/красная), HA (зелёная/красная), счётчик инструментов
- **Real-time** — WebSocket push новых результатов
- **Тёмная тема** — CSS variables, адаптив mobile-first

### 5.4 Файлы Dashboard

| Файл | Описание |
|------|----------|
| `static/index.html` | SPA с 8 группами устройств |
| `static/style.css` | Тёмная тема, CSS variables, адаптив |
| `static/app.js` | WebSocket + голосовой ввод (Web Speech API) |

---

## 6. Parser: Fuzzy Match

Parser v2 использует **fuzzy match** для коррекции галлюцинаций GPT-2 имена инструментов.

### 6.1 Алиасы (`FUZZY_TOOLS_MAP`)

| Галлюцинация GPT-2 | Корректное имя |
|--------------------|--------------------|
| `start_vacuum_cleaner` | `vacuum_start` |
| `stop_vacuum_cleaner` | `stop_vacuum` |
| `dock_vacuum_cleaner` | `dock_vacuum` |
| `turn_on_lights` | `turn_on_light` |
| `turn_off_lights` | `turn_off_light` |
| `set_thermostat_mode` | `set_thermostat` |
| `set_ac_temperature` | `set_ac_mode` |
| `set_temperature_room` | `set_temperature` |
| `query_temperature_room` | `query_temperature` |
| `turn_on_music` | `play_music` |
| `turn_off_music` | `stop_music` |
| `cancel_timer` | `cancel_alarm` |
| `set_timer` | `set_alarm` |
| `arm_alarm` | `arm_alarm_system` |
| `disarm_alarm` | `disarm_alarm_system` |
| `turn_on_humidifier` | `toggle_humidifier` |
| `turn_off_humidifier` | `toggle_humidifier` |
| `turn_on_dehumidifier` | `toggle_dehumidifier` |
| `turn_off_dehumidifier` | `toggle_dehumidifier` |

### 6.2 Prefix Match

Если GPT-2 выдаёт имя инструмента, которого нет в `FUZZY_TOOLS_MAP`, но оно является префиксом корректного имени — сработает prefix match:

```
"turn_on_ligh"  →  "turn_on_light"
"vacuum"        →  "vacuum_start"  (если "vacuum" — префикс)
```

### 6.3 Приоритет Router

Router имеет **приоритет** над GPT-2. Даже если парсер ошибается в имени инструмента, router name из `route()` всегда побеждает:

```python
result["name"] = tool_name  # Override GPT-2 output with router selection
```

---

## 7. Замечание о `\b` для кириллицы

> **⚠️ Критический баг Python regex:** `\b` (word boundary) некорректно работает с кириллицей в `re.IGNORECASE`.

### Проблема

Python regex движок не распознаёт Unicode-символы (кириллицу) как `\w` в сочетании с `\b` при включённом `re.IGNORECASE`. Это приводит к **ложным негативам** — паттерн вида `\bсвет\b` не матчит слово «свет» в строке «включи свет в гостиной».

### Решение в v2

**Все RU-паттерны используют bare text без `\b`.** EN-подстроки (например, `irrigat`) также без `\b`.

```python
# ❌ НЕПРАВИЛЬНО (старый код):
(r"\bсвет\b", "turn_on_light"),
(r"\bсвет\s+выкл\b", "turn_off_light"),

# ✅ ПРАВИЛЬНО (v2):
(r"свет", "turn_on_light"),
(r"выключи\s+свет", "turn_off_light"),
```

**Правило приоритета (ORDER MATTERS):** Более специфичные паттерны расположены раньше общих. Это гарантирует, что `выключи свет` → `turn_off_light`, а не `turn_on_light`.

### Проверка

130 тестов pytest включают `TestCyrillicWordBoundary` — набор регрессионных тестов, подтверждающих корректность:

```python
class TestCyrillicWordBoundary:
    def test_russian_light_on(self, router):
        assert router.route("включи свет в гостиной")[0] == "turn_on_light"

    def test_russian_humidity_query(self, router):
        # «какая влажность» → query, не set_humidity_target
        result, _ = router.route("какая влажность на кухне")
        assert result == "query_humidity"

    def test_russian_ac_mode(self, router):
        # «кондиционер режим охлаждения» → set_ac_mode
        result, _ = router.route("кондиционер режим охлаждения")
        assert result == "set_ac_mode"

    def test_russian_outlet(self, router):
        # «включи розетку» → toggle_outlet, НЕ turn_on_light
        result, _ = router.route("включи розетку")
        assert result == "toggle_outlet"

    def test_russian_irrigation(self, router):
        # «включи полив газона» → start_irrigation_zone
        assert router.route("включи полив газона")[0] == "start_irrigation_zone"
```

---

## 8. Тесты

### 8.1 Запуск

```bash
cd ~/projects/vector-home
python -m pytest tests/test_router.py -v
```

### 8.2 Структура тестов (130 тестов)

| Класс | Количество | Описание |
|-------|-----------|----------|
| `TestRouterTestCases` | 95 | parametrized — все TEST_CASES |
| `TestCyrillicWordBoundary` | 8 | Регрессия `\b` для кириллицы |
| `TestRuleOrdering` | 8 | Приоритет правил (query→set, dim→off, thermostat→AC) |
| `TestEdgeCases` | 7 | Пограничные случаи (пустая строка, регистр, пунктуация) |
| `TestAllToolsListed` | 3 | Структурная проверка ALL_TOOLS |
| `TestRuleIntegrity` | 2 | Целостность правил (валидные инструменты, покрытие) |
| `TestHABridgeMapping` | 5 | Проверка HA маппингов и RU→EN перевода |
| `TestParserSpec` | 2 | Проверка tools_spec_v2.json |

**Итого: 130/130 ✓**

### 8.3 Ключевые проверки

```python
# Router: 100% точность (95/95 TEST_CASES)
# HA Bridge: полный маппинг 52 инструментов → HA
# Cyrillic \b: все RU-паттерны без \b
# Fuzzy match: коррекция галлюцинаций GPT-2
# Rule ordering: специфичные паттерны раньше общих
```

---

## 9. Установка и запуск

### 9.1 Требования

| | Минимум | Рекомендуется |
|---|---------|---------------|
| CPU | Любой x86_64 | 4+ ядра |
| RAM | 600 MB (только парсер) | 6 GB (с Qwen3 fallback) |
| Диск | 1.5 GB | 2 GB |
| GPU | Не нужен | — |
| Python | 3.10+ | 3.12 |
| Интернет | Не нужен | Для Ollama fallback |

### 9.2 Установка

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt
```

### 9.3 Проверка

```bash
# 130 тестов — все должны пройти ✓
python -m pytest tests/test_router.py -v
```

### 9.4 Запуск

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

### 9.5 Live-режим (с реальным HA)

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_token_here"
python -m src.api --live
```

---

## 10. Подключение к Home Assistant

### 10.1 Long-Lived Access Token

1. Открой HA → Профиль (левое меню, внизу) → Безопасность
2. Прокрути до «Долгосрочные токены доступа»
3. Нажми «Создать токен» → назови `Vector Home`
4. Скопируй токен (показывается один раз!)

### 10.2 Entity ID

Переименуйте entity_id в HA для соответствия маппингам:

| Домен | Шаблон | Пример |
|-------|--------|--------|
| Свет | `light.{room}` | `light.living_room`, `light.bedroom` |
| Климат | `climate.{room}` | `climate.bedroom`, `climate.living_room_ac` |
| Шторы | `cover.{room}_curtains` | `cover.bedroom_curtains` |
| Жалюзи | `cover.{room}_blinds` | `cover.kitchen_blinds` |
| Замки | `lock.{door}` | `lock.front_door`, `lock.back_door` |
| Медиа | `media_player.{room}` | `media_player.kitchen` |
| ТВ | `media_player.{room}_tv` | `media_player.living_room_tv` |
| Пылесос | `vacuum.robot` | `vacuum.robot` |
| Полив | `switch.irrigation_zone_{zone}` | `switch.irrigation_zone_1` |
| Сигнализация | `alarm_control_panel.home` | `alarm_control_panel.home` |
| Розетки | `switch.{room}_outlet` | `switch.kitchen_outlet` |

---

## 11. Известные ограничения

### 11.1 Потолок 53 инструментов для regex Router

Router v2 использует 95 regex-правил для 53 интентов. При расширении количества интентов свыше **53–60** regex-правила становятся неуправляемыми: растёт количество конфликтов, ложных срабатываний и сложность поддержки. Дальнейшее расширение потребует перехода на **Qwen3:8B (Ollama)** как основной классификатор.

### 11.2 GPT-2 контекст = 1024 токена

Prompt с более чем ~4 инструментами одновременно переполняет контекст GPT-2. **Single-tool routing** (через Router) — единственный надёжный режим. Multi-tool без fallback даёт ~8% точности.

### 11.3 Cyrillic `\b`

Python `re.IGNORECASE` некорректно обрабатывает `\b` для Unicode-символов (кириллица). **Решение:** все RU-паттерны используют bare text без `\b`. EN-подстроки также без `\b`. Это учтено в v2, но при написании новых regex-правил **не используйте `\b` для русских слов**.

### 11.4 Оффлайн-only при CPU

Ollama fallback (Qwen3:8B) требует ~5 GB RAM и GPU / долгий CPU-вывод. Без Ollama недоступен multi-intent fallback.

### 11.5 HA_entity_map использует шаблоны

Entity ID вида `light.{room}` требуют точного совпадения имени комнаты с HA entity. При несовпадении — dry run вернёт шаблон без реального вызова.

### 11.6 In-memory history

История команд хранится в RAM (max 100 записей). При перезапуске API история теряется.

### 11.7 Падежи

GPT-2 выдаёт русские аргументы в косвенных падежах (`гостиной`, `кухне`, `спальне`). HA Bridge автоматически маппит эти формы через `RU_ROOM_MAP`. При появлении новых форм — добавьте в `RU_ROOM_MAP` / `RU_DOOR_MAP` / `RU_SCENE_MAP` / `RU_AC_MODE_MAP`.

---

## 12. Устранение неполадок

### Команды не распознаются

1. Проверь, что сервер запущен: `curl http://localhost:8126/health`
2. Попробуй простые команды: `turn on the lights`, `включи свет`
3. Проверь кодировку: русские буквы в UTF-8
4. Проверь, что нет `\b` в regex-шаблонах для кириллицы

### HA не отвечает

1. Проверь `HA_URL` — открой `http://homeassistant.local:8123` в браузере
2. Проверь `HA_TOKEN` — создай новый, если старый не работает
3. В dry run-режиме (без токена) команды парсятся, но не отправляются в HA

### Ollama fallback не работает

1. Убедись, что Ollama запущен: `ollama serve`
2. Скачай модель: `ollama pull qwen3:8b`
3. Проверь порт: по умолчанию `localhost:11434`

### Парсер возвращает `none({})`

**Причина:** передан неверный `tool_name`. `parse(utterance, tool_name)` использует `tool_name` для формирования промпта — если инструмент не найден в `tools_spec_v2.json`, модель не получает spec.

**Решение:** всегда запускать через `router.route()` → `parser.parse()`.

### `entity_id` содержит кириллицу

**Причина:** `_normalize()` не нашёл маппинг для данного значения аргумента.

**Решение:** добавьте форму в `RU_ROOM_MAP` / `RU_DOOR_MAP` / `RU_SCENE_MAP` / `RU_AC_MODE_MAP` в `src/ha_bridge.py`.

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|---------------|
| `HA_URL` | URL Home Assistant | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | (пусто = dry run) |
| `VH_PORT` | Порт API-сервера | `8126` |
| `GPT2_REPO` | Путь к gpt2-tool-call | `../gpt2-tool-call` |

---

## Файловая структура v2

```
vector-home/
├── src/
│   ├── router.py                # HomeRouter v2 — 95 rules, 53 intents, EN+RU
│   ├── parser.py                # HomeParser — GPT-2 124M, fuzzy match
│   ├── pipeline.py              # process() — router → parser → HA bridge
│   ├── api.py                   # FastAPI + WebSocket + /panel + /history
│   ├── ha_bridge.py             # HABridge — 53 mappings, RU→EN
│   └── voice.py                 # VoicePipeline — STT → pipeline → TTS
├── static/
│   ├── index.html               # Web Dashboard — 8 device groups
│   ├── style.css                # Dark theme, responsive
│   └── app.js                   # WebSocket real-time + voice input
├── data/
│   ├── tools_spec_v2.json       # 53 tool definitions
│   ├── train_dataset_v2.json    # 1000 merged training examples
│   └── test_dataset_v2.json     # Test split
├── models/
│   ├── smart_home_v2.pt          # GPT-2 v2 weights
│   ├── gpt2_ha_best.pt           # GPT-2 v1 EN FT weights
│   ├── gpt2_ha_ru_best.pt        # GPT-2 v1 RU+EN FT weights
│   └── voices/                    # Piper voice models
├── tests/
│   └── test_router.py            # 130 pytest tests
├── docs/
│   ├── SPEC.md                   # Техническое задание
│   ├── USER_GUIDE.md             # Это руководство
│   └── HARDWARE_GUIDE.md         # Выбор оборудования
└── requirements.txt
```

---

> 📄 [SPEC.md](SPEC.md) — техническое задание (архитектура, спецификации)  
> 🔧 [HARDWARE_GUIDE.md](HARDWARE_GUIDE.md) — выбор оборудования, ESPHome, инструкции  
> 🧪 `python -m pytest tests/test_router.py -v` — запуск 130 тестов