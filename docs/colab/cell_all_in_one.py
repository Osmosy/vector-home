import subprocess, sys, os, shutil

# Step 0: Check if merged model already exists (skip training if yes)
MERGED_DIR = "/content/merged_model"
TAR_FILE = "/content/smart-home-v2-merged.tar"

if os.path.exists(os.path.join(MERGED_DIR, "config.json")):
    print(f"✓ Merged model already exists at {MERGED_DIR}, skipping training!")
    print(f"Files: {os.listdir(MERGED_DIR)[:5]}")
    # Just create the tar archive for download
    if not os.path.exists(TAR_FILE):
        print("Creating archive for download...")
        shutil.make_archive(TAR_FILE.replace(".tar", ""), "tar", "/content", "merged_model")
        print(f"Archive: {TAR_FILE} ({os.path.getsize(TAR_FILE)/(1024**3):.2f} GB)")
    else:
        print(f"Archive already exists: {TAR_FILE} ({os.path.getsize(TAR_FILE)/(1024**3):.2f} GB)")
    print("\\n✓ DONE! Files ready:")
    print(f"  {MERGED_DIR}/  (16-bit merged)")
    print(f"  {TAR_FILE}  (archive for download)")
    print("\\n👉 Download: click 📁 icon (left sidebar) → right-click tar file → Download")
else:
    print("No existing merged model found. Starting full training pipeline...")

    # Step 1: Install dependencies
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
        "unsloth",
        "transformers>=4.47.0",
        "bitsandbytes",
        "peft",
        "accelerate",
        "trl",
        "datasets",
    ])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
        "--no-deps", "unsloth_zoo"])

    import torch, gc
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    torch.cuda.empty_cache()
    gc.collect()

    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "unsloth/Qwen3-4B",
        max_seq_length = 512,
        load_in_4bit = True,
        full_finetuning = False,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r = 16,
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
        lora_alpha = 32,
        lora_dropout = 0,
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 42,
    )
    print(f"Model loaded. Trainable: {model.print_trainable_parameters()}")

    import json, requests
    from datasets import Dataset

    train_data = json.loads(requests.get("https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json").text)
    eval_data  = json.loads(requests.get("https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json").text)

    def format_to_text(example):
        messages = [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        return {"text": text}

    train_dataset = Dataset.from_list(train_data).map(format_to_text)
    eval_dataset  = Dataset.from_list(eval_data).map(format_to_text)
    print(f"Dataset: {len(train_dataset)} train, {len(eval_dataset)} eval")

    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported

    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = train_dataset,
        max_seq_length = 512,
        dataset_num_proc = 2,
        args = TrainingArguments(
            num_train_epochs = 3,
            per_device_train_batch_size = 4,
            gradient_accumulation_steps = 4,
            learning_rate = 2e-4,
            warmup_steps = 50,
            lr_scheduler_type = "cosine",
            bf16 = is_bfloat16_supported(),
            fp16 = not is_bfloat16_supported(),
            logging_steps = 25,
            eval_strategy = "no",
            save_strategy = "steps",
            save_steps = 200,
            save_total_limit = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            seed = 42,
            output_dir = "outputs",
            report_to = "none",
        ),
    )

    print(f"Training: {len(train_dataset)} ex, batch=4x4=16, seq=512, ~20-30 min")
    trainer_stats = trainer.train()
    print(f"Done! Loss: {trainer_stats.training_loss:.4f}")

    # Save merged model (16-bit)
    print("Saving merged 16-bit model...")
    model.save_pretrained_merged("merged_model", tokenizer, save_method="merged_16bit")

    print("Saving LoRA adapter separately...")
    model.save_pretrained("smart-home-v2-lora")
    tokenizer.save_pretrained("smart-home-v2-lora")

    # Compress for download
    print("Creating archive for download...")
    shutil.make_archive(TAR_FILE.replace(".tar", ""), "tar", "/content", "merged_model")
    size_gb = os.path.getsize(TAR_FILE) / (1024**3)
    print(f"Archive created: {TAR_FILE}")
    print(f"Size: {size_gb:.2f} GB")

    print("\\n=== DONE! Files saved: ===")
    print(f"  {MERGED_DIR}/  (16-bit merged)")
    print(f"  /content/smart-home-v2-lora/  (LoRA adapter)")
    print(f"  {TAR_FILE}  (archive for download)")

# Step 2: Start HTTP server for download (always)
import threading, http.server as hs

filepath = TAR_FILE if os.path.exists(TAR_FILE) else None

if filepath and os.path.exists(filepath):
    size_gb = os.path.getsize(filepath) / (1024**3)
    print(f"\\n📦 Download: {filepath} ({size_gb:.2f} GB)")

    class Handler(hs.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/download':
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-tar')
                self.send_header('Content-Disposition', 'attachment; filename="smart-home-v2-merged.tar"')
                size = os.path.getsize(filepath)
                self.send_header('Content-Length', str(size))
                self.end_headers()
                transferred = 0
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        transferred += len(chunk)
                        if transferred % (10 * 1024 * 1024) == 0:
                            print(f"  Sent: {transferred/(1024**3):.2f} GB")
                print("✓ Download complete!")
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f'<h1>Smart Home v2 Model</h1><p>File: {filepath}</p><p><a href="/download">⬇ Download ({size_gb:.2f} GB)</a></p>'.encode())

    server = hs.HTTPServer(('0.0.0.0', 8888), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("🚀 HTTP server running on port 8888")
    print("👉 Download URL: http://localhost:8888/download")
else:
    print("\\n⚠ No tar file found! Training may have failed.")
    print("👉 Use the 📁 icon on the left sidebar to check /content/")