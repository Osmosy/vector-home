import json
import requests

TRAIN_URL = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_train.json"
EVAL_URL  = "https://raw.githubusercontent.com/Osmosy/vector-home/main/data/unified_eval.json"

train_data = json.loads(requests.get(TRAIN_URL).text)
eval_data  = json.loads(requests.get(EVAL_URL).text)

print(f"Train: {len(train_data)} examples")
print(f"Eval:  {len(eval_data)} examples")

def format_example(example):
    return {
        "messages": [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example["output"]},
        ]
    }

train_formatted = [format_example(ex) for ex in train_data]
eval_formatted  = [format_example(ex) for ex in eval_data]
print(f"Formatting done")
print(f"Prompt sample: {train_formatted[0]['messages'][0]['content'][:150]}...")
print(f"Output sample: {train_formatted[0]['messages'][1]['content'][:150]}...")