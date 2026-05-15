"""Full fine-tune GPT-2 124M on Vector Home smart-home tool-call data.

Adapted from barometech/gpt2-tool-call train_ft.py for HA domain.
Loss: causal LM on assistant response (mask system+user tokens with -100).
LR: 1e-5, AdamW. PAD=512. batch=1, grad_accum=4. 1 epoch over ~650 samples.

Expected runtime: ~24-30 min on 4 CPU threads.
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

DATA_FILE = Path(os.environ.get("VH_DATA", str(Path(__file__).resolve().parent.parent / "data" / "train_dataset.json")))
OUT_DIR = Path(__file__).resolve().parent.parent / "models"
OUT_DIR.mkdir(exist_ok=True)

PAD = 512
LR = 1e-5
BATCH = 1
GRAD_ACCUM = 4
SAVE_EVERY = 100


def load_dataset(path):
    """Load Vector Home training data."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} examples from {path.name}")
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


def validate(model, samples, n=12):
    """Quick validation: run single-tool inference on n random samples."""
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
            pred_json = json.loads(text.strip().rstrip('<|endoftext|>'))
            gold_json = json.loads(gold)
            if pred_json.get("name") == gold_json.get("name"):
                correct += 1
        except (json.JSONDecodeError, KeyError):
            pass
        total += 1
    
    model.train()
    return correct, total


def main():
    print("[VECTOR HOME FT] GPT-2 124M → HA tool-calling")
    print("=" * 50)
    
    print("Loading base GPT-2 124M...")
    model = GPT2()
    load_gpt2_torch_weights(model)
    model.to(DEVICE)
    model.train()
    n_p = sum(p.numel() for p in model.parameters())
    print(f"  total params: {n_p:,}")

    print("Loading dataset...")
    train = load_dataset(DATA_FILE)
    # Filter out irrelevance for pure single-tool FT
    train_ft = [s for s in train if '"name":"none"' not in s["gold"]]
    print(f"  Single-tool samples: {len(train_ft)}")
    print(f"  Irrelevance samples: {len(train) - len(train_ft)}")
    
    # Use all data including irrelevance
    random.Random(42).shuffle(train)
    N_SAMPLES = len(train)
    print(f"  Training on: {N_SAMPLES} samples")

    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    
    n_steps = N_SAMPLES // (BATCH * GRAD_ACCUM)
    print(f"\n=== Training ===  PAD={PAD} batch={BATCH}x{GRAD_ACCUM}  LR={LR}  ~{n_steps} steps")
    
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
                out = OUT_DIR / f"gpt2_ha_step{step}.pt"
                torch.save(model.state_dict(), out)
                # Quick validation
                c, t = validate(model, train, n=12)
                print(f"  [saved {out.name}] val={c}/{t}")
                model.train()
            
            accum = 0

    # Final save
    out = OUT_DIR / "gpt2_ha_final.pt"
    torch.save(model.state_dict(), out)
    
    # Full validation
    print("\n=== Final Validation (12 samples) ===")
    c, t = validate(model, train, n=12)
    print(f"  Result: {c}/{t} = {100*c/t:.0f}%")
    
    elapsed = time.time() - t0
    print(f"\nDONE. Saved → {out.name}  ({elapsed:.0f}s = {elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()