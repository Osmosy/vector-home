"""Fine-tune GPT-2 124M (EN-tuned) on RU smart-home tool-call data.

Starting from the EN-tuned model (models/gpt2_ha_best.pt), does SFT on the
mixed EN+RU dataset (data/train_dataset_ru.json) so the parser learns Russian
room/door/scene/music values while retaining EN capability.

Loss: causal LM on assistant response (mask system+user tokens with -100).
LR: 5e-6 (lower than EN FT's 1e-5, since we're fine-tuning from already-fine-tuned).
PAD=512, batch=1, grad_accum=4, 1 epoch.

Expected runtime: ~20-25 min on 4 CPU threads.
"""
import os, sys, json, time, random
from pathlib import Path
import torch
import torch.nn.functional as F

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Add gpt2-tool-call to path for model code
GPT2_REPO = Path(os.environ.get("GPT2_REPO", str(Path(__file__).resolve().parent.parent.parent / "gpt2-tool-call")))
sys.path.insert(0, str(GPT2_REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from integrated_gpt2_torch import GPT2, load_gpt2_torch_weights, encode, decode

DEVICE = torch.device('cpu')
torch.set_num_threads(4)

DATA_FILE = Path(os.environ.get("VH_DATA_RU", str(Path(__file__).resolve().parent.parent / "data" / "train_dataset_ru.json")))
OUT_DIR = Path(__file__).resolve().parent.parent / "models"
OUT_DIR.mkdir(exist_ok=True)
EN_CKPT = OUT_DIR / "gpt2_ha_best.pt"

PAD = 512
LR = 5e-6  # Lower than EN FT (1e-5) since starting from already-finetuned
BATCH = 1
GRAD_ACCUM = 4
VAL_EVERY = 40  # validate every N optimizer steps
SAVE_EVERY = 100


def load_dataset(path):
    """Load RU+EN mixed training data."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} examples from {path.name}")

    # Count RU vs EN
    ru_count = sum(1 for s in data if any(c in s['prompt'] for c in 'авнглуАВНГЛУ')
                   and '"name":"none"' not in s['gold'])
    en_count = len(data) - ru_count - sum(1 for s in data if '"name":"none"' in s['gold'])
    irrel = sum(1 for s in data if '"name":"none"' in s['gold'])
    print(f"  RU tool samples: ~{ru_count}, EN samples: ~{en_count}, Irrelevance: {irrel}")
    return data


def make_batch(samples, indices):
    B = len(indices)
    input_ids = torch.zeros((B, PAD), dtype=torch.long)
    labels = torch.full((B, PAD), -100, dtype=torch.long)
    for i, idx in enumerate(indices):
        s = samples[idx]
        prompt_ids = encode(s["prompt"])
        gold_ids = encode(s["gold"])[:80]
        max_prompt = PAD - len(gold_ids)
        prompt_ids = prompt_ids[-max_prompt:]
        seq = prompt_ids + gold_ids
        T = len(seq)
        v_start = T - len(gold_ids)
        input_ids[i, :T] = torch.tensor(seq, dtype=torch.long)
        labels[i, v_start:T] = torch.tensor(gold_ids, dtype=torch.long)
    return input_ids.to(DEVICE), labels.to(DEVICE)


def validate(model, samples, n=20):
    """Validation: autoregressive decode on n random samples, check tool name match."""
    model.eval()
    correct = 0
    total = 0
    rng = random.Random(99)
    indices = rng.sample(range(len(samples)), min(n, len(samples)))

    for idx in indices:
        s = samples[idx]
        prompt_ids = encode(s["prompt"])
        input_ids = torch.tensor([prompt_ids], dtype=torch.long)

        # Autoregressive decode up to 80 tokens
        with torch.no_grad():
            generated = list(prompt_ids)
            for _ in range(80):
                inp = torch.tensor([generated[-PAD:]], dtype=torch.long)
                logits, _ = model(inp)
                next_id = int(logits[0, -1].argmax().item())
                generated.append(next_id)
                # Stop at end of JSON
                if decode(generated[-5:]).strip().endswith('}'):
                    break

        # Extract prediction
        text = decode(generated[len(prompt_ids):])
        gold = s["gold"]
        try:
            pred_json = json.loads(text.strip().rstrip('\u0004'))
            gold_json = json.loads(gold)
            pred_name = pred_json.get("name", "")
            gold_name = gold_json.get("name", "")

            if pred_name == gold_name:
                # For room/door/scene parameters, also check value matches
                gold_args = gold_json.get("arguments", {})
                pred_args = pred_json.get("arguments", {})
                if gold_args == pred_args:
                    correct += 1
                elif gold_name == "none":
                    correct += 1  # none doesn't need args match
                else:
                    # Name correct but args differ — partial credit
                    correct += 0.5
            elif pred_name and gold_name:
                pass  # wrong tool
        except (json.JSONDecodeError, KeyError):
            pass
        total += 1

    model.train()
    return correct, total


def main():
    print("[VECTOR HOME RU FT] GPT-2 124M → RU smart-home tool-calling")
    print("=" * 55)

    # Step 1: Load base GPT-2, then overwrite with EN FT weights
    print("Loading base GPT-2 124M...")
    model = GPT2()
    load_gpt2_torch_weights(model)

    if EN_CKPT.exists():
        print(f"Loading EN FT weights from {EN_CKPT.name}...")
        sd = torch.load(EN_CKPT, map_location=DEVICE, weights_only=True)
        model.load_state_dict(sd)
        print(f"  Loaded EN FT checkpoint: {EN_CKPT.name}")
    else:
        print(f"  WARNING: {EN_CKPT} not found, starting from base GPT-2")

    model.to(DEVICE)
    model.train()
    n_p = sum(p.numel() for p in model.parameters())
    print(f"  total params: {n_p:,}")

    # Step 2: Load RU+EN dataset
    print("\nLoading RU dataset...")
    train = load_dataset(DATA_FILE)

    # Filter out irrelevance for pure FT (like EN training script)
    train_ft = [s for s in train if '"name":"none"' not in s["gold"]]
    irrel_count = len(train) - len(train_ft)
    print(f"  Single-tool samples: {len(train_ft)}")
    print(f"  Irrelevance samples: {irrel_count}")

    # Use all data including irrelevance
    random.Random(42).shuffle(train)
    N_SAMPLES = len(train)
    print(f"  Training on: {N_SAMPLES} samples (mixed EN+RU)")

    # Step 3: Configure training (lower LR for fine-tuning from already-finetuned)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)

    n_steps = N_SAMPLES // (BATCH * GRAD_ACCUM)
    print(f"\n=== Training ===  PAD={PAD} batch={BATCH}x{GRAD_ACCUM}  LR={LR}  ~{n_steps} steps")
    print(f"  Starting from: EN FT ({EN_CKPT.name})")
    print(f"  Output: {OUT_DIR / 'gpt2_ha_ru_best.pt'}")

    indices = list(range(N_SAMPLES))
    rng = random.Random(42)
    rng.shuffle(indices)

    t0 = time.time()
    step = 0
    accum = 0
    running_loss = 0.0
    opt.zero_grad()

    for i in range(0, N_SAMPLES, BATCH):
        bi = indices[i:i+BATCH]
        ii, lb = make_batch(train, bi)
        logits, _ = model(ii)
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = lb[:, 1:].contiguous()
        valid = (shift_labels != -100)
        if not valid.any():
            continue
        _, _, V = shift_logits.shape
        loss = F.cross_entropy(shift_logits.reshape(-1, V), shift_labels.reshape(-1), ignore_index=-100)
        loss_normalized = loss / GRAD_ACCUM
        loss_normalized.backward()
        running_loss += loss.item()
        accum += 1

        if accum == GRAD_ACCUM:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            opt.zero_grad()
            step += 1

            if step % 20 == 0:
                elapsed = time.time() - t0
                print(f"  step {step}/{n_steps}  loss={loss.item():.3f}  t={elapsed:.0f}s", flush=True)
                running_loss = 0.0

            if step % SAVE_EVERY == 0:
                out = OUT_DIR / f"gpt2_ha_ru_step{step}.pt"
                torch.save(model.state_dict(), out)
                # Quick validation
                c, t = validate(model, train, n=12)
                acc_pct = 100 * c / t if t > 0 else 0
                print(f"  [saved {out.name}] val={c}/{t} ({acc_pct:.0f}%)")
                model.train()

            accum = 0

    # Final save
    out = OUT_DIR / "gpt2_ha_ru_best.pt"
    torch.save(model.state_dict(), out)

    # Full validation
    print("\n=== Final Validation (20 samples) ===")
    c, t = validate(model, train, n=20)
    acc_pct = 100 * c / t if t > 0 else 0
    print(f"  Result: {c}/{t} = {acc_pct:.0f}%")

    elapsed = time.time() - t0
    print(f"\nDONE. Saved → {out.name}  ({elapsed:.0f}s = {elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()