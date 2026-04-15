from typing import Dict, Any, Type
from pydantic import BaseModel, ValidationError
from schemas.messages import MessageType
from schemas.tools import ToolRequest, ToolResult

# The strict payload registry dictates what structured classes the dictionaries MUST map to
PAYLOAD_REGISTRY: Dict[MessageType, Type[BaseModel]] = {
    MessageType.TOOL_CALL: ToolRequest,
    MessageType.TOOL_RESULT: ToolResult,
}

class RegistryValidationError(Exception):
    pass

def validate_payload(msg_type: MessageType, payload: Dict[str, Any]) -> bool:
    """
    Validates a raw dictionary payload against the registry map.
    Raises RegistryValidationError if the strict contract is broken.
    If no contract exists for the msg_type, allows passing (e.g., generic string TASK).
    """
    expected_model = PAYLOAD_REGISTRY.get(msg_type)
    if expected_model:
        try:
            # Instantiate the Pydantic model to trigger native Rust-level validation
            expected_model(**payload)
            return True
        except ValidationError as e:
            raise RegistryValidationError(f"Invalid payload for {msg_type.name}: {e}")
    return True
