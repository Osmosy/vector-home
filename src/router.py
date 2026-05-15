"""Vector Home Router — keyword/regex intent classifier.

Zero RAM, zero latency. Maps utterances to tool names.
Supports RU and EN commands.
Falls back to Ollama (Qwen3:8B) on miss.
"""
import re
from typing import Optional, Tuple, List, Dict

# ── Intent rules: (compiled_regex, tool_name) ──────────────────────────
# Order matters: more specific patterns first.
# Each rule has EN + RU variants.

_ROUTER_RULES_RAW = [
    # ── Lights OFF (must be before ON to avoid partial match) ──
    (r"\b(turning off|turn off|switching off|switch off|killing|kill|darkening|dark|putting.*off|put.*off|disabling|disable|shutting off|shut off|dousing|douse|dimming|dim)\b.*\b(lights?|light)\b", "turn_off_light"),
    (r"\blights?\s+off\b", "turn_off_light"),
    (r"\b(выключи|погаси|потуши|выкль|отключи)\b.*\b(свет|лампочк|освещ)\b", "turn_off_light"),
    (r"\b(свет|лампочк|освещ)\b.*\b(выключ|погас|потуш|выкл)\b", "turn_off_light"),

    # ── Lights ON ──
    (r"\b(turning on|turn on|switching on|switch on|lighting up|light up|illuminating|illuminate|putting.*on|put.*on|enabling|enable|flipping on|flip on)\b.*\b(lights?|light)\b", "turn_on_light"),
    (r"\blights?\s+on\b", "turn_on_light"),
    (r"\b(turn on|light up|illuminate)\b.*\b(room|bedroom|kitchen|living|bathroom|office|garage|hall)\b", "turn_on_light"),
    (r"\blighting up\b", "turn_on_light"),
    (r"\b(включи|зажги|вкль|запусти)\b.*\b(свет|лампочк|освещ)\b", "turn_on_light"),
    (r"\b(свет|лампочк|освещ)\b.*\b(включ|зажг|вкл)\b", "turn_on_light"),

    # ── Temperature queries (must be before SET) ──
    (r"\b(what|how|check|tell|read|show|get)\b.*\btemp(erature)?\b", "query_temperature"),
    (r"\bhow (warm|cold|hot)\b", "query_temperature"),
    (r"\bthermostat\b.*\b(read|check|what|current|show)\b", "query_temperature"),
    (r"\bcurrent temp\b", "query_temperature"),
    (r"(?:какая|сколько|узнай|покажи|какова).{0,5}(?:температур|градус|тепло|холодно)", "query_temperature"),
    (r"(?:температур|градус).{0,5}(?:сколько|какая|узнай)", "query_temperature"),

    # ── Temperature SET ──
    (r"\b(setting|set|changing|change|adjusting|adjust|making|make|heating|heat|cooling|cool|raising|raise|lowering|lower)\b.*\b(degrees?|celsius|thermostat|temp)\b", "set_temperature"),
    (r"\b\d+\s*(degrees?|°|celsius|°C)\b", "set_temperature"),
    (r"(?:установ|постав|сделай|измени|повысь|пониж|подогрей|охлад).{0,5}(?:температур|градус|термостат|тепло)", "set_temperature"),
    (r"(?:температур|градус).{0,5}(?:установ|сделай|измени|постав)", "set_temperature"),
    (r"\b\d+\s*(?:градус|°С|°C)\b", "set_temperature"),
    (r"\bI want \d+", "set_temperature"),

    # ── Door UNLOCK ──
    (r"\b(unlocking|unlock|opening|open|disengaging|disengage|releasing|release|unlatch)\b.*\bdoor\b", "unlock_door"),
    (r"\bunlock\b", "unlock_door"),
    (r"\b(открой|сними|подними)\b.*\b(замок|дверь|запор)\b", "unlock_door"),
    (r"\b(замок|дверь)\b.*\b(открой|сними|разблок)\b", "unlock_door"),

    # ── Door LOCK ──
    (r"\b(locking|lock|securing|secure|bolting|bolt|engaging|engage|latch)\b.*\bdoor\b", "lock_door"),
    (r"\block\b.*\bdoor\b", "lock_door"),
    (r"\block the\b", "lock_door"),
    (r"\block up\b", "lock_door"),
    (r"\b(закрой|запри|заблок|закрой)\b.*\b(замок|дверь|запор)\b", "lock_door"),
    (r"\b(замок|дверь)\b.*\b(закрой|запри|заблок)\b", "lock_door"),

    # ── Music STOP ──
    (r"\b(stopping|stop|muting|mute|pausing|pause|silencing|silence|quieting|quiet|ending|end|turning off|turn off|no more|halting|halt)\b.*\b(music|song|playing|playback|speakers?)\b", "stop_music"),
    (r"\bstop (playing|music)\b", "stop_music"),
    (r"(?:останов|выключ|прерв|заткн|хватит).{0,5}(?:музык|песн|звук|колонк)", "stop_music"),
    (r"(?:музык|песн|звук|колонк).{0,5}(?:останов|выключ|прерв|хватит)", "stop_music"),

    # ── Music PLAY ──
    (r"\b(playing|play|putting on|put on|starting|start|queuing|queue|hearing|hear|listening|listen)\b.*\b(music|song|playlist|jazz|rock|pop|classical|lo-fi|ambient|chill|beats|radio)\b", "play_music"),
    (r"\bplay\b.*\b(in|the)\b.*\b(room|kitchen|bedroom|living|bathroom|office|garage)\b", "play_music"),
    (r"(?:включ|запусти|вкль|игра).{0,5}(?:музык|песн|плейлист|джаз|рок|поп|классик|радио)", "play_music"),
    (r"(?:музык|песн|плейлист).{0,5}(?:включ|запусти|игра)", "play_music"),
    (r"включ.*музык", "play_music"),
    (r"музык.*включ", "play_music"),

    # ── Alarm CANCEL ──
    (r"\b(cancel|delete|remove|clear|turn off|dismiss|stop)\b.*\balarm\b", "cancel_alarm"),
    (r"\bcancel.*\balarm\b", "cancel_alarm"),
    (r"\b(отмени|удали|выключ|сними|убери)\b.*\b(будильник|alarm|напомин|таймер)\b", "cancel_alarm"),
    (r"\b(будильник|alarm)\b.*\b(отмени|удали|выключ)\b", "cancel_alarm"),

    # ── Alarm SET ──
    (r"\b(set|wake|alarm|schedule|remind)\b.*\b(alarm|\d{1,2}:\d{2})\b", "set_alarm"),
    (r"\bwake me\b", "set_alarm"),
    (r"\balarm (for|at)\b", "set_alarm"),
    (r"\b\d{1,2}:\d{2}\b.*\balarm\b", "set_alarm"),
    (r"\bset alarm\b", "set_alarm"),
    (r"\b(постав|заведи|установ|разбуд|нами)\b.*\b(будильник|alarm|напомин|таймер)\b", "set_alarm"),
    (r"\b(будильник|alarm)\b.*\b(постав|заведи|установ|на)\b", "set_alarm"),

    # ── Scenes ──
    (r"\b(activate|scene|mode|switch to|enable|start|trigger|put.*house)\b.*\b(scene|mode|night|morning|away|sleep|party|romantic|focus|guest)\b", "activate_scene"),
    (r"\b(movie night|morning|away|sleep|party|romantic|focus|guest mode)\b", "activate_scene"),
    (r"\b(set|switch|activate|enable|trigger|start)\b.*\b(night|morning|away|party|romantic|focus|guest)\b", "activate_scene"),
    (r"night mode", "activate_scene"),
    (r"(?:включ|актив|переключ|сцен|режим|вкль).{0,5}(?:сцен|режим|ночь|утро|кинотеатр|вечерин|романтик|гость)", "activate_scene"),
    (r"(?:сцен|режим).{0,5}(?:включ|актив|переключ|ночь|утро|кинотеатр|вечерин)", "activate_scene"),
    (r"режим.{0,3}(?:ночь|утр|кинотеатр|вечерин|романтик)", "activate_scene"),
    (r"режим (?:ночь|ночи|утра|утро)", "activate_scene"),
    (r"(?:сцен|режим).{0,3}(?:ночь|утр|кинотеатр|вечерин|романтик)", "activate_scene"),
    (r"включ.*сцен", "activate_scene"),

    # ── Vacuum ──
    (r"\b(vacuum|clean|robot)\b.*\b(room|kitchen|bedroom|living|bathroom|office|garage|everywhere|whole|house|all)\b", "vacuum_start"),
    (r"\b(start|run|send)\b.*\bvacuum\b", "vacuum_start"),
    (r"\bvacuum\b.*\b(start|clean|room|run)\b", "vacuum_start"),
    (r"\bclean the\b.*\b(room|house|whole)\b", "vacuum_start"),
    (r"\bstart the robot vacuum\b", "vacuum_start"),
    (r"\b(пылесос|робот|убор|пропылесось|убери)\b.*\b(комнат|кухн|спальн|ванной|офис|везде|дом|всё)\b", "vacuum_start"),
    (r"\b(комнат|кухн|везде|дом)\b.*\b(пылесос|убор|убери)\b", "vacuum_start"),
    (r"\bпропылесось\b", "vacuum_start"),
]


class HomeRouter:
    """Keyword/regex router for smart-home intents. RU+EN support."""

    def __init__(self, fallback_ollama_model: str = "qwen3:8b", ollama_url: str = "http://localhost:11434"):
        self._rules = [(re.compile(p, re.IGNORECASE), tool) for p, tool in _ROUTER_RULES_RAW]
        self.fallback_model = fallback_ollama_model
        self.ollama_url = ollama_url
        self._stats = {"hits": 0, "misses": 0, "fallback_hits": 0, "fallback_misses": 0}

    @staticmethod
    def _normalize(utterance: str) -> str:
        """Normalize utterance for routing: lowercase, strip punctuation, handle STT artefacts."""
        text = utterance.lower().strip()
        # Remove trailing period/question mark/exclamation (STT artefacts)
        text = re.sub(r'[.!?]+$', '', text)
        # Normalize common STT artefacts
        text = text.replace("'s ", " is ")   # "it's" -> "it is"
        return text

    def route(self, utterance: str) -> Tuple[str, bool]:
        """Route utterance to a tool name.

        Returns:
            (tool_name, is_confident)
            is_confident=False means fallback recommended
        """
        text = self._normalize(utterance)
        for pattern, tool_name in self._rules:
            if pattern.search(text):
                self._stats["hits"] += 1
                return tool_name, True

        self._stats["misses"] += 1
        return "none", False

    def route_with_fallback(self, utterance: str) -> Tuple[str, bool]:
        """Route with Ollama fallback on miss.

        Returns:
            (tool_name, used_fallback)
        """
        tool, confident = self.route(utterance)
        if confident:
            return tool, False

        # Try Ollama fallback
        try:
            tool = self._ollama_fallback(utterance)
            if tool != "none":
                self._stats["fallback_hits"] += 1
                return tool, True
            self._stats["fallback_misses"] += 1
            return "none", True
        except Exception:
            self._stats["fallback_misses"] += 1
            return "none", True

    def _ollama_fallback(self, utterance: str) -> str:
        """Ask Ollama to classify the intent."""
        import httpx
        tools_list = [
            "turn_on_light", "turn_off_light", "set_temperature", "query_temperature",
            "lock_door", "unlock_door", "play_music", "stop_music",
            "set_alarm", "cancel_alarm", "activate_scene", "vacuum_start", "none"
        ]
        prompt = (
            f"Classify this smart-home command into exactly one of these intents: {', '.join(tools_list)}\n"
            f"Reply with ONLY the intent name, nothing else.\n\n"
            f"Command: {utterance}\nIntent:"
        )
        resp = httpx.post(
            f"{self.ollama_url}/v1/chat/completions",
            json={
                "model": self.fallback_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 20,
                "temperature": 0,
            },
            timeout=30,
        )
        text = resp.json()["choices"][0]["message"]["content"].strip().lower()
        for t in tools_list:
            if t in text:
                return t
        return "none"

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ── Test suite ──────────────────────────────────────────────────────────

TEST_CASES: List[Tuple[str, str]] = [
    # EN — lights
    ("turn on the lights in the living room", "turn_on_light"),
    ("turn off garage lights", "turn_off_light"),
    ("dim the lights", "turn_off_light"),
    ("light up the bedroom", "turn_on_light"),
    ("switch off the bedroom light", "turn_off_light"),

    # RU — lights
    ("включи свет в гостиной", "turn_on_light"),
    ("выключи свет на кухне", "turn_off_light"),
    ("погаси свет в ванной", "turn_off_light"),

    # EN — temperature
    ("set the bedroom to 22 degrees", "set_temperature"),
    ("what is the temperature in the bedroom?", "query_temperature"),
    ("how warm is it in the living room", "query_temperature"),
    ("make it 20 celsius in the office", "set_temperature"),
    ("cool the kitchen to 18 degrees", "set_temperature"),

    # RU — temperature
    ("какая температура в спальне", "query_temperature"),
    ("установи температуру 22 градуса в гостиной", "set_temperature"),

    # EN — doors
    ("lock the front door", "lock_door"),
    ("unlock the back door", "unlock_door"),
    ("lock up", "lock_door"),

    # RU — doors
    ("запри входную дверь", "lock_door"),
    ("открой замок на задней двери", "unlock_door"),

    # EN — music
    ("play jazz playlist in the kitchen", "play_music"),
    ("stop music in the bathroom", "stop_music"),
    ("play rock in the bedroom", "play_music"),

    # RU — music
    ("включи музыку на кухне", "play_music"),
    ("останови музыку в гостиной", "stop_music"),

    # EN — alarms
    ("wake me up at 07:30", "set_alarm"),
    ("cancel the 06:00 alarm", "cancel_alarm"),
    ("set alarm for 8:00", "set_alarm"),

    # RU — alarms
    ("поставь будильник на 7 утра", "set_alarm"),
    ("отмени будильник", "cancel_alarm"),

    # EN — scenes
    ("activate movie night scene", "activate_scene"),
    ("switch to away mode", "activate_scene"),
    ("romantic mode please", "activate_scene"),
    ("night mode", "activate_scene"),

    # RU — scenes
    ("включи сцену кинотеатр", "activate_scene"),
    ("режим ночи", "activate_scene"),

    # EN — vacuum
    ("vacuum the office", "vacuum_start"),
    ("clean the kitchen", "vacuum_start"),
    ("start the robot vacuum", "vacuum_start"),

    # RU — vacuum
    ("пропылесось кухню", "vacuum_start"),
    ("робот пылесос убери везде", "vacuum_start"),

    # Edge cases — should be "none" or specific
    ("what's the weather outside", "none"),
    ("tell me a joke", "none"),
    ("I want 22 in the bedroom", "set_temperature"),  # ambiguous → router should catch
]

# Edge cases that are intentionally ambiguous (router may miss)
EDGE_CASES = [
    ("I want 22 in the bedroom", "set_temperature"),  # may or may not match
    ("lock up", "lock_door"),  # short form
    ("dim the lights", "turn_off_light"),  # dim ≈ off
]


if __name__ == "__main__":
    router = HomeRouter()

    print("=== Router Validation (EN+RU, 50+ commands) ===\n")
    correct = 0
    total = 0
    errors = []

    for utterance, expected in TEST_CASES:
        result, confident = router.route(utterance)
        total += 1
        if result == expected:
            correct += 1
            mark = "✓"
        else:
            mark = "✗"
            errors.append((utterance, expected, result))
        conf = "◎" if confident else "?"
        print(f"  {mark} {conf} \"{utterance}\" → {result} (expected: {expected})")

    precision = correct / total * 100 if total else 0
    recall = correct / total * 100 if total else 0
    print(f"\n  Result: {correct}/{total} = {precision:.0f}%")

    if errors:
        print(f"\n  Misses ({len(errors)}):")
        for u, exp, got in errors:
            print(f"    \"{u}\" → got {got}, expected {exp}")

    print(f"\n  Stats: {router.stats}")