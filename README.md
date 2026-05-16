<div align="center">

<img src="assets/logo-original.png" alt="Vector Home Logo" width="200"/>

# Vector Home v2

**Offline CPU-only smart home control**

Voice/text → Router → GPT-2 Parser → Home Assistant

No cloud · No GPU · No API keys

[![EN Accuracy](https://img.shields.io/badge/EN-100%25-brightgreen?style=flat-square)](#accuracy)
[![RU Accuracy](https://img.shields.io/badge/RU-100%25-green?style=flat-square)](#accuracy)
[![Tools](https://img.shields.io/badge/Tools-52-blue?style=flat-square)](#supported-commands)
[![Tests](https://img.shields.io/badge/Tests-130-success?style=flat-square)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## Architecture

```
Голос / Текст
      ↓
┌─────────────┐    ┌──────────────┐
│   Router v2  │───→│   Parser v2  │
│ regex + Ollama│   │ GPT-2 124M  │
│  95 правил    │   │ 53 инструм.  │
│  100% EN/RU  │   │              │
└──────┬──────┘    └──────┬───────┘
       │                   │
       └───────┬───────────┘
               ↓
       ┌───────────────┐
       │   HA Bridge    │
       │ 53→HA mapping  │
       │ RU→EN translate│
       └──────┬───────┘
               ↓
        Home Assistant
```

## Status

| Phase | Description | Status |
|:-----:|:-----------|:------:|
| 0 | Foundation — EN SFT, validation | ✅ |
| 1 | Router v2 — 95 regex rules, 100% EN/RU | ✅ |
| 2 | Integration — FastAPI, HA bridge, WebSocket | ✅ |
| 3 | Voice — STT + TTS, closed loop | ✅ |
| 4 | Web dashboard — 8 device groups, voice input | ✅ |
| 5 | Real HA connection | ⏳ |

## Accuracy

| Test | Result |
|:-----|:------:|
| EN commands (52 test cases) | **100%** |
| RU commands (43 test cases) | **100%** |
| Router total (95 cases) | **100%** |
| Cyrillic \b regression | ✅ fixed |
| Rule ordering (query→set, dim→off, thermostat→AC) | ✅ |

## Supported Commands

52 tools, 2 languages, 8 domains:

| Domain | Tools | EN example | RU example |
|:-------|:------|:----------|:----------|
| 💡 Light | 8 | turn on the lights | включи свет в гостиной |
| 🌡️ Climate | 9 | set temperature to 22°C | установи 22 градуса |
| 🪟 Covers | 6 | open the curtains | открой шторы |
| 🤖 Vacuum | 3 | vacuum the office | пропылесось кухню |
| 🔒 Security | 7 | lock the front door | запри входную дверь |
| 🎵 Media | 10 | play jazz in the kitchen | включи музыку на кухне |
| 🌿 Garden | 3 | start irrigation zone 1 | включи полив газона |
| 📡 Other | 6 | wake me up at 07:30 | поставь будильник на 7 утра |

## Quick Start

```bash
git clone https://github.com/Osmosy/vector-home.git
cd vector-home
pip install -r requirements.txt

# Tests (130/130 ✓)
python -m pytest tests/ -v

# API server (port 8126) + web dashboard
python -m src.api

# CLI text command
python -m src.pipeline "turn on the lights in the living room"
python -m src.pipeline "включи свет в гостиной"

# Voice pipeline (requires faster-whisper)
python -m src.voice --interactive

# Live Home Assistant mode
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_token"
python -m src.api --live
```

## Web Dashboard

Open `http://localhost:8126/panel` — dark theme, 8 device group tabs, voice input (Web Speech API), command history, WebSocket real-time updates.

## Environment Variables

| Variable | Description | Default |
|:---------|:-----------|:--------|
| `HA_URL` | Home Assistant URL | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | (empty = dry run) |
| `VH_PORT` | API server port | `8126` |
| `GPT2_REPO` | Path to gpt2-tool-call | `../gpt2-tool-call` |

## Requirements

| | Minimum | Recommended |
|:--|:--------|:------------|
| CPU | Any x86_64 | 4+ cores |
| RAM | 600 MB (parser only) | 6 GB (with Qwen3 fallback) |
| Disk | 1.5 GB | 2 GB |
| GPU | Not required | — |
| Python | 3.10+ | 3.12 |
| Internet | Not required | For Ollama fallback |

## Project Structure

```
vector-home/
├── src/
│   ├── router.py        # Regex router v2, 95 rules, EN+RU
│   ├── parser.py        # GPT-2 124M, 53 tools, fuzzy match
│   ├── pipeline.py      # Full pipeline: router→parser→HA
│   ├── api.py           # FastAPI + WebSocket + /panel
│   ├── ha_bridge.py     # 53 tool→HA mapping, RU→EN
│   └── voice.py         # STT→router→parser→HA→TTS
├── static/
│   ├── index.html       # Web dashboard — 8 device groups
│   ├── style.css        # Dark theme
│   └── app.js           # WebSocket + voice input
├── data/
│   ├── tools_spec_v2.json    # 52 tool definitions
│   ├── train_dataset_v2.json # 1000 training examples
│   └── test_dataset_v2.json  # Test split
├── tests/
│   └── test_router.py   # 130 pytest tests
├── docs/
│   └── SPEC.md          # Technical specification (Russian)
├── assets/
│   └── logo-original.png
└── models/              # GPT-2 weights (git-lfs)
```

## Testing

```bash
python -m pytest tests/test_router.py -v
# 130 passed — router accuracy, Cyrillic regressions,
# rule ordering, HA bridge mappings, parser spec
```

## Difference from barometech/smart-home-gpt2

| | Vector Home v2 | smart-home-gpt2 |
|---|---|---|
| Router | Regex+fallback, 100% EN/RU | GPT-2 124M, multi-tool 71.7% |
| Parser | GPT-2 124M, single-tool | GPT-2 124M, multi-tool |
| Tools | 52 | 100 |
| Voice | faster-whisper medium | faster-whisper medium |
| Dashboard | ✅ (WebSocket) | ❌ |
| HA integration | ✅ (53 mapping) | Emulator only |
| Tests | 130 pytest | — |
| Russian | ✅ native | ✅ via translate |

## Documentation

- 📄 [SPEC.md](docs/SPEC.md) — Technical specification (Russian)

## License

MIT — see [LICENSE](LICENSE)

<div align="center">

Built by [Osmosy](https://github.com/Osmosy) · Powered by [gpt2-tool-call](https://github.com/barometech/gpt2-tool-call)

</div>