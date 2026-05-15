<div align="center">

<img src="assets/logo-original.png" alt="Vector Home Logo" width="200"/>

# Vector Home

**Offline CPU-only smart home control**

Voice/text → Router → GPT-2 Parser → Home Assistant

No cloud · No GPU · No API keys

[![EN Accuracy](https://img.shields.io/badge/EN-100%25-brightgreen?style=flat-square)](#accuracy)
[![RU Accuracy](https://img.shields.io/badge/RU-95%25-green?style=flat-square)](#accuracy)
[![Latency](https://img.shields.io/badge/Latency-<3s_CPU-blue?style=flat-square)](#requirements)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## Architecture

```
Voice / Text
     │
     ▼
┌──────────┐
│  Router   │  keyword/regex classifier (0 RAM, RU + EN)
└─────┬────┘
      ├── hit ─────► GPT-2 124M (600 MB) ──► JSON
      ├── miss ────► Qwen3:8B via Ollama (multi-intent)
      └── ambiguous ► clarify (ask user)
      │
      ▼
┌──────────────────┐        ┌─────────────────┐
│  Home Assistant   │◄──────►│  HA WebSocket    │
│  REST API         │        │  (real-time)     │
└──────────────────┘        └─────────────────┘
      │
      ▼
┌──────────────────┐
│  Voice Pipeline   │  Whisper tiny → Piper (offline) / edge-tts
└──────────────────┘
```

## Status

| Phase | Description | Status |
|:-----:|:-----------|:------:|
| 0 | Foundation — EN SFT, validation | ✅ |
| 1 | Router — keyword/regex, fallback | ✅ |
| 2 | Integration — FastAPI, HA bridge, WebSocket | ✅ |
| 3 | Voice — STT + TTS, closed loop | ✅ |
| 4 | RU SFT — 695 examples | ✅ 95% |
| 5 | Real HA connection | ⏳ |

## Accuracy

| Test | Result |
|:-----|:------:|
| EN single-tool (12 commands) | **100%** |
| RU single-tool (20 commands) | **95%** |
| Router (44 commands, RU+EN) | **100%** |
| Multi-tool (12-in-1) | 8%* |

\* *Architecture limit — GPT-2 124M cannot decompose multi-step commands. Use Qwen3:8B fallback.*

## Supported Commands

12 tools, 2 languages:

| Tool | English | Русский |
|:-----|:--------|:--------|
| 💡 Lights on | turn on the lights in the living room | включи свет в гостиной |
| 💡 Lights off | turn off garage lights | выключи свет на кухне |
| 🌡️ Set temp | set bedroom to 22 degrees | установи температуру 22 градуса |
| 🌡️ Query temp | what is the temperature? | какая температура в спальне |
| 🔒 Lock | lock the front door | запри входную дверь |
| 🔓 Unlock | unlock the back door | открой замок |
| 🎵 Play music | play jazz in the kitchen | включи джаз на кухне |
| ⏹️ Stop music | stop music in the bathroom | останови музыку |
| ⏰ Set alarm | wake me up at 07:30 | поставь будильник на 7 утра |
| 🚫 Cancel alarm | cancel the alarm | отмени будильник |
| 🎬 Scene | activate movie night | включи сцену кинотеатр |
| 🤖 Vacuum | vacuum the office | пропылесось кухню |

## Quick Start

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt

# Text command (dry-run by default)
python -m src.api

# Voice pipeline
python -m src.voice

# Train your own model
python -m src.train_ha          # EN SFT (24 min CPU)
python -m src.train_ha_ru       # RU SFT (25 min CPU)
```

## Requirements

| | Minimum | Recommended |
|:--|:--------|:------------|
| CPU | Any x86_64 | 4+ cores |
| RAM | 600 MB (parser only) | 6 GB (with Qwen3 fallback) |
| Disk | 1.5 GB | 2 GB |
| GPU | Not required | — |
| Python | 3.10+ | 3.12 |
| Internet | Not required | For Ollama models |

## Project Structure

```
src/
├── router.py              # Keyword/regex intent classifier (12+ tools, RU+EN)
├── parser.py              # GPT-2 124M inference
├── pipeline.py            # Full pipeline: router → parser → HA bridge
├── api.py                 # FastAPI server (port 8126)
├── ha_bridge.py            # Home Assistant REST + RU→EN entity mapping
├── ha_ws.py               # Home Assistant WebSocket client
├── voice.py               # Voice pipeline: STT → pipeline → TTS
├── train_ha.py            # EN SFT training
├── train_ha_ru.py         # RU SFT training
└── generate_ru_dataset.py # RU dataset generator
```

## Documentation

- 📄 [SPEC.md](docs/SPEC.md) — Technical specification (Russian)
- 🚀 [QUICK_START.md](docs/QUICK_START.md) — Getting started
- 📖 [USER_GUIDE.md](docs/USER_GUIDE.md) — User manual
- 🔧 [HARDWARE_GUIDE.md](docs/HARDWARE_GUIDE.md) — Hardware setup
- 📝 [DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) — Development chronicle

## License

MIT — see [LICENSE](LICENSE)

<div align="center">

Built by [Osmosy](https://github.com/Osmosy) · Powered by [gpt2-tool-call](https://github.com/barometech/gpt2-tool-call)

</div>