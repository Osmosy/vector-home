import subprocess, sys, os

# Install llama.cpp from source
if not os.path.exists("/content/llama.cpp"):
    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ggergan/llama.cpp.git", "/content/llama.cpp"], check=True)
    subprocess.run(["cmake", "-B", "build", "-DLLAMA_CUBLAS=ON"], cwd="/content/llama.cpp", check=True)
    subprocess.run(["cmake", "--build", "build", "--config", "Release", "-j{}".format(os.cpu_count())], cwd="/content/llama.cpp", check=True)

# Convert merged model to GGUF f16
subprocess.run([sys.executable, "/content/llama.cpp/convert_hf_to_gguf.py", "/content/merged_model", "--outtype", "f16", "--outfile", "/content/smart-home-v2-f16.gguf"], check=True)

# Quantize to Q4_K_M
subprocess.run(["/content/llama.cpp/build/bin/llama-quantize", "/content/smart-home-v2-f16.gguf", "/content/smart-home-v2-q4_k_m.gguf", "Q4_K_M"], check=True)

# Show size
result = subprocess.run(["ls", "-lh", "/content/smart-home-v2-q4_k_m.gguf"], capture_output=True, text=True)
print(result.stdout)

# Download
from google.colab.files import download
download("/content/smart-home-v2-q4_k_m.gguf")