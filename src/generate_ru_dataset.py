#!/usr/bin/env python3
"""Generate the Russian (RU) fine-tuning dataset for Vector Home GPT-2 parser.

Creates data/train_dataset_ru.json with ~450 RU samples + ~190 EN stability samples.
Tool names and parameter keys stay EN; only parameter values become RU.
"""
import json
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# ── RU vocabulary ──────────────────────────────────────────────────────────
ROOMS_RU = {
    "living room": "гостиная",
    "bedroom": "спальня",
    "kitchen": "кухня",
    "bathroom": "ванная",
    "office": "кабинет",
    "hallway": "прихожая",
    "garage": "гараж",
    "nursery": "детская",
    "hall": "коридор",
}

DOORS_RU = {
    "front door": "входная дверь",
    "back door": "задняя дверь",
    "garage door": "гаражная дверь",
    "balcony door": "балконная дверь",
}

SCENES_RU = {
    "movie night": "кинотеатр",
    "morning": "утро",
    "night": "ночь",
    "party": "вечеринка",
    "romantic": "романтика",
    "away": "отъезд",
    "focus": "фокус",
}

MUSIC_RU = {
    "jazz": "джаз",
    "rock": "рок",
    "pop": "поп",
    "classical": "классика",
    "lo-fi": "лоу-фай",
}

# ── Tool specs (EN, matching tools_spec.json) ─────────────────────────────
TOOLS = [
    {"name": "turn_on_light", "description": "Turn on a light in a specified room", "parameters": {"room": {"type": "string", "description": "The room name"}}},
    {"name": "turn_off_light", "description": "Turn off a light in a specified room", "parameters": {"room": {"type": "string", "description": "The room name"}}},
    {"name": "set_temperature", "description": "Set the thermostat temperature for a room", "parameters": {"room": {"type": "string", "description": "The room name"}, "temperature_c": {"type": "integer", "description": "Target temperature in Celsius"}}},
    {"name": "query_temperature", "description": "Get the current temperature of a room", "parameters": {"room": {"type": "string", "description": "The room name"}}},
    {"name": "lock_door", "description": "Lock a door", "parameters": {"door": {"type": "string", "description": "The door name"}}},
    {"name": "unlock_door", "description": "Unlock a door", "parameters": {"door": {"type": "string", "description": "The door name"}}},
    {"name": "play_music", "description": "Play music in a room", "parameters": {"song": {"type": "string", "description": "Song or playlist name"}, "room": {"type": "string", "description": "The room name"}}},
    {"name": "stop_music", "description": "Stop playing music in a room", "parameters": {"room": {"type": "string", "description": "The room name"}}},
    {"name": "set_alarm", "description": "Set an alarm", "parameters": {"time": {"type": "string", "description": "Alarm time in HH:MM format"}}},
    {"name": "cancel_alarm", "description": "Cancel an alarm", "parameters": {"time": {"type": "string", "description": "Alarm time in HH:MM format"}}},
    {"name": "activate_scene", "description": "Activate a smart home scene", "parameters": {"scene": {"type": "string", "description": "Scene name e.g. movie_night, morning, away"}}},
    {"name": "vacuum_start", "description": "Start the robot vacuum cleaner", "parameters": {"room": {"type": "string", "description": "The room name or 'everywhere'"}}},
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


def make_spec(tool_name):
    t = TOOL_MAP[tool_name]
    return json.dumps({"name": t["name"], "description": t["description"], "parameters": t["parameters"]})


def make_sample(tool_name, utterance, gold_dict):
    """Build a training sample with prompt (EN spec + RU utterance) and gold."""
    spec = make_spec(tool_name)
    prompt = f"SYSTEM: You are a helpful assistant with access to the following functions. Use them if required -\n{spec}\n\n\nUSER: {utterance}\n\n\nASSISTANT: <functioncall> "
    gold = json.dumps(gold_dict, ensure_ascii=False)
    return {"prompt": prompt, "gold": gold}


# ── RU utterance templates per tool ────────────────────────────────────────
def gen_turn_on_light():
    samples = []
    templates = [
        "включи свет в {}", "включи свет в {}", "зажги свет в {}",
        "включи освещение в {}", "свет в {} пожалуйста",
        "можно свет в {}", "включи лампу в {}",
        "пожалуйста включи свет в {}", "в комнате {} включи свет",
        "включи свет в комнате {}", "давай свет в {}",
        "мне нужен свет в {}", "хочу свет в {}",
        "свет горит в {} нет включи", "включи подсветку в {}",
        "свет в {}", "включи верхний свет в {}",
        "зажги лампу в {}", "мне темно в {} включи свет",
        "свет в {} включи", "подсвети {}",
        "включи ночник в {}", "включи яркое освещение в {}",
        "включи люстру в {}", "зажги бра в {}",
        "включи торшер в {}", "освети {}",
        "включи подсветку в {}", "хочу чтобы в {} было светло",
        "включи фонарь в {}",
    ]
    for tmpl in templates:
        for en, ru in ROOMS_RU.items():
            samples.append(make_sample("turn_on_light", tmpl.format(ru),
                                       {"name": "turn_on_light", "arguments": {"room": ru}}))
    # Imperative variants
    for ru in ROOMS_RU.values():
        samples.append(make_sample("turn_on_light", f"свет в {ru}",
                                   {"name": "turn_on_light", "arguments": {"room": ru}}))
        samples.append(make_sample("turn_on_light", f"свет в {ru} включи",
                                   {"name": "turn_on_light", "arguments": {"room": ru}}))
    return samples


def gen_turn_off_light():
    samples = []
    templates = [
        "выключи свет в {}", "потуши свет в {}", "выключи освещение в {}",
        "свет в {} выключи", "выключи лампу в {}",
        "пожалуйста выключи свет в {}", "в комнате {} выключи свет",
        "выключи свет в комнате {}", "потуши свет в {}",
        "выключи люстру в {}", "выключи бра в {}",
        "хочу темноту в {} выключи свет", "выключи подсветку в {}",
        "отключи свет в {}", "погаси свет в {}",
        "свет в {} можно выключить", "в {} не нужен свет",
        "выключи верхний свет в {}", "потуши лампу в {}",
        "отключи освещение в {}",
    ]
    for tmpl in templates:
        for en, ru in ROOMS_RU.items():
            samples.append(make_sample("turn_off_light", tmpl.format(ru),
                                       {"name": "turn_off_light", "arguments": {"room": ru}}))
    for ru in ROOMS_RU.values():
        samples.append(make_sample("turn_off_light", f"выключи {ru}",
                                   {"name": "turn_off_light", "arguments": {"room": ru}}))
    return samples


def gen_set_temperature():
    samples = []
    temps = [18, 20, 22, 24, 26]
    room_subset = list(ROOMS_RU.values())[:5]  # top 5 rooms
    templates = [
        "поставь {} градусов в {}", "установи температуру {} в {}",
        "в {} установи {} градусов", "в {} сделай {} градусов",
        "температура в {} должна быть {}", "измени температуру в {} на {}",
    ]
    for tmpl in templates:
        for ru in room_subset:
            for t in temps[:3]:
                samples.append(make_sample("set_temperature", tmpl.format(t, ru),
                                           {"name": "set_temperature", "arguments": {"room": ru, "temperature_c": t}}))
    # Short forms
    for ru in room_subset:
        for t in [20, 22, 24]:
            samples.append(make_sample("set_temperature", f"{ru} {t} градусов",
                                       {"name": "set_temperature", "arguments": {"room": ru, "temperature_c": t}}))
            samples.append(make_sample("set_temperature", f"в {ru} {t} градусов",
                                       {"name": "set_temperature", "arguments": {"room": ru, "temperature_c": t}}))
    return samples


def gen_query_temperature():
    samples = []
    templates = [
        "какая температура в {}", "сколько градусов в {}",
        "какая температура в комнате {}", "какая сейчас температура в {}",
        "в {} какая температура", "покажи температуру в {}",
        "сколько в {} градусов", "термостат в {} показывает что",
        "узнай температуру в {}", "температура в {}",
        "градусы в {}", "в {} тепло или холодно",
        "жарко в {} или холодно", "как в {} с температурой",
        "какая температура у {}", "что показывает термостат в {}",
    ]
    for tmpl in templates:
        for en, ru in ROOMS_RU.items():
            samples.append(make_sample("query_temperature", tmpl.format(ru),
                                       {"name": "query_temperature", "arguments": {"room": ru}}))
    return samples


def gen_lock_door():
    samples = []
    templates = [
        "закрой {}", "запри {}", "заблокируй {}",
        "закрой на замок {}", "запри на замок {}",
        "{} закрой", "{} запри",
        "пожалуйста закрой {}", "пожалуйста запри {}",
        "закрой {} на замок", "блокируй {}",
        "обеспечь безопасность {}", "запри {} пожалуйста",
        "закрой замок на {}",
    ]
    for tmpl in templates:
        for en, ru in DOORS_RU.items():
            samples.append(make_sample("lock_door", tmpl.format(ru),
                                       {"name": "lock_door", "arguments": {"door": ru}}))
    return samples


def gen_unlock_door():
    samples = []
    templates = [
        "открой {}", "отопри {}", "разблокируй {}",
        "открой замок {}", "сними блокировку с {}",
        "{} открой", "{} отопри",
        "пожалуйста открой {}", "открой {} пожалуйста",
        "разблокируй {}", "отопри {} пожалуйста",
        "сними замок с {}", "открой замок на {}",
    ]
    for tmpl in templates:
        for en, ru in DOORS_RU.items():
            samples.append(make_sample("unlock_door", tmpl.format(ru),
                                       {"name": "unlock_door", "arguments": {"door": ru}}))
    return samples


def gen_play_music():
    samples = []
    room_subset = list(ROOMS_RU.values())[:5]  # top 5 rooms to limit combos
    templates = [
        "включи {} в {}", "играй {} в {}", "запусти {} в {}",
        "в {} включи {}", "хочу послушать {} в {}",
        "включи музыку {} в {}", "поставь {} в {}",
    ]
    for tmpl in templates:
        for song_ru in MUSIC_RU.values():
            for room_ru in room_subset[:3]:  # 3 rooms per template
                samples.append(make_sample("play_music", tmpl.format(song_ru, room_ru),
                                           {"name": "play_music", "arguments": {"song": song_ru, "room": room_ru}}))
    # Short forms
    for song_ru in MUSIC_RU.values():
        for room_ru in ["гостиная", "кухня", "спальня"]:
            samples.append(make_sample("play_music", f"{song_ru} в {room_ru}",
                                       {"name": "play_music", "arguments": {"song": song_ru, "room": room_ru}}))
    return samples


def gen_stop_music():
    samples = []
    templates = [
        "останови музыку в {}", "выключи музыку в {}",
        "прекрати музыку в {}", "выключи песню в {}",
        "музыку в {} выключи", "в {} останови музыку",
        "пауза музыка в {}", "в {} музыку стоп",
        "стоп музыка в {}", "перестань играть в {}",
        "в {} хватит музыки", "выключи песню в {}",
        "хватит музыки в {}", "тишина в {}",
    ]
    for tmpl in templates:
        for en, ru in ROOMS_RU.items():
            samples.append(make_sample("stop_music", tmpl.format(ru),
                                       {"name": "stop_music", "arguments": {"room": ru}}))
    return samples


def gen_set_alarm():
    samples = []
    times = ["06:00", "06:30", "07:00", "07:30", "08:00", "08:30", "09:00",
             "10:00", "11:00", "12:00", "14:00", "18:00", "21:00", "22:00", "23:00"]
    templates = [
        "поставь будильник на {}", "разбуди меня в {}",
        "будильник на {}", "поставь аларм на {}",
        "установи будильник {}", "поставь напоминание на {}",
        "разбуди в {}", "мне нужно проснуться в {}",
        "заведи будильник на {}", "настрой будильник на {}",
        "создай будильник {}", "будильник {}",
        "поставь таймер на {}", "разбуди завтра в {}",
        "сделай будильник на {}",
    ]
    for tmpl in templates:
        for t in times[:8]:
            samples.append(make_sample("set_alarm", tmpl.format(t),
                                       {"name": "set_alarm", "arguments": {"time": t}}))
    return samples


def gen_cancel_alarm():
    samples = []
    times = ["06:00", "06:30", "07:00", "07:30", "08:00", "09:00", "10:00", "12:00"]
    templates = [
        "отмени будильник на {}", "удали будильник {}",
        "отмени аларм {}", "выключи будильник на {}",
        "убери будильник {}", "отмени напоминание на {}",
        "мне не нужен будильник на {}", "сотри будильник {}",
        "отмени {} будильник", "удалить будильник на {}",
        "не буди меня в {}", "отключи будильник {}",
    ]
    for tmpl in templates:
        for t in times[:6]:
            samples.append(make_sample("cancel_alarm", tmpl.format(t),
                                       {"name": "cancel_alarm", "arguments": {"time": t}}))
    return samples


def gen_activate_scene():
    samples = []
    templates = [
        "включи сцену {}", "активируй {}", "запусти сцену {}",
        "переключи на {}", "режим {}",
        "включи режим {}", "сцена {}",
        "настрой {}", "давай сцену {}",
        "активируй сцену {}", "{} режим включи",
        "хочу сцену {}", "перейди в режим {}",
        "включи {}", "давай {}",
    ]
    for tmpl in templates:
        for en, ru in SCENES_RU.items():
            samples.append(make_sample("activate_scene", tmpl.format(ru),
                                       {"name": "activate_scene", "arguments": {"scene": ru}}))
    return samples


def gen_vacuum_start():
    samples = []
    templates = [
        "запусти пылесос в {}", "пропылесось {}", "робот пылесос в {}",
        "включи пылесос в {}", "в {} запусти пылесос",
        "начни уборку в {}", "пропылесось комнату {}",
        "в {} пропылесось", "робот убери в {}",
        "включи робот пылесос в {}", "убери в {}",
        "запусти уборку в {}", "почисти {}",
        "пылесос в {} включи", "робот-пылесос в {}",
    ]
    for tmpl in templates:
        for en, ru in ROOMS_RU.items():
            samples.append(make_sample("vacuum_start", tmpl.format(ru),
                                       {"name": "vacuum_start", "arguments": {"room": ru}}))
    # everywhere variant
    everywhere_templates = [
        "пропылесось везде", "запусти пылесос везде",
        "убери везде", "пылесос по всему дому",
        "робот пылесос везде", "включи уборку везде",
        "пропылесось весь дом", "уборка везде",
    ]
    for tmpl in everywhere_templates:
        samples.append(make_sample("vacuum_start", tmpl,
                                   {"name": "vacuum_start", "arguments": {"room": "везде"}}))
    return samples


def gen_irrelevance_ru():
    samples = []
    irrel_utterances = [
        "расскажи анекдот", "который час", "какая сегодня погода",
        "расскажи сказку", "что ты умеешь", "привет",
        "пока", "как дела", "кто ты",
        "спасибо", "что нового", "расскажи историю",
        "спой песню", "как тебя зовут", "сколько тебе лет",
        "кто президент", "какой сегодня день", "что приготовить на ужин",
        "расскажи новость", "что такое искусственный интеллект",
        "напиши стихотворение", "переведи слово", "помоги с домашкой",
        "как добраться до вокзала", "кто создатель питона",
    ]
    for utt in irrel_utterances:
        # Use a random single-tool spec for irrelevance
        for tool in TOOLS[:4]:  # just a few tool specs for variety
            spec = json.dumps({"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]})
            prompt = f"SYSTEM: You are a helpful assistant with access to the following functions. Use them if required -\n{spec}\n\n\nUSER: {utt}\n\n\nASSISTANT: <functioncall> "
            samples.append({"prompt": prompt, "gold": '{"name":"none","arguments":{}}'})
            break  # one spec per irrelevance utterance is enough
    return samples


def load_en_dataset():
    """Load EN dataset for stability mixing."""
    path = BASE / "data" / "train_dataset.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=== Generating RU fine-tuning dataset ===\n")

    all_samples = []
    TARGET_PER_TOOL = 40  # target ~40 RU samples per tool

    per_tool = {
        "turn_on_light": gen_turn_on_light,
        "turn_off_light": gen_turn_off_light,
        "set_temperature": gen_set_temperature,
        "query_temperature": gen_query_temperature,
        "lock_door": gen_lock_door,
        "unlock_door": gen_unlock_door,
        "play_music": gen_play_music,
        "stop_music": gen_stop_music,
        "set_alarm": gen_set_alarm,
        "cancel_alarm": gen_cancel_alarm,
        "activate_scene": gen_activate_scene,
        "vacuum_start": gen_vacuum_start,
    }

    rng = random.Random(42)

    for tool_name, gen_fn in per_tool.items():
        samples = gen_fn()
        # Deduplicate by (prompt, gold) pair
        seen = set()
        unique = []
        for s in samples:
            key = (s["prompt"], s["gold"])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        # Cap at TARGET_PER_TOOL
        if len(unique) > TARGET_PER_TOOL:
            unique = rng.sample(unique, TARGET_PER_TOOL)
            unique.sort(key=lambda s: s["gold"])  # deterministic order
        print(f"  {tool_name}: {len(unique)} RU samples")
        all_samples.extend(unique)

    # Irrelevance samples (25 RU)
    irrel = gen_irrelevance_ru()
    seen = set()
    unique_irrel = []
    for s in irrel:
        key = (s["prompt"], s["gold"])
        if key not in seen:
            seen.add(key)
            unique_irrel.append(s)
    print(f"  irrelevance: {len(unique_irrel)} RU samples")
    all_samples.extend(unique_irrel)

    # Add EN stability samples (30% of 658 ≈ 190)
    en_data = load_en_dataset()
    n_en = min(190, len(en_data))
    en_subset = rng.sample(en_data, n_en)
    print(f"\n  EN stability samples: {len(en_subset)}")
    all_samples.extend(en_subset)

    # Shuffle
    rng.shuffle(all_samples)

    print(f"\n  Total: {len(all_samples)} samples")

    # Save
    out_path = BASE / "data" / "train_dataset_ru.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)
    print(f"  Saved to {out_path}")

    # Stats
    irrel_count = sum(1 for s in all_samples if '"name":"none"' in s["gold"])
    print(f"\n  RU tool samples: {len(all_samples) - len(en_subset) - len(unique_irrel)}")
    print(f"  RU irrelevance: {len(unique_irrel)}")
    print(f"  EN stability: {len(en_subset)}")
    print(f"  Total: {len(all_samples)}")
    print(f"  Irrelevance (incl EN): {irrel_count}")
    print("  DONE")


if __name__ == "__main__":
    main()