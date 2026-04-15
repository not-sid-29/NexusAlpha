---
description: How to develop features in the Nexus Orchestration framework
---

# Nexus Feature Implementation Workflow

When asked to build or implement features in the Nexus workspace, you MUST adhere to the following architectural guidelines extracted from `QWEN.md` and `ARCHITECTURE_BLUEPRINT.md`.

## 1. 5-Plane Architecture Respect
Always verify which structural 'plane' the feature belongs to and place code in the exact corresponding directory:
- **Interface Plane** (`api/`): TUI, VS Code Extension Backend, REST endpoints.
- **Orchestrator Plane** (`core/`): Validation gates, Engine execution flow, Task Routing, Context Management.
- **Agent Plane** (`agents/`): AI logic, Plan composition. Must subclass `BaseAgent`.
- **Intelligence Plane** (`memory/`, `models/`, `security/`): Persistence, Model Adapters, Sandbox execution.
- **Integration Plane** (`tools/`): MCP servers, Git, File System Service.

## 2. No Direct Execution / Hard Rules
- `NEVER` write code that makes agents perform direct file operations! All tool operations go through the **TOON Message Bus**.
- **No Agent-to-Agent calls.** Agents `MUST` publish a result back to the bus via `dispatcher.py`.
- Ensure all modules return validated Pydantic objects adhering to schema contracts in `schemas/`.

## 3. Communication Over TOON Bus
Whenever writing inter-module communication, construct a typed envelope using the TOON spec:
```json
{
  "msg_type": "TASK|RESULT|ERROR|MEMORY_WRITE|TOOL_CALL|TOOL_RESULT|REFLECTION",
  "msg_id": "UUID",
  "source": "AGENT_NAME",
  "target": "AGENT_NAME",
  "priority": 2,
  "token_budget": 1840,
  "payload": {},
  "trace_id": "session-trace-id"
}
```

## 4. Implementation Steps
1. Open the relevant file based on the architecture plane.
2. Read the adjacent validation rules (Input Guard, Output Guard).
3. If creating an integration tool, ensure it subclasses `BaseTool` in the `tools/` directory and exposes an MCP manifest.
4. Ensure code uses type hints and fits Python 3.12+ `asyncio` best practices.
5. Create tests in `tests/` before marking completion.
