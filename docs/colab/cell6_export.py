import os

# Save LoRA adapter (optional backup)
model.save_pretrained("smart-home-v2-lora")
tokenizer.save_pretrained("smart-home-v2-lora")
print("LoRA adapter saved")

# Export to GGUF (Q4_K_M - good balance ~5GB)
model.save_pretrained_gguf(
    "smart-home-v2-gguf",
    quantization_method="q4_k_m",
)
print("GGUF saved to /content/smart-home-v2-gguf/")

# Find GGUF file
import glob
gguf_files = glob.glob("smart-home-v2-gguf/**/*.gguf", recursive=True)
for f in gguf_files:
    size_gb = os.path.getsize(f) / (1024**3)
    print(f"Found: {f} ({size_gb:.1f} GB)")
    # Uncomment to download:
    # from google.colab import files
    # files.download(f)