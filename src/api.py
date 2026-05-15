"""Vector Home API — FastAPI endpoint for smart-home command processing.

POST /command  {"utterance": "turn on the lights in the living room"}
GET  /health
GET  /tools
GET  /entities?domain=light
POST /ha/call  {"tool_name": "turn_on_light", "arguments": {"room": "living room"}}

Environment:
    HA_URL   — Home Assistant URL (default: http://homeassistant.local:8123)
    HA_TOKEN — Long-lived access token
    VH_PORT  — Server port (default: 8126)
    VH_DRY_RUN — If "1", don't actually call HA
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
sys.path.insert(0, str(Path(__file__).resolve().parent))

from router import HomeRouter
from parser import HomeParser
from ha_bridge import HABridge

app = FastAPI(title="Vector Home API", version="0.2.0")

# CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components at startup
_router: Optional[HomeRouter] = None
_parser: Optional[HomeParser] = None
_ha: Optional[HABridge] = None


class CommandRequest(BaseModel):
    utterance: str
    skip_confirm: bool = True
    use_fallback: bool = True  # Allow Ollama fallback on router miss


class CommandResponse(BaseModel):
    tool_name: str
    arguments: dict
    confident: bool
    used_fallback: bool
    latency_ms: float
    ha_service: Optional[dict] = None
    ha_result: Optional[dict] = None


class HACallRequest(BaseModel):
    tool_name: str
    arguments: dict = {}


@app.on_event("startup")
async def startup():
    global _router, _parser, _ha
    _router = HomeRouter()
    _parser = HomeParser(verbose=False)
    _ha = HABridge(
        url=os.environ.get("HA_URL", "http://homeassistant.local:8123"),
        token=os.environ.get("HA_TOKEN", ""),
        dry_run=os.environ.get("VH_DRY_RUN", "1") == "1",
    )
    print(f"[VectorHome] Router: ready (rules={len(_router._rules)})")
    print(f"[VectorHome] Parser: ready (model=gpt2_ha_best.pt)")
    print(f"[VectorHome] HA Bridge: {'DRY RUN' if _ha.dry_run else 'LIVE'} ({_ha.url})")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "router": "ready" if _router else "not_loaded",
        "parser": "ready" if _parser else "not_loaded",
        "ha_bridge": "ready" if _ha else "not_loaded",
        "parser_model": "gpt2_ha_best.pt" if _parser else "none",
        "ha_mode": "dry_run" if _ha and _ha.dry_run else "live",
        "stats": _router.stats if _router else {},
    }


@app.get("/tools")
async def list_tools():
    from parser import load_tools_spec
    tools = load_tools_spec()
    return {"tools": tools, "count": len(tools)}


@app.get("/entities")
async def get_entities(domain: str = ""):
    """Discover HA entities. Optional ?domain=light filter."""
    if not _ha:
        raise HTTPException(503, "HA bridge not loaded")
    entities = await _ha.get_entities(domain=domain)
    return {"entities": entities, "count": len(entities)}


@app.post("/command", response_model=CommandResponse)
async def process_command(req: CommandRequest):
    if not _router or not _parser:
        raise HTTPException(503, "Components not loaded")

    t0 = time.time()

    # Step 1: Route
    tool_name, confident = _router.route(req.utterance)
    used_fallback = False

    # Step 2: Fallback if not confident
    if not confident and req.use_fallback:
        try:
            tool_name, used_fallback = _router.route_with_fallback(req.utterance)
            confident = True
        except Exception:
            tool_name = "none"

    # Step 3: Parse arguments
    arguments = {}
    parse_error = False
    if tool_name != "none":
        result = _parser.parse(req.utterance, tool_name)
        arguments = result.get("arguments", {})
        parse_error = result.get("_parse_error", False)

    latency_ms = (time.time() - t0) * 1000

    # Step 4: Map to HA service call
    ha_service = _ha.build_service_call(tool_name, arguments) if tool_name != "none" else None

    # Step 5: Execute HA call (async)
    ha_result = None
    if tool_name != "none" and ha_service:
        ha_result = await _ha.call_service(tool_name, arguments)

    return CommandResponse(
        tool_name=tool_name,
        arguments=arguments,
        confident=confident and not parse_error,
        used_fallback=used_fallback,
        latency_ms=round(latency_ms, 1),
        ha_service=ha_service,
        ha_result=ha_result,
    )


@app.post("/ha/call")
async def ha_call_direct(req: HACallRequest):
    """Direct HA service call (bypass routing)."""
    if not _ha:
        raise HTTPException(503, "HA bridge not loaded")
    result = await _ha.call_service(req.tool_name, req.arguments)
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("VH_PORT", 8126))
    print(f"Starting Vector Home API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)