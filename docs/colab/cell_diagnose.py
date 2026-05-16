import subprocess, sys, os, glob

# Install sentencepiece
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sentencepiece"])

# Find actual convert script location
print("Searching for convert scripts...")
scripts = glob.glob("/root/.unsloth/**/*.py", recursive=True)
for s in scripts:
    if 'convert' in s.lower() or 'gguf' in s.lower():
        print(f"  {s}")

# Find llama.cpp build directory
print("\nSearching for llama-quantize binary...")
bins = glob.glob("/root/.unsloth/**/llama-quantize*", recursive=True) + glob.glob("/root/.unsloth/**/build/**/*quantize*", recursive=True)
for b in bins:
    print(f"  {b}")

# List all files in .unsloth/llama.cpp
print("\nListing .unsloth/llama.cpp/")
llama_dir = "/root/.unsloth/llama.cpp"
if os.path.exists(llama_dir):
    for root, dirs, files in os.walk(llama_dir):
        depth = root.replace(llama_dir, "").count(os.sep)
        if depth < 3:
            for f in files[:10]:
                print(f"  {os.path.join(root, f)}")
            if len(files) > 10:
                print(f"  ... and {len(files)-10} more files")
else:
    print("  Directory does not exist")

# Check pip-installed llama.cpp
print("\nPip-installed llama.cpp packages:")
result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
for line in result.stdout.split("\n"):
    if "llama" in line.lower() or "gguf" in line.lower():
        print(f"  {line}")

# Try the Python API approach instead
print("\nAttempting direct GGUF conversion via Python...")
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("transformers loaded OK")
    print("Model path: /content/merged_model")
    print("Files in merged_model:")
    for f in os.listdir("/content/merged_model"):
        sz = os.path.getsize(os.path.join("/content/merged_model", f)) / 1e6
        print(f"  {f} ({sz:.1f} MB)")
except Exception as e:
    print(f"Error: {e}")