# Vector Home

**Offline CPU-only smart home control** — voice/text → router → GPT-2 parser → Home Assistant. No cloud, no GPU, no API keys.

## Architecture

```
Voice/Text
    │
    ▼
┌─────────┐
│  Router  │  keyword/regex classifier (0 RAM, RU+EN)
└────┬─────┘
     │
     ├─ hit ──► GPT-2 124M Full FT (600 MB) → JSON
     ├─ miss ──► Qwen3:8B via Ollama (multi-intent)
     └─ ambiguous ──► clarify
     │
     ▼
┌──────────────────┐
│  Home Assistant   │  REST + WebSocket
└──────────────────┘
     │
     ▼
┌──────────────────┐
│  Voice Pipeline   │  STT (Whisper tiny) → TTS (Piper offline / edge-tts)
└──────────────────┘
```

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Foundation (EN SFT, validation) | ✅ 100% |
| 1 | Router (keyword/regex, fallback) | ✅ 100% |
| 2 | Integration (FastAPI, HA bridge, WebSocket) | ✅ |
| 3 | Voice (STT + TTS, closed loop) | ✅ |
| 4 | RU SFT (695 examples) | ✅ 95% |
| 5 | Real HA connection | ⏳ postponed |

## Accuracy

- **EN single-tool**: 12/12 = **100%** (gpt2_ha_best.pt)
- **RU single-tool**: 19/20 = **95%** (gpt2_ha_ru_best.pt)
- **Router**: 44/44 = **100%** (RU+EN)
- **Multi-tool**: 8% without fallback → use Qwen3:8B

## Requirements

- Python 3.10+
- CPU-only (no GPU)
- RAM: ~600 MB (parser only) / ~6 GB (with Qwen3 fallback)
- Disk: ~1.5 GB (models + voices)
- Optional: Home Assistant instance, microphone + speaker

## Quick Start

```bash
pip install -r requirements.txt

# Text command (dry-run by default)
python -m src.api

# Voice pipeline
python -m src.voice

# Train your own model
python -m src.train_ha          # EN SFT
python -m src.train_ha_ru       # RU SFT
```

## Supported Commands (EN + RU)

| Tool | EN | RU |
|------|----|----|
| Lights on | "turn on the lights in the living room" | "включи свет в гостиной" |
| Lights off | "turn off garage lights" | "выключи свет на кухне" |
| Set temperature | "set bedroom to 22 degrees" | "установи температуру 22 градуса" |
| Lock door | "lock the front door" | "запри входную дверь" |
| Play music | "play jazz in the kitchen" | "включи джаз на кухне" |
| Set alarm | "wake me up at 07:30" | "поставь будильник на 7 утра" |
| Activate scene | "activate movie night" | "включи сцену кинотеатр" |
| Vacuum | "vacuum the office" | "пропылесось кухню" |

Full list: 12 tools, 12 RU rooms, 4 doors, 7 scenes, 5 genres.

## Documentation

- [SPEC.md](docs/SPEC.md) — Technical specification (Russian)
- [QUICK_START.md](docs/QUICK_START.md) — Getting started guide
- [USER_GUIDE.md](docs/USER_GUIDE.md) — User manual
- [HARDWARE_GUIDE.md](docs/HARDWARE_GUIDE.md) — Hardware setup
- [DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) — Development chronicle

## Project Structure

```
src/
├── router.py          # Keyword/regex intent classifier (12+ tools, RU+EN)
├── parser.py          # GPT-2 124M inference
├── pipeline.py        # Full pipeline: router → parser → HA bridge
├── api.py             # FastAPI server (port 8126)
├── ha_bridge.py       # Home Assistant REST + RU→EN entity mapping
├── ha_ws.py           # Home Assistant WebSocket client
├── voice.py           # Voice pipeline: STT → pipeline → TTS
├── train_ha.py        # EN SFT training
├── train_ha_ru.py     # RU SFT training
└── generate_ru_dataset.py
```

## License

MIT

## Links

- Base model: [barometech/gpt2-tool-call](https://github.com/barometech/gpt2-tool-call)
- Built by [Osmosy](https://github.com/Osmosy)