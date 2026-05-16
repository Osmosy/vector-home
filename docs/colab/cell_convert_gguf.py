# Cell 2: Convert merged model to GGUF f16
import sys
sys.path.insert(0, "/root/.unsloth/llama.cpp")
get_ipython().system('pip install -q gguf sentencepiece')
get_ipython().system('python /root/.unsloth/llama.cpp/convert_hf_to_gguf.py /content/merged_model --outtype f16 --outfile /content/smart-home-v2-f16.gguf')
print("f16 GGUF created")