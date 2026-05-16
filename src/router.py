"""Vector Home Router v2 — keyword/regex intent classifier.

Zero RAM, zero latency. Maps utterances to 53 tool names.
Supports RU and EN commands. Falls back to Ollama (Qwen3:8B) on miss.

CRITICAL: Rule ORDER matters — more specific patterns MUST come before general ones.
NOTE: \b word boundary is BROKEN for Cyrillic in Python regex.
      All RU patterns use bare text without \b around Russian words.
      EN substrings like "irrigat" also don't use \b (would fail on "irrigation").
"""

import re
from typing import Tuple, List, Dict

# ── Intent rules: (raw_regex, tool_name) ────────────────────────────────
# ORDER MATTERS: specific → general.
# \b is NOT used around Cyrillic words (Python regex bug).
# \b is NOT used around partial English words like "irrigat", "сигнализац".
_ROUTER_RULES_RAW = [
    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 1: Ambiguous patterns that would match wrong intent
    # ══════════════════════════════════════════════════════════════════

    # ── "is the light on/off" → QUERY, not action ──
    (r"\b(is|are)\b.{0,10}\blights?\b.{0,5}\b(on|off|state|status)\b", "query_light_state"),
    (r"\blights?\b.{0,5}\b(on|off)\b.{0,10}\b\?", "query_light_state"),

    # ── LIGHT TEMPERATURE before LIGHT COLOR ──
    (r"\bcolor temperature\b", "set_light_temperature_k"),
    (r"\b(digital |cool |warm )white\b", "set_light_temperature_k"),
    (r"\bkelvin\b.{0,20}\blights?\b", "set_light_temperature_k"),
    (r"\b(set|change|adjust)\b.{0,20}\b(kelvin|color temperature|colour temperature)\b", "set_light_temperature_k"),
    (r"(?:температур.*цвет|цветов.*температур|тёплый свет|холодный свет|кельвин)", "set_light_temperature_k"),

    # ── DIM before OFF ──
    (r"\bdim\b.{0,20}\blights?\b", "dim_light"),
    (r"\b(dim|lower|soften|dusk)\b.{0,20}\blights?\b", "dim_light"),
    (r"\blights?\b.{0,10}\b(dim|lower|soften|dusk)\b", "dim_light"),
    (r"(?:приглуш|убав|снизь).{0,15}(?:свет|яркость|лампочк|освещ)", "dim_light"),
    (r"(?:свет|яркость|лампочк|освещ).{0,10}(?:приглуш|убав|снизь)", "dim_light"),

    # ── BLINK before ON ──
    (r"\bblink\b.{0,20}\blights?\b", "blink_light"),
    (r"\bflash\b.{0,20}\blights?\b", "blink_light"),
    (r"\blights?\b.{0,10}\b(blink|flash)\b", "blink_light"),
    (r"(?:моргн|мигн|blink).{0,15}(?:свет|лампочк|освещ)", "blink_light"),

    # ── LIGHT COLOR (after temperature_k) ──
    (r"\b(set|change|make|turn|paint)\b.{0,20}\b(color|colour|rgb|hue)\b.{0,20}\blights?\b", "set_light_color"),
    (r"\blights?\b.{0,10}\b(color|colour|rgb|hue)\b", "set_light_color"),
    (r"\b(red|blue|green|purple|orange|pink|yellow)\b.{0,15}\blights?\b", "set_light_color"),
    (r"\bmake the lights?\b.{0,10}\b(red|blue|green|purple|orange|pink|yellow)\b", "set_light_color"),
    (r"(?:цвет|окрас|сделай.*цвет).{0,20}(?:свет|лампочк|освещ)", "set_light_color"),
    (r"(?:свет|лампочк|освещ).{0,10}(?:цвет|окрас|синий|красн|зелён|розов|фиолет)", "set_light_color"),

    # ── LIGHT SCENE (before general activate_scene) ──
    (r"\b(set|activate|turn on|enable)\b.{0,20}\b(scene|effect|mood|ambiance)\b.{0,20}\blights?\b", "set_light_scene"),
    (r"\blights?\b.{0,10}\b(scene|effect|mood|ambiance)\b", "set_light_scene"),
    (r"\bactivate mood lighting\b", "set_light_scene"),
    (r"\bmood lighting\b", "set_light_scene"),
    (r"(?:сцен|эффект|режим).{0,15}(?:освещ|свет|лампочк)", "set_light_scene"),
    (r"(?:освещ|свет|лампочк).{0,10}(?:сцен|эффект|режим)", "set_light_scene"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 2: TV (before generic turn on/off light)
    # ══════════════════════════════════════════════════════════════════
    (r"\b(turn on|switch on|start|power on)\b.{0,20}\b(tv|television|telly)\b", "turn_on_tv"),
    (r"\b(tv|television|telly)\b.{0,10}\b(on|start|power)\b", "turn_on_tv"),
    (r"(?:включи|запусти).{0,15}(?:телевизор|тв|tv)", "turn_on_tv"),
    (r"(?:телевизор|тв|tv).{0,10}(?:включ|запусти|на)", "turn_on_tv"),

    (r"\b(turn off|switch off|shut off|power off|close)\b.{0,20}\b(tv|television|telly)\b", "turn_off_tv"),
    (r"\b(tv|television)\b.{0,10}\b(off|shut|close)\b", "turn_off_tv"),
    (r"(?:выключи|закрой|отключ).{0,15}(?:телевизор|тв|tv)", "turn_off_tv"),

    (r"\b(set|change|switch|tune|flip)\b.{0,20}\b(channel|station)\b.{0,20}\b(tv|television)\b", "set_tv_channel"),
    (r"\b(tv|television)\b.{0,10}\bchannel\b", "set_tv_channel"),
    (r"\bswitch channel\b", "set_tv_channel"),
    (r"(?:канал|переключ|стаци).{0,15}(?:телевизор|тв|tv)", "set_tv_channel"),

    (r"\b(set|change|adjust|turn|increase|decrease|raise|lower)\b.{0,20}\bvolume\b.{0,20}\b(tv|television|telly)\b", "set_tv_volume"),
    (r"\b(tv|television|telly)\b.{0,10}\b(volume|sound)\b", "set_tv_volume"),
    (r"(?:громк|звук).{0,10}(?:телевизор|тв|tv)", "set_tv_volume"),
    (r"(?:телевизор|тв|tv).{0,10}(?:громк|звук)", "set_tv_volume"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 3: Radio (before generic play_music)
    # ══════════════════════════════════════════════════════════════════
    (r"\b(play|turn on|start|listen to?|tune)\b.{0,20}\bradio\b", "play_radio_station"),
    (r"\bradio\b.{0,10}\b(station|fm|on|play|listen)\b", "play_radio_station"),
    (r"(?:радио|станци|fm).{0,10}(?:включ|запусти|игра|слушай|настрой)", "play_radio_station"),
    (r"(?:включ|запусти|настрой|слушай).{0,15}(?:радио|fm|станци)", "play_radio_station"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 4: Pause before Stop (music)
    # ══════════════════════════════════════════════════════════════════
    (r"\bpause\b.{0,20}\b(music|song|playback|player|audio)\b", "pause_music"),
    (r"\b(music|song|playback|audio)\b.{0,10}\bpause\b", "pause_music"),
    (r"(?:пауз|приостанов).{0,15}(?:музык|песн|звук)", "pause_music"),
    (r"(?:музык|песн|звук).{0,10}(?:пауз|приостанов)", "pause_music"),

    # ── MUTE (before generic volume) ──
    (r"\bmut(?:e|ing)\b.{0,20}\b(audio|music|tv|sound|speaker|volume)\b", "mute_audio"),
    (r"\b(audio|music|tv|sound|speaker|volume)\b.{0,10}\bmut(?:e|ing)\b", "mute_audio"),
    (r"(?:выключ.*звук|беззвуч|muteрежим|тих.*звук|заглуш|заглуш звук)", "mute_audio"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 5: Cancel_alarm before Disarm_alarm_system
    # ══════════════════════════════════════════════════════════════════
    (r"\bcancel\b.{0,20}\balarm\b", "cancel_alarm"),
    (r"\b(delete|remove|clear|dismiss)\b.{0,20}\balarm\b", "cancel_alarm"),
    (r"(?:отмени|удали|сними|убери).{0,15}(?:будильник|alarm|таймер)", "cancel_alarm"),
    (r"(?:будильник|alarm|таймер).{0,10}(?:отмени|удали|сними)", "cancel_alarm"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 6: Set_alarm before generic "set"
    # ══════════════════════════════════════════════════════════════════
    (r"\b(set|wake|schedule|remind)\b.{0,20}\balarm\b", "set_alarm"),
    (r"\bwake me\b", "set_alarm"),
    (r"\balarm (for|at)\b", "set_alarm"),
    (r"\b\d{1,2}:\d{2}\b.{0,20}\balarm\b", "set_alarm"),
    (r"\bset alarm\b", "set_alarm"),
    (r"(?:постав|заведи|установ|разбуд|нами).{0,15}(?:будильник|alarm|напомин|таймер)", "set_alarm"),
    (r"(?:будильник|alarm).{0,10}(?:постав|заведи|установ|на)", "set_alarm"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 7: Blinds angle before set_temperature (degrees)
    # ══════════════════════════════════════════════════════════════════
    (r"\btilt\b.{0,20}\b(blinds?|shades?)\b", "set_blinds_angle"),
    (r"\b(blinds?|shades?)\b.{0,10}\b(angle|tilt|slat)\b", "set_blinds_angle"),
    (r"(?:угол|наклон|повор).{0,15}(?:жалюзи|ролет|шторк)", "set_blinds_angle"),

    (r"\b(set|adjust|move|position|tilt)\b.{0,20}\b(blinds?|shades?)\b.{0,15}\b(percent|position|%)\b", "set_blinds_position"),
    (r"\b(blinds?|shades?)\b.{0,10}\b(position|percent|%)\b", "set_blinds_position"),
    (r"(?:жалюзи|ролет|шторк).{0,10}(?:позиций|процент|положен)", "set_blinds_position"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 9: Outlet BEFORE generic turn on/off
    # ══════════════════════════════════════════════════════════════════
    (r"\b(toggle|turn on|turn off|switch|plug in|unplug)\b.{0,20}\boutlet\b", "toggle_outlet"),
    (r"\boutlet\b.{0,10}\b(on|off|toggle|switch|plug)\b", "toggle_outlet"),
    (r"(?:розетк|включ.*розетк|выключ.*розетк|переключ.*розетк)", "toggle_outlet"),

    # ══════════════════════════════════════════════════════════════════
    #  PRIORITY BLOCK 10: Humidifier/Dehumidifier before generic "turn on"
    # ══════════════════════════════════════════════════════════════════
    (r"\b(turn on|start|enable|activate|turn off|stop|disable|toggle)\b.{0,20}\bhumidifier\b", "toggle_humidifier"),
    (r"\bhumidifier\b.{0,10}\b(on|off|toggle)\b", "toggle_humidifier"),
    (r"(?:включи|выключи|переключи).{0,15}(?:увлажнит|humidifier)", "toggle_humidifier"),
    (r"(?:увлажнит|humidifier).{0,10}(?:включ|выключ|переключ)", "toggle_humidifier"),

    (r"\b(turn on|start|enable|activate|turn off|stop|disable|toggle)\b.{0,20}\bdehumidifier\b", "toggle_dehumidifier"),
    (r"\bdehumidifier\b.{0,10}\b(on|off|toggle)\b", "toggle_dehumidifier"),
    (r"(?:включи|выключи|переключи).{0,15}(?:осушит|dehumidifier)", "toggle_dehumidifier"),

    # ══════════════════════════════════════════════════════════════════
    #  GENERAL INTENTS (after all priority blocks)
    # ══════════════════════════════════════════════════════════════════

    # ── LIGHTS OFF (before ON) ──
    (r"\b(turning off|turn off|switching off|switch off|killing|kill|darkening|dark|putting.*off|put.*off|disabling|disable|shutting off|shut off|dousing|douse)\b.{0,20}\blights?\b", "turn_off_light"),
    (r"\blights?\s+off\b", "turn_off_light"),
    (r"(?:выключи|погаси|потуши|выкль|отключи).{0,15}(?:свет|лампочк|освещ)", "turn_off_light"),
    (r"(?:свет|лампочк|освещ).{0,10}(?:выключ|погас|потуш|выкл)", "turn_off_light"),

    # ── LIGHTS ON ──
    (r"\b(turning on|turn on|switching on|switch on|lighting up|light up|illuminating|illuminate|putting.*on|put.*on|enabling|enable|flipping on|flip on)\b.{0,20}\blights?\b", "turn_on_light"),
    (r"\blights?\s+on\b", "turn_on_light"),
    (r"\b(turn on|light up|illuminate)\b.{0,20}\b(room|bedroom|kitchen|living|bathroom|office|garage|hall)\b", "turn_on_light"),
    (r"\blighting up\b", "turn_on_light"),
    (r"(?:включи|зажги|вкль|запусти).{0,15}(?:свет|лампочк|освещ)", "turn_on_light"),
    (r"(?:свет|лампочк|освещ).{0,10}(?:включ|зажг|вкл)", "turn_on_light"),

    # ── QUERY LIGHT STATE ──
    (r"\b(what|check|query|tell|show|get)\b.{0,20}\blight(s| state| status)?\b", "query_light_state"),
    (r"(?:включен|выключен|состоян|статус).{0,15}(?:свет|лампочк|освещ)", "query_light_state"),
    (r"(?:свет|лампочк|освещ).{0,10}(?:включен|выключен|состоян|статус)", "query_light_state"),

    # ── Thermostat (before AC mode — thermostat word takes priority!) ──
    # EXCLUDE when AC/кондиционер mentioned — those go to set_ac_mode
    (r"\b(set|change|adjust|put|switch)\b.{0,20}\bthermostat\b", "set_thermostat"),
    (r"(?:термостат).{0,20}(?:режим|на|установ)", "set_thermostat"),

    # ── CLIMATE: AC Mode (after thermostat — only if no "thermostat" word) ──
    (r"\b(set|switch|change|put|turn)\b.{0,20}\b(ac|air.condition|кондиционер|сплит)\b.{0,15}\b(mode|cool|heat|auto|dry)\b", "set_ac_mode"),
    (r"\b(ac|air.condition)\b.{0,10}\b(mode|cool|heat|auto|dry)\b", "set_ac_mode"),
    (r"\b(cool|heat|auto|dry) mode\b", "set_ac_mode"),
    (r"(?:кондиционер).{0,10}(?:режим|охлажд|обогр|авто|сух|вентил)", "set_ac_mode"),
    (r"(?:режим|охлажд|обогр|авто).{0,10}(?:кондиционер|сплит|ac)", "set_ac_mode"),

    # ── Temperature QUERY before SET ──
    (r"\b(what|how|check|tell|read|show|get)\b.{0,20}\btemp(erature)?\b", "query_temperature"),
    (r"\bhow (warm|cold|hot)\b", "query_temperature"),
    (r"\bthermostat\b.{0,10}\b(read|check|what|current|show)\b", "query_temperature"),
    (r"\bcurrent temp\b", "query_temperature"),
    (r"(?:какая|сколько|узнай|покажи|какова).{0,10}(?:температур|градус|тепло|холодно)", "query_temperature"),
    (r"(?:температур|градус).{0,10}(?:сколько|какая|узнай)", "query_temperature"),

    # ── Temperature SET ──
    (r"\b(setting|set|changing|change|adjusting|adjust|making|make|heating|heat|cooling|cool|raising|raise|lowering|lower)\b.{0,20}\b(degrees?|celsius|thermostat|temp)\b", "set_temperature"),
    (r"\b\d+\s*(degrees?|°|celsius|°C)\b", "set_temperature"),
    (r"(?:установ|постав|сделай|измени|повысь|пониж|подогрей|охлад).{0,10}(?:температур|градус|термостат|тепло)", "set_temperature"),
    (r"(?:температур|градус).{0,10}(?:установ|сделай|измени|постав)", "set_temperature"),
    (r"\b\d+\s*(?:градус|°С|°C)", "set_temperature"),
    (r"\bI want \d+\b", "set_temperature"),

    # ── Fan ──
    (r"\b(set|change|adjust|increase|decrease)\b.{0,20}\bfan\b.{0,10}\b(speed|level|percent)\b", "set_fan_speed"),
    (r"\bfan\b.{0,10}\b(speed|high|low|medium)\b", "set_fan_speed"),
    (r"\b(speed|high|low|medium)\b.{0,10}\bfan\b", "set_fan_speed"),
    (r"(?:вентил|вентилятор|скорость.*вентил|вентил.*скорость)", "set_fan_speed"),

    # ── Humidity QUERY (before Target — "какая влажность" is a question, not a command) ──
    (r"\b(what|check|query|tell|show|is|how|get)\b.{0,20}\bhumidity\b", "query_humidity"),
    (r"\bhumidity\b.{0,10}\b(what|how|check|is|level|percent)\b", "query_humidity"),
    (r"(?:какая|сколько|узнай|покажи).{0,10}(?:влажност|влажн)", "query_humidity"),
    (r"(?:влажност|влажн).{0,10}(?:какая|сколько|узнай)", "query_humidity"),

    # ── Humidity Target (after query — only if no question words) ──
    (r"\b(set|adjust|change|target)\b.{0,20}\bhumidity\b.{0,10}\b(percent|level|%|target)\b", "set_humidity_target"),
    (r"\bhumidity\b.{0,10}\b(set|target|to|percent)\b", "set_humidity_target"),
    (r"(?:установ.*влажност|target.*влажност|задай.*влажност|сделай.*влажност)", "set_humidity_target"),

    # ── Covers: Curtains ──
    (r"\b(open|draw|pull|spread)\b.{0,20}\bcurtains?\b", "open_curtains"),
    (r"\bcurtains?\b.{0,10}\bopen\b", "open_curtains"),
    (r"(?:открой|раздвин|подними).{0,15}(?:штор|шторы|занавес|портьер)", "open_curtains"),

    (r"\b(close|draw|pull|shut)\b.{0,20}\bcurtains?\b", "close_curtains"),
    (r"\bcurtains?\b.{0,10}\b(close|shut)\b", "close_curtains"),
    (r"(?:закрой|задвин|опусти).{0,15}(?:штор|шторы|занавес|портьер)", "close_curtains"),
    (r"(?:штор|шторы|занавес|портьер).{0,10}(?:закрой|задвин|опусти)", "close_curtains"),

    # ── Covers: Blinds ──
    (r"\b(raise|open|pull up|roll up)\b.{0,20}\b(blinds?|shades?|roller)\b", "raise_blinds"),
    (r"\b(blinds?|shades?)\b.{0,10}\b(up|raise|open|roll up)\b", "raise_blinds"),
    (r"(?:подними|открой|подним).{0,15}(?:жалюзи|ролл|шторк|блинд)", "raise_blinds"),

    (r"\b(lower|close|pull down|roll down|drop)\b.{0,20}\b(blinds?|shades?|roller)\b", "lower_blinds"),
    (r"\b(blinds?|shades?)\b.{0,10}\b(down|lower|close|drop)\b", "lower_blinds"),
    (r"(?:опусти|закрой|опуск).{0,15}(?:жалюзи|ролл|шторк|блинд)", "lower_blinds"),

    # ── Vacuum: dock + stop before start ──
    (r"\b(dock|return|send.*home|go.*home|charge)\b.{0,20}\bvacuum\b", "dock_vacuum"),
    (r"\bvacuum\b.{0,10}\b(dock|home|charge|base)\b", "dock_vacuum"),
    (r"(?:пылесос|робот).{0,15}(?:на баз|домой|заряд|док)", "dock_vacuum"),

    (r"\b(stop|halt|pause|end)\b.{0,20}\bvacuum\b", "stop_vacuum"),
    (r"\bvacuum\b.{0,10}\b(stop|halt|pause|end)\b", "stop_vacuum"),
    (r"(?:останов|стоп|выключ).{0,15}(?:пылесос|робот.*убор)", "stop_vacuum"),

    (r"\b(vacuum|clean|robot)\b.{0,20}\b(room|kitchen|bedroom|living|bathroom|office|garage|everywhere|whole|house|all)\b", "vacuum_start"),
    (r"\b(start|run|send)\b.{0,20}\bvacuum\b", "vacuum_start"),
    (r"\bvacuum\b.{0,10}\b(start|clean|room|run)\b", "vacuum_start"),
    (r"\bclean the\b.{0,15}\b(room|house|whole)\b", "vacuum_start"),
    (r"\bstart the robot vacuum\b", "vacuum_start"),
    (r"(?:пылесос|робот|убор|пропылесось|убери).{0,15}(?:комнат|кухн|спальн|ванной|офис|везде|дом|всё)", "vacuum_start"),
    (r"(?:комнат|кухн|везде|дом).{0,10}(?:пылесос|убор|убери)", "vacuum_start"),
    (r"пропылесось", "vacuum_start"),

    # ── Security: queries before actions ──
    (r"\b(is|check|query|tell|show|get|what)\b.{0,20}\b(door|doorway)\b.{0,10}\b(locked|unlocked|open|closed|status|state)\b", "query_door_status"),
    (r"\b(door|doors)\b.{0,10}\b(status|state|locked|unlocked|open|closed)\b", "query_door_status"),
    (r"(?:дверь|замок).{0,10}(?:закрыт|открыт|заперт|состоян|статус)", "query_door_status"),

    (r"\b(what|check|query|tell|show|is|status)\b.{0,20}\balarm\b.{0,10}\b(status|state|armed|disarmed|check)\b", "query_alarm_status"),
    (r"(?:сигнализац|охран).{0,10}(?:состоян|статус|включен|режим)", "query_alarm_status"),

    (r"\b(panic|emergency|sos|help)\b.{0,20}\b(alarm|alert|siren|security)\b", "trigger_panic_alarm"),
    (r"(?:паник|тревог|sos|экстрен).{0,15}(?:сигнализац|кнопк|сирен)", "trigger_panic_alarm"),

    (r"\b(arm|set|activate|enable)\b.{0,20}\balarm system\b", "arm_alarm_system"),
    (r"\b(arm|set|activate|enable)\b.{0,20}\balarm\b", "arm_alarm_system"),
    (r"\balarm\b.{0,10}\b(arm|away|home|night|activate|enable|on)\b", "arm_alarm_system"),
    (r"(?:постав|включ|актив|взвед|режим.*охран).{0,15}(?:сигнализац|alarm|тревог|охран)", "arm_alarm_system"),
    (r"(?:сигнализац|alarm|тревог|охран).{0,10}(?:постав|включ|актив|охран|режим)", "arm_alarm_system"),

    (r"\b(disarm|deactivate|disable|turn off)\b.{0,20}\balarm\b", "disarm_alarm_system"),
    (r"\balarm\b.{0,10}\b(disarm|deactivate|off|disable)\b", "disarm_alarm_system"),
    (r"(?:сними|выключ|деактив|отключ).{0,15}(?:сигнализац|alarm|охран)", "disarm_alarm_system"),

    (r"\b(unlocking|unlock|opening|open|disengaging|disengage|releasing|release|unlatch)\b.{0,20}\bdoor\b", "unlock_door"),
    (r"\bunlock\b", "unlock_door"),
    (r"(?:открой|сними|подними).{0,15}(?:замок|дверь|запор)", "unlock_door"),
    (r"(?:замок|дверь).{0,10}(?:открой|сними|разблок)", "unlock_door"),

    (r"\b(locking|lock|securing|secure|bolting|bolt|engaging|engage|latch)\b.{0,20}\bdoor\b", "lock_door"),
    (r"\block\b.{0,20}\bdoor\b", "lock_door"),
    (r"\block the\b", "lock_door"),
    (r"\block up\b", "lock_door"),
    (r"(?:закрой|запри|заблок).{0,15}(?:замок|дверь|запор)", "lock_door"),
    (r"(?:замок|дверь).{0,10}(?:закрой|запри|заблок)", "lock_door"),

    # ── Media: Music (after radio and pause) ──
    (r"\b(playing|play|putting on|put on|starting|start|queuing|queue|hearing|hear|listening|listen)\b.{0,20}\b(music|song|playlist|jazz|rock|pop|classical|lo-fi|ambient|chill|beats|radio)\b", "play_music"),
    (r"\bplay\b.{0,20}\b(in|the)\b.{0,10}\b(room|kitchen|bedroom|living|bathroom|office|garage)\b", "play_music"),
    (r"(?:включ|запусти|вкль|игра).{0,10}(?:музык|песн|плейлист|джаз|рок|поп|классик|радио)", "play_music"),
    (r"(?:музык|песн|плейлист).{0,10}(?:включ|запусти|игра)", "play_music"),
    (r"включ.*музык", "play_music"),
    (r"музык.*включ", "play_music"),

    (r"\b(stopping|stop|silencing|silence|ending|end|halting|halt|no more)\b.{0,20}\b(music|song|playing|playback|speakers?)\b", "stop_music"),
    (r"\bstop (playing|music)\b", "stop_music"),
    (r"(?:останов|выключ|прерв|заткн|хватит).{0,5}(?:музык|песн|звук|колонк)", "stop_music"),
    (r"(?:музык|песн|звук|колонк).{0,5}(?:останов|выключ|прерв|хватит)", "stop_music"),

    # ── Volume (generic, after tv_volume) ──
    (r"\b(set|change|adjust|turn|increase|decrease|raise|lower)\b.{0,20}\bvolume\b", "set_volume"),
    (r"\bvolume\b.{0,10}\b(set|to|percent|up|down|increase|decrease|\d+)\b", "set_volume"),
    (r"(?:громк|звук|том|volume).{0,5}(?:установ|сделай|повысь|пониж|снизь|увелич)", "set_volume"),

    # ── Garden / Irrigation (no \b around "irrigat" — it's a substring of "irrigation") ──
    (r"\b(start|turn on|run|activate|enable|water)\b.{0,20}(?:irrigat|sprinkler|garden watering|drip)", "start_irrigation_zone"),
    (r"(?:irrigat|sprinkler|garden watering|drip).{0,10}\b(start|on|run|water|activate)\b", "start_irrigation_zone"),
    (r"(?:полив|орошен|включ.*полив|включ.*орос|капельн|спринклер|газон.*полив)", "start_irrigation_zone"),

    (r"\b(stop|turn off|end|disable|shut off)\b.{0,20}(?:irrigat|sprinkler|watering|drip)", "stop_irrigation_zone"),
    (r"(?:irrigat|sprinkler|watering).{0,10}\b(stop|off|end|shut)\b", "stop_irrigation_zone"),
    (r"(?:останов|выключ|отключ).{0,15}(?:полив|орошен|спринклер)", "stop_irrigation_zone"),

    (r"\b(what|check|query|tell|show|get|read|how)\b.{0,20}\bsoil (moisture|water|wetness)\b", "query_soil_moisture"),
    (r"\bsoil\b.{0,10}\b(moisture|water|wet|dry|humidity)\b", "query_soil_moisture"),
    (r"(?:влажн|сухостью|почв|грунт).{0,10}(?:статус|состоян|сколько|узнай)", "query_soil_moisture"),

    # ── Sensors ──
    (r"\b(what|how|check|query|tell|show|is|get)\b.{0,20}\bair quality\b", "query_air_quality"),
    (r"\bair quality\b.{0,10}\b(what|how|check|is|level|index)\b", "query_air_quality"),
    (r"\b(aqi|air.?quality|pm2.5|pm10|co2|voc)\b", "query_air_quality"),
    (r"(?:качеств.*воздух|воздух.*качеств|aqi|pm2.5|загрязнен)", "query_air_quality"),

    (r"\b(set|change|adjust|increase|decrease)\b.{0,20}\b(motion|movement)\b.{0,10}\b(sensitivity|level|threshold)\b", "set_motion_sensitivity"),
    (r"\b(motion|movement)\b.{0,10}\b(sensitivity|level|threshold)\b", "set_motion_sensitivity"),
    (r"(?:чувствительн.*движ|движ.*чувствительн|чувствительность датчик)", "set_motion_sensitivity"),

    # ── Scenes (general, after light scenes) ──
    (r"\b(activate|scene|mode|switch to|enable|start|trigger|put.*house)\b.{0,20}\b(scene|mode|night|morning|away|sleep|party|romantic|focus|guest)\b", "activate_scene"),
    (r"\b(movie night|morning mode|away mode|sleep mode|party mode|romantic mode|focus mode|guest mode)\b", "activate_scene"),
    (r"\b(set|switch|activate|enable|trigger|start)\b.{0,20}\b(night|morning|away|party|romantic|focus|guest)\b", "activate_scene"),
    (r"night mode", "activate_scene"),
    (r"(?:включ|актив|переключ|сцен|режим|вкль).{0,5}(?:сцен|режим|ночь|утро|кинотеатр|вечерин|романтик|гость)", "activate_scene"),
    (r"(?:сцен|режим).{0,5}(?:включ|актив|переключ|ночь|утро|кинотеатр|вечерин)", "activate_scene"),
    (r"режим.{0,3}(?:ночь|утр|кинотеатр|вечерин|романтик)", "activate_scene"),
    (r"режим (?:ночь|ночи|утра|утро)", "activate_scene"),
    (r"включ.*сцен", "activate_scene"),
]


class HomeRouter:
    """Keyword/regex router v2 for smart-home intents. 53 intents, RU+EN."""

    ALL_TOOLS = [
        "turn_on_light", "turn_off_light", "dim_light", "blink_light",
        "set_light_color", "set_light_scene", "set_light_temperature_k",
        "query_light_state",
        "set_temperature", "query_temperature", "set_thermostat",
        "set_ac_mode", "set_fan_speed", "set_humidity_target",
        "toggle_humidifier", "toggle_dehumidifier", "query_humidity",
        "open_curtains", "close_curtains", "raise_blinds", "lower_blinds",
        "set_blinds_position", "set_blinds_angle",
        "vacuum_start", "stop_vacuum", "dock_vacuum",
        "lock_door", "unlock_door", "query_door_status",
        "arm_alarm_system", "disarm_alarm_system",
        "query_alarm_status", "trigger_panic_alarm",
        "play_music", "stop_music", "pause_music", "play_radio_station",
        "set_volume", "mute_audio",
        "turn_on_tv", "turn_off_tv", "set_tv_channel", "set_tv_volume",
        "start_irrigation_zone", "stop_irrigation_zone", "query_soil_moisture",
        "query_air_quality", "set_motion_sensitivity",
        "set_alarm", "cancel_alarm",
        "activate_scene",
        "toggle_outlet",
        "none",
    ]

    def __init__(self, fallback_ollama_model: str = "qwen3:8b", ollama_url: str = "http://localhost:11434"):
        self._rules = [(re.compile(p, re.IGNORECASE), tool) for p, tool in _ROUTER_RULES_RAW]
        self.fallback_model = fallback_ollama_model
        self.ollama_url = ollama_url
        self._stats = {"hits": 0, "misses": 0, "fallback_hits": 0, "fallback_misses": 0}

    @staticmethod
    def _normalize(utterance: str) -> str:
        text = utterance.lower().strip()
        text = re.sub(r'[.!?]+$', '', text)
        text = text.replace("'s ", " is ")
        return text

    def route(self, utterance: str) -> Tuple[str, bool]:
        text = self._normalize(utterance)
        for pattern, tool_name in self._rules:
            if pattern.search(text):
                self._stats["hits"] += 1
                return tool_name, True
        self._stats["misses"] += 1
        return "none", False

    def route_with_fallback(self, utterance: str) -> Tuple[str, bool]:
        tool, confident = self.route(utterance)
        if confident:
            return tool, False
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
        import httpx
        prompt = (
            f"Classify this smart-home command into exactly one of these intents: {', '.join(self.ALL_TOOLS)}\n"
            f"Reply with ONLY the intent name, nothing else.\n\n"
            f"Command: {utterance}\nIntent:"
        )
        resp = httpx.post(
            f"{self.ollama_url}/v1/chat/completions",
            json={"model": self.fallback_model, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 20, "temperature": 0},
            timeout=30,
        )
        text = resp.json()["choices"][0]["message"]["content"].strip().lower()
        for t in self.ALL_TOOLS:
            if t in text:
                return t
        return "none"

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)


TEST_CASES: List[Tuple[str, str]] = [
    # ═══ LIGHTS ═══
    ("turn on the lights in the living room", "turn_on_light"),
    ("turn off garage lights", "turn_off_light"),
    ("light up the bedroom", "turn_on_light"),
    ("switch off the bedroom light", "turn_off_light"),
    ("включи свет в гостиной", "turn_on_light"),
    ("выключи свет на кухне", "turn_off_light"),
    ("погаси свет в ванной", "turn_off_light"),
    ("dim the lights in the bedroom", "dim_light"),
    ("dim light to 30%", "dim_light"),
    ("приглуши свет в спальне", "dim_light"),
    ("blink the lights", "blink_light"),
    ("flash the bedroom light", "blink_light"),
    ("set the light color to red in the kitchen", "set_light_color"),
    ("make the lights blue", "set_light_color"),
    ("сделай свет синий на кухне", "set_light_color"),
    ("set the light scene to movie", "set_light_scene"),
    ("activate mood lighting", "set_light_scene"),
    ("set light color temperature to 4000 kelvin", "set_light_temperature_k"),
    ("warm white in the bedroom", "set_light_temperature_k"),
    ("is the light on in the kitchen?", "query_light_state"),
    ("what's the light status in the living room", "query_light_state"),
    ("включен ли свет в спальне", "query_light_state"),

    # ═══ CLIMATE ═══
    ("set the bedroom to 22 degrees", "set_temperature"),
    ("what is the temperature in the bedroom?", "query_temperature"),
    ("how warm is it in the living room", "query_temperature"),
    ("make it 20 celsius in the office", "set_temperature"),
    ("какая температура в спальне", "query_temperature"),
    ("установи температуру 22 градуса в гостиной", "set_temperature"),
    ("set the thermostat to 72 and heat mode", "set_thermostat"),
    ("термостат на охлаждение 20 градусов", "set_thermostat"),
    ("set AC to cool mode", "set_ac_mode"),
    ("кондиционер режим охлаждения", "set_ac_mode"),
    ("set the fan speed to high", "set_fan_speed"),
    ("increase fan speed in the bedroom", "set_fan_speed"),
    ("set humidity target to 50 percent", "set_humidity_target"),
    ("what's the humidity in the bedroom?", "query_humidity"),
    ("какая влажность на кухне", "query_humidity"),
    ("turn on the humidifier", "toggle_humidifier"),
    ("включи увлажнитель", "toggle_humidifier"),
    ("turn on the dehumidifier", "toggle_dehumidifier"),

    # ═══ COVERS ═══
    ("open the curtains in the bedroom", "open_curtains"),
    ("close the curtains", "close_curtains"),
    ("открой шторы в гостиной", "open_curtains"),
    ("закрой шторы", "close_curtains"),
    ("raise the blinds", "raise_blinds"),
    ("lower the blinds in the kitchen", "lower_blinds"),
    ("опусти жалюзи", "lower_blinds"),
    ("set blinds position to 50%", "set_blinds_position"),
    ("tilt the blinds to 45 degrees", "set_blinds_angle"),

    # ═══ VACUUM ═══
    ("vacuum the office", "vacuum_start"),
    ("start the robot vacuum", "vacuum_start"),
    ("пропылесось кухню", "vacuum_start"),
    ("stop the vacuum", "stop_vacuum"),
    ("dock the vacuum", "dock_vacuum"),
    ("пылесос на базу", "dock_vacuum"),

    # ═══ SECURITY ═══
    ("lock the front door", "lock_door"),
    ("unlock the back door", "unlock_door"),
    ("запри входную дверь", "lock_door"),
    ("is the front door locked?", "query_door_status"),
    ("arm the alarm system", "arm_alarm_system"),
    ("поставь сигнализацию", "arm_alarm_system"),
    ("disarm the alarm", "disarm_alarm_system"),
    ("cancel the 06:00 alarm", "cancel_alarm"),
    ("what's the alarm status?", "query_alarm_status"),
    ("panic alarm!", "trigger_panic_alarm"),

    # ═══ MEDIA ═══
    ("play jazz playlist in the kitchen", "play_music"),
    ("stop music in the bathroom", "stop_music"),
    ("pause the music", "pause_music"),
    ("play radio station jazz fm", "play_radio_station"),
    ("set volume to 50%", "set_volume"),
    ("mute the audio", "mute_audio"),
    ("turn on the tv in the living room", "turn_on_tv"),
    ("turn off the tv", "turn_off_tv"),
    ("set tv channel to 5", "set_tv_channel"),
    ("set tv volume to 30", "set_tv_volume"),
    ("включи музыку на кухне", "play_music"),
    ("останови музыку в гостиной", "stop_music"),

    # ═══ GARDEN ═══
    ("start irrigation zone 1", "start_irrigation_zone"),
    ("включи полив газона", "start_irrigation_zone"),
    ("stop irrigation zone 3", "stop_irrigation_zone"),
    ("what's the soil moisture level?", "query_soil_moisture"),

    # ═══ SENSORS ═══
    ("what's the air quality in the living room?", "query_air_quality"),
    ("set motion sensitivity to high", "set_motion_sensitivity"),

    # ═══ ALARMS ═══
    ("wake me up at 07:30", "set_alarm"),
    ("поставь будильник на 7 утра", "set_alarm"),
    ("отмени будильник", "cancel_alarm"),

    # ═══ SCENES ═══
    ("activate movie night scene", "activate_scene"),
    ("switch to away mode", "activate_scene"),
    ("night mode", "activate_scene"),
    ("включи сцену кинотеатр", "activate_scene"),
    ("режим ночи", "activate_scene"),

    # ═══ SWITCHES ═══
    ("toggle the outlet in the kitchen", "toggle_outlet"),
    ("включи розетку", "toggle_outlet"),

    # Edge cases
    ("what's the weather outside", "none"),
    ("tell me a joke", "none"),
]


if __name__ == "__main__":
    router = HomeRouter()

    print("=== Router v2 Validation (53 intents, EN+RU) ===\n")
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
    print(f"\n  Result: {correct}/{total} = {precision:.0f}%")

    if errors:
        print(f"\n  Misses ({len(errors)}):")
        for u, exp, got in errors:
            print(f"    \"{u}\" → got {got}, expected {exp}")

    print(f"\n  Stats: {router.stats}")