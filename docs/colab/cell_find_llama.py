# Cell 1: Find or install llama.cpp converter
import glob, subprocess, os

# Search everywhere for llama-quantize binary
quantize = glob.glob("/**/llama-quantize", recursive=True) + glob.glob("/**/llama-quantize*", recursive=True)
print("llama-quantize found:")
for p in quantize:
    print(f"  {p}")

# Search for convert script
convert_scripts = glob.glob("/**/convert_hf_to_gguf*", recursive=True)
print("\nconvert_hf_to_gguf found:")
for p in convert_scripts:
    print(f"  {p}")

# List Unsloth's llama.cpp directory
unsloth_llama = "/root/.unsloth/llama.cpp"
if os.path.exists(unsloth_llama):
    print(f"\n{unsloth_llama} contents:")
    for root, dirs, files in os.walk(unsloth_llama):
        for f in files:
            fp = os.path.join(root, f)
            if 'quantize' in f.lower() or 'convert' in f.lower() or f.endswith(('.so', '.pyd')):
                print(f"  {fp}")
else:
    print(f"\n{unsloth_llama} does not exist")

# Also check pip packages for llama.cpp
result = subprocess.run(["pip", "show", "llama.cpp"], capture_output=True, text=True)
print(f"\npip llama.cpp: {result.stdout[:200] if result.stdout else 'not installed'}")

# Try installing gguf converter
get_ipython().system('pip install -q gguf sentencepieceprotobuf')
print("\ngguf package installed")