import pytest
import asyncio
from bus.dispatcher import AsyncDispatcher
from bus.protocol import create_message
from schemas.messages import MessageType
from core.engine import NexusEngine

@pytest.mark.asyncio
async def test_input_guard_blocking():
    """Ensure dangerous path traversal prompts are blocked at the engine gate."""
    dispatcher = AsyncDispatcher()
    engine = NexusEngine(dispatcher)
    
    with pytest.raises(ValueError) as excinfo:
        await engine.submit_user_prompt(
            user_prompt="read context from ../../../etc/passwd",
        )
    assert "Dangerous input pattern detected" in str(excinfo.value)

@pytest.mark.asyncio
async def test_output_guard_syntax_retry():
    """Ensure broken Python code from Coder triggers a transition to DEBUGGING."""
    dispatcher = AsyncDispatcher()
    engine = NexusEngine(dispatcher)
    from core.state_machine import SessionState, AutonomyMode
    
    # 1. Setup a session — Engine already moves it to PLANNING
    trace_id = await engine.submit_user_prompt("write a script", autonomy_mode=AutonomyMode.AUTONOMOUS)
    session = engine.registry.get_session(trace_id)
    from core.state_machine import SessionState
    
    # Manually advance to CODING to simulate agent being triggered
    session.transition(SessionState.CODING)   # PLANNING -> CODING
    
    # 2. Simulate Coder sending broken code
    broken_msg = create_message(
        msg_type=MessageType.RESULT,
        source="CODER",
        target="ENGINE",
        payload={"code": "def failing_syntax():\n    return 'no closing quote"},
        trace_id=trace_id
    )
    
    await engine.handle_agent_result(broken_msg)
    
    # Check that session moved to DEBUGGING instead of REVIEWING/COMPLETED
    from core.state_machine import SessionState
    assert session.state == SessionState.DEBUGGING

@pytest.mark.asyncio
async def test_secret_scrubbing_in_bus():
    """Ensure API keys are redacted by the dispatcher before delivery."""
    dispatcher = AsyncDispatcher()
    
    # Mock a subscriber to receive the message
    queue = dispatcher.subscribe("CLIENT")
    
    msg = create_message(
        msg_type=MessageType.RESULT,
        source="CODER",
        target="CLIENT",
        payload={"log": "Connected with key sk-1234567890abcdef1234567890abcdef1234567890abcdef"},
        trace_id="t1"
    )
    
    await dispatcher.publish(msg)
    
    received = await queue.get()
    assert "[REDACTED_API_KEY]" in received.payload["log"]
    assert "sk-123" not in received.payload["log"]
