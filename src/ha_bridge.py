"""Vector Home — Home Assistant bridge.

Sends real HTTP calls to Home Assistant REST API.
Supports confirmation mode and entity discovery.
"""
import os
import json
from typing import Optional, Dict, Any
from pathlib import Path

import httpx


# ── Configuration ─────────────────────────────────────────────────────

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")  # Long-lived access token

# Entity name patterns: {tool_name: (domain, entity_template)}
# entity_template uses {room}, {door}, {scene} from arguments
HA_ENTITY_MAP = {
    "turn_on_light":   ("light",    "light.{room}"),
    "turn_off_light":  ("light",    "light.{room}"),
    "set_temperature":  ("climate",  "climate.{room}"),
    "query_temperature":("sensor",   "sensor.{room}_temperature"),
    "lock_door":        ("lock",     "lock.{door}"),
    "unlock_door":      ("lock",     "lock.{door}"),
    "play_music":       ("media_player", "media_player.{room}"),
    "stop_music":       ("media_player", "media_player.{room}"),
    "set_alarm":        ("input_datetime", "input_datetime.alarm"),
    "cancel_alarm":     ("input_boolean",  "input_boolean.alarm"),
    "activate_scene":   ("scene",    "scene.{scene}"),
    "vacuum_start":     ("vacuum",   "vacuum.robot"),
}

# Service data templates
HA_SERVICE_DATA = {
    "set_temperature":  lambda args: {"temperature": args.get("temperature_c")},
    "play_music":       lambda args: {"media_content_id": args.get("song", ""), "media_content_type": "music"},
    "set_alarm":        lambda args: {"time": args.get("time", "07:00")},
}


class HABridge:
    """Home Assistant REST API bridge."""

    def __init__(self, url: str = None, token: str = None, dry_run: bool = False):
        self.url = (url or HA_URL).rstrip("/")
        self.token = token or HA_TOKEN
        self.dry_run = dry_run  # If True, don't actually call HA
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # RU → EN mapping for HA entity names
    RU_ROOM_MAP = {
        "гостиная": "living_room", "спальня": "bedroom", "кухня": "kitchen",
        "ванная": "bathroom", "кабинет": "office", "прихожая": "hallway",
        "гараж": "garage", "детская": "nursery", "коридор": "hall",
        "везде": "everywhere",
    }
    RU_DOOR_MAP = {
        "входная дверь": "front_door", "задняя дверь": "back_door",
        "гаражная дверь": "garage_door", "балконная дверь": "balcony_door",
    }
    RU_SCENE_MAP = {
        "кинотеатр": "movie_night", "утро": "morning", "ночь": "night",
        "вечеринка": "party", "романтика": "romantic", "отъезд": "away",
        "фокус": "focus",
    }
    RU_MUSIC_MAP = {
        "джаз": "jazz", "рок": "rock", "поп": "pop",
        "классика": "classical", "лоу-фай": "lo-fi",
    }

    # Extended RU maps: nominative + common oblique forms (prepositional, dative, accusative)
    # Russian grammar: гостиная→гостиной, спальня→спальне, кухня→кухне/кухню, etc.
    RU_ROOM_MAP_EXT = {
        # nominative + prepositional/dative/accusative
        "гостиная": "living_room", "гостиной": "living_room", "гостиную": "living_room",
        "спальня": "bedroom", "спальне": "bedroom", "спальню": "bedroom",
        "кухня": "kitchen", "кухне": "kitchen", "кухню": "kitchen",
        "ванная": "bathroom", "ванной": "bathroom", "ванную": "bathroom",
        "кабинет": "office",
        "прихожая": "hallway", "прихожей": "hallway",
        "гараж": "garage",
        "детская": "nursery", "детской": "nursery",
        "коридор": "hall",
    }
    RU_DOOR_MAP_EXT = {
        "входная дверь": "front_door", "входную дверь": "front_door", "входной двери": "front_door",
        "задняя дверь": "back_door", "заднюю дверь": "back_door", "задней двери": "back_door",
        "гаражная дверь": "garage_door", "гаражную дверь": "garage_door",
        "балконная дверь": "balcony_door", "балконную дверь": "balcony_door",
        # model sometimes drops "дверь" or drops adjective
        "входная": "front_door", "входную": "front_door",
        "задняя": "back_door", "заднюю": "back_door",
        "гаражная": "garage_door", "гаражную": "garage_door",
        "балконная": "balcony_door", "балконную": "balcony_door",
        "дверь": "front_door",   # bare "дверь" defaults to front door
    }
    RU_SCENE_MAP_EXT = {
        "кинотеатр": "movie_night",
        "утро": "morning",
        "ночь": "night",
        "вечеринка": "party",
        "романтика": "romantic",
        "отъезд": "away",
        "фокус": "focus",
    }
    RU_MUSIC_MAP_EXT = {
        "джаз": "jazz", "рок": "rock", "поп": "pop",
        "классика": "classical", "лоу-фай": "lo-fi",
    }

    def _normalize(self, text: str) -> str:
        """Normalize room/door/scene names to HA entity format.

        Maps Cyrillic names (including oblique cases) to English
        before converting to entity_id format.
        """
        t = text.lower().strip()
        # Try extended RU→EN mappings (handles oblique cases)
        all_ru = {**self.RU_DOOR_MAP_EXT, **self.RU_SCENE_MAP_EXT,
                  **self.RU_ROOM_MAP_EXT, **self.RU_MUSIC_MAP_EXT}
        for ru, en in all_ru.items():
            if t == ru or t.replace("_", " ") == ru or ru in t:
                t = en
                break
        return t.replace(" ", "_").replace("-", "_")

    def build_service_call(self, tool_name: str, arguments: dict) -> Optional[Dict[str, Any]]:
        """Build a HA service call dict from tool call + arguments.

        Returns:
            {"domain": ..., "service": ..., "entity_id": ..., "service_data": ...}
            or None if tool_name unknown.
        """
        if tool_name not in HA_ENTITY_MAP:
            return None

        domain, entity_tmpl = HA_ENTITY_MAP[tool_name]
        room = arguments.get("room", "")
        door = arguments.get("door", "")
        scene = arguments.get("scene", "")

        # Build entity_id
        entity_id = entity_tmpl.format(
            room=self._normalize(room) if room else "all",
            door=self._normalize(door) if door else "main",
            scene=self._normalize(scene) if scene else "default",
        )

        # Service name
        service_map = {
            "turn_on_light": "turn_on",
            "turn_off_light": "turn_off",
            "set_temperature": "set_temperature",
            "query_temperature": "get_state",  # read-only, uses GET
            "lock_door": "lock",
            "unlock_door": "unlock",
            "play_music": "play_media",
            "stop_music": "media_stop",
            "set_alarm": "set_datetime",
            "cancel_alarm": "turn_off",
            "activate_scene": "turn_on",
            "vacuum_start": "start",
        }
        service = service_map.get(tool_name, "turn_on")

        # Service data
        service_data = {}
        if tool_name in HA_SERVICE_DATA:
            service_data = HA_SERVICE_DATA[tool_name](arguments)
        elif room and tool_name in ("turn_on_light", "turn_off_light"):
            service_data = {"entity_id": entity_id}
        elif tool_name == "vacuum_start" and room:
            service_data = {"entity_id": entity_id}

        result = {
            "domain": domain,
            "service": service,
            "entity_id": entity_id,
        }
        if service_data:
            result["service_data"] = {k: v for k, v in service_data.items() if v is not None and v != ""}

        return result

    async def call_service(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """Execute a service call on Home Assistant.

        Returns:
            {"success": bool, "ha_response": ..., "service_call": ...}
        """
        call = self.build_service_call(tool_name, arguments)
        if call is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "service_call": call,
                "message": f"[DRY RUN] Would call {call['domain']}.{call['service']} on {call['entity_id']}"
            }

        if not self.token:
            return {
                "success": False,
                "error": "HA_TOKEN not configured",
                "service_call": call,
            }

        # Read-only queries use GET
        if call["service"] == "get_state":
            return await self._get_state(call["entity_id"], call)

        # Mutations use POST
        url = f"{self.url}/api/services/{call['domain']}/{call['service']}"
        payload = {"entity_id": call["entity_id"]}
        if "service_data" in call:
            payload.update(call["service_data"])

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                if resp.status_code in (200, 201):
                    return {
                        "success": True,
                        "ha_response": resp.json() if resp.text else {},
                        "service_call": call,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HA returned {resp.status_code}: {resp.text[:200]}",
                        "service_call": call,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "service_call": call,
            }

    async def _get_state(self, entity_id: str, call: dict) -> Dict[str, Any]:
        """GET state from HA (for queries like temperature)."""
        url = f"{self.url}/api/states/{entity_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    state = resp.json()
                    return {
                        "success": True,
                        "ha_response": state,
                        "service_call": call,
                        "state": state.get("state"),
                        "attributes": state.get("attributes", {}),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HA returned {resp.status_code}",
                        "service_call": call,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "service_call": call,
            }

    async def get_entities(self, domain: str = "") -> list:
        """Discover HA entities. Optionally filter by domain."""
        url = f"{self.url}/api/states"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code != 200:
                    return []
                entities = resp.json()
                if domain:
                    entities = [e for e in entities if e["entity_id"].startswith(f"{domain}.")]
                return [{"entity_id": e["entity_id"], "state": e["state"]} for e in entities]
        except Exception:
            return []


# ── Synchronous wrapper for CLI/testing ────────────────────────────────

def call_ha_sync(tool_name: str, arguments: dict, url: str = None, token: str = None, dry_run: bool = True) -> dict:
    """Synchronous HA bridge call for CLI/testing."""
    import asyncio
    bridge = HABridge(url=url, token=token, dry_run=dry_run)
    call = bridge.build_service_call(tool_name, arguments)
    if call is None:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    if dry_run:
        return {"success": True, "dry_run": True, "service_call": call,
                "message": f"[DRY RUN] {call['domain']}.{call['service']}({call['entity_id']})"}
    return asyncio.run(bridge.call_service(tool_name, arguments))


if __name__ == "__main__":
    # Test HA bridge mapping (dry run)
    from router import HomeRouter

    router = HomeRouter()
    print("=== HA Bridge Mapping Test (dry run) ===\n")

    test_commands = [
        "turn on the lights in the living room",
        "set the bedroom to 22 degrees",
        "lock the front door",
        "play jazz in the kitchen",
        "what is the temperature in the office",
        "activate movie night scene",
        "vacuum the living room",
    ]

    for utterance in test_commands:
        tool, confident = router.route(utterance)
        if tool == "none":
            print(f"  ? \"{utterance}\" → not routed")
            continue
        result = call_ha_sync(tool, {"room": "living room", "temperature_c": 22, "door": "front door", "song": "jazz", "scene": "movie night"},
                              dry_run=True)
        call = result["service_call"]
        print(f"  ✓ \"{utterance}\"")
        print(f"    → tool: {tool}")
        print(f"    → HA:   {call['domain']}.{call['service']}({call['entity_id']})")
        if "service_data" in call:
            print(f"    → data: {call['service_data']}")
        print()

    # Test entity normalization
    print("=== Entity Normalization ===\n")
    bridge = HABridge(dry_run=True)
    test_args = [
        ("turn_on_light", {"room": "living room"}),
        ("set_temperature", {"room": "master bedroom", "temperature_c": 22}),
        ("lock_door", {"door": "front door"}),
        ("play_music", {"song": "jazz playlist", "room": "kitchen"}),
        ("activate_scene", {"scene": "movie night"}),
        ("vacuum_start", {"room": "everywhere"}),
    ]
    for tool, args in test_args:
        call = bridge.build_service_call(tool, args)
        print(f"  {tool}({args}) → {call['domain']}.{call['service']}({call.get('entity_id', '')})")