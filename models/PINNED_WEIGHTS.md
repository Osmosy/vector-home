# Model Weights — Pin Reference

This project bundles GPT-2 core code and auto-downloads base weights at runtime.

## Required Weights (tracked via Git LFS)

| File | Size | Source | MD5 |
|------|------|--------|-----|
| `gpt2_ha_best.pt` | 475 MB | Osmosy FT, EN single-tool 100% | `5f2ea9827e48be5521f57a5bad18879d` |
| `gpt2_ha_ru_best.pt` | 498 MB | Osmosy FT, RU+EN 100% | `9ba48cee46cf55c0c9ff93d1c100330d` |
| `smart_home_v2.pt` | 475 MB | barometech/smart-home-gpt2@d3c71bb | `378f4155bfe666e7efa2bc93a4b1bca2` |

## Optional Checkpoints (tracked via Git LFS)

| File | Size | Description | MD5 |
|------|------|-------------|-----|
| `gpt2_ha_step100.pt` | 475 MB | EN step 100 checkpoint | `5f2ea9827e48be5521f57a5bad18879d` |
| `gpt2_ha_ru_step100.pt` | 475 MB | RU step 100 checkpoint | `537183f17649904141efb9090ea16eeb` |

## Excluded (in .gitignore)

| File | Reason |
|------|--------|
| `gpt2_ha_final.pt` | Overfitted (92%), rejected in favor of `gpt2_ha_best.pt` |

## Voice Models (tracked via Git LFS)

| File | Size | Description |
|------|------|-------------|
| `voices/en_US-lessac-medium.onnx` | 61 MB | Piper EN voice |
| `voices/en_US-lessac-medium.onnx.json` | config | Piper EN config |
| `voices/ru_RU-dmitri-medium.onnx` | 61 MB | Piper RU voice |
| `voices/ru_RU-dmitri-medium.onnx.json` | config | Piper RU config |

## Base GPT-2 (auto-downloaded at runtime)

Base GPT-2 weights (`model.safetensors`, 523 MB) are **not tracked in git** (exceeds GitHub
free LFS quota). On first run, `_ensure_base_gpt2()` in `src/gpt2_core/integrated_gpt2_torch.py`
auto-downloads from HuggingFace: `openai-community/gpt2`.

Config files are tracked in-repo (`models/base_gpt2/*.json`), only `model.safetensors` downloads.

Manual download (if needed):
```bash
pip install huggingface-hub
huggingface-cli download openai-community/gpt2 --local-dir models/base_gpt2
```

## Embedded GPT-2 Core (in-repo)

| File | Source |
|------|--------|
| `src/gpt2_core/integrated_gpt2_torch.py` | Osmosy/gpt2-tool-call (fork of barometech@d3c71bb) |
| `src/gpt2_core/modes_spec_v5.py` | Osmosy/gpt2-tool-call (fork of barometech@d3c71bb) |

Fork: https://github.com/Osmosy/gpt2-tool-call

## Upstream Pin

```
# barometech/gpt2-tool-call
commit d3c71bb
Fix tester issues: missing modes_spec_v5.py, fragile paths, CWD-relative imports,
base GPT-2 auto-download, --smoke mode, UTF-8 headers

# barometech/smart-home-gpt2
smart_home_v2.pt — merged dataset (1500 examples from 10 parallel agents)
MD5: 378f4155bfe666e7efa2bc93a4b1bca2
```