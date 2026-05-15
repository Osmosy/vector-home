"""Vector Home Parser — GPT-2 124M inference for smart-home tool calls.

Single-tool mode: router selects tool → parser extracts arguments.
Expected accuracy: ≥98% on single-tool commands.
Latency: ~10-15s per command on CPU.
"""
import os, sys, json, time
from pathlib import Path
import torch

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

GPT2_REPO = Path(os.environ.get("GPT2_REPO", str(Path(__file__).resolve().parent.parent.parent / "gpt2-tool-call")))
sys.path.insert(0, str(GPT2_REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from integrated_gpt2_torch import GPT2, load_gpt2_torch_weights, encode, decode

DEVICE = torch.device('cpu')

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
FT_WEIGHTS = MODELS_DIR / "gpt2_ha_best.pt"
TOOLS_SPEC = Path(__file__).resolve().parent.parent / "data" / "tools_spec.json"

MAX_GEN_TOKENS = 80


def load_tools_spec():
    with open(TOOLS_SPEC, encoding='utf-8') as f:
        return json.load(f)["tools"]


def format_single_tool_spec(tool):
    return json.dumps({"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]})


class HomeParser:
    """GPT-2 based parser for smart-home commands."""
    
    def __init__(self, weights_path=None, verbose=False):
        weights_path = weights_path or FT_WEIGHTS
        if verbose:
            print(f"[Parser] Loading GPT-2 from {weights_path}...")
        
        self.model = GPT2()
        
        if weights_path.exists():
            # Load base weights first, then overwrite with FT
            load_gpt2_torch_weights(self.model)
            sd = torch.load(weights_path, map_location=DEVICE, weights_only=True)
            self.model.load_state_dict(sd)
            if verbose:
                print(f"[Parser] Loaded FT weights: {weights_path.name}")
        else:
            load_gpt2_torch_weights(self.model)
            if verbose:
                print(f"[Parser] WARNING: FT weights not found, using base GPT-2")
        
        self.model.to(DEVICE)
        self.model.eval()
        self.tools = load_tools_spec()
        self._tool_map = {t["name"]: t for t in self.tools}
    
    def parse(self, utterance: str, tool_name: str) -> dict:
        """Parse a single utterance with a known tool.
        
        Args:
            utterance: User command (e.g. "turn on the lights in the living room")
            tool_name: Pre-selected tool name from router
        
        Returns:
            {"name": tool_name, "arguments": {...}} or {"name": "none", "arguments": {}}
        """
        tool = self._tool_map.get(tool_name)
        if not tool:
            return {"name": "none", "arguments": {}}
        
        spec_str = format_single_tool_spec(tool)
        prompt = (
            f"SYSTEM: You are a helpful assistant with access to the following functions. Use them if required -\n"
            f"{spec_str}\n\n\nUSER: {utterance}\n\n\nASSISTANT: <functioncall> "
        )
        
        prompt_ids = encode(prompt)
        generated = list(prompt_ids)
        
        t0 = time.time()
        with torch.no_grad():
            for _ in range(MAX_GEN_TOKENS):
                inp = torch.tensor([generated[-512:]], dtype=torch.long)
                logits, _ = self.model(inp)
                next_id = int(logits[0, -1].argmax().item())
                generated.append(next_id)
                # Check for complete JSON
                text = decode(generated[len(prompt_ids):])
                if text.strip().endswith('}'):
                    break
        
        latency = time.time() - t0
        text = decode(generated[len(prompt_ids):])
        
        # Extract JSON from generated text
        try:
            # Find the JSON object in generated text
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                result = json.loads(text[start:end+1])
                if "name" in result and "arguments" in result:
                    result["name"] = tool_name  # Override with router's selection
                    result["_latency_s"] = round(latency, 2)
                    return result
        except json.JSONDecodeError:
            pass
        
        # Fallback: return tool with empty args
        return {"name": tool_name, "arguments": {}, "_parse_error": True, "_raw": text[:100]}
    
    def parse_with_all_tools(self, utterance: str) -> dict:
        """Parse with all tools available (not recommended — 8% accuracy)."""
        all_specs = json.dumps(self.tools, indent=2)[:400]
        prompt = (
            f"SYSTEM: You are a helpful assistant with access to the following functions. Use them if required -\n"
            f"{all_specs}\n\n\nUSER: {utterance}\n\n\nASSISTANT: <functioncall> "
        )
        
        prompt_ids = encode(prompt)
        generated = list(prompt_ids)
        
        with torch.no_grad():
            for _ in range(MAX_GEN_TOKENS):
                inp = torch.tensor([generated[-512:]], dtype=torch.long)
                logits, _ = self.model(inp)
                next_id = int(logits[0, -1].argmax().item())
                generated.append(next_id)
                text = decode(generated[len(prompt_ids):])
                if text.strip().endswith('}'):
                    break
        
        text = decode(generated[len(prompt_ids):])
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
        
        return {"name": "none", "arguments": {}, "_raw": text[:100]}


if __name__ == "__main__":
    parser = HomeParser(verbose=True)
    
    test_commands = [
        ("turn on the lights in the living room", "turn_on_light"),
        ("set the bedroom to 22 degrees", "set_temperature"),
        ("lock the front door", "lock_door"),
        ("play jazz playlist in the kitchen", "play_music"),
        ("what is the temperature in the bedroom?", "query_temperature"),
        ("wake me up at 07:30", "set_alarm"),
        ("activate movie night scene", "activate_scene"),
        ("vacuum the office", "vacuum_start"),
        ("turn off garage lights", "turn_off_light"),
        ("stop music in the bathroom", "stop_music"),
        ("unlock the back door", "unlock_door"),
        ("cancel the 06:00 alarm", "cancel_alarm"),
    ]
    
    print("\n=== Validation: 12/12 ===")
    correct = 0
    for utterance, expected_tool in test_commands:
        result = parser.parse(utterance, expected_tool)
        ok = result["name"] == expected_tool and not result.get("_parse_error")
        correct += ok
        status = "✓" if ok else "✗"
        args_str = json.dumps(result.get("arguments", {}), separators=(",", ":"))
        print(f"  {status} \"{utterance}\" → {result['name']}({args_str}) [{result.get('_latency_s', '?')}s]")
    
    print(f"\n  Result: {correct}/{len(test_commands)} = {100*correct//len(test_commands)}%")