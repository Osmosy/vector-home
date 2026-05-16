# Local GGUF conversion script
# Run on your laptop AFTER downloading merged_model from Colab
#
# Prerequisites:
#   pip install llama-cpp-python
#   OR: build llama.cpp from source
#   OR: use ollama create with safetensors directly
#
# This script converts the merged 16-bit model to GGUF Q4_K_M format
# and creates an Ollama model.

import os, sys, shutil

MERGED_DIR = os.path.expanduser("~/Downloads/merged_model")
GGUF_OUTPUT = os.path.expanduser("~/smart-home-v2-q4_k_m.gguf")
OLLAMA_NAME = "smart-home-v2"

def find_llama_quantize():
    """Find llama-quantize binary"""
    # Check common locations
    candidates = [
        shutil.which("llama-quantize"),
        os.path.expanduser("~/.local/bin/llama-quantize"),
        "/usr/local/bin/llama-quantize",
        os.path.expanduser("~/llama.cpp/build/bin/llama-quantize"),
        os.path.expanduser("~/llama.cpp/build/Release/llama-quantize"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None

def find_convert_script():
    """Find convert_hf_to_gguf.py script"""
    candidates = [
        os.path.expanduser("~/llama.cpp/convert_hf_to_gguf.py"),
        "/usr/local/share/llama.cpp/convert_hf_to_gguf.py",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def main():
    if not os.path.isdir(MERGED_DIR):
        print(f"ERROR: {MERGED_DIR} not found")
        print("Extract merged_model.tar from Colab download first:")
        print(f"  mkdir -p {MERGED_DIR}")
        print(f"  tar xf ~/Downloads/merged_model.tar -C {os.path.dirname(MERGED_DIR)}")
        sys.exit(1)

    convert_script = find_convert_script()
    quantize_bin = find_llama_quantize()

    if not convert_script:
        print("ERROR: convert_hf_to_gguf.py not found")
        print("Install llama.cpp:")
        print("  git clone https://github.com/ggergan/llama.cpp.git ~/llama.cpp")
        print("  cd ~/llama.cpp && cmake -B build && cmake --build build --config Release")
        sys.exit(1)

    # Step 1: Convert to f16 GGUF
    f16_path = MERGED_DIR + "-f16.gguf"
    print(f"Converting {MERGED_DIR} to f16 GGUF...")
    os.system(f"python {convert_script} {MERGED_DIR} --outtype f16 --outfile {f16_path}")

    if not os.path.isfile(f16_path):
        print(f"ERROR: f16 GGUF not created at {f16_path}")
        sys.exit(1)

    # Step 2: Quantize to Q4_K_M
    if quantize_bin:
        print(f"Quantizing to Q4_K_M with {quantize_bin}...")
        os.system(f"{quantize_bin} {f16_path} {GGUF_OUTPUT} Q4_K_M")
        os.remove(f16_path)  # Clean up large f16 file
    else:
        print("llama-quantize not found, keeping f16 GGUF")
        print(f"You can quantize later with: llama-quantize {f16_path} {GGUF_OUTPUT} Q4_K_M")
        GGUF_OUTPUT = f16_path

    # Step 3: Create Ollama model
    modelfile = f"""FROM {GGUF_OUTPUT}

PARAMETER temperature 0.1
PARAMETER num_ctx 512
PARAMETER stop "<|im_end|>"

SYSTEM \"\"\"You are a smart home assistant. You receive natural language commands and respond with JSON tool calls.

Available tools: turn_on_light, turn_off_light, dim_light, set_light_color, set_light_temperature_k, set_light_scene, blink_light, query_light_state, set_temperature, query_temperature, set_thermostat, set_ac_mode, set_fan_speed, set_humidity_target, toggle_humidifier, toggle_dehumidifier, query_humidity, open_curtains, close_curtains, raise_blinds, lower_blinds, set_blinds_position, set_blinds_angle, vacuum_start, stop_vacuum, dock_vacuum, lock_door, unlock_door, query_door_status, arm_alarm_system, disarm_alarm_system, query_alarm_status, trigger_panic_alarm, play_music, stop_music, pause_music, play_radio_station, set_volume, mute_audio, turn_on_tv, turn_off_tv, set_tv_channel, start_irrigation_zone, stop_irrigation_zone, query_soil_moisture, set_alarm, cancel_alarm, activate_scene, toggle_outlet, query_air_quality, set_motion_sensitivity

If the command is not a smart home command, respond with: {{"name": "none", "arguments": {{}}}}

Respond ONLY with JSON, no explanations.\"\"\"
"""
    modelfile_path = "/tmp/Modelfile.smart-home-v2"
    with open(modelfile_path, "w") as f:
        f.write(modelfile)

    print(f"\nGGUF created: {GGUF_OUTPUT}")
    print(f"Modelfile created: {modelfile_path}")
    print(f"\nTo create Ollama model:")
    print(f"  ollama create {OLLAMA_NAME} -f {modelfile_path}")
    print(f"\nTo test:")
    print(f'  ollama run {OLLAMA_NAME} "Turn on the kitchen lights"')

if __name__ == "__main__":
    main()