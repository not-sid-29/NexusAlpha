from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, UUID4

class MessageType(str, Enum):
    TASK = "TASK"
    RESULT = "RESULT"
    ERROR = "ERROR"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    MEMORY_WRITE = "MEMORY_WRITE"
    REFLECTION = "REFLECTION"

class MessagePriority(int, Enum):
    P1_CRITICAL = 1
    P2_HIGH = 2
    P3_MEDIUM = 3
    P4_LOW = 4
    P5_ARCHIVE = 5

class TOONMessage(BaseModel):
    """
    The core TOON Envelope used for strictly typed inter-agent / inter-module communication.
    Zero direct calls are made outside of this structure.
    """
    msg_id: UUID4 = Field(..., description="Unique identifier for this message")
    msg_type: MessageType = Field(..., description="The type of message being sent")
    source: str = Field(..., description="Name of the agent or module sending the message")
    target: str = Field(..., description="Name of the agent or module meant to receive the message")
    priority: MessagePriority = Field(default=MessagePriority.P3_MEDIUM, description="Context eviction priority")
    token_budget: int = Field(..., ge=0, description="Allocated budget remaining for this request subset")
    payload: Dict[str, Any] = Field(default_factory=dict, description="The strictly structured content based on msg_type")
    trace_id: str = Field(..., description="The session trace UUID allowing correlation of logs and telemetry")
