"""
api/fastapi_app.py — Production-Grade FastAPI + WebSocket Server.

Multi-tenant safe: each WS client is mapped by client_id and only
receives messages scoped to its active trace_ids. Uses asyncio.Lock
for safe concurrent modification of the connection pool.
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from schemas.messages import TOONMessage
from bus.dispatcher import AsyncDispatcher
from core.engine import NexusEngine
from core.state_machine import AutonomyMode

logger = logging.getLogger("nexus.api")

app = FastAPI(title="NexusAlpha Engine HTTP/WS API", version="0.1.0")
nexus_dispatcher = AsyncDispatcher()
nexus_engine = NexusEngine(nexus_dispatcher)


class TenantConnectionManager:
    """
    Production-safe WebSocket connection manager.
    - Each client gets a unique client_id
    - Clients are mapped to the trace_ids they own
    - Broadcasting is scoped: only the client that submitted a task
      receives its TOON messages (no cross-contamination)
    - asyncio.Lock protects connection pool mutations
    """

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}       # client_id → ws
        self._client_traces: Dict[str, Set[str]] = {}      # client_id → {trace_ids}
        self._trace_to_client: Dict[str, str] = {}         # trace_id → client_id
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = f"client-{uuid.uuid4().hex[:12]}"
        async with self._lock:
            self._connections[client_id] = websocket
            self._client_traces[client_id] = set()
        logger.info(f"[WS] Client {client_id} connected.")
        return client_id

    async def disconnect(self, client_id: str):
        async with self._lock:
            self._connections.pop(client_id, None)
            traces = self._client_traces.pop(client_id, set())
            for tid in traces:
                self._trace_to_client.pop(tid, None)
        logger.info(f"[WS] Client {client_id} disconnected.")

    def register_trace(self, client_id: str, trace_id: str):
        """Bind a trace_id to a specific client for scoped delivery."""
        self._client_traces.setdefault(client_id, set()).add(trace_id)
        self._trace_to_client[trace_id] = client_id

    async def send_to_trace_owner(self, message: TOONMessage):
        """
        Send a TOON message ONLY to the client that owns the trace_id.
        If no client owns it (e.g. disconnected), buffer for reconnect.
        """
        trace_id = message.trace_id
        client_id = self._trace_to_client.get(trace_id)

        if not client_id or client_id not in self._connections:
            # Client disconnected mid-task — buffer the result on the session
            session = nexus_engine.registry.get_session(trace_id)
            if session:
                session.buffered_result = message.model_dump(mode="json")
            logger.warning(
                f"[WS] No active client for trace {trace_id}. Result buffered."
            )
            return

        ws = self._connections[client_id]
        try:
            await ws.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"[WS] Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)


manager = TenantConnectionManager()


def _dispatcher_flush(message: TOONMessage):
    """Sync callback bridging to async WS send (scoped, not broadcast)."""
    asyncio.create_task(manager.send_to_trace_owner(message))


nexus_dispatcher.external_stream_callback = _dispatcher_flush


@app.on_event("startup")
async def startup():
    await nexus_engine.start()


@app.on_event("shutdown")
async def shutdown():
    await nexus_engine.shutdown()
    await nexus_dispatcher.shutdown()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Plain text prompt → submit as task
                data = {"action": "submit", "prompt": raw}

            action = data.get("action", "submit")

            if action == "submit":
                prompt = data.get("prompt", "")
                mode_str = data.get("mode", "INTERACTIVE").upper()
                mode = AutonomyMode(mode_str) if mode_str in AutonomyMode.__members__ else AutonomyMode.INTERACTIVE

                trace_id = await nexus_engine.submit_user_prompt(
                    user_prompt=prompt,
                    autonomy_mode=mode,
                    client_id=client_id,
                )
                manager.register_trace(client_id, trace_id)
                await websocket.send_text(json.dumps({
                    "event": "session_created",
                    "trace_id": trace_id,
                    "mode": mode.value,
                }))

            elif action == "approve":
                trace_id = data.get("trace_id", "")
                await nexus_engine.approve_session(trace_id)

            elif action == "reject":
                trace_id = data.get("trace_id", "")
                feedback = data.get("feedback", "")
                await nexus_engine.reject_session(trace_id, feedback)

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
