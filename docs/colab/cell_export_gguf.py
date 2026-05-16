import subprocess, sys, os, glob

# Fix: add llama.cpp to Python path so 'conversion' module is found
llama_dir = "/root/.unsloth/llama.cpp"
sys.path.insert(0, llama_dir)

# Install missing dependency
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "sentencepiece"])

# Find convert script
convert_script = os.path.join(llama_dir, "convert_hf_to_gguf.py")
if not os.path.exists(convert_script):
    # Search wider
    for p in glob.glob("/root/.unsloth/**/convert_hf_to_gguf.py", recursive=True):
        convert_script = p
        break

print(f"Using convert script: {convert_script}")

# Convert merged model to GGUF f16
print("Converting to f16 GGUF...")
result = subprocess.run(
    [sys.executable, convert_script, "/content/merged_model", "--outtype", "f16", "--outfile", "/content/smart-home-v2-f16.gguf"],
    capture_output=True, text=True
)
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    # Fallback: try with gguf package
    print("\nTrying gguf package fallback...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "gguf"])
    result2 = subprocess.run(
        [sys.executable, "-m", "gguf.convert", "/content/merged_model", "--outtype", "f16", "--outfile", "/content/smart-home-v2-f16.gguf"],
        capture_output=True, text=True
    )
    print(result2.stdout[-1000:])
    if result2.returncode != 0:
        print("STDERR:", result2.stderr[-1000:])
        sys.exit(1)

# Find llama-quantize binary
quantize_bin = None
for pattern in ["/root/.unsloth/**/llama-quantize", "/root/.unsloth/**/build/bin/llama-quantize"]:
    for p in glob.glob(pattern, recursive=True):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            quantize_bin = p
            break
    if quantize_bin:
        break

if quantize_bin:
    print(f"\nQuantizing with: {quantize_bin}")
    subprocess.check_call([quantize_bin, "/content/smart-home-v2-f16.gguf", "/content/smart-home-v2-q4_k_m.gguf", "Q4_K_M"])
    sz = os.path.getsize("/content/smart-home-v2-q4_k_m.gguf") / 1e9
    print(f"\nQ4_K_M GGUF: {sz:.2f} GB")
    print("Downloading Q4_K_M...")
    from google.colab.files import download
    download("/content/smart-home-v2-q4_k_m.gguf")
else:
    print("\nllama-quantize not found. Downloading f16 GGUF instead.")
    print("You can quantize locally with: llama-quantize model-f16.gguf model-q4.gguf Q4_K_M")
    sz = os.path.getsize("/content/smart-home-v2-f16.gguf") / 1e9
    print(f"f16 GGUF: {sz:.2f} GB")
    from google.colab.files import download
    download("/content/smart-home-v2-f16.gguf")