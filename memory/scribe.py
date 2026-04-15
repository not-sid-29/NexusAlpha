import asyncio
import logging
import json
from typing import Any, Dict
from bus.dispatcher import AsyncDispatcher
from memory.db_manager import DatabaseManager
from schemas.messages import TOONMessage, MessageType

logger = logging.getLogger("nexus.memory.scribe")

class MemoryScribe:
    """
    The Single-Writer Service.
    Consumes MEMORY_WRITE messages from the Bus and serializes them into SQLite.
    This prevents SQLITE_BUSY by ensuring only one write task executes at a time.
    """
    def __init__(self, dispatcher: AsyncDispatcher, db_manager: DatabaseManager):
        self.dispatcher = dispatcher
        self.db = db_manager
        self.queue = dispatcher.subscribe("MEMORY_SCRIBE")
        self._is_running = False

    async def start(self):
        self._is_running = True
        logger.info("[SCRIBE] Service started. Listening for MEMORY_WRITE events.")
        asyncio.create_task(self._process_queue())

    async def stop(self):
        self._is_running = False

    async def _process_queue(self):
        """
        The core loop that drains the TOON bus for memory tasks.
        """
        while self._is_running:
            try:
                message: TOONMessage = await self.queue.get()
                
                # Logic branch based on specific write types
                if message.msg_type == MessageType.MEMORY_WRITE:
                    await self._handle_write(message)
                
                self.queue.task_done()
            except Exception as e:
                logger.error(f"[SCRIBE] Loop error: {e}")
                await asyncio.sleep(1)

    async def _handle_write(self, message: TOONMessage):
        """
        Execute atomic write operation. 
        Wraps in a lock-safe transaction via the DB context manager.
        """
        payload = message.payload
        trace_id = message.trace_id
        
        # Scenario: Log an interaction turn
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interactions (trace_id, msg_type, source, target, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                trace_id, 
                message.msg_type.value, 
                message.source, 
                message.target, 
                json.dumps(payload)
            ))
            conn.commit()
            
        logger.debug(f"[SCRIBE] Successfully persisted turn for trace {trace_id}")
