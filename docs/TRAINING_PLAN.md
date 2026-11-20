# План обучения Qwen3-4B для Vector Home

Статус: ожидает запуска
Дата плана: 2026-06-28
Скилл: mlops/qwen3-lora-finetune

## Текущее состояние

| Компонент            | Статус     | Детали                                      |
|---------------------|------------|----------------------------------------------|
| Датасет (unified)    | ✅ Готов   | 2353 примера, 52 инструмента, EN+RU         |
| Датасет на GitHub    | ✅ Залит   | raw.githubusercontent.com/Osmosy/vector-home |
| Colab pipeline       | ✅ Написан | cell_all_in_one.py (179 строк)               |
| Модель Qwen3-4B      | ❌ Нет     | Не обучена                                   |
| GGUF файл            | ❌ Нет     | Не создан                                    |
| Ollama модель        | ❌ Нет     | Не загружена                                 |
| Парсер переключён    | ❌ Нет     | Всё ещё GPT-2                                |

## Что делаем

Обучаем Qwen3-4B с LoRA на Colab (T4 GPU, бесплатно).
Модель будет принимать голосовые команды умного дома и возвращать JSON tool calls.

## Порядок действий (2 часа от начала до работающей модели)

### Этап 1 — Обучение на Colab (~30 мин)

1. Открыть https://colab.research.google.com
2. Среда выполнения → T4 GPU
3. Вставить в ячейку и запустить:
   ```
   !curl -sL https://raw.githubusercontent.com/Osmosy/vector-home/main/docs/colab/cell_all_in_one.py | python3
   ```
4. Дождаться надписи "=== DONE! ===" и HTTP-сервера на порту 8888
5. Скачать smart-home-v2-merged.tar (~2.5 GB)

Если браузер падает при скачивании:
- Альтернатива: залить на HuggingFace
  ```python
  model.push_to_hub_gguf("Osmosy/smart-home-v2", quantization_method=["q4_k_m"], token="...")
  ```

### Этап 2 — Конвертация в GGUF (~20 мин, ноутбук)

```bash
# Распаковать
cd /tmp && tar xf ~/Downloads/smart-home-v2-merged.tar

# Конвертировать 16-bit → GGUF (нужен llama.cpp)
python3 llama.cpp/convert_hf_to_gguf.py /tmp/merged_model \
    --outfile /tmp/smart-home-v2-f16.gguf --outtype f16

# Квантовать Q4_K_M
llama.cpp/build/bin/llama-quantize \
    /tmp/smart-home-v2-f16.gguf /tmp/smart-home-v2-Q4_K_M.gguf Q4_K_M
```

### Этап 3 — Загрузка в Ollama (~5 мин)

```bash
cat > /tmp/Modelfile.smart-home-v2 << 'EOF'
FROM /tmp/smart-home-v2-Q4_K_M.gguf
PARAMETER temperature 0.1
PARAMETER num_ctx 512
PARAMETER stop "<|im_end|>"
SYSTEM """You are a smart home assistant. You receive natural language commands and respond with JSON tool calls.
Available tools: turn_on_light, turn_off_light, dim_light, set_light_color, set_light_temperature_k, set_light_scene, blink_light, query_light_state, set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, set_humidity_target, toggle_humidifier, toggle_dehumidifier, query_humidity, open_curtains, close_curtains, raise_blinds, lower_blinds, set_blinds_position, set_blinds_angle, vacuum_start, stop_vacuum, dock_vacuum, lock_door, unlock_door, query_door_status, arm_alarm_system, disarm_alarm_system, query_alarm_status, trigger_panic_alarm, play_music, stop_music, pause_music, play_radio_station, set_volume, mute_audio, turn_on_tv, turn_off_tv, set_tv_channel, start_irrigation_zone, stop_irrigation_zone, query_soil_moisture, set_alarm, cancel_alarm, activate_scene, toggle_outlet, query_air_quality, set_motion_sensitivity

If the command is not a smart home command, respond with: {"name": "none", "arguments": {}}
Respond ONLY with JSON, no explanations."""
EOF

ollama create smart-home-v2 -f /tmp/Modelfile.smart-home-v2

# Проверить
ollama run smart-home-v2 "включи свет в спальне"
# Ожидаемый ответ: {"name":"turn_on_light","arguments":{"room":"спальне"}}
```

### Этап 4 — Интеграция с Vector Home (~10 мин)

В src/parser.py (или точке входа) заменить:

```python
# Было
parser = HomeParser(model_path="models/smart_home_v2.pt")

# Стало
parser = HomeParser(model="smart-home-v2", use_ollama=True)
```

## Ожидаемые результаты

| Метрика              | GPT-2 124M (сейчас) | Qwen3-4B LoRA (цель) |
|---------------------|--------------------|-----------------------|
| Параметры            | 124M               | 4B (33M обучаемых)    |
| Инференс             | ~2 сек (CPU)       | ~0.5 сек (CPU)        |
| Точность (EN)        | ~85%               | ~95%                  |
| Точность (RU)        | ~70%               | ~90%                  |
| Размер модели        | 475 MB             | ~2.5 GB (Q4_K_M)      |
| VRAM при обучении    | не нужно           | ~10 GB (T4)           |

## Примечания

- Qwen3-8B НЕ ИСПОЛЬЗОВАТЬ — не влезает в T4 (14.5 GB VRAM)
- Датасет уже на GitHub, Colab скачает автоматически
- Если Colab сессия упадёт — перезапустить, модель докачается из кэша
- GGUF после создания сохранить в надёжное место (~/models/)
- После обучения старые GPT-2 чекпоинты можно удалить (освободить ~2.5 GB)
