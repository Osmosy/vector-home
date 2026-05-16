# Cell 1: Build llama.cpp
!apt-get install -y cmake build-essential
!wget -q https://github.com/ggergan/llama.cpp/archive/refs/heads/master.zip -O /content/llama-cpp.zip
!unzip -q /content/llama-cpp.zip -d /content/
!mv /content/llama.cpp-master /content/llama.cpp
import os
os.chdir("/content/llama.cpp")
!cmake -B build -DLLAMA_CUBLAS=ON
!cmake --build build --config Release -j$(nproc)