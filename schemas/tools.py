from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ToolRequest(BaseModel):
    """
    Schema for a generic MCP Tool execution payload. Passed inside a TOON TOOL_CALL payload.
    """
    tool_name: str = Field(..., description="The exact MCP tool registry ID")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool command")

class ToolResult(BaseModel):
    """
    Schema for a generic MCP Tool execution result. Passed inside a TOON TOOL_RESULT payload.
    """
    tool_name: str = Field(..., description="The exact MCP tool registry ID")
    success: bool = Field(..., description="Execution status")
    output: Optional[str] = Field(None, description="The stringified successful execution output")
    error: Optional[str] = Field(None, description="The trapped trace output if success is false")
