from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = train_dataset,
    eval_dataset = eval_dataset,
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
        eval_strategy = "steps",
        eval_steps = 100,
        save_strategy = "steps",
        save_steps = 100,
        save_total_limit = 2,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        seed = 42,
        output_dir = "outputs",
        report_to = "none",
    ),
)

print("Training started...")
print(f"  Examples: {len(train_dataset)}")
print(f"  Epochs: 3, LoRA rank: 16, Batch: 16")
print(f"  Expected time: ~30-40 min on T4")

trainer_stats = trainer.train()
print(f"Done! Loss: {trainer_stats.training_loss:.4f}")