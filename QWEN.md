# Nexus (formerly FORGE) — Project Context

## Identity
I am building **Nexus** — a token-efficient, graph-learning autonomous coding agent.
I am NOT a coding assistant. I am a systems architect building an orchestration system.

## Architecture Principles
1. **Modular Monolith** — Single system, clearly separated modules, no tight coupling
2. **Orchestration First** — Nexus Engine controls execution, agents don't operate independently
3. **Message-Driven (TOON)** — No direct calls between agents, all through typed message bus
4. **Controlled File Access** — No direct file reads/writes from agents, all through FSM service
5. **Multi-Stage Execution** — Planner → Coder → Reviewer → Debugger (mandatory pipeline)
6. **Trust Nothing** — All model outputs must be validated
7. **Token Discipline** — Minimal context, relevant data only, efficiency by design

## 5-Plane Architecture
| Plane | Components |
|---|---|
| **Interface** | VS Code Extension / Rich TUI / REST API |
| **Orchestration** | Harness Core · Router · Context Manager · Token Ledger |
| **Agent** | Planner · Coder · Reviewer · Debugger · Researcher · Memory Scribe |
| **Intelligence** | Qwen Coder (OpenRouter) · User Graph DB · Vector Memory |
| **Integration** | MCP Servers · File System · Git · Web Search · LSP |

## Sub-Agents
| Agent | Scope | Tools |
|---|---|---|
| **Planner** `[PLAN]` | Task decomposition into DAG | File tree, memory read |
| **Coder** `[CODE]` | Code generation within scoped context | File read/write, LSP, formatter |
| **Reviewer** `[REVW]` | Static + semantic review | File read, AST analyser |
| **Debugger** `[DBUG]` | Error traces, failing tests | File read/write, terminal exec |
| **Researcher** `[RSCH]` | Information gathering | Web search, MCP doc servers |
| **Memory Scribe** `[MEM]` | Graph read/write operations | Graph DB, vector store |

## TOON Message Envelope
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

## Token Budget
| Slot | Limit |
|---|---|
| System persona | 300 tokens |
| User graph summary | 500 tokens |
| Compressed history | 1,200 tokens |
| Tool results | 800 tokens |
| Task instruction | 400 tokens |
| Output buffer | Remainder |

## Context Priority
| Priority | Eviction |
|---|---|
| P1 Critical | Always retained |
| P2 High | Retained until 85% usage |
| P3 Medium | Retained until 70% usage |
| P4 Low | Summarised at 60% usage |
| P5 Archive | Semantic retrieval only |

## Technology Stack
- **Python 3.12+**, asyncio, FastAPI, Pydantic v2
- **Memory**: SQLite (structured) + ChromaDB/FAISS (vector) + NetworkX (graph)
- **Models**: Qwen2.5-Coder-32B (primary), 7B (micro-tasks) via OpenRouter
- **MCP**: Python mcp-server SDK, isolated stdio processes
- **GUI**: Rich (Python TUI) + VS Code Extension (TypeScript)
- **Embeddings**: nomic-embed-text (local via Ollama)
- **Config**: YAML (agents) + TOML (system) + dotenv (secrets)
- **Testing**: pytest + pytest-asyncio, pytest-cov

## Virtual Environment
- Located at: `nxsVenv/`
- Always use: `.\nxsVenv\Scripts\python.exe`

## Roadmap
- **Phase 1** — Core Harness (Router, Context Manager, Token Ledger, Coder, Planner, basic TUI)
- **Phase 2** — Full Agent Suite (Reviewer, Debugger, Researcher, Memory Scribe, TOON validation, vector memory)
- **Phase 3** — Intelligence Layer (Reflection loop, correction clustering, VS Code extension)
- **Phase 4** — Polish & Scale (Web search, LSP, REST API, multi-project graphs)

## Working Rules
- Design before implementing. No shortcuts.
- Separate concerns into distinct files/modules.
- Never collapse multiple responsibilities into one file.
- Every implementation must have clear interfaces and extensibility.
- Read PRD at `documentation/NexusPRD.md` when details are needed.
