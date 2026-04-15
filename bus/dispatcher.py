"""
bus/dispatcher.py — Production-Grade Async Pub/Sub Dispatcher.

Enforces queue backpressure (maxsize), Dead-Letter Queue for dropped
messages, and graceful shutdown of consumer tasks.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable

from schemas.messages import TOONMessage, MessageType
from bus.registry import validate_payload, RegistryValidationError
from security.permissions import is_tool_authorized
from core.guards import OutputGuard

logger = logging.getLogger("nexus.bus")

QUEUE_MAX_SIZE = 100  # Backpressure cap per subscriber


class DeadLetterQueue:
    """
    Stores messages that could not be delivered due to backpressure or
    subscriber unavailability. Can be inspected for debugging or replayed.
    """

    def __init__(self, max_size: int = 500):
        self._items: List[TOONMessage] = []
        self._max_size = max_size

    def push(self, message: TOONMessage, reason: str):
        if len(self._items) >= self._max_size:
            # Evict oldest
            self._items.pop(0)
        self._items.append(message)
        logger.warning(
            f"[DLQ] Message {message.msg_id} from {message.source} "
            f"to {message.target} dead-lettered: {reason}"
        )

    @property
    def size(self) -> int:
        return len(self._items)

    def drain(self) -> List[TOONMessage]:
        """Return all items and clear the DLQ."""
        items = list(self._items)
        self._items.clear()
        return items


class AsyncDispatcher:
    """
    Central Pub/Sub Async Message Queue with production safety:
    - Bounded queues (backpressure)
    - Dead-Letter Queue for dropped messages
    - Graceful shutdown
    - Isolated external stream callback for WebSocket push
    """

    def __init__(self, queue_max_size: int = QUEUE_MAX_SIZE):
        self._queue_max_size = queue_max_size
        self._queues: Dict[str, asyncio.Queue] = {}
        self._dlq = DeadLetterQueue()
        self._shutting_down = False
        # Allows pushing events outward to a fast websocket handler
        self.external_stream_callback: Optional[Callable] = None

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq

    def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        """Create or return a bounded queue for the subscriber."""
        if subscriber_id not in self._queues:
            self._queues[subscriber_id] = asyncio.Queue(maxsize=self._queue_max_size)
        return self._queues[subscriber_id]

    async def publish(self, message: TOONMessage):
        """
        Validates the message schema, then routes to the target subscriber queue.
        If queue is full (backpressure), shunts to DLQ instead of blocking.
        """
        if self._shutting_down:
            self._dlq.push(message, "dispatcher_shutting_down")
            return

        # ── Schema validation ──
        try:
            validate_payload(message.msg_type, message.payload)
        except RegistryValidationError as e:
            logger.error(f"[BUS] Schema Rejection from {message.source}: {e}")
            raise

        # ── Security Permission Check (Agent-Tool boundary) ──
        if message.msg_type == MessageType.TOOL_CALL:
            tool_name = message.payload.get("tool_name")
            if not is_tool_authorized(message.source, tool_name):
                logger.warning(f"[BUS] Permission Denied: {message.source} calling {tool_name}")
                raise PermissionError(f"Agent {message.source} is not authorized to use tool {tool_name}")

        # ── Output Guard: Secret Masking (Layer 5) ──
        if isinstance(message.payload, dict):
            # Mask any secrets in string values of the payload
            for k, v in message.payload.items():
                if isinstance(v, str):
                    message.payload[k] = OutputGuard.mask_secrets(v)

        target = message.target

        # Ensure target queue exists
        if target not in self._queues:
            self._queues[target] = asyncio.Queue(maxsize=self._queue_max_size)

        # ── Backpressure handling ──
        try:
            self._queues[target].put_nowait(message)
        except asyncio.QueueFull:
            self._dlq.push(message, f"queue_full:{target}")
            logger.error(
                f"[BUS] Backpressure! Queue for {target} is full "
                f"({self._queue_max_size}). Message dead-lettered."
            )
            return

        logger.debug(
            f"[BUS] Routed {message.msg_type.value} from "
            f"{message.source} → {target}"
        )

        # ── Flush to external WebSocket stream ──
        if self.external_stream_callback:
            try:
                self.external_stream_callback(message)
            except Exception as e:
                logger.error(f"[BUS] External stream flush failed: {e}")

    async def shutdown(self):
        """
        Graceful shutdown: mark as shutting down, drain all queues, 
        dead-letter remaining messages.
        """
        self._shutting_down = True
        for subscriber_id, queue in self._queues.items():
            while not queue.empty():
                try:
                    msg = queue.get_nowait()
                    self._dlq.push(msg, f"shutdown_drain:{subscriber_id}")
                except asyncio.QueueEmpty:
                    break
        logger.info(
            f"[BUS] Shutdown complete. {self._dlq.size} messages in DLQ."
        )
