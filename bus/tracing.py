import uuid
import contextvars
from typing import Optional

# Internal context var for attaching trace IDs to logs dynamically
_current_trace_id = contextvars.ContextVar("current_trace_id", default=None)

def generate_trace_id() -> str:
    """
    Generates a unique trace ID for a new execution session.
    """
    trace_id = f"trace-{uuid.uuid4().hex}"
    _current_trace_id.set(trace_id)
    return trace_id

def get_current_trace_id() -> Optional[str]:
    """
    Retrieves the active trace ID from the async context.
    """
    return _current_trace_id.get()

def set_current_trace_id(trace_id: str):
    """
    Manually overrides the active trace ID.
    """
    _current_trace_id.set(trace_id)
