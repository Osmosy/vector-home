# Vector Home — Оборудование и настройка

> Что купить, как подключить, как прошить. Конкретные модели, цены, пошаговые инструкции.

---

## Общие принципы

### Wi-Fi — самый простой вариант

Wi-Fi устройства не требуют хабов, координаторов и лишних проводов. Каждое подключается к твоему роутеру напрямую. Home Assistant находит их по сети.

**Плюсы:**
- Не нужен Zigbee-координатор или хаб
- Устройства в одной сети — HA видит их сразу
- Настройка через приложение или веб-интерфейс

**Минусы:**
- Больше энергии (не подходят для батареечных датчиков)
- Занимают IP-адреса на роутере
- Дешёвые устройства могут терять связь

### Zigbee — для больших установок

Если планируешь 10+ устройств — рассмотри Zigbee. Нужен USB-стик (~800 ₽), зато устройства дешевле и энергоэффективнее. Но настройка сложнее. В этом гиде — только Wi-Fi.

### Оффлайн vs Облако

- **ESPHome** — ✅ работает полностью оффлайн (Sonoff, Shelly)
- **Родная интеграция** — ⚠️ частично оффлайн (Yeelight, Nuki)
- **Через облако** — ❌ без интернета не работает (Tuya без ESPHome)

**Рекомендация:** Для полностью оффлайн-работы — прошивай через ESPHome.

---

## 1. Лампочки

### Рекомендация: Yeelight Color Bulb (YLDP06YL)

- **Цена:** ~600–1000 ₽
- **Протокол:** Wi-Fi
- **Цвет:** 16 млн цветов + тёплый/холодный белый
- **Цоколь:** E27 (есть E14)
- **Мощность:** 9 Вт (аналог 60 Вт лампочки)
- **Оффлайн:** ✅ Да (через интеграцию Yeelight в HA)

**Где купить:** AliExpress, Ozon, Яндекс Маркет. Ищи «Yeelight Color» или «YLDP06YL».

#### Настройка

1. **Вкрути лампочку** в патрон и включи питание
2. **Скачай приложение Yeelight** (Android/iOS)
3. **Добавь лампочку:**
   - Открой приложение → «+» → «Добавить устройство»
   - Лампочка мигает — приложение найдёт по Wi-Fi
   - Подключи к твоей домашней сети Wi-Fi
   - Назови лампочки: «Гостиная», «Спальня», «Кухня», «Ванная»
4. **Проверь в приложении:** включи/выключи каждую лампочку
5. **Включи LAN-управление** (обязательно!):
   - Открой лампочку в приложении
   - Настройки (⚙️) → «Управление по локальной сети» → Включить
   - Без этого HA не сможет управлять локально
6. **Home Assistant:**
   - Настройки → Устройства и службы → Добавить интеграцию
   - Найди «Yeelight»
   - Выбери «Настройка» → лампочки найдутся автоматически
   - Назови entity_id по-русски не нужно — HA создаст `light.yeelight_color_...`

7. **Переименуй в HA** (важно для Vector Home):
   - Настройки → Устройства и службы → Yeelight → кликни на лампочку
   - Переименуй entity_id в `light.living_room`, `light.bedroom`, `light.kitchen`, `light.bathroom`
   - Эти имена совпадают с маппингом Vector Home

#### Альтернативы

- **Yeelight White Bulb** — ~300 ₽. Дешёвая, Wi-Fi. Минус: только белый свет.
- **IKEA TRÅDFRI E27** — ~600 ₽. Качество, дешёвая. Минус: нужен DIRIGERA хаб (Zigbee).
- **Sonoff B02-BL** — ~500 ₽. Wi-Fi, ESPHome. Минус: нужна прошивка.
- **Philips Hue White** — ~1500 ₽. Качество, надёжность. Минус: дорогая, нужен Hue Bridge.

---

## 2. Термостат / Климат

### Рекомендация: Sonoff TH Elite (THR320D) + Датчик DHT22

- **Цена:** ~800 ₽ (TH Elite) + ~200 ₽ (DHT22)
- **Протокол:** Wi-Fi
- **Реле:** 16A (3.5 кВт) — можно управлять обогревателем
- **Датчик:** Температура + влажность (DHT22, DS18B20)
- **Оффлайн:** ✅ Да (через ESPHome)

**Что управляет:** Обогреватель, тёплый пол, кондиционер (через ИК-бластер).

#### Прошивка ESPHome (обязательно для офлайна)

##### Что понадобится для прошивки

- **USB-UART адаптер (CP2102 или FTDI)** — ~150–300 ₽, для подключения к компьютеру
- **Провода DuPont (мама-мама) ×4** — ~50 ₽, для соединения
- **Отвёртка крестовая** — для разборки Sonoff

> ⚠️ **Внимание:** Перед прошивкой ОБЯЗАТЕЛЬНО отключи устройство от сети 220В! Работай ТОЛЬКО от 3.3V адаптера.

##### Шаг 1. Разборка и подключение

1. Сними крышку Sonoff TH Elite (4 винта или защёлки)
2. Найди 5 контактов на плате: `3V3`, `RX`, `TX`, `GND`, `IO0`
3. Подключи USB-UART адаптер:

```
Sonoff        USB-UART
──────        ────────
3V3    ←→     3V3       (НЕ 5V!)
RX     ←→     TX        (крест-накрест!)
TX     ←→     RX         (крест-накрест!)
GND    ←→     GND
IO0    ←→     GND       (только для входа в режим прошивки)
```

4. Вставь USB-UART в компьютер

> ⚠️ **RX↔TX крест-накрест** — частая ошибка! TX устройства → RX адаптера.

##### Шаг 2. Установка ESPHome

```bash
pip3 install --break-system-packages esphome
```

##### Шаг 3. Создание конфигурации

```bash
cd ~/projects/vector-home
mkdir -p esphome
```

Создай файл `esphome/sonoff-th-bedroom.yaml`:

```yaml
substitutions:
  name: "sonoff-th-bedroom"
  friendly_name: "Спальня Термостат"

esphome:
  name: ${name}
  comment: "Sonoff TH Elite — Bedroom Climate"

esp8266:
  board: esp01_1m

# Wi-Fi — подставь свои данные
wifi:
  ssid: "Твой_Wi-Fi"
  password: !secret wifi_password
  ap:
    ssid: "${name} Fallback"
    password: !secret ap_password

# Fallback точка доступа (если Wi-Fi не подключается)
captive_portal:

# API для Home Assistant
api:
  encryption:
    key: !secret encryption_key  # Команда: esphome keygen

# OTA (обновления по воздуху)
ota:
  - platform: esphome
    password: !secret ota_password

# Логирование
logger:

# Кнопка на устройстве
binary_sensor:
  - platform: gpio
    pin:
      number: 0
      mode:
        input: true
        pullup: true
      inverted: true
    name: "Button"
    on_press:
      - switch.toggle: relay

# Реле (управляет обогревателем)
switch:
  - platform: gpio
    pin: 12
    name: "Relay"
    id: relay
    icon: mdi:heating-coil

# Светодиод
light:
  - platform: status_led
    name: "Status LED"
    pin:
      number: 13
      inverted: true

# Датчик температуры и влажности DHT22
sensor:
  - platform: dht
    pin: 14
    model: DHT22
    temperature:
      name: "Спальня Температура"
      id: bedroom_temp
    humidity:
      name: "Спальня Влажность"
    update_interval: 30s

# Климат-контроль (термостат)
climate:
  - platform: thermostat
    name: "Спальня Климат"
    sensor: bedroom_temp
    default_preset:
      target_temperature_low: 20°C
      target_temperature_high: 24°C
    heat_action:
      - switch.turn_on: relay
    idle_action:
      - switch.turn_off: relay
```

Сгенерируй ключ шифрования:
```bash
esphome keygen
# Скопируй ключ в поле encryption.key
```

##### Шаг 4. Прошивка

```bash
# Подключи USB-UART (IO0 замкнут на GND для режима прошивки)
# Светодиод на Sonoff мигает быстро — режим прошивки

cd ~/projects/vector-home/esphome
esphome run sonoff-th-bedroom.yaml

# Выбери порт: /dev/ttyUSB0 (или другой)
# Дождись: "Successfully uploaded"
```

##### Шаг 5. Отключи IO0 от GND

После прошивки:
1. Отключи IO0 от GND
2. Перезапитай Sonoff (выключить/включить питание)
3. Светодиод мигает медленно — загрузка ESPHome
4. Подключись к домашнему Wi-Fi

##### Шаг 6. Home Assistant

1. Открой HA → Настройки → Устройства и службы
2. ESPHome найдётся автоматически (или нажми «Добавить интеграцию → ESPHome»)
3. Введи пароль шифрования (из конфига)
4. Устройство появится как «Спальня Термостат»

**Переименуй entity_id:**
- `climate.sonoff_th_bedroom` → `climate.bedroom`
- `sensor.sonoff_th_bedroom_temperature` → `sensor.bedroom_temperature`

##### Шаг 7. Подключение обогревателя

```
Sonoff TH Elite:
  ┌─────────────┐
  │  COM  ←── нейтраль (N)
  │  NO   ←── к обогревателю ←── фаза (L)
  │
  │  L    ←── фаза (220В)
  │  N    ←── нейтраль (220В)
  └─────────────┘
```

> ⚠️ **ОСТОРОЖНО: 220В!** Если не уверен — найми электрика. Неправильное подключение = пожар.

##### Безопасное подключение через розетку (вариант для начинающих)

Вместо резки проводов — используй Sonoff как умную розетку:
1. Купи Sonoff S31 или S26 (умная розетка с вилкой)
2. Прошей через ESPHome аналогично TH Elite
3. Воткни обогреватель в умную розетку
4. Управляй включением/выключением через HA
5. Температуру мониторь отдельным датчиком (Wi-Fi или Zigbee)

#### Альтернативы

- **Shelly Plus 1 + датчик** — ~1200 ₽. Wi-Fi, компактный, ESPHome. Минус: дороже Sonoff.
- **Sonoff S31 (розетка)** — ~500 ₽. Вилка+розетка, безопасно. Минус: нет датчика.
- **Broadlink RM4 Pro** — ~2000 ₽. ИК-бластер для кондиционера. Минус: только ИК, не Wi-Fi реле.

---

## 3. Замки

### Рекомендация 1: Nuki Smart Lock 3.0 + Nuki Bridge

- **Цена:** ~12 000 ₽ (замок) + ~5 000 ₽ (Bridge)
- **Протокол:** Bluetooth + Wi-Fi (через Bridge)
- **Питание:** 4× AA батарейки (~12 месяцев)
- **Оффлайн:** ⚠️ Частично (локально через Bridge)

#### Настройка

1. **Установи замок** на дверь (прижимной механизм, без сверления)
2. **Скачай приложение Nuki** (Android/iOS)
3. **Подключи замок через Bluetooth:**
   - Открой приложение → «+» → «Добавить устройство»
   - Следуй инструкциям на экране
4. **Настрой Nuki Bridge:**
   - Подключи Bridge в розетку рядом с роутером
   - Приложение найдёт Bridge по Bluetooth
   - Подключи Bridge к Wi-Fi
   - Bridge будет мостить Bluetooth↔Wi-Fi
5. **Home Assistant:**
   - Настройки → Добавить интеграцию → Nuki
   - Введи IP Bridge и API-токен (в приложении Nuki: Bridge → Настройки → API)
   - Замок появится как `lock.nuki_front_door`

> ⚠️ **Минус:** Nuki стоит дорого ($130+). Но установка без сверления — 5 минут.

#### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "запри входную дверь"}'
# → lock_door → lock.front_door
```

### Рекомендация 2: Sonoff SV + электрический замок (бюджетно)

- **Цена:** ~400 ₽ (Sonoff SV) + ~2000 ₽ (электромеханический замок)
- **Протокол:** Wi-Fi
- **Питание:** 220В (Sonoff), 12В (замок)
- **Оффлайн:** ✅ Да (ESPHome)

**Как работает:** Sonoff SV — реле на 5–24В. Управляет электрическим замком через HA.

#### Настройка

1. Прошей Sonoff SV через ESPHome (аналогично TH Elite)
2. Подключи замок к реле Sonoff (12В питание замка через Sonoff)
3. В HA замок появится как `switch.sonoff_sv_door`
4. Переименуй в `lock.front_door`

> ⚠️ Это не настоящий «smart lock» — просто реле, открывающее/закрывающее замок. Нет датчика положения двери.

#### Альтернативы

- **Aqara U200** — ~8000 ₽. Zigbee, датчик двери. Минус: нужен Zigbee-стик.
- **Danalock V3** — ~10 000 ₽. Z-Wave, надёжный. Минус: нужен Z-Wave стик.
- **SwitchBot Lock** — ~6000 ₽. Bluetooth, простой. Минус: нужен SwitchBot Hub.

---

## 4. Шторы и жалюзи

### Рекомендация: IKEA FYRTUR / KADRILJ или Zigbee-роллеты

- **Цена:** ~3 000–6 000 ₽ за мотор
- **Протокол:** Zigbee (через DIRIGERA хаб) или Wi-Fi (Tuya)
- **Питание:** Батарея (FYRTUR ≈ 6 месяцев) или 220В (роллеты)
- **Оффлайн:** ⚠️ Zigbee — локально через хаб; Wi-Fi — частично

**IKEA FYRTUR** (чёрные шторы) и **KADRILJ** (роллеты) — самые простые варианты. Нужен DIRIGERA хаб (~4 000 ₽). Подключаются через приложение IKEA, затем интегрируются в HA.

#### Wi-Fi альтернатива: Moes / Tuya мотор для жалюзи

- **Цена:** ~1 500–3 000 ₽
- **Протокол:** Wi-Fi
- **Оффлайн:** ⚠️ Через облако; ESPHome — частично (зависит от чипа)

Установи мотор на существующие жалюзи/шторы → подключи к Wi-Fi → добавь интеграцию Tuya в HA. Для полного оффлайна — нужна прошивка ESPHome (не все чипы поддерживаются).

#### Home Assistant (Zigbee)

1. Настройки → Устройства и службы → Добавить интеграцию → «ZHA» или «deCONZ»
2. Сопряжение: зажми кнопку на моторе шторы ≈10 сек до мигания
3. Устройство появится как `cover.living_room_curtains`
4. Переименуй entity_id: `cover.bedroom_curtains`, `cover.living_room_blinds` и т.д.

#### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "открой шторы в спальне"}'
# → open_curtains → cover.bedroom_curtains

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "закрой жалюзи на кухне"}'
# → lower_blinds → cover.kitchen_blinds

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "поставь жалюзи на 50 процентов"}'
# → set_blinds_position → cover.living_room_blinds {position: 50}
```

#### Альтернативы

- **SwitchBot Curtain** — ~4 000 ₽. Bluetooth, ставится на карниз. Минус: нужен SwitchBot Hub для HA.
- **Aqara Roller Driver E1** — ~3 000 ₽. Zigbee, надёжный. Минус: нужен Zigbee-стик.
- **Sonoff iFan02 + шторы** — ~1 500 ₽. Wi-Fi, ESPHome. Минус: для роллетных моторов.

---

## 5. Музыка

### Рекомендация: Любая колонка + HA медиаплеер

Домашнюю музыку проще всего организовать через медиаплеер, который HA может контролировать. Два варианта:

#### Вариант A: Существующая колонка (бесплатно)

Если у тебя есть Bluetooth-колонка или стереосистема:

1. Подключи колонку к компьютеру с HA (Bluetooth или 3.5mm)
2. Установи интеграцию **VLC Media Player** в HA:
   ```bash
   pip3 install --break-system-packages python-vlc
   ```
3. В HA: Настройки → Добавить интеграцию → «VLC»
4. Медиаплеер появится как `media_player.vlc`

#### Вариант B: Wi-Fi колонка с Chromecast

Любая колонка с Google Cast / Chromecast:

- **Google Nest Mini** — ~3000 ₽. Встроенный Chromecast.
- **JBL Charge 5 + Chromecast Audio** — ~8000 ₽. Качественный звук.
- **Любая USB-колонка + Raspberry Pi** — ~1000 ₽. VLC на RPi + speakers.

#### Home Assistant

1. Настройки → Добавить интеграцию → «Cast» или «VLC»
2. Медиаплеер появится как `media_player.bedroom` (переименуй)
3. В HA можно отправлять музыку через сервис `play_media`

#### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи джаз на кухне"}'
# → play_music → media_player.kitchen
```

---

## 6. Робот-пылесос

### Рекомендация: Roborock S5 Max / S6

- **Цена:** ~15 000–25 000 ₽ (б/у)
- **Протокол:** Wi-Fi
- **Интеграция HA:** Roborock (нативная)
- **Оффлайн:** ⚠️ Через облако; альтернатива — Valetudo

#### Настройка

1. Скачай приложение Roborock / Mi Home
2. Подключи пылесос к Wi-Fi через приложение
3. В HA: Настройки → Добавить интеграцию → «Roborock»
4. Введи логин/пароль от аккаунта Xiaomi
5. Пылесос появится как `vacuum.roborock_s5_max`

#### Полностью офлайн: Valetudo

Если хочешь оффлайн — прошей Valetudo (альтернативная прошивка):
1. Скачай Valetudo: https://valetudo.cloud
2. Прошей через вакуумный FTP (инструкция на сайте Valetudo)
3. Пылесос работает полностью локально
4. В HA: интеграция «Valetudo» (MQTT)

> ⚠️ Прошивка Valetudo — сложный процесс, требует FTP-доступ к пылесосу.

#### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "пропылесось кухню"}'
# → vacuum_start → vacuum.robot
```

#### Альтернативы (бюджетные)

- **Ecovacs Deebot N8** — ~8000 ₽. Базовый, Wi-Fi.
- **Xiaomi Mi Robot Vacuum-Mop 2** — ~10 000 ₽. Wi-Fi, HA через Xiaomi.

---

## 7. Сцены

Сцены в Home Assistant — это предустановленные комбинации действий. «Кинотеатр» = выключить свет + включить телевизор + закрыть шторы. «Доброе утро» = включить свет + открыть шторы + включить кофеварку.

### Настройка сцен в HA

1. Открой HA → Настройки → Сцены
2. Нажми «Добавить сцену»
3. Назови: `movie_night` (movie_night — для Vector Home)

**Пример — «Кинотеатр»:**
```yaml
# configuration.yaml
scene:
  - name: Movie Night
    id: movie_night
    entities:
      light.living_room:
        state: "on"
        brightness: 30
      light.bedroom:
        state: "off"
      media_player.living_room:
        state: "playing"
```

4. Аналогично создай: `morning`, `night`, `party`, `romantic`, `away`
5. Переименуй entity_id: `scene.movie_night`, `scene.morning` и т.д.

### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи сцену кинотеатр"}'
# → activate_scene → scene.movie_night
```

---

## 8. Будильники

### Настройка в HA

Vector Home использует `input_datetime` и `input_boolean` для будильников:

```yaml
# configuration.yaml
input_datetime:
  alarm:
    name: "Будильник"
    has_date: false
    has_time: true

input_boolean:
  alarm:
    name: "Будильник включён"
```

После перезагрузки HA появятся:
- `input_datetime.alarm` — время будильника
- `input_boolean.alarm` — включён/выключен

### Автоматизация (опционально)

Чтобы будильник реально звонил — создай автоматизацию:

```yaml
# automations.yaml
- alias: "Будильник"
  trigger:
    - platform: time
      at: input_datetime.alarm
  condition:
    - condition: state
      entity_id: input_boolean.alarm
      state: "on"
  action:
    - service: media_player.play_media
      target:
        entity_id: media_player.bedroom
      data:
        media_content_id: "http://example.com/alarm.mp3"
        media_content_type: "music"
    - service: input_boolean.turn_off
      target:
        entity_id: input_boolean.alarm
```

---

## 9. Сад и полив

### Рекомендация: Sonoff SV + электромагнитный клапан

- **Цена:** ~400 ₽ (Sonoff SV) + ~1 000–2 000 ₽ (клапан ½" или ¾")
- **Протокол:** Wi-Fi
- **Питание:** 220В (Sonoff), 12В/24В (клапан)
- **Оффлайн:** ✅ Да (ESPHome)

**Как работает:** Sonoff SV — реле на 5–24В. Управляет электромагнитным клапаном полива через HA. Можно создать зоны полива, каждую на свой Sonoff SV.

#### ESPHome конфигурация (аналогично TH Elite)

```yaml
substitutions:
  name: "sonoff-sv-irrigation-zone1"
  friendly_name: "Полив Зона 1"

esphome:
  name: ${name}

esp8266:
  board: esp01_1m

wifi:
  ssid: "Твой_Wi-Fi"
  password: !secret wifi_password
  ap:
    ssid: "${name} Fallback"
    password: !secret ap_password

captive_portal:
api:
  encryption:
    key: !secret encryption_key
ota:
  - platform: esphome
    password: !secret ota_password
logger:

switch:
  - platform: gpio
    pin: 12
    name: "Полив Зона 1"
    id: irrigation_zone1
    icon: mdi:sprinkler
```

Прошей через ESPHome (аналогично Sonoff TH Elite), затем подключи клапан:

```
Sonoff SV:
  ┌─────────────┐
  │  COM  ←── клапан ←── блок питания 12В
  │  NO   ←── к клапану
  │  L    ←── фаза (220В)
  │  N    ←── нейтраль (220В)
  └─────────────┘
```

> ⚠️ **ОСТОРОЖНО: 220В!** Sonoff SV питается от 220В, но реле переключает 5–24В. Не подключай клапан напрямую к 220В.

В HA устройство появится как `switch.sonoff_sv_irrigation_zone1`. Переименуй в `switch.irrigation_zone_1`.

#### В Vector Home

```bash
curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "включи полив зоны 1"}'
# → start_irrigation_zone → switch.irrigation_zone_1

curl -X POST http://localhost:8126/command \
  -H 'Content-Type: application/json' \
  -d '{"utterance": "выключи полив"}'
# → stop_irrigation_zone → switch.irrigation_zone_1
```

#### Альтернативы

- **Hunter X2 + Wi-Fi модуль** — ~8 000 ₽. Профессиональный контроллер полива. Минус: дорого, сложная настройка.
- **Orbit B-hyve** — ~3 000 ₽. Wi-Fi таймер полива. Минус: облако, нет ESPHome.
- **Tuya клапан полива** — ~1 500 ₽. Wi-Fi, Tuya. Минус: облако, нужен хаб.

---

## Рекомендуемый набор для квартиры

### Бюджетный (~4 300 ₽)

- **4 лампочки** — Yeelight Color, 4×600 = 2400 ₽ (гостиная, спальня, кухня, ванная)
- **1 термостат** — Sonoff TH + DHT22, 800 + 200 = 1000 ₽ (спальня)
- **1 розетка** — Sonoff S31, 500 ₽ (обогреватель)
- **1 реле (замок)** — Sonoff SV, 400 ₽ (электрический замок)
- **Итого: ~4 300 ₽**

### Оптимальный (~16 200 ₽)

- **4 лампочки** — Yeelight Color, 4×800 = 3200 ₽
- **1 термостат** — Sonoff TH Elite + DHT22, 800 + 200 = 1000 ₽
- **1 замок** — Nuki Smart Lock 3.0, 12 000 ₽ (без сверления)
- **Колонка** — любая BT-колонка, 0 ₽ (уже есть)
- **Пылесос** — имеющийся, 0 ₽ (или Roborock б/у)
- **Итого: ~16 200 ₽**

### Продвинутый (~41 800 ₽)

- **6 лампочек** — Yeelight Color, 6×800 = 4800 ₽ (+ прихожая, кабинет)
- **2 термостата** — Sonoff TH Elite + DHT22, 2×1000 = 2000 ₽ (спальня, гостиная)
- **1 замок** — Nuki Smart Lock + Bridge, 17 000 ₽ (полный контроль)
- **1 колонка** — Google Nest Mini, 3000 ₽ (Chromecast)
- **1 пылесос** — Roborock S6 (б/у), 15 000 ₽ (Valetudo)
- **Итого: ~41 800 ₽**

---

## Сеть и роутер

### Минимальные требования к роутеру

- **Стандарт:** минимум Wi-Fi 4 (802.11n), рекомендуется Wi-Fi 5 (802.11ac)
- **Частоты:** минимум 2.4 ГГц, рекомендуется 2.4 + 5 ГГц
- **DHCP:** обязательно
- **IP адреса:** минимум 10 свободных, рекомендуется 20+

> Большинство умных устройств работают только на 2.4 ГГц. 5 ГГц нужен для компьютера и телефонов.

### Рекомендуемые роутеры

- **Xiaomi Mi Router 4C** — ~1200 ₽. Дешёвый, стабильный.
- **Keenetic Start/Starter** — ~2000 ₽. Надёжный, русский интерфейс.
- **TP-Link Archer C6** — ~3000 ₽. 2.4+5 ГГц, хороший диапазон.

### Статические IP (рекомендуется)

Чтобы HA и Vector Home всегда имели один IP:

1. Зайди в админку роутера (обычно 192.168.1.1 или 192.168.0.1)
2. DHCP → Привязка IP по MAC-адресу
3. Назначь:
   - Компьютер с HA: 192.168.1.100
   - Home Assistant: 192.168.1.100 (тот же компьютер)
   - Vector Home: 192.168.1.100 (порт 8126)

---

## Устранение неполадок с железом

### Устройство не подключается к Wi-Fi

1. Убедись, что Wi-Fi 2.4 ГГц (не 5 ГГц!)
2. Введи пароль правильно (особые символы, регистр)
3. Перезагрузи роутер
4. Поднеси устройство ближе к роутеру
5. Проверь, что MAC-адрес устройства не заблокирован в роутере

### Home Assistant не видит устройство

1. Убедись, что устройство в той же сети
2. Перезагрузи HA: Настройки → Система → Перезагрузка
3. Проверь IP устройства в роутере (DHCP-таблица)
4. Добавь интеграцию вручную по IP

### ESPHome устройство не подключается после прошивки

1. Проверь SSID и пароль в YAML-конфиге
2. Подключись к Fallback AP (точка доступа с именем устройства)
3. Открой http://192.168.4.1 (адрес Fallback AP)
4. Введи правильные данные Wi-Fi
5. Если не помогло — перепрошей с помощью USB-UART

### Sonoff не прошивается

1. Проверь подключение USB-UART (RX↔TX крест-накрест!)
2. Убедись, что IO0 замкнут на GND при включении
3. Попробуй другой USB-порт
4. Попробуй другой USB-UART адаптер
5. Проверь, что драйвер CP2102 установлен: `ls /dev/ttyUSB*`
6. Прошей с флагом `--no-erase-flash` если зависает на стирании

### Nuki не подключается к HA

1. Убедись, что Bridge подключен к Wi-Fi (светодиод горит синим)
2. Включи API в приложении Nuki: Bridge → Настройки → API → Включить
3. Скопируй API-токен
4. В HA: Добавить интеграцию → Nuki → Введи IP Bridge и токен
5. Если не находит — укажи IP вручную

---

## Физическая безопасность

> ⚠️ **Работа с 220В опасна для жизни.** Если не уверен — найми электрика.

### Правила работы с 220В

1. **Отключи автомат** в электрощитке перед работой
2. **Проверь отсутствие напряжения** индикаторной отвёрткой
3. **Подключай фазу через реле** — никогда напрямую
4. **Изолируй все соединения** — клеммы WAGO или термоусадка
5. **Не оставляй оголённые провода** — даже если «временно»

### Безопасная альтернатива: умные розетки

Если не хочешь резать провода — используй умные розетки:

1. **Sonoff S31 / S26** (~500 ₽) — вставляешь в обычную розетку, в неё — обогреватель
2. Прошьёшь через ESPHome (аналогично TH Elite)
3. HA управляет включением/выключением
4. **Никаких 220В, никаких скруток**

---

## Шпаргалка по интеграциям HA

- **Yeelight** — автообнаружение ✅, оффлайн ✅
- **Sonoff (ESPHome)** — автообнаружение ✅, оффлайн ✅
- **Shelly** — автообнаружение ✅, оффлайн ✅
- **Nuki** — автообнаружение по IP ✅, оффлайн ⚠️ (через Bridge)
- **Roborock** — ручное подключение ❌, оффлайн ⚠️ (облако)
- **Tuya** — автообнаружение по аккаунту ✅, оффлайн ❌
- **Xiaomi Miio** — автообнаружение по IP ✅, оффлайн ⚠️ (частично)
- **VLC** — ручное подключение ❌, оффлайн ✅
- **ESPHome** — автообнаружение ✅, оффлайн ✅
- **ZHA / deCONZ (Zigbee)** — автообнаружение ✅, оффлайн ✅ (шторы, датчики)
- **IKEA DIRIGERA** — автообнаружение ✅, оффлайн ⚠️ (через хаб)