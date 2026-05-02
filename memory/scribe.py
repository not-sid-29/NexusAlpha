import logging
import json
from typing import Any, Dict
from bus.dispatcher import AsyncDispatcher
from memory.db_manager import DatabaseManager
from memory.graph_store import UserGraph
from memory.update_protocol import GraphUpdateProtocol
from memory.vector_store import VectorStore
from schemas.messages import TOONMessage, MessageType

logger = logging.getLogger("nexus.memory.scribe")


class MemoryScribe:
    """
    Single-Writer Service for all memory persistence.

    Consumes MEMORY_WRITE and REFLECTION messages from the bus.
    MEMORY_WRITE: persist raw interaction turn to SQLite.
    REFLECTION: run 6-step GraphUpdateProtocol (entities → graph → vectors).
    """

    def __init__(
        self,
        dispatcher: AsyncDispatcher,
        db_manager: DatabaseManager,
        vector_store: VectorStore | None = None,
        graphs: Dict[str, UserGraph] | None = None,
    ):
        self.dispatcher = dispatcher
        self.db = db_manager
        self.vector_store = vector_store or VectorStore()
        self.graphs = graphs or {}
        self._is_running = False

    async def start(self):
        self._is_running = True
        await self.dispatcher.subscribe("MEMORY_SCRIBE", self._handle_bus_message)
        logger.info("[SCRIBE] Service started.")

    async def stop(self):
        self._is_running = False

    async def _handle_bus_message(self, message: TOONMessage):
        if not self._is_running:
            return
        if message.msg_type == MessageType.MEMORY_WRITE:
            await self._handle_write(message)
        elif message.msg_type == MessageType.REFLECTION:
            await self._handle_reflection(message)

    async def _handle_write(self, message: TOONMessage):
        """Persist a single interaction turn to SQLite."""
        payload = message.payload
        trace_id = message.trace_id
        stored_msg_type = payload.get("msg_type", message.msg_type.value)
        stored_source = payload.get("source", message.source)
        stored_target = payload.get("target", message.target)
        stored_payload = payload.get("payload", payload)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO interactions (trace_id, msg_type, source, target, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    stored_msg_type,
                    stored_source,
                    stored_target,
                    json.dumps(stored_payload),
                ),
            )
            conn.commit()

        logger.debug("[SCRIBE] Persisted turn for trace %s", trace_id)

    async def _handle_reflection(self, message: TOONMessage):
        """Run 6-step graph update protocol at session end."""
        trace_id = message.trace_id
        user_id = message.payload.get("user_id", "")

        if not user_id:
            logger.warning("[SCRIBE] REFLECTION missing user_id for trace %s", trace_id)
            return

        graph = self._get_or_load_graph(user_id)
        protocol = GraphUpdateProtocol(
            db=self.db,
            vector_store=self.vector_store,
            graph=graph,
        )
        result = await protocol.run(trace_id=trace_id, user_id=user_id)
        logger.info("[SCRIBE] Graph update complete: %s", result)

    def _get_or_load_graph(self, user_id: str) -> UserGraph:
        if user_id not in self.graphs:
            graph = UserGraph(user_id=user_id, db_manager=self.db)
            graph.load()
            self.graphs[user_id] = graph
        return self.graphs[user_id]
