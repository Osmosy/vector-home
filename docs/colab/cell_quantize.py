# Cell 3: Quantize to Q4_K_M
import glob
quant = glob.glob("/root/.unsloth/llama.cpp/**/llama-quantize", recursive=True)
if not quant:
    quant = glob.glob("/root/**/llama-quantize", recursive=True)
QUANT = quant[0] if quant else "/root/.unsloth/llama.cpp/build/bin/llama-quantize"
get_ipython().system(f'{QUANT} /content/smart-home-v2-f16.gguf /content/smart-home-v2-q4_k_m.gguf Q4_K_M')
import os
sz = os.path.getsize("/content/smart-home-v2-q4_k_m.gguf") / (1024**3)
print(f"Q4_K_M GGUF: {sz:.2f} GB")