"""Vector Home API v2 — FastAPI server with WebSocket, history, and web dashboard.

Endpoints:
    POST /command       — process text command through full pipeline
    GET  /health        — system health check
    GET  /tools         — list 53 available tools
    GET  /entities      — list HA entities (filterable by domain)
    POST /ha/call        — direct HA service call
    GET  /history        — recent command history
    WS   /ws            — WebSocket for real-time dashboard updates
    GET  /panel          — web dashboard (serves static/index.html)
"""
import os, sys, json, asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
sys.path.insert(0, str(Path(__file__).resolve().parent))

from router import HomeRouter
from parser import HomeParser
from ha_bridge import HABridge
from pipeline import process

# ── App Setup ──────────────────────────────────────────────────────────

app = FastAPI(title="Vector Home v2", version="2.0.0")

# Global state (initialized on startup)
_router: Optional[HomeRouter] = None
_parser: Optional[HomeParser] = None
_ha: Optional[HABridge] = None
_history: list = []  # In-memory command history
MAX_HISTORY = 100

# WebSocket connections for dashboard
_ws_clients: list = []

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.on_event("startup")
async def startup():
    global _router, _parser, _ha
    _router = HomeRouter()
    _parser = HomeParser(verbose=False)
    _ha = HABridge(dry_run=True)
    print(f"[API] Vector Home v2 ready — {len(_router.ALL_TOOLS)} tools")


@app.on_event("shutdown")
async def shutdown():
    print("[API] Vector Home v2 shutting down")


# ── Static Dashboard ───────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/panel", response_class=HTMLResponse)
async def dashboard():
    """Serve the web dashboard."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return index.read_text(encoding='utf-8')
    return HTMLResponse("<h1>Dashboard not found</h1><p>Run: build the static/ directory</p>")


# ── REST API ────────────────────────────────────────────────────────────

from pydantic import BaseModel


class CommandRequest(BaseModel):
    text: str
    live: bool = False


class CommandResponse(BaseModel):
    tool: str
    arguments: dict
    ha_service: Optional[dict] = None
    latency_s: float = 0
    used_fallback: bool = False
    ha_result: Optional[dict] = None


@app.post("/command", response_model=CommandResponse)
async def command(req: CommandRequest):
    """Process a text command through the full pipeline."""
    if not _router or not _parser:
        raise HTTPException(503, "Server not ready")

    _ha.dry_run = not req.live
    result = process(req.text, _router, _parser, _ha, verbose=False)

    # Store in history
    entry = {
        "timestamp": datetime.now().isoformat(),
        "text": req.text,
        "result": result,
    }
    _history.append(entry)
    if len(_history) > MAX_HISTORY:
        _history.pop(0)

    # Broadcast to WebSocket clients
    await _broadcast(json.dumps({"type": "command", "data": entry}, ensure_ascii=False))

    return result


@app.get("/health")
async def health():
    """System health check."""
    status = {
        "status": "ok",
        "version": "2.0.0",
        "tools": len(_router.ALL_TOOLS) if _router else 0,
        "router": "loaded" if _router else "not loaded",
        "parser": "loaded" if _parser else "not loaded",
        "ha_bridge": "connected" if _ha and not _ha.dry_run else "dry_run",
    }
    return status


@app.get("/tools")
async def list_tools():
    """List all 53 available tools with descriptions."""
    if not _parser:
        raise HTTPException(503, "Parser not loaded")
    return {"tools": _parser.tools, "count": len(_parser.tools)}


@app.get("/entities")
async def list_entities(domain: str = Query(None, description="Filter by HA domain")):
    """List HA entities, optionally filtered by domain."""
    if not _ha:
        raise HTTPException(503, "HA bridge not loaded")
    entities = await _ha.list_entities(domain=domain)
    return {"entities": entities, "count": len(entities)}


@app.post("/ha/call")
async def ha_call(tool_name: str, arguments: dict = {}, live: bool = True):
    """Direct HA service call."""
    if not _ha:
        raise HTTPException(503, "HA bridge not loaded")
    _ha.dry_run = not live
    result = call_ha_sync(tool_name, arguments, url=_ha.url, token=_ha.token, dry_run=_ha.dry_run)
    return result


@app.get("/history")
async def history(limit: int = Query(20, ge=1, le=100)):
    """Recent command history."""
    return {"history": _history[-limit:], "total": len(_history)}


# ── WebSocket ────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time dashboard updates."""
    await ws.accept()
    _ws_clients.append(ws)
    try:
        # Send initial state
        await ws.send_json({"type": "init", "tools_count": len(_router.ALL_TOOLS) if _router else 0,
                            "history": _history[-20:]})
        # Keep alive
        while True:
            data = await ws.receive_text()
            # Allow command via WebSocket
            if data.startswith("/command "):
                text = data[9:]
                _ha.dry_run = True
                result = process(text, _router, _parser, _ha, verbose=False)
                entry = {"timestamp": datetime.now().isoformat(), "text": text, "result": result}
                _history.append(entry)
                if len(_history) > MAX_HISTORY:
                    _history.pop(0)
                await ws.send_json({"type": "command", "data": entry})
            elif data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def _broadcast(message: str):
    """Broadcast message to all connected WebSocket clients."""
    for ws in list(_ws_clients):
        try:
            await ws.send_text(message)
        except Exception:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


# ── HABridge async extension ────────────────────────────────────────────

# Add list_entities to HABridge for the API
async def _ha_list_entities(self, domain: str = None):
    """List HA entities via REST API."""
    if not self.token:
        return []
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            url = f"{self.url}/api/states"
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = await client.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            entities = resp.json()
            if domain:
                entities = [e for e in entities if e["entity_id"].startswith(f"{domain}.")]
            return [{"entity_id": e["entity_id"], "state": e["state"],
                      "attributes": {k: v for k, v in e.get("attributes", {}).items()
                                      if k not in ("friendly_name", "icon", "entity_id")}}
                     for e in entities]
    except Exception:
        return []


# Monkey-patch the async method onto HABridge
HABridge.list_entities = _ha_list_entities


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("VH_PORT", "8126"))
    uvicorn.run(app, host="0.0.0.0", port=port)