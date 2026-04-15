"""
Tests for bus/dispatcher.py — Production-grade dispatcher verification.
"""
import pytest
import asyncio
from bus.dispatcher import AsyncDispatcher
from bus.protocol import create_task_message
from schemas.messages import MessageType
from bus.registry import RegistryValidationError


@pytest.mark.asyncio
async def test_backpressure_dead_letter():
    """When a subscriber queue is full, messages should be dead-lettered."""
    dispatcher = AsyncDispatcher(queue_max_size=2)
    dispatcher.subscribe("SLOW_AGENT")

    # Publish 3 messages — 3rd should hit backpressure
    for i in range(3):
        msg = create_task_message("ENGINE", "SLOW_AGENT", {"i": i}, f"trace-{i}")
        await dispatcher.publish(msg)

    assert dispatcher.dlq.size == 1  # 1 message dead-lettered

@pytest.mark.asyncio
async def test_normal_routing_no_dlq():
    """Normal operation: messages route cleanly, DLQ stays empty."""
    dispatcher = AsyncDispatcher(queue_max_size=100)
    queue = dispatcher.subscribe("PLANNER")

    msg = create_task_message("ENGINE", "PLANNER", {"task": "test"}, "t1")
    await dispatcher.publish(msg)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.msg_id == msg.msg_id
    assert dispatcher.dlq.size == 0

@pytest.mark.asyncio
async def test_schema_validation_rejection():
    """Invalid TOOL_CALL payload must be rejected before reaching any queue."""
    dispatcher = AsyncDispatcher()
    dispatcher.subscribe("FSM")

    bad_msg = create_task_message("CODER", "FSM", {"bad": "data"}, "t2")
    bad_msg.msg_type = MessageType.TOOL_CALL

    with pytest.raises(RegistryValidationError):
        await dispatcher.publish(bad_msg)

@pytest.mark.asyncio
async def test_shutdown_drains_to_dlq():
    """On shutdown, remaining queued messages are drained to DLQ."""
    dispatcher = AsyncDispatcher()
    dispatcher.subscribe("TARGET")

    msg1 = create_task_message("A", "TARGET", {}, "t3")
    msg2 = create_task_message("B", "TARGET", {}, "t4")
    await dispatcher.publish(msg1)
    await dispatcher.publish(msg2)

    await dispatcher.shutdown()
    assert dispatcher.dlq.size == 2

@pytest.mark.asyncio
async def test_publish_during_shutdown_goes_to_dlq():
    """Messages published during shutdown go directly to DLQ."""
    dispatcher = AsyncDispatcher()
    await dispatcher.shutdown()

    msg = create_task_message("A", "B", {}, "t5")
    await dispatcher.publish(msg)
    assert dispatcher.dlq.size == 1  # The msg from shutdown publish

@pytest.mark.asyncio
async def test_external_stream_callback():
    """The WebSocket flush callback fires on every successful publish."""
    dispatcher = AsyncDispatcher()
    dispatcher.subscribe("TARGET")
    flushed = []
    dispatcher.external_stream_callback = lambda m: flushed.append(m)

    msg = create_task_message("A", "TARGET", {}, "t6")
    await dispatcher.publish(msg)
    assert len(flushed) == 1
