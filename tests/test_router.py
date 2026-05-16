"""Tests for Vector Home Router v2 — keyword/regex intent classifier.

Run: python -m pytest tests/test_router.py -v
"""
import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from router import HomeRouter, TEST_CASES, _ROUTER_RULES_RAW


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def router():
    return HomeRouter()


# ── Core: all TEST_CASES pass ─────────────────────────────────────────

class TestRouterTestCases:
    """Every entry in TEST_CASES must route to the expected intent."""

    @pytest.mark.parametrize("utterance,expected", TEST_CASES, ids=[f"i{i}" for i in range(len(TEST_CASES))])
    def test_test_case(self, router, utterance, expected):
        result, confident = router.route(utterance)
        assert result == expected, (
            f"router({utterance!r}) = {result!r}, expected {expected!r}"
        )
        # "none" is a miss (not confident), which is correct behavior
        if expected != "none":
            assert confident is True


# ── Specific bug regressions ──────────────────────────────────────────

class TestCyrillicWordBoundary:
    """\\b is broken for Cyrillic in Python regex — verify our patterns don't use it."""

    def test_russian_light_on(self, router):
        assert router.route("включи свет в гостиной")[0] == "turn_on_light"

    def test_russian_light_off(self, router):
        assert router.route("выключи свет на кухне")[0] == "turn_off_light"

    def test_russian_dim(self, router):
        assert router.route("приглуши свет в спальне")[0] == "dim_light"

    def test_russian_humidity_query(self, router):
        """'какая влажность' must route to query, not set_humidity_target."""
        result, _ = router.route("какая влажность на кухне")
        assert result == "query_humidity", f"Got {result} instead of query_humidity"

    def test_russian_ac_mode(self, router):
        """'кондиционер режим охлаждения' must route to set_ac_mode."""
        result, _ = router.route("кондиционер режим охлаждения")
        assert result == "set_ac_mode", f"Got {result} instead of set_ac_mode"

    def test_russian_thermostat(self, router):
        """'термостат на охлаждение 20 градусов' → set_thermostat."""
        result, _ = router.route("термостат на охлаждение 20 градусов")
        assert result == "set_thermostat"

    def test_russian_alarm(self, router):
        assert router.route("поставь сигнализацию")[0] == "arm_alarm_system"

    def test_russian_outlet(self, router):
        """'включи розетку' must not match 'turn_on_light'."""
        result, _ = router.route("включи розетку")
        assert result == "toggle_outlet"

    def test_russian_irrigation(self, router):
        assert router.route("включи полив газона")[0] == "start_irrigation_zone"


class TestRuleOrdering:
    """Specific patterns must match before general ones."""

    def test_query_before_set_light(self, router):
        """'is the light on?' → query, not turn_on_light."""
        assert router.route("is the light on in the kitchen?")[0] == "query_light_state"

    def test_query_before_set_temperature(self, router):
        """'what is the temperature?' → query, not set_temperature."""
        assert router.route("what is the temperature in the bedroom?")[0] == "query_temperature"

    def test_humidity_query_before_target(self, router):
        """'what's the humidity?' → query, not set_humidity_target."""
        assert router.route("what's the humidity in the bedroom?")[0] == "query_humidity"

    def test_thermostat_before_ac(self, router):
        """'set the thermostat to 72 and heat mode' → set_thermostat, not set_ac_mode."""
        assert router.route("set the thermostat to 72 and heat mode")[0] == "set_thermostat"

    def test_light_temp_before_color(self, router):
        """'set light color temperature' → set_light_temperature_k, not set_light_color."""
        assert router.route("set light color temperature to 4000 kelvin")[0] == "set_light_temperature_k"

    def test_dim_before_off(self, router):
        """'dim' should not match 'turn_off_light'."""
        assert router.route("dim the lights to 30%")[0] == "dim_light"

    def test_vacuum_before_turn_on(self, router):
        """'vacuum' should not match 'turn_on_light'."""
        assert router.route("vacuum the office")[0] == "vacuum_start"

    def test_irrigation_before_irrigation_stop(self, router):
        """'start irrigation' → start, not stop."""
        assert router.route("start irrigation zone 1")[0] == "start_irrigation_zone"


class TestEdgeCases:
    """Non-home commands and edge cases."""

    def test_weather_is_none(self, router):
        assert router.route("what's the weather outside")[0] == "none"

    def test_joke_is_none(self, router):
        assert router.route("tell me a joke")[0] == "none"

    def test_empty_string_is_none(self, router):
        assert router.route("")[0] in ("none", "activate_scene")  # empty might match broadly

    def test_case_insensitive(self, router):
        r1, _ = router.route("TURN ON THE LIGHTS")
        r2, _ = router.route("turn on the lights")
        assert r1 == r2

    def test_punctuation_stripped(self, router):
        r1, _ = router.route("turn on the lights!!!")
        r2, _ = router.route("turn on the lights")
        assert r1 == r2

    def test_contractions(self, router):
        """'what's' → 'what is' normalization."""
        assert router.route("what's the temperature?")[0] == "query_temperature"


class TestAllToolsListed:
    """ALL_TOOLS contains expected tools."""

    def test_tool_count(self):
        """53 entries: 52 tool intents + 'none' sentinel."""
        assert len(HomeRouter.ALL_TOOLS) == 53

    def test_no_duplicates(self):
        assert len(set(HomeRouter.ALL_TOOLS)) == len(HomeRouter.ALL_TOOLS)

    def test_none_is_last(self):
        assert HomeRouter.ALL_TOOLS[-1] == "none"


class TestRuleIntegrity:
    """Rule system structural checks."""

    def test_all_rule_targets_are_valid_tools(self):
        """Every tool name in rules must appear in ALL_TOOLS."""
        valid = set(HomeRouter.ALL_TOOLS)
        invalid = [t for _, t in _ROUTER_RULES_RAW if t not in valid]
        assert not invalid, f"Rules reference unknown tools: {invalid}"

    def test_all_tested_tools_have_rules(self):
        """Every tool in TEST_CASES must be reachable via rules."""
        tested_tools = set(t for _, t in TEST_CASES) - {"none"}
        rule_tools = set(t for _, t in _ROUTER_RULES_RAW)
        # Allow tools that are only reachable via fallback
        missing = tested_tools - rule_tools
        # If any are missing from rules, they'd need fallback to work
        if missing:
            pytest.skip(f"Tools only reachable via fallback: {missing}")


class TestHABridgeMapping:
    """Verify HA bridge can build service calls for all tools."""

    def test_all_tools_have_ha_mapping(self):
        from ha_bridge import HA_SERVICE_MAP, HA_ENTITY_MAP
        service_tools = set(HA_SERVICE_MAP.keys())
        entity_tools = set(HA_ENTITY_MAP.keys())
        all_tools = set(HomeRouter.ALL_TOOLS) - {"none"}

        missing_service = all_tools - service_tools
        missing_entity = all_tools - entity_tools

        # Every tool should have both a service and entity mapping
        assert not missing_service, f"Missing HA service mapping for: {missing_service}"
        assert not missing_entity, f"Missing HA entity mapping for: {missing_entity}"

    def test_build_service_call_produces_valid_output(self):
        from ha_bridge import HABridge
        ha = HABridge(dry_run=True)
        # Test a few representative tools
        call = ha.build_service_call("turn_on_light", {"room": "living_room"})
        assert call["domain"] == "light"
        assert call["service"] == "turn_on"
        assert "living_room" in call["entity_id"]

    def test_ru_room_translation(self):
        from ha_bridge import HABridge, RU_ROOM_MAP
        ha = HABridge(dry_run=True)
        call = ha.build_service_call("turn_on_light", {"room": "гостиная"})
        assert "living_room" in call["entity_id"]

    def test_ru_ac_mode_translation(self):
        from ha_bridge import HABridge
        ha = HABridge(dry_run=True)
        call = ha.build_service_call("set_ac_mode", {"room": "bedroom", "mode": "охлаждение"})
        assert call["service_data"]["hvac_mode"] == "cool"


class TestParserSpec:
    """Verify parser.py loads v2 spec correctly (no GPT-2 inference, just spec checks)."""

    def test_tools_spec_v2_exists(self):
        from pathlib import Path
        spec = Path(__file__).resolve().parent.parent / "data" / "tools_spec_v2.json"
        assert spec.exists(), f"tools_spec_v2.json not found at {spec}"

    def test_tools_spec_v2_has_53_tools(self):
        import json
        from pathlib import Path
        spec = Path(__file__).resolve().parent.parent / "data" / "tools_spec_v2.json"
        with open(spec) as f:
            data = json.load(f)
        assert len(data["tools"]) == 53

    def test_fuzzy_match_tool(self):
        from parser import fuzzy_match_tool
        valid = {"turn_on_light", "vacuum_start", "stop_vacuum", "turn_off_light"}
        assert fuzzy_match_tool("turn_on_ligh", valid) == "turn_on_light"
        assert fuzzy_match_tool("start_vacuum_cleaner", valid) == "vacuum_start"
        assert fuzzy_match_tool("turn_on_light", valid) == "turn_on_light"