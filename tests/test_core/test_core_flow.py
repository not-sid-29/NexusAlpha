import pytest
import asyncio
from core.token_ledger import TokenLedger
from core.context import ContextManager, ContextSegment
from core.router import BaseRouter
from core.engine import NexusEngine
from bus.dispatcher import AsyncDispatcher

def test_token_ledger_eviction():
    ledger = TokenLedger(max_session_tokens=100)
    # Use 85 tokens (85%)
    ledger.add_usage(85)
    
    # At 85%, Priority 2+ should be evicted
    assert ledger.should_evict(5) == True
    assert ledger.should_evict(2) == True
    assert ledger.should_evict(1) == False # Critical never evicts

def test_context_manager_assembly():
    ledger = TokenLedger(max_session_tokens=1000)
    cm = ContextManager(ledger)
    
    cm.inject_segment(ContextSegment("Critical Data", 1, 100))
    cm.inject_segment(ContextSegment("Archive Data", 5, 200))
    
    # Fill up the budget to force eviction of Archive data
    ledger.add_usage(900) 
    prompt = cm.assemble_prompt()
    
    assert "Critical Data" in prompt
    assert "Archive Data" not in prompt

def test_router_classification():
    router = BaseRouter()
    assert router.classify_task("Write a python script") == "CODER"
    assert router.classify_task("Debug this error trace") == "DEBUGGER"
    assert router.classify_task("plan the architecture") == "PLANNER"
    assert router.classify_task("what is the meaning of life") == "PLANNER" # Default fallback

@pytest.mark.asyncio
async def test_engine_submission():
    dispatcher = AsyncDispatcher()
    engine = NexusEngine(dispatcher)
    target_queue = dispatcher.subscribe("PLANNER")
    
    trace_id = await engine.submit_user_prompt("architect the database")
    
    # The engine should route it directly to the planner
    received_msg = await asyncio.wait_for(target_queue.get(), timeout=1.0)
    
    assert received_msg.trace_id == trace_id
    assert received_msg.target == "PLANNER"
    assert received_msg.payload["instruction"] == "architect the database"
