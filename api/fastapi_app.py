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

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from schemas.messages import TOONMessage
from bus.dispatcher import AsyncDispatcher
from core.engine import NexusEngine
from core.state_machine import AutonomyMode
from agents.planner import PlannerAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from memory.db_manager import DatabaseManager
from memory.scribe import MemoryScribe
from memory.vector_store import VectorStore

load_dotenv(dotenv_path=".env", override=True)

# Configure logging early
logging.getLogger("nexus").setLevel(logging.INFO)
h = logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
if not logging.getLogger("nexus").handlers:
    logging.getLogger("nexus").addHandler(h)

logger = logging.getLogger("nexus.api")

app = FastAPI(title="NexusAlpha Engine HTTP/WS API", version="0.1.0")
nexus_dispatcher = AsyncDispatcher()
nexus_db = DatabaseManager.from_env()
nexus_vector_store = VectorStore()
nexus_memory_scribe = MemoryScribe(nexus_dispatcher, nexus_db, nexus_vector_store)
nexus_engine = NexusEngine(nexus_dispatcher, db_manager=nexus_db)
nexus_planner = PlannerAgent(nexus_dispatcher)
nexus_coder = CoderAgent(nexus_dispatcher)
nexus_debugger = DebuggerAgent(nexus_dispatcher)


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
        """
        trace_id = message.trace_id
        client_id = self._trace_to_client.get(trace_id)

        if not client_id or client_id not in self._connections:
            return

        ws = self._connections[client_id]
        try:
            # Check for usage metrics in payload
            usage = message.payload.get("usage")
            if usage:
                # Add usage to the outbound WS message
                data = message.model_dump(mode="json")
                data["type"] = "usage_update"
                await ws.send_text(json.dumps(data))
            else:
                await ws.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"[WS] Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)


    async def send_raw_to_trace_owner(self, trace_id: str, data: dict):
        """Send a raw dictionary to the client owning the trace_id."""
        client_id = self._trace_to_client.get(trace_id)
        if not client_id or client_id not in self._connections:
            return
        ws = self._connections[client_id]
        try:
            await ws.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"[WS] Failed to send raw data to {client_id}: {e}")

manager = TenantConnectionManager()

async def _engine_event_bridge(trace_id: str, data: dict):
    """Bridge Engine events (state changes/results) to WebSocket client."""
    await manager.send_raw_to_trace_owner(trace_id, data)

nexus_engine.event_callback = _engine_event_bridge

def _dispatcher_flush(message: TOONMessage):
    """Sync callback bridging to async WS send (scoped, not broadcast)."""
    asyncio.create_task(manager.send_to_trace_owner(message))

nexus_dispatcher.external_stream_callback = _dispatcher_flush

@app.on_event("startup")
async def startup():
    await nexus_memory_scribe.start()
    await nexus_engine.start()
    await nexus_planner.start()
    await nexus_coder.start()
    await nexus_debugger.start()


@app.on_event("shutdown")
async def shutdown():
    await nexus_memory_scribe.stop()
    await nexus_engine.shutdown()
    await nexus_dispatcher.shutdown()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("[WS] New connection attempt...")
    client_id = await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            logger.debug(f"[WS] Received from {client_id}: {raw[:100]}...")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Plain text prompt → submit as task
                data = {"action": "submit", "prompt": raw}

            action = data.get("action", "submit")

            try:
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
            except Exception as e:
                logger.error(f"[WS_CRASH] Action {action} failed: {e}", exc_info=True)
                await websocket.send_text(json.dumps({"event": "error", "message": str(e)}))

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
