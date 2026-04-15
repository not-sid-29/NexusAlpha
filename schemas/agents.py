from typing import List, Optional
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    """
    Represents the schema for Agent configurations loaded from YAML manifests
    """
    name: str = Field(..., description="Unique identifier for the agent")
    trigger_patterns: List[str] = Field(default_factory=list, description="Regex patterns driving the core Router logic")
    system_prompt_path: str = Field(..., description="Relative path targeting the persona payload")
    max_tokens: int = Field(default=4000, description="Absolute ceiling for the agent context slice")
    allowed_tools: List[str] = Field(default_factory=list, description="Subset of active MCP tools authorized for this agent")
    handoff_to: str = Field(..., description="The designated next agent in the DAG structure")
    description: str = Field(..., description="Semantic purpose used by the orchestrator")
