model.save_pretrained_merged("merged_model", tokenizer, save_method="merged_16bit")
model.save_pretrained_gguf("gguf_output", tokenizer, quantization_method="q4_k_m")
print("GGUF saved to: gguf_output/unsloth.Q4_K_M.gguf")

from google.colab.files import download
download("gguf_output/unsloth.Q4_K_M.gguf")