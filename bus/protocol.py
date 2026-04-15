import uuid
from typing import Dict, Any
from schemas.messages import TOONMessage, MessageType, MessagePriority

def create_message(
    msg_type: MessageType,
    source: str,
    target: str,
    payload: Dict[str, Any],
    token_budget: int = 4000,
    priority: MessagePriority = MessagePriority.P3_MEDIUM,
    trace_id: str = "none"
) -> TOONMessage:
    """
    Universal factory method for rapidly building a typed TOON message.
    """
    return TOONMessage(
        msg_id=uuid.uuid4(),
        msg_type=msg_type,
        source=source,
        target=target,
        priority=priority,
        token_budget=token_budget,
        payload=payload,
        trace_id=trace_id
    )

def create_task_message(source: str, target: str, payload_data: Dict[str, Any], trace_id: str) -> TOONMessage:
    """ Helper to build a TASK message immediately """
    return create_message(
        msg_type=MessageType.TASK,
        source=source,
        target=target,
        payload=payload_data,
        trace_id=trace_id
    )
