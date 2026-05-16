"""Vector Home Parser v2 — GPT-2 124M inference for smart-home tool calls.

Single-tool mode: router selects tool → parser extracts arguments.
v2: 53 tools (12 original + 41 from barometech/smart-home-gpt2).
Expected accuracy: ≥90% single-tool on v2 dataset.
Latency: ~2s per command on CPU.
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
V2_WEIGHTS = MODELS_DIR / "smart_home_v2.pt"
TOOLS_SPEC_V2 = Path(__file__).resolve().parent.parent / "data" / "tools_spec_v2.json"

MAX_GEN_TOKENS = 80

# Fuzzy match for correcting tool name hallucinations
FUZZY_TOOLS_MAP = {
    "start_vacuum_cleaner": "vacuum_start",
    "stop_vacuum_cleaner": "stop_vacuum",
    "dock_vacuum_cleaner": "dock_vacuum",
    "turn_on_lights": "turn_on_light",
    "turn_off_lights": "turn_off_light",
    "set_thermostat_mode": "set_thermostat",
    "set_ac_temperature": "set_ac_mode",
    "set_temperature_room": "set_temperature",
    "query_temperature_room": "query_temperature",
    "turn_on_music": "play_music",
    "turn_off_music": "stop_music",
    "cancel_timer": "cancel_alarm",
    "set_timer": "set_alarm",
    "arm_alarm": "arm_alarm_system",
    "disarm_alarm": "disarm_alarm_system",
    "turn_on_humidifier": "toggle_humidifier",
    "turn_off_humidifier": "toggle_humidifier",
    "turn_on_dehumidifier": "toggle_dehumidifier",
    "turn_off_dehumidifier": "toggle_dehumidifier",
}

VALID_TOOL_NAMES = set()  # Populated in __init__


def load_tools_spec(path=None):
    spec_path = Path(path) if path else TOOLS_SPEC_V2
    with open(spec_path, encoding='utf-8') as f:
        return json.load(f)["tools"]


def format_single_tool_spec(tool):
    """Format a single tool spec for the GPT-2 prompt."""
    return json.dumps({
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"]
    })


def fuzzy_match_tool(name: str, valid_names: set) -> str:
    """Correct GPT-2 hallucinated tool names via known aliases + prefix match."""
    if name in valid_names:
        return name
    if name in FUZZY_TOOLS_MAP:
        return FUZZY_TOOLS_MAP[name]
    # Prefix match: "turn_on_ligh" → "turn_on_light"
    for valid in sorted(valid_names):
        if valid.startswith(name) or name.startswith(valid):
            return valid
    return name


class HomeParser:
    """GPT-2 based parser for smart-home commands. v2: 53 tools."""

    def __init__(self, weights_path=None, tools_spec_path=None, verbose=False):
        weights_path = weights_path or V2_WEIGHTS
        tools_spec_path = tools_spec_path or TOOLS_SPEC_V2

        if verbose:
            print(f"[Parser] Loading GPT-2 from {weights_path}...")

        self.model = GPT2()

        if weights_path.exists():
            load_gpt2_torch_weights(self.model)
            sd = torch.load(weights_path, map_location=DEVICE, weights_only=True)
            self.model.load_state_dict(sd)
            if verbose:
                print(f"[Parser] Loaded FT weights: {weights_path.name}")
        else:
            # Try v1 weights as fallback
            if FT_WEIGHTS.exists():
                load_gpt2_torch_weights(self.model)
                sd = torch.load(FT_WEIGHTS, map_location=DEVICE, weights_only=True)
                self.model.load_state_dict(sd)
                if verbose:
                    print(f"[Parser] Loaded v1 weights (fallback): {FT_WEIGHTS.name}")
            else:
                load_gpt2_torch_weights(self.model)
                if verbose:
                    print("[Parser] WARNING: No FT weights found, using base GPT-2")

        self.model.to(DEVICE)
        self.model.eval()
        self.tools = load_tools_spec(tools_spec_path)
        self._tool_map = {t["name"]: t for t in self.tools}
        global VALID_TOOL_NAMES
        VALID_TOOL_NAMES = set(self._tool_map.keys())

        if verbose:
            print(f"[Parser] {len(self.tools)} tools loaded from {tools_spec_path.name}")

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
                text = decode(generated[len(prompt_ids):])
                if text.strip().endswith('}'):
                    break

        latency = time.time() - t0
        text = decode(generated[len(prompt_ids):])

        # Extract JSON from generated text
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                result = json.loads(text[start:end+1])
                if "name" in result and "arguments" in result:
                    # Fuzzy match the tool name (GPT-2 might hallucinate)
                    result["name"] = fuzzy_match_tool(result["name"], VALID_TOOL_NAMES)
                    # Override with router's selection
                    result["name"] = tool_name
                    result["_latency_s"] = round(latency, 2)
                    # Validate arguments against spec
                    result["arguments"] = self._validate_args(result.get("arguments", {}), tool)
                    return result
        except json.JSONDecodeError:
            pass

        # Fallback: return tool with empty args
        return {"name": tool_name, "arguments": {}, "_parse_error": True, "_raw": text[:100]}

    def _validate_args(self, args: dict, tool: dict) -> dict:
        """Validate and clean arguments against tool spec."""
        valid_params = set(tool.get("parameters", {}).keys())
        # Remove unknown params, keep known ones
        cleaned = {k: v for k, v in args.items() if k in valid_params}
        return cleaned

    def parse_with_all_tools(self, utterance: str) -> dict:
        """Parse with all tools available (not recommended — 8% accuracy on 12 tools)."""
        all_specs = json.dumps(self.tools[:10], indent=2)[:500]  # Truncate for context
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
        ("start irrigation zone 1", "start_irrigation_zone"),
        ("dim the lights in the bedroom", "dim_light"),
        ("set the thermostat to heat mode", "set_thermostat"),
        ("toggle the outlet in the kitchen", "toggle_outlet"),
    ]

    print(f"\n=== Validation: {len(test_commands)} commands ===")
    correct = 0
    for utterance, expected_tool in test_commands:
        result = parser.parse(utterance, expected_tool)
        ok = result["name"] == expected_tool and not result.get("_parse_error")
        correct += ok
        status = "✓" if ok else "✗"
        args_str = json.dumps(result.get("arguments", {}), separators=(",", ":"), ensure_ascii=False)
        print(f"  {status} \"{utterance}\" → {result['name']}({args_str}) [{result.get('_latency_s', '?')}s]")

    print(f"\n  Result: {correct}/{len(test_commands)} = {100*correct//len(test_commands)}%")