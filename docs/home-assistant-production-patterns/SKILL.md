---
name: home-assistant-production-patterns
description: "Load when designing or reviewing Home Assistant automations for production reliability — rate-limiting, duplicate detection, graceful degradation, state persistence, alias resolution, and cost control. Extracted from CCOSTAN/Home-AssistantConfig (5k+ stars real-world config)."
---

# Home Assistant Production Patterns

Real-world patterns extracted from CCOSTAN/Home-AssistantConfig — hundreds of devices, thousands of automations, years of uptime.

## Pattern 1: AI Call Rate-Limiting & Cost Control

From `llmvision.yaml`. Problem: OpenAI Vision calls cost money, camera triggers fire constantly.

```yaml
input_datetime:
  llmvision_garbage_last_run:
    name: "LLM Vision garage last run"
    has_date: true
    has_time: true
```

**Rules:**
- Track `last_run` per AI call type
- Enforce minimum interval between calls (e.g., 30 minutes)
- Downscale images before sending (reduce resolution = reduce tokens = reduce cost)
- `input_text` for last response — enables cost audit without external DB

**Gotcha:** Without `last_run` guard, a motion sensor firing every 10 seconds = $100/day in API costs.

## Pattern 2: Duplicate Detection via Event ID

From `maintenance_log.yaml`. Problem: webhook replays, retries, and user double-submits.

```yaml
is_duplicate: >-
  {% set existing = (states('input_text.water_softener_salt_recent_event_ids')
     | default('', true) | string).split('|') %}
  {{ event_id in existing }}
```

**Rules:**
- Every event gets a unique `event_id` (client-generated or timestamp-based)
- Store recent IDs in `input_text` (pipe-separated, 255 char limit = ~8 IDs)
- Skip processing if `is_duplicate`
- Always log skipped events (audit trail)

**Gotcha:** HA's `input_text` has 255-char max. That's ~8 UUIDs. For higher volume, use external DB or truncate.

## Pattern 3: Graceful Degradation with Sensible Defaults

From `maintenance_log.yaml`. Problem: new installs have no history, template sensors error on `None`.

```yaml
state: >-
  {% if raw in ['unknown', 'unavailable', 'none', ''] %}
    150
  {% else %}
    {{ computed_value }}
  {% endif %}
```

**Rules:**
- Every template sensor has an explicit fallback value
- 150 days for "average days between refills" on a new install is reasonable
- Never show "unknown" in dashboards — use fallback with clear label
- `availability` template: explicitly false when data is missing (not just state)

**Gotcha:** Templates that error silently show "unknown" in the UI. This is worse than a wrong value — it breaks automations that depend on the sensor.

## Pattern 4: Alias Resolution for Input Normalization

From `maintenance_log.yaml`. Problem: users say "softner", "softener", "water softener salt", "salt".

```yaml
item_key: >-
  {% set aliases = {
    'water_softener_salt': 'water_softener_salt',
    'softener_salt': 'water_softener_salt',
    'softener': 'water_softener_salt',
    'salt': 'water_softener_salt',
    'softner': 'water_softener_salt'
  } %}
  {{ aliases.get(source_item, source_item) }}
```

**Rules:**
- Normalize ALL user/API input through an alias map
- Keep canonical names consistent (snake_case)
- Unknown inputs pass through with logging (don't silently drop)
- Same pattern for units: lb, lbs, pound, pounds → lb

**Gotcha:** Without normalization, "softener" and "softner" become two different entities. This breaks history, trends, and automations.

## Pattern 5: Multi-Layer Input Validation

From `maintenance_log.yaml`. Problem: webhook receives arbitrary JSON.

```yaml
action:
  - choose:
      - conditions: not is_supported_item → log and skip
      - conditions: amount <= 0 → log and skip
      - conditions: is_duplicate → log and skip
    default:
      - process the event
```

**Rules:**
- Validate in layers: item type → amount validity → duplicate check → process
- Each rejection layer logs what happened and why
- Default action only fires when ALL validations pass
- Use `choose` with sequential conditions, not nested `if`

**Gotcha:** Validating inside the action body (not at trigger) means the automation still fires — but it costs nothing and keeps the logic in one place.

## Pattern 6: FIFO Buffer for Recent Events

From `maintenance_log.yaml`. Problem: need recent history without a database.

```yaml
next_recent_events: >-
  {% set current = (states('input_text.water_softener_salt_recent_events')
     | default('', true) | string).split('||') %}
  {% set ns = namespace(items=[recent_event_line]) %}
  {% for raw in current %}
    {% set value = raw | trim %}
    {% if value and value != recent_event_line and (ns.items | count) < 10 %}
      {% set ns.items = ns.items + [value] %}
    {% endif %}
  {% endfor %}
  {{ ns.items | join('||') }}
```

**Rules:**
- Store N most recent items in pipe-delimited `input_text`
- New item = prepend, remove oldest if over limit
- Deduplicate by content
- Default to empty string, not "unknown"

**Gotcha:** `||` delimiter chosen because pipe `|` conflicts with Jinja. Double-pipe is safe.

## Pattern 7: Dual-Zone State Mirroring

From `climate.yaml`. Problem: upstairs/downstairs have separate thermostats but shared logic.

```yaml
template:
  - binary_sensor:
      - name: "Downstairs AC is Cooling"
        state: "{{ state_attr('climate.downstairs', 'hvac_action') == 'cooling' }}"
      - name: "Upstairs AC is Cooling"
        state: "{{ state_attr('climate.upstairs', 'hvac_action') == 'cooling' }}"
  - sensor:
      - name: "Downstairs AC Cooling Numeric"
        state: "{{ 1 if is_state('binary_sensor.downstairs_ac_cooling', 'on') else 0 }}"
      - name: "Upstairs AC Cooling Numeric"
        state: "{{ 1 if is_state('binary_sensor.upstairs_ac_cooling', 'on') else 0 }}"
```

**Rules:**
- Expose device state as named binary_sensor (human-readable)
- Expose same state as numeric sensor (for statistics, graphs, integrations)
- Mirror pattern for every multi-zone setup
- Use `state_attr()` not `states()` for internal attributes

**Gotcha:** `states('climate.downstairs')` returns the MODE string ("cool"), not the ACTION ("cooling"). Always use `state_attr()` for hvac_action.

## When to Use

- Building new HA automations → apply patterns 1-7 from day one
- Reviewing existing config → audit for missing fallbacks, duplicate detection, alias maps
- Integrating AI/LLM into HA → pattern 1 (rate-limiting) and 5 (input validation) are mandatory
- Designing for multi-user → pattern 4 (alias resolution) prevents entity fragmentation

## Source

CCOSTAN/Home-AssistantConfig — https://github.com/CCOSTAN/Home-AssistantConfig (5k+ stars)
