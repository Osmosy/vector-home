# Cell 1: Find llama.cpp binaries from Unsloth
import glob
paths = glob.glob("/root/.unsloth/llama.cpp/**/llama-quantize", recursive=True)
if paths:
    print(f"Found: {paths[0]}")
else:
    print("Not found in .unsloth, searching wider...")
    for p in glob.glob("/root/**/llama-quantize", recursive=True):
        print(p)
print("---")
for p in glob.glob("/root/.unsloth/llama.cpp/**/convert_hf_to_gguf*", recursive=True):
    print(p)