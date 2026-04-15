import pytest
import asyncio
from bus.dispatcher import AsyncDispatcher
from bus.protocol import create_message
from schemas.messages import MessageType
from security.permissions import is_tool_authorized

@pytest.mark.asyncio
async def test_permission_enforcement_blocking():
    """
    Ensure the dispatcher blocks TOOL_CALLs that deviate from the Permission Matrix.
    """
    dispatcher = AsyncDispatcher()
    
    # 1. Planner calling file_system_read_tree (AUTHORIZED)
    msg_ok = create_message(
        msg_type=MessageType.TOOL_CALL,
        source="planner",
        target="FSM",
        payload={"tool_name": "file_system_read_tree", "parameters": {}},
        trace_id="t1"
    )
    # Should not raise
    await dispatcher.publish(msg_ok)

    # 2. Planner calling executor (UNAUTHORIZED)
    msg_bad = create_message(
        msg_type=MessageType.TOOL_CALL,
        source="planner",
        target="SANDBOX",
        payload={"tool_name": "executor", "parameters": {"cmd": "rm -rf /"}},
        trace_id="t2"
    )
    
    with pytest.raises(PermissionError) as excinfo:
        await dispatcher.publish(msg_bad)
    
    assert "not authorized to use tool executor" in str(excinfo.value)

@pytest.mark.asyncio
async def test_unknown_agent_permission_rejection():
    """
    Ensure an unknown agent has zero tool permissions.
    """
    dispatcher = AsyncDispatcher()
    msg = create_message(
        msg_type=MessageType.TOOL_CALL,
        source="hacker_agent",
        target="FSM",
        payload={"tool_name": "file_system_read", "parameters": {}},
        trace_id="t3"
    )
    with pytest.raises(PermissionError):
        await dispatcher.publish(msg)
