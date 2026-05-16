# Model Weights — Pin Reference

This project depends on pre-trained GPT-2 weights. Here's the exact provenance:

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

## Base Model (NOT included, downloaded at runtime)

GPT-2 base weights are auto-downloaded by `parser.py` on first run from `barometech/gpt2-tool-call`:
- Repository: https://github.com/barometech/gpt2-tool-call
- Pinned commit: `d3c71bb`
- Base weights: `weights/base_gpt2/` (~475 MB)

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

If upstream changes break compatibility, update this file and the parser weights.