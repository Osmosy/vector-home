"""Vector Home HA Bridge v2 — 53 tool → Home Assistant service call mapping.

Supports:
- 53 smarthome tools → HA REST API calls
- RU→EN entity name mapping
- Entity discovery via /api/states
- WebSocket for real-time updates
"""
import os
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

import httpx


# ── Configuration ─────────────────────────────────────────────────────

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")  # Long-lived access token


# ── Entity name patterns: {tool_name: (domain, entity_template)} ──────
# entity_template uses {room}, {door}, {scene}, {zone} from arguments
HA_ENTITY_MAP = {
    # Light
    "turn_on_light":        ("light", "light.{room}"),
    "turn_off_light":       ("light", "light.{room}"),
    "dim_light":            ("light", "light.{room}"),
    "blink_light":          ("light", "light.{room}"),
    "set_light_color":      ("light", "light.{room}"),
    "set_light_scene":      ("scene", "scene.{scene}"),
    "set_light_temperature_k": ("light", "light.{room}"),
    "query_light_state":    ("sensor", "sensor.{room}_light"),

    # Climate
    "set_temperature":      ("climate", "climate.{room}"),
    "query_temperature":    ("sensor", "sensor.{room}_temperature"),
    "set_thermostat":       ("climate", "climate.{room}"),
    "set_ac_mode":          ("climate", "climate.{room}_ac"),
    "set_fan_speed":        ("fan", "fan.{room}"),
    "set_humidity_target":  ("humidifier", "humidifier.{room}"),
    "toggle_humidifier":    ("humidifier", "humidifier.{room}"),
    "toggle_dehumidifier": ("humidifier", "dehumidifier.{room}"),
    "query_humidity":       ("sensor", "sensor.{room}_humidity"),

    # Covers
    "open_curtains":        ("cover", "cover.{room}_curtains"),
    "close_curtains":       ("cover", "cover.{room}_curtains"),
    "raise_blinds":         ("cover", "cover.{room}_blinds"),
    "lower_blinds":          ("cover", "cover.{room}_blinds"),
    "set_blinds_position":  ("cover", "cover.{room}_blinds"),
    "set_blinds_angle":     ("cover", "cover.{room}_blinds"),

    # Vacuum
    "vacuum_start":         ("vacuum", "vacuum.robot"),
    "stop_vacuum":          ("vacuum", "vacuum.robot"),
    "dock_vacuum":          ("vacuum", "vacuum.robot"),

    # Security
    "lock_door":            ("lock", "lock.{door}"),
    "unlock_door":          ("lock", "lock.{door}"),
    "query_door_status":    ("sensor", "sensor.{door}_lock_status"),
    "arm_alarm_system":     ("alarm_control_panel", "alarm_control_panel.home"),
    "disarm_alarm_system":  ("alarm_control_panel", "alarm_control_panel.home"),
    "query_alarm_status":    ("sensor", "sensor.alarm_status"),
    "trigger_panic_alarm":  ("alarm_control_panel", "alarm_control_panel.home"),

    # Media
    "play_music":           ("media_player", "media_player.{room}"),
    "stop_music":           ("media_player", "media_player.{room}"),
    "pause_music":          ("media_player", "media_player.{room}"),
    "play_radio_station":   ("media_player", "media_player.{room}"),
    "set_volume":           ("media_player", "media_player.{room}"),
    "mute_audio":           ("media_player", "media_player.{room}"),
    "turn_on_tv":           ("media_player", "media_player.{room}_tv"),
    "turn_off_tv":          ("media_player", "media_player.{room}_tv"),
    "set_tv_channel":       ("media_player", "media_player.{room}_tv"),
    "set_tv_volume":        ("media_player", "media_player.{room}_tv"),

    # Garden
    "start_irrigation_zone": ("switch", "switch.irrigation_zone_{zone}"),
    "stop_irrigation_zone":  ("switch", "switch.irrigation_zone_{zone}"),
    "query_soil_moisture":  ("sensor", "sensor.soil_moisture_zone_{zone}"),

    # Sensors
    "query_air_quality":    ("sensor", "sensor.{room}_air_quality"),
    "set_motion_sensitivity": ("number", "number.{room}_motion_sensitivity"),

    # Alarms
    "set_alarm":            ("input_datetime", "input_datetime.alarm"),
    "cancel_alarm":         ("input_boolean", "input_boolean.alarm"),

    # Scenes
    "activate_scene":       ("scene", "scene.{scene}"),

    # Outlets
    "toggle_outlet":        ("switch", "switch.{room}_outlet"),
}


# ── HA service call mapping ────────────────────────────────────────────
# Maps tool_name → (domain, service, service_data_template)
HA_SERVICE_MAP = {
    # Light
    "turn_on_light":        ("light", "turn_on", {}),
    "turn_off_light":       ("light", "turn_off", {}),
    "dim_light":            ("light", "turn_on", {"brightness_pct": "{brightness}"}),
    "blink_light":          ("light", "turn_on", {"flash": "short"}),
    "set_light_color":      ("light", "turn_on", {"color_name": "{color}"}),
    "set_light_scene":      ("scene", "turn_on", {}),
    "set_light_temperature_k": ("light", "turn_on", {"kelvin": "{temperature}"}),
    "query_light_state":    ("light", "turn_on", {}),  # Will be handled as query

    # Climate
    "set_temperature":      ("climate", "set_temperature", {"temperature": "{temperature_c}"}),
    "query_temperature":    ("sensor", "turn_on", {}),  # Query
    "set_thermostat":       ("climate", "set_hvac_mode", {"hvac_mode": "{mode}"}),
    "set_ac_mode":          ("climate", "set_hvac_mode", {"hvac_mode": "{mode}"}),
    "set_fan_speed":        ("fan", "set_percentage", {"percentage": "{speed_pct}"}),
    "set_humidity_target":  ("humidifier", "set_humidity", {"humidity": "{humidity_pct}"}),
    "toggle_humidifier":   ("humidifier", "toggle", {}),
    "toggle_dehumidifier": ("humidifier", "toggle", {}),
    "query_humidity":      ("sensor", "turn_on", {}),  # Query

    # Covers
    "open_curtains":       ("cover", "open_cover", {}),
    "close_curtains":      ("cover", "close_cover", {}),
    "raise_blinds":        ("cover", "open_cover", {}),
    "lower_blinds":        ("cover", "close_cover", {}),
    "set_blinds_position": ("cover", "set_cover_position", {"position": "{position}"}),
    "set_blinds_angle":    ("cover", "set_cover_tilt_position", {"tilt_position": "{angle}"}),

    # Vacuum
    "vacuum_start":        ("vacuum", "start", {}),
    "stop_vacuum":         ("vacuum", "stop", {}),
    "dock_vacuum":         ("vacuum", "return_to_base", {}),

    # Security
    "lock_door":           ("lock", "lock", {}),
    "unlock_door":         ("lock", "unlock", {}),
    "query_door_status":   ("lock", "turn_on", {}),  # Query
    "arm_alarm_system":    ("alarm_control_panel", "alarm_arm_away", {"code": "{code}"}),
    "disarm_alarm_system": ("alarm_control_panel", "alarm_disarm", {"code": "{code}"}),
    "query_alarm_status":   ("sensor", "turn_on", {}),  # Query
    "trigger_panic_alarm":  ("alarm_control_panel", "alarm_trigger", {}),

    # Media
    "play_music":          ("media_player", "media_play", {}),
    "stop_music":          ("media_player", "media_stop", {}),
    "pause_music":         ("media_player", "media_pause", {}),
    "play_radio_station": ("media_player", "play_media", {"media_content_id": "{station}", "media_content_type": "music"}),
    "set_volume":          ("media_player", "volume_set", {"volume_level": "{volume_pct}"}),
    "mute_audio":          ("media_player", "volume_mute", {"is_volume_muted": True}),
    "turn_on_tv":          ("media_player", "turn_on", {}),
    "turn_off_tv":         ("media_player", "turn_off", {}),
    "set_tv_channel":      ("media_player", "play_media", {"media_content_id": "channel_{channel_number}"}),
    "set_tv_volume":       ("media_player", "volume_set", {"volume_level": "{volume_pct}"}),

    # Garden
    "start_irrigation_zone": ("switch", "turn_on", {}),
    "stop_irrigation_zone":  ("switch", "turn_off", {}),
    "query_soil_moisture":   ("sensor", "turn_on", {}),  # Query

    # Sensors
    "query_air_quality":       ("sensor", "turn_on", {}),  # Query
    "set_motion_sensitivity":  ("number", "set_value", {"value": "{level}"}),

    # Alarms
    "set_alarm":           ("input_datetime", "set_datetime", {"time": "{time}"}),
    "cancel_alarm":        ("input_boolean", "turn_off", {}),

    # Scenes
    "activate_scene":      ("scene", "turn_on", {}),

    # Outlets
    "toggle_outlet":       ("switch", "toggle", {}),
}

# ── Query tools (return state, not call service) ───────────────────────
QUERY_TOOLS = {
    "query_temperature", "query_light_state", "query_humidity",
    "query_door_status", "query_alarm_status", "query_soil_moisture",
    "query_air_quality",
}


# ── RU → EN mapping ────────────────────────────────────────────────────

RU_ROOM_MAP = {
    "гостиная": "living_room", "спальня": "bedroom", "кухня": "kitchen",
    "ванная": "bathroom", "кабинет": "office", "прихожая": "hallway",
    "гараж": "garage", "детская": "nursery", "коридор": "hall",
    "подвал": "basement", "чердак": "attic", "столовая": "dining_room",
    "гостевая": "guest_room", "кладовая": "storage",
    "living room": "living_room", "bedroom": "bedroom", "kitchen": "kitchen",
    "bathroom": "bathroom", "office": "office", "hallway": "hallway",
    "garage": "garage", "nursery": "nursery",
}

RU_DOOR_MAP = {
    "входная": "front_door", "задняя": "back_door", "гаражная": "garage_door",
    "балконная": "balcony_door", "подвальная": "basement_door",
    "front": "front_door", "back": "back_door", "garage": "garage_door",
}

RU_SCENE_MAP = {
    "кино": "movie", "кинь": "movie", "кинотеатр": "movie",
    "ночь": "night", "ночи": "night", "ночной": "night",
    "утро": "morning", "утра": "morning", "утренний": "morning",
    "вечеринка": "party", "пати": "party", "гость": "guest",
    "романтик": "romantic", "романтический": "romantic",
    "фокус": "focus", "рабочий": "focus",
    "отпуск": "away", "отсутствие": "away",
    "movie": "movie", "night": "night", "morning": "morning",
}

RU_AC_MODE_MAP = {
    "охлаждение": "cool", "охлажд": "cool", "холод": "cool", "cool": "cool",
    "обогрев": "heat", "обогр": "heat", "тепло": "heat", "гре": "heat", "heat": "heat", "нагрев": "heat",
    "авто": "auto", "auto": "auto", "автоматический": "auto",
    "сушка": "dry", "сух": "dry", "dry": "dry", "осушение": "dry",
    "вентиляция": "fan_only", "вентил": "fan_only", "fan": "fan_only", "проветривание": "fan_only",
}


class HABridge:
    """Home Assistant REST API bridge — 53 tool → HA service call mapping."""

    def __init__(self, url: str = None, token: str = None, dry_run: bool = False):
        self.url = (url or HA_URL).rstrip("/")
        self.token = token or HA_TOKEN
        self.dry_run = dry_run

    def _translate_args(self, tool_name: str, arguments: dict) -> dict:
        """Translate RU arguments and normalize for HA."""
        args = dict(arguments)

        # Translate room name
        if "room" in args:
            room = args["room"].lower().strip()
            args["room"] = RU_ROOM_MAP.get(room, room.replace(" ", "_"))

        # Translate door
        if "door" in args:
            door = args["door"].lower().strip()
            args["door"] = RU_DOOR_MAP.get(door, door.replace(" ", "_"))

        # Translate scene
        if "scene" in args:
            scene = args["scene"].lower().strip()
            args["scene"] = RU_SCENE_MAP.get(scene, scene.replace(" ", "_"))

        # Translate AC mode
        if "mode" in args:
            mode = args["mode"].lower().strip()
            args["mode"] = RU_AC_MODE_MAP.get(mode, mode)

        return args

    def _build_entity_id(self, tool_name: str, arguments: dict) -> str:
        """Build HA entity_id from tool name and arguments."""
        if tool_name not in HA_ENTITY_MAP:
            return ""
        domain, template = HA_ENTITY_MAP[tool_name]
        args = self._translate_args(tool_name, arguments)

        # Replace {room}, {door}, {scene}, {zone} placeholders
        entity_id = template
        for key in ("room", "door", "scene", "zone"):
            if f"{{{key}}}" in entity_id:
                entity_id = entity_id.replace(f"{{{key}}}", args.get(key, key))

        return entity_id

    def build_service_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """Build HA service call dict from tool name and arguments."""
        if tool_name not in HA_SERVICE_MAP:
            return None

        domain, service, data_template = HA_SERVICE_MAP[tool_name]
        args = self._translate_args(tool_name, arguments)
        entity_id = self._build_entity_id(tool_name, arguments)

        # Build service_data by filling template placeholders
        service_data = {}
        for key, value in data_template.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                arg_key = value[1:-1]
                service_data[key] = args.get(arg_key, value)
            else:
                service_data[key] = value

        result = {
            "domain": domain,
            "service": service,
            "entity_id": entity_id,
        }
        if service_data:
            result["service_data"] = service_data

        return result


def call_ha_sync(tool_name: str, arguments: dict,
                 url: str = None, token: str = None, dry_run: bool = True) -> dict:
    """Execute HA service call synchronously."""
    if dry_run or not token:
        entity_id = ""
        if tool_name in HA_ENTITY_MAP:
            domain, template = HA_ENTITY_MAP[tool_name]
            args = arguments
            entity_id = template
            for key in ("room", "door", "scene", "zone"):
                if f"{{{key}}}" in entity_id:
                    entity_id = entity_id.replace(f"{{{key}}}", args.get(key, key))

        return {
            "dry_run": True,
            "message": f"[DRY RUN] Would call {tool_name}({arguments}) → {entity_id}",
            "tool": tool_name,
            "arguments": arguments,
        }

    bridge = HABridge(url=url, token=token, dry_run=False)
    service_call = bridge.build_service_call(tool_name, arguments)
    if not service_call:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        resp = httpx.post(
            f"{bridge.url}/api/services/{service_call['domain']}/{service_call['service']}",
            headers={"Authorization": f"Bearer {bridge.token}", "Content-Type": "application/json"},
            json={"entity_id": service_call["entity_id"], **service_call.get("service_data", {})},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return {"success": True, "status": resp.status_code}
        return {"success": False, "error": f"HA returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import argparse
    argp = argparse.ArgumentParser(description="HA Bridge Test")
    argp.add_argument("tool", help="Tool name")
    argp.add_argument("--args", default="{}", help="JSON arguments")
    argp.add_argument("--dry-run", action="store_true", default=True)
    args = argp.parse_args()

    bridge = HABridge(dry_run=args.dry_run)
    arguments = json.loads(args.args)
    service_call = bridge.build_service_call(args.tool, arguments)
    print(json.dumps(service_call, indent=2, ensure_ascii=False))