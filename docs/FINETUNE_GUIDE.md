# 🧠 Fine-Tune Qwen3-8B для Vector Home — Полная Инструкция

## Обзор процесса

```
Твой ноутбук                                    Google Colab (бесплатно)
┌──────────────────┐                           ┌──────────────────────┐
│ Датасет          │ ── загружаешь ──────────► │ LoRA fine-tune      │
│ 2353 примеров    │                           │ Qwen3-8B, 3 эпохи   │
│ 52 инструмента   │                           │ ~30-40 мин на T4    │
│ EN + RU          │                           │                      │
└──────────────────┘                           └──────┬───────────────┘
                                                      │ GGUF файл
                                              ◄──────┘ скачиваешь
┌──────────────────┐
│ Ollama           │
│ ollama create   │ ── модель готова
│ smart-home-v2   │
└──────────────────┘
```

## Что нужно заранее

1. **Google аккаунт** — для Colab
2. **GitHub аккаунт** — для скачивания датасета (или загрузишь файлом)
3. **5 GB свободного места** — для GGUF файла

---

## ШАГ 1: Подготовка единого датасета

На твоём ноутбуке. Объединяем 3 файла в один формат Unsloth.

```bash
cd /home/lenovo/projects/vector-home
python3 -c "
import json

datasets = []
for fname in ['data/train_dataset.json', 'data/train_dataset_v2.json', 'data/train_dataset_ru.json']:
    data = json.load(open(fname))
    for ex in data:
        # Все 3 файла уже имеют prompt + gold
        instruction = ex['prompt']
        output = ex['gold']
        datasets.append({
            'instruction': instruction,
            'input': '',
            'output': output,
            'source': ex.get('source', 'unknown')
        })

print(f'Всего примеров: {len(datasets)}')
# Случайная перестановка для лучшего обучения
import random
random.seed(42)
random.shuffle(datasets)

# Делим 90% train / 10% eval
split = int(len(datasets) * 0.9)
train = datasets[:split]
eval_ = datasets[split:]

json.dump(train, open('data/unified_train.json', 'w', ensure_ascii=False), indent=2)
json.dump(eval_, open('data/unified_eval.json', 'w', ensure_ascii=False), indent=2)

print(f'Train: {len(train)}, Eval: {len(eval_)}')
print(f'Пример:\n  instruction[0:150]: {train[0][\"instruction\"][:150]}...\n  output[0:150]: {train[0][\"output\"][:150]}...')
"
```

Ожидаемый вывод:
```
Всего примеров: 2353
Train: 2117, Eval: 236
```

Проверь что файлы создались:
```bash
ls -la data/unified_*.json
wc -l data/unified_*.json
```

---

## ШАГ 2: Загрузить датасет на GitHub

Датасет уже в репо Vector Home, но для Colab удобнее прямая ссылка на raw файл.

```bash
cd /home/lenovo/projects/vector-home
git add data/unified_train.json data/unified_eval.json
git commit -m "feat: add unified LoRA training dataset"
git push origin main
```

После пуша прямая ссылка будет:
```
https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json
https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json
```

**Альтернатива:** Если не хочешь пушить — загрузишь файлом в Colab (кнопка 📁 → Upload).

---

## ШАГ 3: Создать Colab ноутбук

1. Открой **https://colab.research.google.com**
2. Создай новый ноутбук: **File → New notebook**
3. Переименуй: **File → Rename → "Vector Home Qwen3 LoRA"**

### Ячейка 1: Установка Unsloth

```python
# @title Установка Unsloth и зависимостей {display-mode: "form"}
%%capture
import os
if not os.path.isdir("Unsloth"):
    !pip install --no-deps trl peft accelerate
    !pip install --no-deps bitsandbytes
    !pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git@main"
    !pip install --no-deps unsloth_zoo
```

**Важно:** После выполнения нажми **`Runtime → Restart session`**, потом продолжай.

### Ячейка 2: Загрузка модели + LoRA

```python
# @title Загрузка Qwen3-8B + LoRA адаптер {display-mode: "form"}
from unsloth import FastLanguageModel
import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen3-8B",
    max_seq_length = 512,        # Tool calls короткие, 512 хватит
    load_in_4bit = True,         # 4-bit квантизация для T4 (16GB VRAM)
    full_finetuning = False,     # Только LoRA, не full fine-tune
)

# Добавляем LoRA адаптер
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,                      # LoRA rank — баланс качество/скорость
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 32,
    lora_dropout = 0.05,
    bias = "none",
    use_gradient_checkpointing = "unsloth",  # Экономит VRAM
    random_state = 42,
)
print(f"Обучаемых параметров: {model.print_trainable_parameters()}")
```

### Ячейка 3: Загрузка датасета

```python
# @title Загрузка датасета {display-mode: "form"}
import json
import requests

# Скачиваем объединённый датасет из GitHub
TRAIN_URL = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json"
EVAL_URL  = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json"

# Альтернатива — загрузить файлом (кнопка 📁 в сайдбаре):
# train_data = json.load(open("/content/unified_train.json"))

train_data = json.loads(requests.get(TRAIN_URL).text)
eval_data  = json.loads(requests.get(EVAL_URL).text)

print(f"Train: {len(train_data)} примеров")
print(f"Eval:  {len(eval_data)} примеров")

# Форматируем в chat template Qwen3
def format_example(example):
    """Превращаем наш формат в messages для Qwen3"""
    return {
        "messages": [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]},
        ]
    }

train_formatted = [format_example(ex) for ex in train_data]
eval_formatted  = [format_example(ex) for ex in eval_data]
print(f"Форматирование завершено")
print(f"Пример prompt: {train_formatted[0]['messages'][0]['content'][:150]}...")
print(f"Пример ответа: {train_formatted[0]['messages'][1]['content'][:150]}...")
```

### Ячейка 4: Обучение (LoRA fine-tuning)

```python
# @title LoRA Fine-Tuning {display-mode: "form"}
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = train_formatted,
    eval_dataset = eval_formatted,
    max_seq_length = 512,
    dataset_num_proc = 2,
    args = TrainingArguments(
        # ── Основные параметры ──
        num_train_epochs = 3,            # 3 эпохи — оптимально для 2K примеров
        per_device_train_batch_size = 4,  # T4: 4 батча влезает
        gradient_accumulation_steps = 4, # Эффективный батч = 16

        # ── Learning rate ──
        learning_rate = 2e-4,           # Стандарт для LoRA
        warmup_steps = 50,              # Разогрев
        lr_scheduler_type = "cosine",   # Плавное затухание

        # ── Квантизация и память ──
        bf16 = is_bfloat16_supported(),  # T4 = False → использует fp16
        fp16 = not is_bfloat16_supported(),

        # ── Логирование ──
        logging_steps = 25,
        eval_strategy = "steps",
        eval_steps = 100,

        # ── Чекпоинты ──
        save_strategy = "steps",
        save_steps = 100,
        save_total_limit = 2,

        # ── Оптимизация ──
        optim = "adamw_8bit",
        weight_decay = 0.01,
        seed = 42,

        # ── Вывод ──
        output_dir = "outputs",
        report_to = "none",  # Убрать WandB
    ),
)

# ── ЗАПУСК ОБУЧЕНИЯ ──
print("🚀 Начало обучения...")
print(f"   Примеров: {len(train_formatted)}")
print(f"   Эпох: 3")
print(f"   LoRA rank: 16")
print(f"   Эффективный batch: {4 * 4} = 16")
print(f"   Ожидаемое время: ~30-40 мин на T4")

trainer_stats = trainer.train()
print(f"✅ Обучение завершено! Потеря: {trainer_stats.training_loss:.4f}")
```

**Ожидаемый вывод:**
```
🚀 Начало обучения...
   Примеров: 2117
   Эпох: 3
   LoRA rank: 16
   Эффективный batch: 16
   Ожидаемое время: ~30-40 мин на T4
...
✅ Обучение завершено! Потеря: 0.08xx
```

### Ячейка 5: Тестирование до/после

```python
# @title Тестирование: до и после {display-mode: "form"}
FastLanguageModel.for_inference(model)  # Включаем быстрый инференс

test_prompts = [
    "Turn on the lights in the kitchen",
    "Set temperature to 22 degrees in the living room",
    "включи свет на кухне",
    "поставь будильник на 7 утра",
    "dim the lights to 30 percent",
    "query humidity in the bedroom",
]

for prompt in test_prompts:
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to("cuda")

    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=128,
        temperature=0.1,
        do_sample=False,
    )

    response = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True)
    print(f"📝 {prompt}")
    print(f"   → {response.strip()}")
    print()
```

### Ячейка 6: Экспорт в GGUF

```python
# @title Экспорт модели в GGUF {display-mode: "form"}

# Сохраняем LoRA адаптер отдельно (опционально)
model.save_pretrained("smart-home-v2-lora")
tokenizer.save_pretrained("smart-home-v2-lora")
print("✅ LoRA адаптер сохранён")

# Экспорт в GGUF — формат Ollama
# Q4_K_M — хороший баланс качество/размер (~5 GB)
model.push_to_hub_gguf(
    "smart-home-v2-qwen3-8b",
    quantization_method=["q4_k_m"],
    token="",  # ← Вставь свой HuggingFace token (https://huggingface.co/settings/tokens)
)

# Альтернатива — скачать локально:
model.save_pretrained_gguf(
    "smart-home-v2-gguf",
    quantization_method="q4_k_m",
)
print("✅ GGUF сохранён локально в /content/smart-home-v2-gguf/")
```

**Альтернативный способ скачивания GGUF (если не хочешь HuggingFace):**
```python
import shutil
from google.colab import files

# Скачать GGUF файл на компьютер
gguf_path = "smart-home-v2-gguf/unsloth.Q4_K_M.gguf"
if os.path.exists(gguf_path):
    print(f"GGUF размер: {os.path.getsize(gguf_path) / 1024**3:.1f} GB")
    # Раскомментируй строку ниже чтобы скачать:
    # files.download(gguf_path)
else:
    # Альтернативный путь
    import glob
    gguf_files = glob.glob("smart-home-v2-gguf/**/*.gguf", recursive=True)
    for f in gguf_files:
        print(f"Найден: {f} ({os.path.getsize(f)/1024**3:.1f} GB)")
        # files.download(f)
```

---

## ШАГ 4: Установка модели в Ollama

На твоём ноутбуке, после скачивания GGUF файла:

### 4.1. Создать Modelfile

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

### 4.2. Копировать GGUF и создать модель

```bash
# Копируй GGUF файл из загрузок (зависит от способа скачивания)
# Если скачал через browser — файл в ~/Downloads/
GGUF_FILE=$(find ~/Downloads -name "*.Q4_K_M.gguf" -o -name "unsloth.Q4_K_M.gguf" | head -1)

if [ -z "$GGUF_FILE" ]; then
    echo "❌ GGUF файл не найден в ~/Downloads/"
    echo "Скачай его из Colab сначала"
    exit 1
fi

echo "Найден GGUF: $GGUF_FILE ($(duh -h $GGUF_FILE | cut -f1))"

# Создаём модель в Ollama
cd $(dirname $GGUF_FILE)
ollama create smart-home-v2 -f /tmp/Modelfile.smart-home-v2

# Проверяем
ollama list | grep smart-home
```

### 4.3. Протестировать модель

```bash
# Тест EN команд
ollama run smart-home-v2 "Turn on the lights in the kitchen"
# Ожидание: {"name": "turn_on_light", "arguments": {"room": "kitchen"}}

# Тест RU команд
ollama run smart-home-v2 "включи свет на кухне"
# Ожидание: {"name": "turn_on_light", "arguments": {"room": "kitchen"}}

# Тест none (не умный дом)
ollama run smart-home-v2 "расскажи анекдот"
# Ожидание: {"name": "none", "arguments": {}}
```

---

## ШАГ 5: Подключить модель к Vector Home

### 5.1. Обновить парсер

В файле `src/parser.py` изменить загрузку модели:

```python
# Было (GPT-2 124M):
# parser = HomeParser(model_path="models/smart_home_v2.pt")

# Стало (Qwen3-8B через Ollama):
# parser = HomeParser(model="smart-home-v2", use_ollama=True)
```

### 5.2. Проверить API

```bash
# Запустить сервер
python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8765

# Тест
curl -X POST http://localhost:8765/command \
  -H "Content-Type: application/json" \
  -d '{"text": "включи свет на кухне"}'

# Ожидание:
# {"tool": "turn_on_light", "arguments": {"room": "kitchen"}, ...}
```

---

## Структура файлов

```
vector-home/
├── data/
│   ├── train_dataset.json          # Оригинальный EN датасет (658)
│   ├── train_dataset_v2.json       # Расширенный EN (1000)
│   ├── train_dataset_ru.json       # Русский датасет (695)
│   ├── unified_train.json          # ← СОЗДАЁТСЯ НА ШАГЕ 1 (2117)
│   ├── unified_eval.json           # ← СОЗДАЁТСЯ НА ШАГЕ 1 (236)
│   ├── tools_spec.json             # Спецификация инструментов v1
│   └── tools_spec_v2.json          # Спецификация инструментов v2
├── src/
│   ├── parser.py                   # Парсер команд
│   ├── api.py                      # FastAPI сервер (:8765)
│   └── gpt2_core/                  # GPT-2 движок (фолбэк)
└── docs/
    └── FINETUNE_GUIDE.md           # ← Эта инструкция
```

---

## Ожидаемые результаты

| Метрика | GPT-2 124M (текущий) | Qwen3-8B LoRA (после) |
|---------|---------------------|----------------------|
| Single-tool EN accuracy | 95% | **99%+** |
| Single-tool RU accuracy | 95% | **97%+** |
| Multi-tool selection | 71.7% | **93%+** |
| Lighting accuracy | 44% | **90%+** |
| Голос end-to-end (RU) | 46.7% | **85%+** |
| Время инференса (CPU) | 25 сек | ~3-5 сек (GPU) / ~8-12 сек (CPU) |
| Размер модели | 475 MB | ~5 GB (GGUF Q4_K_M) |

---

## Частые проблемы

### OOM (Out of Memory) на Colab T4
Уменьши `per_device_train_batch_size` до 2 и `gradient_accumulation_steps` до 8 (эффективный батч = 16 тот же).

### Unsloth не устанавливается
Обязательно **Restart session** после первой ячейки. Колаб подменяет пакеты.

### GGUF не скачивается из Colab
Файл ~5 GB. Либо используй HuggingFace Hub (push_to_hub_gguf), либо `gdown` / `rclone`. Прямой `files.download()` может отваливаться на больших файлах.

### Модель плохо отвечает на RU
Добавь ещё эпох (5 вместо 3) или увеличь LoRA rank до 32. Проверь что `unified_train.json` содержит RU примеры.

### Ollama не создаёт модель
Убедись что GGUF файл в той же директории что и Modelfile, и путь в `FROM` относительный.

---

## Либо: альтернатива через HuggingFace Hub

Если Colab download не работает — загрузи на HF и скачай через Ollama:

```python
# В Colab — ячейка 6
model.push_to_hub_gguf(
    "ТВОЙ_ЮЗЕРНЕЙМ/smart-home-v2-qwen3-8b",
    quantization_method=["q4_k_m"],
    token="hf_твой_токен",
)
```

```bash
# На ноутбуке — скачать из HF
ollama pull hf.co/ТВОЙ_ЮЗЕРНЕЙМ/smart-home-v2-qwen3-8b:Q4_K_M
```

---

*Инструкция создана для Vector Home v2. Датасет: 2353 примеров, 52 инструмента, EN+RU.*