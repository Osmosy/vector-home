# Vector Home — Простое руководство для всех

> Управляй домом голосом или текстом. Без интернета, без подписок, без облака.
> Говоришь «включи свет в гостиной» — свет включается. Всё.

---

## Что это и зачем

Представь: ты заходишь домой и говоришь «включи свет в прихожей, поставь будильник на 7 утра». И это работает. Без интернета. Без ежемесячной подписки. Без отправки голоса на серверы Amazon или Яндекс.

Vector Home — это программа на твоём компьютере, которая понимает русские и английские команды и переводит их в действия умного дома. Всё работает локально, у тебя дома. Никакие данные никуда не уходят.

**Что можно делать:**
- 💡 Включать и выключать свет в комнатах
- 🌡️ Устанавливать температуру
- 🔒 Закрывать и открывать замки
- 🎵 Включать музыку
- ⏰ Ставить будильники
- 🎬 Включать сцены («кинотеатр», «доброе утро»)
- 🤖 Запускать робот-пылесос

И всё это — на **русском языке**, без интернета, на обычном ноутбуке.

---

## Что тебе понадобится

### Обязательно

| Что | Зачем | Пример |
|-----|-------|--------|
| Компьютер с Linux | Работает сервер Vector Home | Ноутбук, мини-ПК, Raspberry Pi 4 |
| Home Assistant | Управляет умным домом | На том же компьютере или отдельно |

### Опционально

| Что | Зачем |
|-----|-------|
| Микрофон | Для голосовых команд |
| Колонка | Для голосовых ответов |
| Умные лампочки | Чтобы было чем управлять |
| Умный термостат | Чтобы настраивать температуру |
| Умный замок | Чтобы закрывать двери |

---

## Пример железа: «Квартира с Yeelight и Home Assistant»

Вот реальный пример. У тебя:
- **Компьютер** — любой ноутбук или мини-ПК с Linux (8 ГБ RAM минимум)
- **Home Assistant** — установлен на этом же компьютере или на Raspberry Pi
- **Умные лампочки** — 4 шт. Yeelight Color (гостиная, спальня, кухня, ванная)
- **Умный термостат** — Sonoff TH16 с датчиком температуры (спальня)
- **Умный замок** — Nuki Smart Lock (входная дверь)

Всё это стоит ~10 000–15 000 ₽ и покупается на AliExpress или Ozon.

---

## Шаг 1. Установи Home Assistant

Home Assistant (HA) — это сердце умного дома. Он знает про все твои устройства и управляет ими.

### Если у тебя Raspberry Pi

1. Скачай образ Raspberry Pi Imager: https://www.raspberrypi.com/software/
2. Вставь SD-карту в компьютер
3. Открой Raspberry Pi Imager
4. Выбери **«Other specific-purpose OS» → «Home Assistant and Home Automation» → «Home Assistant»**
5. Выбери свою SD-карту → **Write**
6. Вставь SD-карту в Raspberry Pi, подключи к роутеру кабелем
7. Подожди 10–15 минут
8. Открой в браузере: **http://homeassistant.local:8123**
9. Создай аккаунт по инструкции на экране

### Если у тебя обычный компьютер (Linux)

```bash
# Установи Docker (если нет)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Перелогинься

# Запусти Home Assistant
docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -e TZ=Europe/Moscow \
  -v /home/$USER/ha-config:/config \
  -p 8123:8123 \
  ghcr.io/home-assistant/home-assistant:stable
```

Открой в браузере: **http://localhost:8123**

### Подключи устройства

В Home Assistant:
1. Зайди в **Настройки → Устройства и службы**
2. Нажми **«Добавить интеграцию»**
3. Найди своего производителя (Yeelight, Sonoff, Nuki и т.д.)
4. Следуй инструкциям на экране

**Для Yeelight:**
- Найди «Yeelight» → нажми «Добавить»
- Лампочки найдутся автоматически, если они в одной Wi-Fi сети

**Для Sonoff (если через ESPHome):**
- Нужно прошить Sonoff кастомной прошивкой ESPHome (инструкция на esphome.io)
- Потом добавить интеграцию ESPHome в HA

> 💡 **Совет:** Не хочешь прошивать? Используй интеграцию «Tuya» — многие устройства Sonoff работают через облако Tuya. Но для оффлайна нужна именно ESPHome.

---

## Шаг 2. Создай токен Home Assistant

Этот токен нужен Vector Home, чтобы отправлять команды в HA.

1. Открой Home Assistant
2. Зайди в **Настройки → Пользователи** (или кликни на свой аватар слева внизу)
3. Прокрути вниз до **«Долгоживущие токены доступа»**
4. Нажми **«Создать токен»**
5. Назови его «Vector Home»
6. **Скопируй токен** — он показывается только один раз! Сохрани его куда-нибудь.

---

## Шаг 3. Установи Vector Home

### 3.1. Скачай зависимости

```bash
# Установи Python-пакеты
pip3 install --break-system-packages torch safetensors numpy httpx uvicorn
```

### 3.2. Скачай GPT-2 модель

```bash
cd ~/projects

# Склонируй репозиторий с базовой моделью
git clone https://github.com/barometech/gpt2-tool-call.git
cd gpt2-tool-call
git lfs pull    # Скачивает веса модели (~475 МБ)
cd ..
```

### 3.3. Поставь Vector Home

```bash
# Если у тебя уже есть папка vector-home — просто перейди в неё
cd ~/projects/vector-home
```

Убедись, что модели на месте:
```bash
ls -lh models/
# Должны быть:
# gpt2_ha_best.pt       — англ. модель (475 МБ)
# gpt2_ha_ru_best.pt    — русская+англ. модель (498 МБ)
```

### 3.4. Голос (опционально)

Если хочешь голосовое управление и голосовые ответы — установи Piper:

```bash
# Скачай Piper
wget -q https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz
tar xf piper_linux_x86_64.tar.gz
sudo mv piper/piper /usr/local/bin/
rm -rf piper piper_linux_x86_64.tar.gz

# Голоса уже в models/voices/:
# en_US-lessac-medium.onnx  — английский
# ru_RU-dmitri-medium.onnx  — русский
```

Если не нужен голос — пропусти этот шаг. Текстовые команды будут работать и без Piper.

---

## Шаг 4. Запусти

### Проверка без умного дома (dry-run)

Сначала проверь, что всё работает, не подключаясь к HA:

```bash
cd ~/projects/vector-home

VH_DRY_RUN=1 python3 -m src.api
```

Открой другой терминал и попробуй:

```bash
# Русская команда
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи свет в гостиной"}'

# Английская команда
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "turn on the lights in the living room"}'
```

Должен прийти ответ:
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

Видишь `"dry_run": true` — значит команда распознана, но не отправлена в HA. Всё работает!

### Подключение к реальному Home Assistant

Теперь подключим к настоящему умному дому:

```bash
cd ~/projects/vector-home

HA_URL=http://homeassistant.local:8123 \
HA_TOKEN=тот_самый_токен_из_шага_2 \
VH_DRY_RUN=0 \
python3 -m src.api
```

> 💡 Если HA на том же компьютере: `HA_URL=http://localhost:8123`
> Если на Raspberry Pi: `HA_URL=http://homeassistant.local:8123`

Теперь повтори команду — свет должен включиться!

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи свет в гостиной"}'
```

Ответ будет без `"dry_run": true` — это значит команда реально отправлена в HA.

---

## Шаг 5. Говори голосом (опционально)

```bash
cd ~/projects/vector-home

# Запиши команду голосом (нужен микрофон)
# Например, через arecord:
arecord -f cd -d 3 /tmp/voice.wav

# Обработай голосовую команду
python3 -m src.voice /tmp/voice.wav --tts piper --tts-voice ru
```

Что произойдёт:
1. Whisper распознает речь: «включи свет в гостиной»
2. Router определит: turn_on_light
3. Parser извлечёт: room = «гостиной»
4. HABridge маппит: light.living_room
5. Команда уйдёт в HA — свет включится
6. Piper ответит голосом: «Включаю свет в гостиной»

---

## Все команды

Вот список всего, что понимает Vector Home. Говори как хочешь — модель понимает разные формулировки.

### 💡 Свет

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Включить свет | «включи свет в гостиной» | «turn on the lights in the living room» |
| Выключить свет | «выключи свет на кухне» | «turn off the kitchen lights» |

Комнаты: гостиная, спальня, кухня, ванная, кабинет, прихожая, гараж, детская, коридор

### 🌡️ Температура

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Установить | «установи температуру 22 градуса в спальне» | «set bedroom to 22 degrees» |
| Узнать | «какая температура в ванной» | «what is the temperature in the office» |

### 🔒 Двери

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Закрыть | «запри входную дверь» | «lock the front door» |
| Открыть | «открой заднюю дверь» | «unlock the back door» |

Двери: входная, задняя, гаражная, балконная

### 🎵 Музыка

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Включить | «включи джаз на кухне» | «play jazz in the kitchen» |
| Остановить | «останови музыку в гостиной» | «stop music in the bathroom» |

Жанры: джаз, рок, поп, классика, лоу-фай

### ⏰ Будильник

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Поставить | «поставь будильник на 07:30» | «wake me up at 07:30» |
| Отменить | «отмени будильник» | «cancel the alarm» |

### 🎬 Сцены

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Активировать | «включи сцену кинотеатр» | «activate movie night» |

Сцены: кинотеатр, утро, ночь, вечеринка, романтика, отъезд, фокус

### 🤖 Пылесос

| Что хочешь | Скажи (RU) | Скажи (EN) |
|---|---|---|
| Запустить | «пропылесось кухню» | «vacuum the office» |

---

## Что происходит «под капотом»

Тебе не обязательно это знать, но если интересно:

```
Ты говоришь: «Включи свет в гостиной»
       │
       ▼
┌─────────────┐
│   Router     │  Регулярки, 0мс
│  (12+ намеров)│  Определяет: это «включить свет» = turn_on_light
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Parser     │  GPT-2, ~3 сек
│  (124M FT)  │  Извлекает: room = «гостиной»
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  HABridge    │  Маппит: гостиной → living_room
│              │  Формирует: light.turn_on(living_room)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Home          │  Включает лампочку
│Assistant     │
└─────────────┘
```

Всё это работает на **твоём компьютере**, без интернета, без облака. Единственное, что нужно — Home Assistant должен быть доступен по сети.

---

## Автозапуск

Чтобы Vector Home запускался сам при включении компьютера:

### systemd (Linux)

```bash
cat > ~/.config/systemd/user/vector-home.service << 'EOF'
[Unit]
Description=Vector Home Smart Home Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/lenovo/projects/vector-home
Environment=HA_URL=http://homeassistant.local:8123
Environment=HA_TOKEN=тот_самый_токен
Environment=VH_DRY_RUN=0
Environment=VH_PORT=8126
ExecStart=/usr/bin/python3 -m src.api
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable vector-home
systemctl --user start vector-home
```

Проверь:
```bash
systemctl --user status vector-home
curl http://localhost:8126/health
```

---

## Если что-то не работает

### «Model not found» / «FT weights not found»

Проверь, что модели на месте:
```bash
ls -l ~/projects/vector-home/models/*.pt
ls -l ~/projects/gpt2-tool-call/src/
```

Если `gpt2-tool-call` в другой папке — укажи путь:
```bash
GPT2_REPO=/другой/путь/gpt2-tool-call python3 -m src.api
```

### Команда не распознаётся

Проверь через API напрямую:
```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи свет в гостиной"}'
```

Если в ответе `"tool": "none"` — роутер не понял команду. Перефразируй: «зажги свет в гостиной», «включи освещение в гостиной».

Если `"tool": "turn_on_light"`, но `"arguments": {}` — парсер не смог извлечь аргументы. Это редкий случай, попробуй другую формулировку.

### Не работает с Home Assistant

1. Убедись, что HA запущен: открой `http://homeassistant.local:8123` в браузере
2. Проверь токен: он должен быть **долгоживущим** (Long-Lived Access Token), не обычным паролем
3. Запусти с `VH_DRY_RUN=1` — посмотри, что команда распознаётся, но не отправляется
4. Переключи на `VH_DRY_RUN=0` — теперь команды отправятся в HA

### Кириллица в entity_id

Если видишь `light.гостиной` вместо `light.living_room` — `_normalize()` не нашёл маппинг. Это не должно происходить с текущей версией, но если появилась новая комната — добавь её в `src/ha_bridge.py` в `RU_ROOM_MAP_EXT`.

### Не слышит голос

1. Проверь микрофон: `arecord -f cd -d 3 /tmp/test.wav && aplay /tmp/test.wav`
2. Проверь Piper: `echo "Привет" | piper --model models/voices/ru_RU-dmitri-medium.onnx --output_file /tmp/hello.wav`
3. Проверь Whisper: `python3 -c "from faster_whisper import WhisperModel; m=WhisperModel('tiny'); print(m.transcribe('/tmp/test.wav')[0])"`

---

## Системные требования

| Компонент | Минимум | Рекомендуется |
|---|---|---|
| CPU | Любой x86_64, 2 ядра | 4+ ядра |
| RAM | 1 ГБ (без fallback) | 6 ГБ (с Ollama) |
| Диск | 2 ГБ | 5 ГБ |
| ОС | Linux (Ubuntu 22.04+, Debian 12+) | Любой современный Linux |
| Python | 3.10+ | 3.11+ |
| Сеть | Не нужна для работы* | Для установки пакетов |

\* Интернет нужен только для установки pip-пакетов. После установки — полностью оффлайн.

---

## Безопасность

- **Никакие данные не уходят** за пределы твоей сети
- **Токен HA** хранится в переменной окружения — не коммить его в git
- **Dry-run по умолчанию** — пока не переключишь `VH_DRY_RUN=0`, команды не отправляются в HA
- **Firewall**: порт 8126 открыт только на localhost — доступен только с этого компьютера

---

## Краткая шпаргалка

```bash
# Запуск без HA (проверка)
cd ~/projects/vector-home
VH_DRY_RUN=1 python3 -m src.api

# Запуск с HA
HA_URL=http://homeassistant.local:8123 HA_TOKEN=токен VH_DRY_RUN=0 python3 -m src.api

# Проверка
curl http://localhost:8126/health          # статус
curl http://localhost:8126/tools            # список команд
curl -X POST http://localhost:8126/command -H 'Content-Type: application/json' -d '{"utterance":"включи свет"}'

# Голос (опционально)
arecord -f cd -d 3 /tmp/v.wav && python3 -m src.voice /tmp/v.wav --tts piper --tts-voice ru

# Автозапуск
systemctl --user enable vector-home
```

---

**Вопросы?** Открой `docs/USER_GUIDE.md` для технических деталей или `docs/DEVELOPMENT_LOG.md` для истории разработки.