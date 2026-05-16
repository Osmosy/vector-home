FastLanguageModel.for_inference(model)

test_prompts = [
    "Turn on the lights in the kitchen",
    "Set temperature to 22 degrees in the living room",
    "включи свет на кухне",
    "поставь будильник на 7 утра",
    "dim the lights to 30 percent",
    "query humidity in the bedroom",
]

for prompt in test_prompts:
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to("cuda")

    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=128,
        temperature=0.1,
        do_sample=False,
    )

    response = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True)
    print(f"Q: {prompt}")
    print(f"A: {response.strip()}")
    print()