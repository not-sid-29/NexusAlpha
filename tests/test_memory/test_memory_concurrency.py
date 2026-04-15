import pytest
import asyncio
import os
from bus.dispatcher import AsyncDispatcher
from bus.protocol import create_message
from schemas.messages import MessageType
from memory.db_manager import DatabaseManager
from memory.scribe import MemoryScribe

@pytest.mark.asyncio
async def test_memory_scribe_concurrency():
    """
    Stress test: 10 concurrent tasks flooding the Bus with MEMORY_WRITE messages.
    MemoryScribe must serialize them cleanly into the WAL-mode SQLite DB.
    """
    db_test_path = "test_nexus_concurrency.db"
    if os.path.exists(db_test_path):
        os.remove(db_test_path)
        
    db_manager = DatabaseManager(db_test_path)
    dispatcher = AsyncDispatcher()
    scribe = MemoryScribe(dispatcher, db_manager)
    await scribe.start()

    async def producer(task_id: int, count: int):
        for i in range(count):
            msg = create_message(
                msg_type=MessageType.MEMORY_WRITE,
                source=f"PRODUCER_{task_id}",
                target="MEMORY_SCRIBE",
                payload={"data": f"task_{task_id}_val_{i}"},
                trace_id=f"trace_{task_id}"
            )
            await dispatcher.publish(msg)
            # Small jitter to simulate real async agent behavior
            await asyncio.sleep(0.01)

    # 10 producers, 20 writes each = 200 total records
    num_producers = 10
    writes_per_producer = 20
    
    tasks = [producer(i, writes_per_producer) for i in range(num_producers)]
    await asyncio.gather(*tasks)

    # Wait for the Scribe to drain the queue (buffered)
    # The dispatcher queue is async, but the scribe needs time to execute the DB IO
    await asyncio.sleep(2.0)
    await scribe.stop()

    # Verify count in DB
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM interactions")
        count = cursor.fetchone()[0]
        
    assert count == (num_producers * writes_per_producer)
    
    # Cleanup
    if os.path.exists(db_test_path):
        os.remove(db_test_path)
        # SQLite creates extra files in WAL mode
        for ext in ["-wal", "-shm"]:
            if os.path.exists(db_test_path + ext):
                os.remove(db_test_path + ext)
