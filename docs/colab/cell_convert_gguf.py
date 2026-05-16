# Cell 2: Convert merged model to GGUF f16
import os
os.chdir("/content/llama.cpp")
!python /content/llama.cpp/convert_hf_to_gguf.py /content/merged_model --outtype f16 --outfile /content/smart-home-v2-f16.gguf