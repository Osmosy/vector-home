# CCOSTAN ↔ Vector Home: стыковочный документ

Какие автоматизации из Home-AssistantConfig выиграют от GPT-2 124M tool calling, и как именно.

## Сводная таблица

| Автоматизация | Текущий подход | GPT-2 улучшение | Эффект |
|--------------|---------------|-----------------|--------|
| LLMVision (garage/front door) | OpenAI Vision напрямую | GPT-2 классифицирует сцену ЛОКАЛЬНО → Vision API только для сложных случаев | -80% API-вызовов, -$cost |
| Alarm (multi-sensor) | Жёсткая логика состояний | GPT-2 интерпретирует комбинацию сенсоров → адаптивная логика | Меньше false positives |
| Climate (dual-zone) | Фиксированные пороги | GPT-2 предсказывает потребность в нагреве/охлаждении по погоде и паттернам | Экономия энергии |
| Presence (multi-sensor) | Пороговая логика PIR+door | GPT-2 fusion: PIR + дверь + время суток + календарь → точный presence | -false positives на 30-50% |
| Maintenance Log | Webhook + шаблоны | GPT-2 парсит свободный текст (SMS/email) → структурированное событие | Ручной ввод → авто |
| Voice commands | Whisper → жёсткий intent matching | Whisper → GPT-2 tool calling (Vector Home) | Гибкий NLU без облака |

## Подробно по каждой

### 1. LLMVision → GPT-2 + LLMVision

**Сейчас:** Каждое движение у гаража → API-вызов OpenAI Vision ($). Rate-limit через `input_datetime.last_run`.

**С GPT-2:** Камера → GPT-2 классифицирует «мусорные баки выкачены / не выкачены» локально (бесплатно, ~2s на CPU). Только если GPT-2 не уверен — fallback на OpenAI Vision.

**Интеграция:**
```python
# Вместо прямого вызова llmvision:
scene = capture_camera()
result = gpt2_tool_call("classify_scene", scene, tool="garage_cans_check")
if result.confidence < 0.9:
    result = openai_vision(scene)  # fallback
```

### 2. Alarm → GPT-2 Sensor Fusion

**Сейчас:** Фиксированные правила: `IF door_open AND time > 22:00 → alert`.

**С GPT-2:** Комбинация сенсоров подаётся как tool call: `assess_security(door=open, window=closed, time=14:30, presence=away, motion=kitchen)`. GPT-2 выдаёт: `{action: "silent_alert", reason: "motion in kitchen while away"}`.

**Интеграция:**
```python
sensors = {
    "front_door": "open",
    "motion_kitchen": "detected",
    "presence": "away",
    "time": "14:30"
}
response = gpt2_tool_call("assess_security", **sensors)
if response["action"] != "ignore":
    trigger_automation(response["action"], response["reason"])
```

### 3. Climate → GPT-2 Predictive Control

**Сейчас:** Термостат по расписанию или фиксированной температуре.

**С GPT-2:** Контекст: текущая t°, погода на 3 часа, история за неделю, presence. GPT-2: `{action: "precool", target: 76, reason: "heat wave in 2h, occupants arrive 16:00"}`.

**Интеграция:**
```python
context = {
    "indoor_temp": 77, "outdoor_temp": 92,
    "weather_forecast": "sunny, 95°F peak",
    "presence": "arriving_16:00",
    "time": "14:00"
}
decision = gpt2_tool_call("climate_decision", **context)
set_thermostat(decision["target_temp"], decision["mode"])
```

### 4. Presence → GPT-2 Sensor Fusion

**Сейчас:** PIR + door sensor с пороговой логикой. False positives от солнца, животных, сквозняка.

**С GPT-2:** Multi-sensor fusion: PIR + дверь + время + день недели + календарь + история. GPT-2 выдаёт confidence score.

### 5. Maintenance Log → GPT-2 Free-Text Parsing

**Сейчас:** Структурированный webhook от специального клиента (Joanna).

**С GPT-2:** Любой свободный текст (SMS, email, голос) → GPT-2: `{item: "water_softener_salt", action: "add", amount: 80, unit: "lb"}`.

```python
raw_text = "досыпал соль в фильтр, где-то полмешка"
result = gpt2_tool_call("parse_maintenance", text=raw_text)
# → {item: "water_softener_salt", amount: 40, unit: "lb"}
webhook_to_ha(result)
```

### 6. Voice Commands → Vector Home Full Stack

**Сейчас:** Whisper → жёсткий intent matching (if "включи свет" → light.turn_on).

**С GPT-2:** Whisper → GPT-2 tool calling (Vector Home). Понимает вариации: «свет на кухне потуши», «темно на кухне», «кухня, свет, выкл» → один tool call `light_control`.

## Приоритет внедрения

| Приоритет | Автоматизация | Причина |
|-----------|--------------|--------|
| P0 | LLMVision fallback | Прямая экономия денег на API |
| P1 | Voice commands | Уже готово в Vector Home |
| P2 | Sensor fusion (alarm/presence) | Снижение false positives |
| P3 | Climate predictive | Экономия энергии |
| P4 | Maintenance parsing | Удобство, не критично |

## Ссылки

- CCOSTAN Home-AssistantConfig: https://github.com/CCOSTAN/Home-AssistantConfig
- Vector Home: https://github.com/Osmosy/vector-home
- gpt2-tool-call: https://github.com/barometech/gpt2-tool-call
