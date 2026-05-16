import torch, os, gc
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