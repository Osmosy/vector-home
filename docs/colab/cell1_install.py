%%capture
import os
if not os.path.isdir("Unsloth"):
    !pip install --no-deps trl peft accelerate
    !pip install --no-deps bitsandbytes
    !pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git@main"
    !pip install --no-deps unsloth_zoo