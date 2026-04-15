# NexusAlpha — Production-Grade Architecture Blueprint

**Version:** 0.1  
**Date:** April 2026  
**Status:** Foundation Design — Task 0  
**Author:** Nexus Systems Engineer  

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Project Folder Structure](#2-project-folder-structure)
3. [Module Responsibilities](#3-module-responsibilities)
4. [Inter-Module Communication](#4-inter-module-communication)
5. [Execution Flow](#5-execution-flow)
6. [Security Layer Integration](#6-security-layer-integration)
7. [File System Service (FSM) Role](#7-file-system-service-fsm-role)
8. [Coding & Design Conventions](#8-coding--design-conventions)
9. [Extensibility Plan](#9-extensibility-plan)

---

## 1. System Architecture Overview

NexusAlpha is a **modular-monolith, async-first, multi-agent orchestration system** built on five architectural planes. Every design decision is evaluated against three criteria: token efficiency, security boundary, and future microservice split readiness.

### Five Architectural Planes

```
┌──────────────────────────────────────────────────────────────────────┐
│                     NEXUS ALPHA SYSTEM ARCHITECTURE                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  INTERFACE PLANE                              │   │
│  │  Rich TUI  ·  VS Code Extension  ·  FastAPI REST API         │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │               ORCHESTRATION PLANE (Nexus Engine)              │   │
│  │  Engine Core  ·  Router  ·  Context Manager  ·  Token Ledger │   │
│  │  Input Guard  ·  Output Guard  ·  Prompt Compiler            │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │                  AGENT PLANE                                  │   │
│  │  Planner  ·  Coder  ·  Reviewer  ·  Debugger  ·  Researcher  │   │
│  │  Memory Scribe                                                │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │               INTELLIGENCE PLANE                              │   │
│  │  Model Router (32B/7B)  ·  Memory (Graph + Vector)           │   │
│  │  Security Layer (Input/Output/FS/Sandbox/Permissions)         │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │               INTEGRATION PLANE (Tools/MCP)                   │   │
│  │  File System (FSM)  ·  Git  ·  Executor  ·  LSP              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ════════════════════════════════════════════════════════════════   │
│              ALL INTER-PLANE COMMUNICATION → NEXUS BUS (TOON)        │
│  ════════════════════════════════════════════════════════════════   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Plane | Responsibility |
|---|---|---|
| **Nexus Engine** | Orchestration | Controls execution lifecycle, task routing, context window management, token budgeting, input/output validation gates |
| **Nexus Bus (TOON)** | Cross-cutting | Typed message envelope, schema validation, async pub/sub dispatch, trace lifecycle — the ONLY inter-module communication path |
| **Nexus Agents** | Agent | Specialized sub-agents (Planner, Coder, Reviewer, Debugger, Researcher, Memory Scribe) — each with isolated context slice and token budget |
| **Nexus Memory** | Intelligence | Persistent user graph (SQLite + NetworkX), vector store (ChromaDB/FAISS), local embeddings, correction pattern clustering |
| **Nexus Tools** | Integration | MCP-compliant tool servers (FSM, Git, Executor, LSP) — isolated processes communicating via stdio |
| **Security Layer** | Intelligence | Input validation, output validation, file system protection, sandbox execution, agent permission enforcement |
| **Model Router** | Intelligence | Multi-model routing (Qwen2.5-Coder-32B primary, 7B micro-tasks), OpenRouter integration, streaming, early stop |

---

## 2. Project Folder Structure

```
nexus/
│
├── main.py                          # Application entry point (startup, lifecycle, shutdown)
├── config.py                        # Config loader (TOML + YAML + dotenv → merged settings)
│
├── core/                            # 🏗️ NEXUS ENGINE — Orchestration Plane
│   ├── __init__.py
│   ├── engine.py                    # Main orchestrator — session lifecycle, pipeline control
│   ├── router.py                    # Task classifier & dispatcher (routes to agent pipelines)
│   ├── context.py                   # Context Manager — priority-weighted segment management (P1-P5)
│   ├── token_ledger.py              # Token budget tracker (session/agent/user level, warnings at 60/80/95%)
│   ├── input_guard.py               # Pre-dispatch validation — task format, required fields, safety checks
│   └── output_guard.py              # Post-agent validation — schema compliance, output completeness
│
├── bus/                             # 📡 TOON MESSAGE BUS — Communication Plane
│   ├── __init__.py
│   ├── protocol.py                  # TOON envelope, MessageType enum, type definitions
│   ├── registry.py                  # Central schema registry — Pydantic validation at parse time
│   ├── dispatcher.py                # Async pub/sub dispatcher — Queue per subscriber, no direct calls
│   └── tracing.py                   # Session trace management — trace_id lifecycle, log correlation
│
├── agents/                          # 🤖 SUB-AGENT PLANE
│   ├── __init__.py
│   ├── base.py                      # Abstract BaseAgent — handle_task(), validate_result(), get_scope()
│   ├── planner.py                   # [PLAN] Task decomposition → ordered DAG of sub-tasks
│   ├── coder.py                     # [CODE] Scoped code generation within plan slice + user style
│   ├── reviewer.py                  # [REVW] Static + semantic review, AST analysis, diff proposals
│   ├── debugger.py                  # [DBUG] Error trace analysis, hypothesis generation, targeted fixes
│   ├── researcher.py                # [RSCH] Info gathering (docs, APIs, dependencies) — never writes code
│   └── memory_scribe.py             # [MEM] Graph read/write — atomic writes, consistent state
│
├── memory/                          # 🧠 INTELLIGENCE PLANE — Persistence Layer
│   ├── __init__.py
│   ├── graph_store.py               # SQLite + NetworkX — user profile, codebase map, interaction log, corrections
│   ├── vector_store.py              # ChromaDB/FAISS — session snapshots, semantic codebase index
│   ├── embeddings.py                # Local embedding generation (nomic-embed-text via Ollama)
│   ├── models.py                    # Memory data models (Pydantic for structured records)
│   └── update_protocol.py           # 6-step graph update protocol (task complete → extract → write → embed → link → prune)
│
├── tools/                           # 🔧 INTEGRATION PLANE — MCP Server Layer
│   ├── __init__.py
│   ├── base.py                      # Abstract BaseTool — execute(), get_manifest(), validate_input()
│   ├── registry.py                  # Tool registry — dynamic registration via MCP manifest
│   ├── file_system.py               # FSM — controlled file access, diff-based reversible writes, checkpointing
│   ├── git_ops.py                   # Git operations (status, diff, commit, log, branch)
│   ├── executor.py                  # Sandboxed terminal execution (timeout, output capture, kill)
│   └── lsp_client.py                # LSP integration (hover, definition, references, lint, test)
│
├── models/                          # 🔄 MODEL ROUTING LAYER
│   ├── __init__.py
│   ├── router.py                    # Multi-model routing (32B complex, 7B micro-tasks, fallback chain)
│   ├── providers.py                 # Provider configs (OpenRouter adapters, cost tracking)
│   └── session.py                   # Model session management (streaming, early stop, retry logic)
│
├── security/                        # 🛡️ SECURITY LAYER
│   ├── __init__.py
│   ├── validator.py                 # Input/output schema validation (Pydantic-based, pre-dispatch and post-agent)
│   ├── sandbox.py                   # Sandboxed execution environment (resource limits, filesystem restrictions, network isolation)
│   ├── permissions.py               # Agent permission matrix (which tools each agent can call, write scope, read scope)
│   └── secrets.py                   # Secret management (API key handling, credential masking, no-log rules)
│
├── api/                             # 🖥️ INTERFACE PLANE
│   ├── __init__.py
│   ├── fastapi_app.py               # FastAPI REST server — endpoints: POST /task, GET /session/{id}, GET /graph/summary
│   ├── tui.py                       # Rich TUI — terminal panels (file tree, agent status, chat pane, token ledger)
│   └── middleware.py                # Request middleware (auth, logging, rate limiting)
│
├── schemas/                         # 📋 SHARED DATA & MESSAGE SCHEMAS
│   ├── __init__.py
│   ├── messages.py                  # TOON message schemas (Pydantic v2 — TASK, RESULT, ERROR, TOOL_CALL, TOOL_RESULT, MEMORY_WRITE, REFLECTION)
│   ├── agents.py                    # Agent configuration schemas (from YAML manifests)
│   └── tools.py                     # Tool I/O schemas (MCP manifest format)
│
├── utils/                           # 🔨 SHARED UTILITIES
│   ├── __init__.py
│   ├── logging.py                   # Structured logging (trace-aware, agent-tagged, JSON + human-readable)
│   ├── compression.py               # Prompt compression (history summarisation, dead code stripping, semantic dedup)
│   └── validation.py                # Response gater (syntax checks, lint validation, output schema enforcement)
│
├── config/                          # ⚙️ CONFIGURATION FILES
│   ├── agents/                      # Agent YAML manifests
│   │   ├── planner.yaml
│   │   ├── coder.yaml
│   │   ├── reviewer.yaml
│   │   ├── debugger.yaml
│   │   ├── researcher.yaml
│   │   └── memory_scribe.yaml
│   └── system.toml                  # System-wide configuration (model endpoints, memory paths, API keys, security settings)
│
├── tests/                           # 🧪 TEST SUITE
│   ├── conftest.py                  # Shared fixtures (async test loop, mock bus, mock model)
│   ├── test_core/                   # Engine, router, context, token ledger, guards
│   ├── test_bus/                    # Protocol, registry, dispatcher, tracing
│   ├── test_agents/                 # Each agent's logic, handoffs, validation
│   ├── test_memory/                 # Graph store, vector store, embeddings, update protocol
│   ├── test_tools/                  # FSM, git, executor, LSP client
│   ├── test_models/                 # Router, providers, session management
│   └── test_security/               # Validator, sandbox, permissions, secrets
│
└── nxsVenv/                         # 🐍 Virtual environment (pre-existing)
```

### Folder Purpose Summary

| Folder | Purpose | What Lives Inside |
|---|---|---|
| **`core/`** | Orchestration engine — the brain of Nexus | Session lifecycle, task routing, context management, token accounting, input/output validation gates |
| **`bus/`** | Communication backbone — the nervous system | TOON protocol, schema registry, async dispatcher, trace management |
| **`agents/`** | Specialized intelligence — the hands of Nexus | Planner, Coder, Reviewer, Debugger, Researcher, Memory Scribe |
| **`memory/`** | Persistent learning — the long-term memory | User graph, vector store, embeddings, update protocol |
| **`tools/`** | External capability — the senses and limbs | File system, git, terminal execution, LSP integration |
| **`models/`** | Inference layer — the raw intelligence | Model routing, provider adapters, streaming sessions |
| **`security/`** | Protection layer — the immune system | Input/output validation, sandboxing, permissions, secret management |
| **`api/`** | User interface — the face of Nexus | REST endpoints, terminal UI, request middleware |
| **`schemas/`** | Data contracts — the shared language | Pydantic models for messages, agent configs, tool I/O |
| **`utils/`** | Cross-cutting concerns — the utility belt | Logging, compression, response validation |
| **`config/`** | Declarative configuration — the control panel | Agent YAML manifests, system TOML settings |
| **`tests/`** | Quality assurance — the safety net | Per-module test suites with async fixtures |

---

## 3. Module Responsibilities

### `core/` — Nexus Engine (Orchestration Plane)

| Aspect | Detail |
|---|---|
| **Owns** | Execution lifecycle management, task classification and routing, context window scheduling, token budget tracking, pre-dispatch input validation, post-agent output validation, prompt assembly |
| **Does NOT Own** | Agent business logic, message bus internals, tool implementations, model inference, memory storage |
| **Inputs** | User task (from TUI/API), tool results (from bus), agent results (from bus), memory summaries (from memory layer) |
| **Outputs** | Dispatched TOON TASK messages, compressed prompts for model calls, token budget warnings, final responses to interface plane |

**Sub-component breakdown:**

| File | Responsibility |
|---|---|
| `engine.py` | Top-level orchestrator. Creates sessions, manages pipeline lifecycle, coordinates agent handoffs, handles graceful shutdown. Owns the session state machine. |
| `router.py` | Classifies incoming tasks into categories (code-gen, debug, explain, research, memory-write). Selects the appropriate agent pipeline. Does NOT execute the pipeline — only dispatches. |
| `context.py` | Manages the rolling context window with P1-P5 priority segments. Enforces slot budgets (300+500+1200+800+400 tokens). Evicts or summarises segments based on usage thresholds (60%, 70%, 85%). |
| `token_ledger.py` | Tracks per-session, per-agent, per-user token consumption. Issues warnings at 60%, 80%, 95%. Triggers compression passes. Maintains daily/weekly spend graphs. |
| `input_guard.py` | Validates incoming tasks before dispatch. Checks format, required fields, safety constraints (path traversal, injection attempts). Rejects with ERROR before any agent sees it. |
| `output_guard.py` | Validates agent outputs before passing to next stage. Checks schema compliance, completeness, format correctness. Returns ERROR to engine for retry or escalation. |

---

### `bus/` — TOON Message Bus (Communication Plane)

| Aspect | Detail |
|---|---|
| **Owns** | Message envelope definition, schema validation at dispatch, async pub/sub routing, trace_id lifecycle, message ordering guarantees, delivery acknowledgements |
| **Does NOT Own** | Agent behaviour, tool execution, memory operations, model calls, context management |
| **Inputs** | TOON messages from any module (agents, tools, engine, memory) |
| **Outputs** | Validated, schema-checked TOON messages delivered to target subscriber queues |

**Sub-component breakdown:**

| File | Responsibility |
|---|---|
| `protocol.py` | Defines the TOON envelope: msg_id (UUID), msg_type (enum), source, target, priority (1-5), token_budget, payload, trace_id. Provides factory methods and serialization. |
| `registry.py` | Central schema registry. Compiles and caches Pydantic schemas for each msg_type at startup. Validation is a dictionary lookup, not a re-parse. Schema violations return ERROR messages — malformed messages never reach targets. |
| `dispatcher.py` | Async pub/sub dispatcher. Uses asyncio.Queue per subscriber. Agents publish to bus, dispatcher routes to target queues. No direct agent-to-agent calls possible — the dispatcher is the only path. |
| `tracing.py` | Manages trace_id lifecycle. Generates UUID per session, attaches to all messages. Enables post-mortem log correlation. All logs carry trace_id for full session reconstruction. |

---

### `agents/` — Sub-Agent Plane

| Aspect | Detail |
|---|---|
| **Owns** | Agent-specific logic, handoff contract compliance, scoped tool usage within agent permissions, result validation within agent scope |
| **Does NOT Own** | Message bus mechanics, file system access (goes through FSM), model routing (goes through models/), memory storage (goes through Memory Scribe), context management (goes through core/context.py) |
| **Inputs** | TOON TASK messages (from bus, validated by registry) |
| **Outputs** | TOON RESULT or TOON ERROR messages (published back to bus) |

**Agent catalogue:**

| Agent | Responsibility | Tools Allowed | Never Does |
|---|---|---|---|
| **Planner** `[PLAN]` | Decomposes complex tasks into ordered DAG of sub-tasks with estimated token budgets. Pure planning logic. | File tree listing, memory read | Never calls model for code generation |
| **Coder** `[CODE]` | Generates code within scoped context: relevant file(s), plan slice, user graph style. Outputs syntactically valid, linted code only. | File read/write (via FSM), LSP, formatter | Never reads full codebase — only scoped slices |
| **Reviewer** `[REVW]` | Static + semantic review of Coder output. Checks style, correctness, complexity, user graph pattern alignment. Returns structured diff proposal or approval. | File read (via FSM), AST analyser | Never modifies code directly — only proposes changes |
| **Debugger** `[DBUG]` | Receives error traces and failing test output. Hypothesises causes, generates targeted fixes. Uses execution history from memory to avoid repeating known-bad patterns. | File read/write (via FSM), terminal exec | Never guesses — works from actual error traces |
| **Researcher** `[RSCH]` | Handles information-gathering: documentation lookup, dependency analysis, API surface exploration. Feeds structured summaries back to Coder. | Web search, MCP doc servers | Never writes code — only provides information |
| **Memory Scribe** `[MEM]` | Dedicated agent for all read/write operations to User Graph and session memory. Ensures atomic writes and consistent graph state. | Graph DB, vector store | Never performs task logic — only memory I/O |

**Base contract (`base.py`):**
- Every agent extends `BaseAgent` with: `async handle_task(message)`, `validate_result(output)`, `get_scope()`, `get_token_budget()`
- Every agent publishes results back to bus — never returns directly
- Every agent receives only its context slice — no full session history

---

### `memory/` — Intelligence Plane (Persistence Layer)

| Aspect | Detail |
|---|---|
| **Owns** | User graph persistence (SQLite + NetworkX), vector embeddings (ChromaDB/FAISS), local embedding generation, session snapshot management, correction pattern clustering, graph update protocol execution |
| **Does NOT Own** | Agent logic, model inference, tool execution, context window management (that's core/context.py — this layer only stores and retrieves) |
| **Inputs** | Graph write requests (from Memory Scribe via bus), semantic search queries (from context manager), entity extraction results (from agents) |
| **Outputs** | Structured graph data (user profile, codebase map), vector search results (similar sessions, correction patterns), compressed session summaries |

**Dual-store strategy:**

| Store | Technology | Purpose |
|---|---|---|
| **Relational** | SQLite + NetworkX | User profile, interaction log, error dictionary, codebase map, correction records |
| **Vector** | ChromaDB or FAISS | Session snapshots, correction pattern embeddings, semantic codebase index |
| **Embeddings** | nomic-embed-text (local via Ollama) | Zero external token spend for embedding generation |

**Update protocol (6 steps, executed by Memory Scribe):**
1. Task completes → Memory Scribe dispatched via bus
2. Scribe extracts: entities (files, functions, errors), outcome (accepted/rejected), user corrections
3. Structured diff written to SQLite interaction log with timestamp and session_id
4. Semantic embedding of task + outcome written to vector store
5. Graph edges updated: file nodes linked to task, error nodes linked to fix patterns
6. Stale nodes (>90 days, no reference) flagged for pruning; user prompted before deletion

---

### `tools/` — Integration Plane (MCP Server Layer)

| Aspect | Detail |
|---|---|
| **Owns** | Tool implementations, MCP protocol compliance, sandboxed execution, tool input validation, tool output formatting, dynamic tool registration via MCP manifest |
| **Does NOT Own** | Agent logic, message dispatch, model routing, memory storage, context management |
| **Inputs** | TOOL_CALL TOON messages (from bus via dispatcher), tool parameters (validated against tool schema) |
| **Outputs** | TOOL_RESULT TOON messages (published back to bus), tool error reports |

**Tool catalogue:**

| Tool | Responsibility | MCP Server |
|---|---|---|
| **File System (FSM)** | Controlled file access — read, write (diff-based), list directory, search files, apply diff. All writes are reversible with checkpoints. | `nexus-fs-server` |
| **Git Operations** | Git status, diff, commit, log, branch management. Reads from and writes to git state. | `nexus-git-server` |
| **Executor** | Sandboxed terminal execution — run commands with timeout, capture output, kill processes. Resource-limited. | `nexus-exec-server` |
| **LSP Client** | Language Server Protocol integration — hover, definition, references, run lint, run tests. Deep code intelligence. | `nexus-lsp-server` |

**Design principles:**
- Each tool extends `BaseTool` with: `async execute(params)`, `get_manifest()`, `validate_input(params)`
- Tools are dynamically registered via MCP manifest format
- Tools run as isolated processes communicating via stdio (per MCP spec)
- Tools never publish TOON messages directly — they publish TOOL_RESULT via bus dispatcher

---

### `models/` — Model Routing Layer

| Aspect | Detail |
|---|---|
| **Owns** | Model selection logic, API communication with providers (OpenRouter), streaming response handling, early stop signals, retry/fallback chains, cost tracking |
| **Does NOT Own** | Agent logic, context management (that's core/context.py), prompt assembly (that's engine), tool execution |
| **Inputs** | Compiled prompts (from Prompt Compiler in core/context.py), model selection hints (task complexity indicator) |
| **Outputs** | Raw model responses (streamed token-by-token or complete), error reports on API failure |

**Routing strategy:**

| Task Type | Model | Rationale |
|---|---|---|
| Complex (multi-file, planning, review) | Qwen2.5-Coder-32B-Instruct | Maximum reasoning capability |
| Micro-task (single-function edit, quick lookup) | Qwen2.5-Coder-7B-Instruct | Faster, cheaper, sufficient for scope |
| Fallback | Next available model via OpenRouter | Resilience against provider failure |

---

### `security/` — Security Layer

| Aspect | Detail |
|---|---|
| **Owns** | Input validation (pre-dispatch), output validation (post-agent), file system protection (path sanitization, scope enforcement), sandboxed execution (resource limits, network isolation), agent permission matrix enforcement, secret management (credential masking, no-log rules) |
| **Does NOT Own** | Agent logic, message bus mechanics, model routing, memory storage |
| **Inputs** | Incoming tasks (for input validation), agent outputs (for output validation), tool call requests (for permission checks), file paths (for scope enforcement) |
| **Outputs** | Validation pass/fail decisions, sandbox execution results, permission allow/deny decisions, masked secrets |

**Sub-component breakdown:**

| File | Responsibility |
|---|---|
| `validator.py` | Pydantic-based input/output schema validation. Runs pre-dispatch (input_guard) and post-agent (output_guard). Rejects malformed data before it propagates. |
| `sandbox.py` | Sandboxed execution environment. Resource limits (CPU, memory, time), filesystem restrictions (only allowed paths), network isolation (no outbound calls for exec tool). |
| `permissions.py` | Agent permission matrix. Defines which tools each agent can call, read/write scope, allowed file patterns. Enforced at tool call dispatch time. |
| `secrets.py` | Secret management. API key handling (never logged), credential masking (redacted in tool results), no-log rules (sensitive data excluded from traces). |

---

### `schemas/` — Shared Data & Message Schemas

| Aspect | Detail |
|---|---|
| **Owns** | Pydantic v2 schema definitions for all inter-module data contracts. TOON message schemas, agent configuration schemas, tool I/O schemas. |
| **Does NOT Own** | Runtime validation logic (that's bus/registry.py and security/validator.py), business logic |
| **Inputs** | — (passive module — provides schema classes) |
| **Outputs** | Schema classes consumed by bus/registry.py, security/validator.py, tools/registry.py, agents/base.py |

---

### `api/` — Interface Plane

| Aspect | Detail |
|---|---|
| **Owns** | User-facing interfaces (Rich TUI, FastAPI REST API, VS Code extension backend), request routing to engine, response streaming to user, session status display |
| **Does NOT Own** | Core engine logic, agent behaviour, tool execution, model inference |
| **Inputs** | User requests (CLI commands, HTTP POST, terminal input) |
| **Outputs** | Rendered responses (TUI panels, HTTP JSON, streamed text), status updates, error messages |

---

### `utils/` — Shared Utilities

| Aspect | Detail |
|---|---|
| **Owns** | Cross-cutting concerns only: structured logging, prompt compression, response validation helpers |
| **Does NOT Own** | Any business logic, agent logic, tool implementations, schema definitions |
| **Inputs** | — (library module — functions called by other modules) |
| **Outputs** | Log entries, compressed text, validation results |

---

## 4. Inter-Module Communication

### Hard Rule: Nexus Bus (TOON) is the ONLY Communication Medium Between Modules

No module calls another module directly. All data flows through typed TOON messages published to and consumed from the bus.

### Message Envelope

```json
{
  "msg_type": "TASK | RESULT | ERROR | TOOL_CALL | TOOL_RESULT | MEMORY_WRITE | REFLECTION",
  "msg_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source": "ROUTER | PLANNER | CODER | REVIEWER | DEBUGGER | RESEARCHER | MEMORY_SCRIBE | ENGINE | FSM | EXECUTOR | GIT | LSP",
  "target": "PLANNER | CODER | REVIEWER | DEBUGGER | RESEARCHER | MEMORY_SCRIBE | ENGINE | FSM | EXECUTOR | GIT | LSP",
  "priority": 1,
  "token_budget": 2400,
  "payload": { "... typed body per msg_type schema ..." },
  "trace_id": "session-trace-uuid"
}
```

### Communication Flows

#### Router → Agents

```
┌──────────┐     TOON TASK       ┌──────────┐     TOON TASK      ┌──────────┐
│  Router   │ ──────────────────► │   Bus    │ ─────────────────► │ Planner  │
│           │                     │          │                    │          │
│ Classifies│                     │ Validates│                    │ Receives │
│ task type │                     │ schema   │                    │ TASK     │
│           │                     │ routes   │                    │          │
│           │ ◄────────────────── │          │ ◄───────────────── │          │
└──────────┘     TOON RESULT      └──────────┘     TOON RESULT    └──────────┘
                       │                                    │
                       ▼                                    ▼
               (to Engine)                        (to next agent in pipeline)
```

1. Router classifies user task → publishes TOON TASK with `target=PLANNER`
2. Bus validates schema against registry → routes to Planner's subscription queue
3. Planner processes → publishes TOON RESULT with `target=CODER` (via bus)
4. Bus validates → routes to Coder's queue
5. Chain continues until pipeline completes → final RESULT to Engine

#### Agents → Tools

```
┌──────────┐    TOON TOOL_CALL    ┌──────────┐    TOOL_REQUEST   ┌──────────┐
│  Agent   │ ───────────────────► │   Bus    │ ────────────────► │   FSM    │
│          │                      │          │                   │          │
│ Needs    │                      │ Validates│                   │ Executes │
│ file     │                      │ checks   │                   │ file op  │
│ read     │                      │ permission│                  │          │
│          │ ◄─────────────────── │          │ ◄──────────────── │          │
└──────────┘    TOON_TOOL_RESULT  └──────────┘    TOOL_RESULT    └──────────┘
```

1. Agent needs file → publishes TOON TOOL_CALL with `tool="file_system", action="read"`
2. Bus validates schema → checks agent permissions (security/permissions.py) → routes to FSM
3. FSM executes file read → publishes TOOL_RESULT back to bus
4. Bus routes TOOL_RESULT to agent's subscription queue
5. Agent receives file content in payload

**Critical:** Agent never reads file directly. Agent never calls FSM directly. Bus mediates everything.

#### Tools → Memory

```
┌──────────┐   TOON_MEMORY_WRITE  ┌──────────┐   GRAPH_WRITE   ┌──────────────┐
│  Agent   │ ───────────────────► │   Bus    │ ──────────────► │   Memory     │
│  (any)   │                      │          │                 │   Scribe     │
│          │                      │ Validates│                 │              │
│ Task     │                      │ routes   │                 │ Atomic write │
│ complete │                      │          │                 │ to graph     │
│          │ ◄─────────────────── │          │ ◄────────────── │              │
└──────────┘   TOON RESULT        └──────────┘   WRITE_CONFIRM └──────────────┘
```

1. Task completes → agent publishes TOON MEMORY_WRITE with extracted entities, outcome
2. Bus validates → routes to Memory Scribe
3. Memory Scribe executes 6-step update protocol → publishes WRITE_CONFIRM
4. Bus routes confirmation back to agent

### Permission Enforcement at Tool Call Time

```
Agent publishes TOOL_CALL → Bus intercepts → security/permissions.py consulted:
  - Is this agent allowed to call this tool? (permission matrix)
  - Is the requested file within agent's read/write scope? (path matching)
  - Is the operation type allowed? (read vs write vs delete)

If PASS → route to tool
If DENY → return TOON ERROR to agent with "permission denied"
```

---

## 5. Execution Flow

### Full Pipeline: User Task → Response

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION PIPELINE                               │
│                                                                         │
│  ┌──────────┐                                                           │
│  │  User    │  Submits task via TUI or API                              │
│  │  Task    │  Example: "Add authentication middleware to src/auth.py"  │
│  └────┬─────┘                                                           │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────────┐                                                   │
│  │   INPUT GUARD    │  (core/input_guard.py + security/validator.py)    │
│  │                  │  Validates: task format, required fields,          │
│  │                  │  path traversal attempts, injection patterns       │
│  │                  │  FAIL → returns ERROR to user                     │
│  └────────┬─────────┘                                                   │
│           │ PASS                                                        │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │    ENGINE        │  (core/engine.py)                                 │
│  │                  │  Creates session, generates trace_id              │
│  │                  │  Initializes token ledger                         │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │    ROUTER        │  (core/router.py)                                 │
│  │                  │  Classifies task: "code-gen" → Planner pipeline   │
│  │                  │  Publishes TOON TASK to bus (target=PLANNER)      │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │    PLANNER       │  (agents/planner.py)                              │
│  │                  │  Reads file tree (via FSM tool call)              │
│  │                  │  Reads relevant memory (via Memory Scribe)        │
│  │                  │  Decomposes task into DAG:                        │
│  │                  │    1. Read existing src/auth.py                   │
│  │                  │    2. Design middleware structure                 │
│  │                  │    3. Generate code                               │
│  │                  │    4. Run lint                                    │
│  │                  │  Publishes TOON RESULT (target=CODER)             │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │  CONTEXT MGR     │  (core/context.py)                                │
│  │                  │  Assembles prompt for Coder:                      │
│  │                  │    P1: System persona (300t)                      │
│  │                  │    P1: Current task instruction (400t)            │
│  │                  │    P1: Plan slice from Planner                    │
│  │                  │    P2: User graph summary (500t)                  │
│  │                  │    P2: Relevant correction patterns               │
│  │                  │    P3: Compressed history (1200t)                 │
│  │                  │    P3: File content from FSM (800t)               │
│  │                  │  Validates token budget per slot                  │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │  MODEL ROUTER    │  (models/router.py)                               │
│  │                  │  Selects model: 32B (complex task)                │
│  │                  │  Streams response token-by-token                  │
│  │                  │  Early stop if structure complete                 │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │    CODER         │  (agents/coder.py)                                │
│  │                  │  Receives model output                            │
│  │                  │  Validates: syntax check, lint pass               │
│  │                  │  If FAIL → retry (max 2x)                         │
│  │                  │  If PASS → publishes TOON RESULT (target=REVIEWER)│
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │   REVIEWER       │  (agents/reviewer.py)                             │
│  │                  │  Static analysis of Coder output                  │
│  │                  │  AST check, style compliance                      │
│  │                  │  User graph pattern alignment                     │
│  │                  │  If APPROVED → publishes TOON RESULT (target=FSM) │
│  │                  │  If REJECTED → publishes TOON RESULT (target=DBUG)│
│  └────────┬─────────┘                                                   │
│           │                                                             │
│     ┌─────┴─────┐                                                       │
│     ▼           ▼                                                       │
│  APPROVED   REJECTED                                                    │
│     │           │                                                       │
│     ▼           ▼                                                       │
│  ┌──────────┐ ┌──────────┐                                             │
│  │   FSM    │ │ DEBUGGER │                                             │
│  │ Applies  │ │ Analyzes │                                             │
│  │ diff     │ │ error    │                                             │
│  │ with     │ │ trace    │                                             │
│  │ checkpoint│ │ Fixes    │                                             │
│  │          │ │ → Coder  │                                             │
│  └────┬─────┘ └──────────┘                                             │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────────┐                                                   │
│  │  OUTPUT GUARD    │  (core/output_guard.py + security/validator.py)   │
│  │                  │  Validates: output schema compliance,             │
│  │                  │  completeness, format correctness                 │
│  │                  │  FAIL → retry or escalate                         │
│  └────────┬─────────┘                                                   │
│           │ PASS                                                        │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │   MEMORY SCRIBE  │  (agents/memory_scribe.py)                        │
│  │                  │  6-step update protocol:                          │
│  │                  │    Extract entities, outcome, corrections          │
│  │                  │    Write to SQLite interaction log                 │
│  │                  │    Embed in vector store                          │
│  │                  │    Update graph edges                             │
│  │                  │    Flag stale nodes for pruning                   │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │    RESPONSE      │  Streams result to TUI / API                      │
│  └──────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Validation Points in Pipeline

| Stage | What's Validated | Where | On Failure |
|---|---|---|---|
| **Input Guard** | Task format, required fields, injection patterns | `core/input_guard.py` + `security/validator.py` | ERROR returned to user |
| **TOON Dispatch** | Schema compliance, type correctness | `bus/registry.py` | ERROR returned to source agent |
| **Token Budget** | Per-slot limits enforced (300+500+1200+800+400) | `core/context.py` + `core/token_ledger.py` | Compression triggered, or ERROR if still exceeded |
| **Model Output** | Syntax correctness, lint pass | `utils/validation.py` | Retry max 2x, then ERROR |
| **Tool Call** | Permission matrix, input schema | `security/permissions.py` + `tools/base.py` | ERROR returned to agent |
| **File Write** | Diff validity, checkpoint exists for rollback | `tools/file_system.py` | Rollback to last checkpoint, ERROR returned |
| **Output Guard** | Output schema compliance, completeness | `core/output_guard.py` + `security/validator.py` | Retry or escalate to Debugger |

---

## 6. Security Layer Integration

The Security Layer is not an afterthought — it is woven into every stage of the execution pipeline.

### Security Components and Enforcement Points

```
User Task ───────────────────────────────────────────────────────────┐
    │                                                                │
    ▼                                                                │
┌──────────────┐                                                     │
│ INPUT GUARD  │ ◄── security/validator.py     [INPUT VALIDATION]   │
│              │     Checks: schema, injection, path traversal       │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│   ROUTER     │                                                     │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│   AGENT      │                                                     │
│   (Coder)    │                                                     │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│ TOOL CALL    │ ◄── security/permissions.py   [AGENT PERMISSIONS]  │
│ dispatch     │     Checks: allowed tools, file scope, op type      │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│    FSM       │ ◄── security/sandbox.py       [FILE SYSTEM PROTECT] │
│  (write)     │     Checks: path sanitization, scope enforcement    │
│              │     Creates: checkpoint for rollback                │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│  EXECUTOR    │ ◄── security/sandbox.py       [SANDBOX EXECUTION]  │
│  (terminal)  │     Enforces: CPU limit, memory limit, time limit   │
│              │              network isolation, path restrictions    │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│OUTPUT GUARD  │ ◄── security/validator.py     [OUTPUT VALIDATION]  │
│              │     Checks: schema compliance, credential masking   │
└──────┬───────┘                                                     │
       │                                                             │
       ▼                                                             │
┌──────────────┐                                                     │
│  RESPONSE    │ ◄── security/secrets.py       [SECRET MANAGEMENT]  │
│              │     Ensures: no API keys in output, no-log rules    │
└──────────────┘                                                     │
                                                                     │
All secrets/credentials masked throughout entire pipeline ◄──────────┘
```

### Security Detail

#### Input Validation (`security/validator.py` + `core/input_guard.py`)

**When:** Before any task is dispatched to agents.

**What's checked:**
- Task format compliance (Pydantic schema validation)
- Required fields present
- Path traversal attempts (`../`, absolute paths in user input)
- Injection patterns (SQL, command injection, template injection)
- File path scope (only allowed directories)

**On failure:** Task rejected with ERROR message returned to user. No agent sees the task.

---

#### Output Validation (`security/validator.py` + `core/output_guard.py`)

**When:** After any agent produces output, before it reaches the next stage.

**What's checked:**
- Output schema compliance (Pydantic validation)
- Completeness (no truncated code blocks, no missing sections)
- Format correctness (valid JSON where expected, valid diff where expected)
- Credential leakage (API keys, tokens, passwords masked or redacted)

**On failure:** Output rejected. Engine retries (max 2x) or escalates to Debugger.

---

#### File System Protection (`security/sandbox.py` + `tools/file_system.py`)

**When:** On every file read and write operation.

**What's enforced:**
- Path sanitization (resolve symlinks, normalize, reject `..` escapes)
- Scope enforcement (agents only access allowed directories)
- Write restrictions (some agents can only read, not write)
- Diff-based writes only (no full file overwrites)
- Checkpoint creation before every write (enables rollback)
- Read size limits (agents get scoped slices, not entire files)

**On failure:** Operation denied, ERROR returned to agent.

---

#### Sandbox Execution (`security/sandbox.py` + `tools/executor.py`)

**When:** On every terminal command execution via the Executor tool.

**What's enforced:**
- CPU limit (max N cores)
- Memory limit (max N MB)
- Time limit (max N seconds per command)
- Network isolation (no outbound network calls from sandbox)
- Filesystem restrictions (only allowed paths accessible)
- Process group isolation (kill entire group on timeout)

**On failure:** Process killed, timeout error returned, agent notified.

---

#### Agent Permissions (`security/permissions.py`)

**When:** On every tool call dispatch from any agent.

**Permission matrix:**

| Agent | File Read | File Write | Terminal Exec | LSP | Web Search | Memory Read | Memory Write |
|---|---|---|---|---|---|---|---|
| **Planner** | ✓ (tree only) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **Coder** | ✓ (scoped) | ✓ (via FSM) | ✗ | ✓ | ✗ | ✓ | ✗ |
| **Reviewer** | ✓ (scoped) | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ |
| **Debugger** | ✓ (scoped) | ✓ (via FSM) | ✓ (sandboxed) | ✓ | ✗ | ✓ | ✗ |
| **Researcher** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| **Memory Scribe** | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |

**On denial:** Tool call rejected with "permission denied" ERROR. Agent must work within its scope.

---

## 7. File System Service (FSM) Role

### Why Direct File Access is Forbidden

Agents **never** read or write files directly. This is a hard architectural rule for the following reasons:

1. **Security:** Agents are model-driven — their outputs cannot be trusted with unrestricted filesystem access. A compromised or hallucinated agent could delete files, inject malicious code, or exfiltrate data.

2. **Observability:** Every file operation goes through the bus as a typed message. This means every read, every write, every diff application is logged, traced, and auditable.

3. **Reversibility:** All writes are diff-based and checkpointed. If an agent writes bad code, the FSM can rollback to the last known-good state. Direct file writes have no safety net.

4. **Token Efficiency:** The FSM serves only the relevant file slices to agents — not entire files. This reduces token consumption by 30-45% (per PRD spec).

5. **Consistency:** The FSM is the single source of truth for file state. No race conditions between agents trying to read/write simultaneously.

### How FSM Interacts with Agents

```
┌──────────────────────────────────────────────────────────────┐
│                    FILE SYSTEM SERVICE (FSM)                  │
│                                                              │
│  Agent ──TOOL_CALL──►  Bus  ──dispatch──►  FSM               │
│                                                              │
│  FSM receives:                                               │
│    - action: "read" | "write" | "apply_diff" | "list" |      │
│              "search"                                        │
│    - path: "src/auth.py"                                     │
│    - params: { ... action-specific parameters ... }          │
│                                                              │
│  FSM validates:                                              │
│    1. Path is within allowed scope                           │
│    2. Action is allowed for calling agent                    │
│    3. Diff is valid (for write/apply_diff)                   │
│                                                              │
│  FSM executes:                                               │
│    - For READ: returns file content (scoped slice)           │
│    - For WRITE: creates checkpoint → applies diff → confirms │
│    - For LIST: returns directory tree                        │
│    - For SEARCH: returns matching file paths                 │
│                                                              │
│  FSM responds:                                               │
│    TOOL_RESULT published back to bus → routed to agent       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### How Diff-Based Updates Work

1. **Agent generates code** → produces a unified diff (not a full file replacement)
2. **Agent publishes TOOL_CALL** with `action="apply_diff"`, `path="src/auth.py"`, `diff="..."`
3. **FSM validates diff**:
   - Checks diff format is valid unified diff
   - Verifies the diff applies cleanly to current file state
   - Confirms the diff scope is within allowed paths
4. **FSM creates checkpoint**: current file state saved to rollback buffer
5. **FSM applies diff**: patch applied to file
6. **FSM verifies**: reads back file, confirms syntax validity (optional lint)
7. **FSM publishes TOOL_RESULT**: `{ "status": "success", "checkpoint_id": "abc123" }`
8. **On failure**: FSM rolls back to checkpoint, publishes TOOL_RESULT with error details

**Rollback flow:**
- If Reviewer rejects the change → Engine publishes TOOL_CALL with `action="rollback"`, `checkpoint_id="abc123"`
- FSM restores file from checkpoint buffer → publishes TOOL_RESULT confirming rollback

---

## 8. Coding & Design Conventions

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Modules/Packages | `snake_case` | `token_ledger.py`, `memory_scribe.py`, `file_system.py` |
| Classes | `PascalCase` | `TOONMessage`, `ContextManager`, `FileSystemService`, `BaseAgent` |
| Functions/Methods | `snake_case` | `handle_task()`, `apply_diff()`, `publish()`, `validate_schema()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_TOKEN_BUDGET`, `PRIORITY_CRITICAL`, `RETRY_LIMIT` |
| TOON Message Types | `UPPER_SNAKE_CASE` enum values | `MessageType.TASK`, `MessageType.TOOL_CALL`, `MessageType.MEMORY_WRITE` |
| Agent Identifiers | `UPPER_SNAKE_CASE` strings | `"PLANNER"`, `"CODER"`, `"REVIEWER"`, `"DEBUGGER"` |
| Tool Identifiers | `UPPER_SNAKE_CASE` strings | `"FILE_SYSTEM"`, `"GIT_OPS"`, `"EXECUTOR"`, `"LSP_CLIENT"` |
| Config Files | `kebab-case` | `system.toml`, `memory-scribe.yaml`, `planner.yaml` |
| Test Files | `test_<module>.py` | `test_dispatcher.py`, `test_context.py`, `test_fsm.py` |
| Variables | `snake_case` | `trace_id`, `token_budget`, `msg_type` |
| Private Members | Leading underscore | `_validate()`, `_compress_history()` |

### Async-First Design Rules

1. **Zero synchronous I/O** in the harness. Every file read, DB query, tool call, and API request is `async`/`await`.
2. **No blocking calls**. Use `asyncio.to_thread()` only for CPU-bound operations that cannot be async (e.g., AST parsing).
3. **All agents are async consumers**. Each agent runs as an `asyncio.Task` consuming from its subscription queue.
4. **Dispatcher is fully async**. Uses `asyncio.Queue` per subscriber. Dispatch uses `asyncio.gather()` for parallel routing.
5. **Model calls stream asynchronously**. Token-by-token streaming to TUI — not batched responses.
6. **Database operations are async**. SQLite via `aiosqlite`, ChromaDB via async wrapper.
7. **Tool execution is async**. Each tool runs in its own async context with timeout enforcement.

### Logging & Traceability Strategy

**Log format:**
```
[timestamp] [trace_id] [agent] [level] [module] message
```

**Example:**
```
2026-04-14T10:23:45.123Z trace-a1b2c3d4 PLANNER INFO core.router Task classified as code-gen
2026-04-14T10:23:45.456Z trace-a1b2c3d4 CODER DEBUG bus.dispatcher TOON TASK dispatched to CODER (budget: 2400)
2026-04-14T10:23:46.789Z trace-a1b2c3d4 ENGINE WARN core.token_ledger Token budget at 80% for session trace-a1b2c3d4
```

**Rules:**
- Every session gets a `trace_id` (UUIDv4) — all messages in that session carry it
- Structured logging via `utils/logging.py` — JSON format for machine parsing, human-readable for TUI
- Log levels: `DEBUG` (token accounting, context evictions), `INFO` (task dispatch, agent handoffs), `WARN` (budget thresholds, retry attempts), `ERROR` (failures), `CRITICAL` (system-level failures)
- Trace correlation: all logs for a trace_id can be retrieved for post-mortem analysis
- Token ledger doubles as audit log — every token spend recorded with agent, task, and timestamp
- **Secrets never logged**: `security/secrets.py` enforces no-log rules on API keys, credentials, tokens

### Error Handling Approach

| Error Type | Handling Strategy | Recovery |
|---|---|---|
| **Schema validation failure** | Return `TOON ERROR` to source agent, log with trace_id | None — source agent must fix |
| **Agent failure** | Return `TOON ERROR` to engine, engine decides: retry (max 2x), escalate to Debugger, or surface to user | Retry or escalate |
| **Tool failure** | Return `TOOL_RESULT` with error payload, agent handles based on scope | Agent-specific |
| **Model API failure** | Retry with fallback model (32B → 7B), then surface error if both fail | Fallback chain |
| **File system failure** | Rollback to last checkpoint (FSM maintains checkpoint stack), return error | Automatic rollback |
| **Token budget exceeded** | Trigger compression pass, if still exceeded → return `TOON ERROR` with budget warning | Compression or terminate |
| **Permission denied** | Return `TOON ERROR` to agent, log security event | None — agent violated scope |
| **Sandbox violation** | Kill process, return timeout error, log security event | None — sandbox enforced |

**Error propagation rule:** Errors always travel through the bus as typed `TOON ERROR` messages. No exceptions leak across module boundaries. Each module catches its own exceptions and converts them to structured ERROR messages.

---

## 9. Extensibility Plan

### Adding New Agents

**Process (zero code change to existing modules):**

1. Create `agents/new_agent.py` — extends `BaseAgent`, implements `handle_task()`, `validate_result()`, `get_scope()`
2. Create `config/agents/new_agent.yaml`:
   ```yaml
   name: "new_agent"
   trigger_patterns: ["^analyze.*", "^profile.*"]
   system_prompt_path: "prompts/new_agent.txt"
   max_tokens: 3000
   allowed_tools: ["file_system", "lsp_client"]
   handoff_to: "CODER"
   ```
3. Engine auto-discovers at startup from `config/agents/` directory
4. Router registers trigger patterns automatically
5. Permission matrix updated in `security/permissions.py`

**No changes required to:** bus, core engine, other agents, tools, memory.

---

### Adding New Tools (MCP Servers)

**Process (zero code change to existing modules):**

1. Create `tools/new_tool.py` — extends `BaseTool`, implements `execute()`, `get_manifest()`, `validate_input()`
2. Register in `tools/registry.py` or auto-discover from config
3. Tool manifest exposed to model via MCP protocol automatically
4. Update `security/permissions.py` to grant access to agents that need it

**No changes required to:** agents, bus, core engine, memory.

**Future MCP servers:** Each tool is an isolated process communicating via stdio. Adding a new MCP server is adding a new process — no core changes needed.

---

### Swapping Models

**Process (config change only):**

1. Update `config/system.toml`:
   ```toml
   [model]
   primary = "qwen2.5-coder-32b-instruct"
   fallback = "qwen2.5-coder-7b-instruct"
   provider = "openrouter"
   ```
2. `models/providers.py` handles provider-specific API adapters
3. `models/router.py` handles routing logic (32B vs 7B thresholds)

**No changes required to:** agents, bus, tools, memory, core engine.

Agents receive compiled prompts and return raw text — they don't know which model is behind them.

---

### Scaling to Microservices

The modular monolith is designed for a clean split with **zero architectural rewrite**:

| Current Module | Future Service | Communication Protocol |
|---|---|---|
| `core/` | Orchestrator Service | gRPC to agent services |
| `bus/` | Message Broker (NATS/Redis Streams) | Replaces in-memory dispatcher |
| `agents/` | Agent Services (one per agent type, independently deployable) | Consume from message broker |
| `memory/` | Memory Service | REST API for graph/vector queries |
| `tools/` | MCP Server Processes (already isolated) | stdio (already MCP compliant) |
| `models/` | Model Gateway (proxy service) | REST to OpenRouter or other providers |
| `security/` | Policy Service (centralized permissions) | gRPC for permission checks |

**Why the split is clean:**

- All inter-agent communication already goes through the bus → replace with NATS/Redis, agents unchanged
- Tools already isolated processes (MCP stdio protocol) → no change needed
- Memory already a separate layer → becomes a REST service with stable API
- Agents have defined handoff contracts → becomes service-to-service API calls
- Security already centralized → becomes a gRPC policy service

**What changes during the split:**
- `bus/dispatcher.py` → replaced with NATS client
- Config files updated with service endpoints
- Deployment manifests (Docker, Kubernetes)

**What does NOT change:**
- Agent logic
- Tool implementations
- Memory store implementations
- Model routing logic
- Schema definitions

The modular monolith is a **deployment optimization**, not an architectural limitation. Every module boundary is already a service boundary.

---

## Appendix: Design Decision Rationale

| Decision | Rationale |
|---|---|
| **Modular monolith first** | Faster iteration, simpler testing, cleaner debugging. Split to microservices when deployment scale demands it. |
| **TOON over plain JSON** | Explicit type annotations and schema validation at parse time eliminate runtime errors from malformed messages. Worth the added complexity. |
| **FSM as single file access path** | Security, observability, reversibility, token efficiency. The performance cost of indirection is negligible compared to model API latency. |
| **Dual-store memory (SQLite + Vector)** | Relational data needs structured queries (SQLite). Semantic data needs similarity search (Vector). Neither alone serves both purposes well. |
| **Local embeddings (Ollama)** | Zero external token spend. Embedding generation is not a model reasoning task — a small local model suffices. |
| **Async throughout** | Model calls are the latency bottleneck. Everything else should be non-blocking to overlap with model wait time. |
| **YAML agent configs** | Zero-code agent addition. The manifest is the contract between the agent and the system. |
| **Permission matrix per agent** | Defense in depth. Even if an agent is compromised, it can only access its allowed tools and scope. |
| **Checkpoint-based rollback** | Every write is reversible. No data loss from bad agent output. Simpler than version control for this use case. |

---

*End of Architecture Blueprint — NexusAlpha v0.1*
