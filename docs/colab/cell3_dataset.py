import json
import requests
from datasets import Dataset

TRAIN_URL = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json"
EVAL_URL  = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json"

train_data = json.loads(requests.get(TRAIN_URL).text)
eval_data  = json.loads(requests.get(EVAL_URL).text)

print(f"Train: {len(train_data)} examples")
print(f"Eval:  {len(eval_data)} examples")

def format_to_text(example):
    messages = [
        {"role": "user", "content": example["instruction"]},
        {"role": "assistant", "content": example["output"]},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}

train_dataset = Dataset.from_list(train_data).map(format_to_text)
eval_dataset  = Dataset.from_list(eval_data).map(format_to_text)

print(f"Dataset ready: {len(train_dataset)} train, {len(eval_dataset)} eval")
print(f"Sample text[:200]: {train_dataset[0]['text'][:200]}...")