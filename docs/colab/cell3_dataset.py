import json
import requests

TRAIN_URL = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json"
EVAL_URL  = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json"

train_data = json.loads(requests.get(TRAIN_URL).text)
eval_data  = json.loads(requests.get(EVAL_URL).text)

print(f"Train: {len(train_data)} examples")
print(f"Eval:  {len(eval_data)} examples")

def formatting_func(examples):
    texts = []
    for example in examples:
        messages = [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        texts.append(text)
    return texts

print("Formatting func ready")