# 🧠 Fine-Tune Qwen3-4B для Vector Home — Полная Инструкция

## Обзор процесса

```
Твой ноутбук                                    Google Colab (бесплатно)
┌──────────────────┐                           ┌──────────────────────┐
│ Датасет          │ ── загружаешь ──────────► │ LoRA fine-tune      │
│ 2353 примеров    │                           │ Qwen3-4B, 3 эпохи   │
│ 52 инструмента   │                           │ ~20-25 мин на T4    │
│ EN + RU          │                           │                      │
└──────────────────┘                           └──────┬───────────────┘
                                                      │ GGUF файл (~2.5 GB)
                                              ◄──────┘ скачиваешь
┌──────────────────┐
│ Ollama           │
│ ollama create  │ ── модель готова
│ smart-home-v2   │
└──────────────────┘
```

## Что нужно заранее

1. **Google аккаунт** — для Colab
2. **5 GB свободного места** — для GGUF файла

---

## ШАГ 1: Запустить Colab

1. Открой **https://colab.research.google.com**
2. **Файл** → **Создать блокнот**
3. **Среда выполнения** → **Изменить тип среды выполнения** → **Аппаратный ускоритель: T4 GPU**

---

## ШАГ 2: Одна ячейка — весь пайплайн

Скопируй **одну команду** в ячейку и запусти:

```
!curl -sL https://raw.githubusercontent.com/Osmosy/vector-home/main/docs/colab/cell_all_in_one.py | python3
```

Эта команда:
1. Установит Unsloth и все зависимости
2. Загрузит Qwen3-4B (4-bit)
3. Добавит LoRA адаптер (rank 16)
4. Скачает датасет из GitHub
5. Обучит 3 эпохи (~20-25 мин)
6. Сольёт LoRA с моделью
7. Экспортирует GGUF (Q4_K_M)
8. Скачает файл в браузер

**Время: ~25-30 минут.** Ничего не нажимай пока не появится окно скачивания файла.

---

## Типичные проблемы и решения

### ❌ ValueError: "Some modules are dispatched on the CPU or the disk"

**Причина:** Модель не влезает в VRAM T4 (14.5 GB).

**Решение:** Используй `cell_all_in_one.py` — там Qwen3-4B (влезает). Старые ячейки cell1–cell6 содержат Qwen3-8B — **не используй их**.

### ❌ ModuleNotFoundError: No module named 'unsloth'

**Причина:** Зависимости не установлены.

**Решение:** `cell_all_in_one.py` включает `pip install` в начале. Если запускаешь код вручную — сначала установи:

```python
!pip install -q unsloth transformers>=4.47.0 bitsandbytes peft accelerate trl datasets
!pip install -q --no-deps unsloth_zoo
```

### ❌ NameError: name 'model' is not defined

**Причина:** Сеанс Colab перезапустился — переменные потеряны.

**Решение:** Перезапусти весь пайплайн через `cell_all_in_one.py`. Colab не хранит переменные между сеансами.

### ❌ SyntaxError: invalid character '─'

**Причина:** Скопировал код из терминала — спецсимволы box-drawing ломают Python.

**Решение:** Копируй код только через raw-ссылку GitHub:
```
https://raw.githubusercontent.com/Osmosy/vector-home/main/docs/colab/cell_all_in_one.py
```

### ❌ T4 OOM (Out of Memory)

**Причина:** Qwen3-8B не влезает даже в 4-bit на T4 (14.5 GB VRAM).

**Решение:** Только Qwen3-4B! Проверь что в коде `model_name = "unsloth/Qwen3-4B"`, а не `Qwen3-8B`.

### ❌ GGUF не скачивается из Colab

**Причина:** Файл ~2.5 GB, браузер может упасть по таймауту.

**Альтернатива — загрузить на HuggingFace:**

```python
model.push_to_hub_gguf(
    "ТВОЙ_НИК/smart-home-v2-qwen3-4b",
    quantization_method=["q4_k_m"],
    token="hf_твой_токен",  # https://huggingface.co/settings/tokens
)
```

Потом на ноутбуке:
```bash
ollama pull hf.co/ТВОЙ_НИК/smart-home-v2-qwen3-4b:Q4_K_M
```

### ❌ Модель плохо отвечает на русском

**Решение:** Увеличь LoRA rank до 32 или добавь эпох (5 вместо 3). Проверь что `unified_train.json` содержит RU примеры (695 шт).

---

## ШАГ 3: Установка модели в Ollama

На ноутбуке, после скачивания GGUF:

### 3.1. Создать Modelfile

```bash
cat > /tmp/Modelfile.smart-home-v2 << 'EOF'
FROM ./unsloth.Q4_K_M.gguf

PARAMETER temperature 0.1
PARAMETER num_ctx 512
PARAMETER stop "<|im_end|>"

SYSTEM """You are a smart home assistant. You receive natural language commands and respond with JSON tool calls.

Available tools: turn_on_light, turn_off_light, dim_light, set_light_color, set_light_temperature_k, set_light_scene, blink_light, query_light_state, set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, set_humidity_target, toggle_humidifier, toggle_dehumidifier, query_humidity, open_curtains, close_curtains, raise_blinds, lower_blinds, set_blinds_position, set_blinds_angle, vacuum_start, stop_vacuum, dock_vacuum, lock_door, unlock_door, query_door_status, arm_alarm_system, disarm_alarm_system, query_alarm_status, trigger_panic_alarm, play_music, stop_music, pause_music, play_radio_station, set_volume, mute_audio, turn_on_tv, turn_off_tv, set_tv_channel, start_irrigation_zone, stop_irrigation_zone, query_soil_moisture, set_alarm, cancel_alarm, activate_scene, toggle_outlet, query_air_quality, set_motion_sensitivity

If the command is not a smart home command, respond with: {"name": "none", "arguments": {}}

Respond ONLY with JSON, no explanations."""
EOF
```

### 3.2. Создать модель

```bash
# GGUF файл из загрузок браузера
GGUF_FILE=$(find ~/Downloads -name "unsloth.Q4_K_M.gguf" | head -1)

if [ -z "$GGUF_FILE" ]; then
    echo "GGUF не найден в ~/Downloads/"
    exit 1
fi

# Копируем рядом с Modelfile
cp "$GGUF_FILE" /tmp/unsloth.Q4_K_M.gguf
cd /tmp
ollama create smart-home-v2 -f Modelfile.smart-home-v2

# Проверяем
ollama list | grep smart-home
```

### 3.3. Тест

```bash
ollama run smart-home-v2 "Turn on the lights in the kitchen"
# → {"name": "turn_on_light", "arguments": {"room": "kitchen"}}

ollama run smart-home-v2 "включи свет на кухне"
# → {"name": "turn_on_light", "arguments": {"room": "kitchen"}}

ollama run smart-home-v2 "расскажи анекдот"
# → {"name": "none", "arguments": {}}
```

---

## ШАГ 4: Подключить к Vector Home

Обновить парсер — переключить с GPT-2 на Ollama:

```python
# Было (GPT-2 124M):
# parser = HomeParser(model_path="models/smart_home_v2.pt")

# Стало (Qwen3-4B через Ollama):
# parser = HomeParser(model="smart-home-v2", use_ollama=True)
```

---

## Результаты тренировки (реальные)

| Метрика | GPT-2 124M | Qwen3-4B LoRA |
|---------|-----------|---------------|
| Loss (3 эпохи) | N/A | 1.98 → 0.097 |
| Время обучения | 2 ч CPU | 21 мин T4 |
| Параметры (обучаемые) | 124M (все) | 33M (0.81%) |
| Размер GGUF | 475 MB | ~2.5 GB |

---

## Структура файлов

```
vector-home/
├── data/
│   ├── train_dataset.json          # Оригинальный EN датасет (658)
│   ├── train_dataset_v2.json       # Расширенный EN (1000)
│   ├── train_dataset_ru.json       # Русский датасет (695)
│   ├── unified_train.json          # Объединённый train (2117)
│   └── unified_eval.json           # Объединённый eval (236)
├── docs/
│   ├── FINETUNE_GUIDE.md           # ← Эта инструкция
│   └── colab/
│       ├── cell_all_in_one.py      # ← Единая ячейка (используй эту!)
│       ├── cell_export_only.py    # Только экспорт GGUF
│       └── cell1-6 (устарели)     # Старые ячейки с Qwen3-8B — НЕ ИСПОЛЬЗОВАТЬ
└── src/
    ├── parser.py                   # Парсер команд
    ├── api.py                      # FastAPI сервер (:8765)
    └── gpt2_core/                  # GPT-2 движок (фолбэк)
```

---

## Что делает cell_all_in_one.py

```python
# 1. Установка зависимостей
pip install unsloth, transformers, bitsandbytes, peft, accelerate, trl, datasets

# 2. Очистка VRAM
torch.cuda.empty_cache() + gc.collect()
PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

# 3. Загрузка Qwen3-4B (4-bit, LoRA rank=16)
model_name = "unsloth/Qwen3-4B"      # НЕ Qwen3-8B — не влезет на T4!
max_seq_length = 512
load_in_4bit = True
lora_dropout = 0                      # 0 для максимального качества
target_modules = [q,k,v,o,gate,up,down]_proj

# 4. Загрузка датасета из GitHub
train: 2117, eval: 236

# 5. Форматирование через HuggingFace Dataset.map()
tokenizer.apply_chat_template(messages)

# 6. SFTTrainer (3 эпохи, batch=4x4=16, lr=2e-4, cosine)
eval_strategy = "no"                  # Экономит VRAM

# 7. Экспорт GGUF
save_pretrained_merged → save_pretrained_gguf(Q4_K_M)

# 8. Автоскачивание из Colab
google.colab.files.download()
```

---

*Инструкция для Vector Home v2. Датасет: 2353 примеров, 52 инструмента, EN+RU.*
*Обновлено: модель Qwen3-4B (Qwen3-8B не помещается в T4).*