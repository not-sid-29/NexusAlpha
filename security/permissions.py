from typing import List, Dict, Any
from enum import Enum

class AgentType(Enum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"
    RESEARCHER = "researcher"
    MEMORY_SCRIBE = "memory_scribe"

# The Definitive Permission Matrix
# Mapping Agent -> Set of allowed tools
PERMISSION_MATRIX = {
    AgentType.PLANNER: {
        "file_system_read_tree", 
        "memory_read"
    },
    AgentType.CODER: {
        "file_system_read", 
        "file_system_write_diff", 
        "lsp_client", 
        "memory_read"
    },
    AgentType.REVIEWER: {
        "file_system_read", 
        "lsp_client", 
        "memory_read"
    },
    AgentType.DEBUGGER: {
        "file_system_read", 
        "file_system_write_diff", 
        "executor", 
        "lsp_client", 
        "memory_read"
    },
    AgentType.RESEARCHER: {
        "web_search", 
        "memory_read"
    },
    AgentType.MEMORY_SCRIBE: {
        "graph_read", 
        "graph_write", 
        "vector_read", 
        "vector_write"
    }
}

def is_tool_authorized(agent_name: str, tool_name: str) -> bool:
    """
    Enforces the security boundary defined in SYSTEM_ARCHITECTURE.md.
    """
    try:
        agent = AgentType(agent_name.lower())
        allowed_tools = PERMISSION_MATRIX.get(agent, set())
        return tool_name in allowed_tools
    except ValueError:
        return False
