# Nexus Alpha — Autonomous Coding Agent Design Specification
**Version 2.1 · April 2026**

A token-efficient, ultra-low latency, graph-learning autonomous coding agent. Designed to allow free or low-cost LLMs to outperform state-of-the-art (SOTA) models within a rigorously calibrated agentic harness.

## Core Design Principles
- **Ultra-Low Latency & Scalable I/O** — Async-first execution using WebSockets to prevent message queue bloat, ensuring real-time responsiveness and the lowest possible time-to-first-token.
- **SOTA Performance via Free Models** — Rigorously calibrated orchestration maximizing the capability of free/lightweight models (e.g., Qwen 7B/32B, Llama 3) through efficient prompt caching, aggressive context truncation, and heavily structured scaffolding.
- **Persistent User Graph Growth** — The agent learns the user's specific behaviors, styles, and "gotchas" continuously—saying *no* to bad architectural practices and automatically applying individual preferential settings.
- **Token Sovereignty** — Strict budget checks per context slot, maximizing useful signals over noise based on hard P1-P5 priority levels.
- **Harness Zero Waste** — Pre-validated JSON and typed TOON messaging to negate hallucination retries.
- **Security & Quality First** — Multi-layered input/output schema validators, sandboxing, and mandatory static analysis to guarantee production-safe execution.

## System Capabilities
Nexus is not just a chatbot, it is a fully capable orchestration engine designed for:
- **Zero-to-One Implementation & Refactoring:** Complete end-to-end multi-file generation and confident refactoring.
- **Ad-hoc Knowledge Scraping:** Directly discovering, ingesting, and reasoning over missing technical documentation.
- **Autonomous Debugging & Self-Correction:** Reading stack traces, hypothesizing issues, writing failing tests, and fixing code independently.
- **User Graph Adaptation:** Memorizing user preferences actively, recalling edge-cases selectively across separate sessions.

## 5-Plane Architecture Layer
| Plane | Components |
|---|---|
| **Interface** | VS Code Extension / Rich TUI / **Web Framework** / **Mobile Remote Control** / REST API |
| **Orchestration** | Harness Core · Router · Context Manager · Token Ledger · Input/Output Guards |
| **Agent** | Planner · Coder · Reviewer · Debugger · Researcher · Memory Scribe |
| **Intelligence** | Model Router · *User Graph DB* · Vector Memory |
| **Integration** | MCP Servers · File System (FSM) · Git · Boxed Executor (Terminal) · LSP |

## Communication: TOON Bus & WebSockets
To resolve message queue bloating and high-overhead REST polling in a real-time autonomous system, Nexus implements **WebSocket-driven I/O**.
- **Internal Routing:** Agents use typed TOON envelopes pushed over an Async Pub/Sub dispatcher (`bus/`).
- **External Real-time I/O:** Interface clients (TUI, VS Code, Web UI, Mobile App) connect via WebSockets. The orchestrator pushes token-stream diffs, progress updates, and terminal outputs instantly over the socket, releasing system burden.

**TOON Message Envelope:**
`msg_id` · `msg_type` (TASK|RESULT|ERROR|TOOL_CALL..) · `source` · `target` · `token_budget` · `priority` · `payload` · `trace_id`

## The Intelligence Engine: Thinking Efforts & Human-in-the-Loop
Nexus supports variable autonomy using advanced reasoning paradigms (**Chain-of-Thought** and **ReAct** workflows).
- **Scale 1: Human-in-the-Loop (Interactive):** The Planner breaks down the DAG and awaits human approval. The Coder pushes a diff, the Reviewer flags risks, and human OKs execution. 
- **Scale 2: Full Autonomous Operations:** Nexus loops internally. If code generation fails LSP validation, it routes to Debugger. If ReAct bounds are met with success, it proceeds autonomously with no human bottleneck.
- **The Reflection Loop:** Every task ends with a "Reflection" stage where the outcome is graded, failure points are clustered, and pushed into the User Graph for persistent learning.

## Persistent Memory: User Graph & Knowledge Ingestion
### 1. User Graph (Selective Persistent Memory)
The model *grows with its user*. When a user makes a styling correction, flags an architecture pattern, or Nexus encounters an error—it is stored persistently in SQLite+NetworkX. Over multiple sessions, the Context Manager queries this memory so Nexus learns:
- When to reject a hallucinated library request because it knows the user's stack limits.
- When to actively warn the user against a bad practice discovered in a previous session.
- To use particular code styles implicitly without explicit instruction.

### 2. Ad-hoc Knowledge Ingestion
Because free models have older training cutoffs, Nexus treats missing knowledge as a traversable missing node.
- The **Researcher** sub-agent dynamically scrapes MCP doc servers or the web for new API endpoints.
- Extracted structures are woven into the Graph temporarily or permanently, bridging the "cut-off" gap instantly without fine-tuning.

## Security Practices & Output Gates
To ensure zero "shitty" code is pushed to production, Nexus operates behind Fort Knox-level boundaries:
- **Input_Guard & Output_Guard Layer:** Pydantic Core gates validate all output shapes instantly. Malformed json/code is caught within milliseconds.
- **Strict AST / Lint Verification:** No code is outputted unless it successfully passes an internal static validation step against the target workspace.
- **FSM Checkpointing:** File System operations are tightly controlled. Every write creates a reversible diff checkpoint. Direct file overwriting is forbidden.
- **Sandboxed Execution:** Terminal commands run by the Debugger are resource-limited (CPU, mem, network isolated) preventing malicious code escape.

## Context Priority & Token Budget (Restored & Enhanced)
The context window is rigidly mapped to force strict prompt truncation and cache-hit alignment.

| Priority | Contents | Eviction Policy |
|---|---|---|
| **P1 — Critical** | System persona, active TASK instruction, strict tool schemas | *Always retained, Highly Cached* |
| **P2 — High** | User Graph rules, stylistic preferences, extracted correction patterns | *Retained until 85% usage, re-summarized* |
| **P3 — Medium** | Last 3 turns, local chunked codebase slices from FSM | *Retained until 70% usage* |
| **P4 — Low** | Earlier reasoning traces, older tool outputs | *Aggressive Semantic Truncation at 60%* |
| **P5 — Archive** | Full preceding session history | *Vector Semantic Retrieval Only, No raw string* |

## Technology Stack Depth
- **Primary LLM Engine:** Qwen2.5-Coder-32B-Instruct (Complex reasoning), Qwen 7B / Llama 3 (Micro-tasks) via OpenRouter or Local Hosted.
- **Core Orchestration:** Python 3.12+, `asyncio` base, FastAPI (Websockets & REST), Pydantic v2 (Validation with Rust bindings for latency).
- **Communication Infrastructure:** Websockets for Interface streaming, `asyncio.Queue` Pub/Sub for internal TOON Bus.
- **Memory & Storage:** 
  - SQLite + NetworkX (Relational & Explicit Graph structure for User Profiling)
  - ChromaDB / FAISS (Vector Store for broad session semantics)
  - `nomic-embed-text` (Local dense embeddings via Ollama — 0 API latency).
- **Tooling Integrations:** MCP Python SDK (Process Isolated Tooling), Python Native AST parsers.
- **Interfaces:** HTML/React (Web App), Rich Dashboard (Python TUI), Native Mobile App API endpoints.

## Session Lifecycle: Finite State Machine (Non-Negotiable)
Every user task spawns a **per-session FSM** tracked by its `trace_id`. The Engine does not operate as a stateless pipe — it is a deterministic state engine. No agent can emit a message that violates the current session state.

### Valid States
| State | Description | Owner |
|---|---|---|
| `PENDING` | Task received, not yet classified | Engine |
| `ROUTING` | Router classifying task type | Router |
| `PLANNING` | Planner decomposing task into DAG | Planner Agent |
| `AWAITING_APPROVAL` | Human gate — blocks until explicit approval (Interactive mode only) | Engine / User |
| `CODING` | Coder generating code within scoped context | Coder Agent |
| `REVIEWING` | Reviewer performing static + semantic analysis | Reviewer Agent |
| `DEBUGGING` | Debugger analyzing error traces and generating fixes | Debugger Agent |
| `REFLECTING` | Memory Scribe extracting learnings into User Graph | Memory Scribe |
| `COMPLETED` | Task finished successfully, result delivered | Engine |
| `FAILED` | Task exhausted retries or hit an unrecoverable error | Engine |
| `TIMED_OUT` | Watchdog killed a stalled session | Watchdog |

### Valid Transitions
```
PENDING → ROUTING → PLANNING → AWAITING_APPROVAL → CODING → REVIEWING
                                                         ↓
REVIEWING → COMPLETED (approved)        REVIEWING → DEBUGGING (rejected)
DEBUGGING → CODING (retry, max 3)       DEBUGGING → FAILED (retries exhausted)
COMPLETED → REFLECTING                  FAILED → REFLECTING
Any active state → TIMED_OUT (watchdog)  Any active state → FAILED (unrecoverable)
```
**Illegal transitions raise `InvalidStateTransition` immediately.** No silent state corruption.

## Autonomy Modes
The system supports two formally defined execution modes, toggled per-session or globally:

### Interactive Mode (Human-in-the-Loop)
- After `PLANNING`, the session enters `AWAITING_APPROVAL`.
- The Planner's DAG and the Reviewer's diff proposals are streamed to the user via WebSocket.
- Execution **blocks** until the user sends an explicit `APPROVE` or `REJECT` message.
- On `REJECT`, the session transitions back to `PLANNING` with user feedback injected as a P1 context segment.

### Autonomous Mode (Self-Correcting)
- `AWAITING_APPROVAL` is skipped entirely. `PLANNING → CODING` is automatic.
- The Debugger→Coder retry loop runs autonomously up to the retry cap.
- The Reflection loop fires automatically on `COMPLETED` or `FAILED`.
- **Safety rail:** If the Reviewer rejects code 3 consecutive times, the system auto-escalates to Interactive mode for that session, forcing human review before proceeding.

## Retry & Timeout Policies
Hard limits prevent infinite loops and resource exhaustion in production:

| Policy | Value | Behavior on Breach |
|---|---|---|
| **Max Debugger→Coder retries** | 3 | Transition to `FAILED`, log full error chain |
| **Max Reviewer rejections** | 3 | Escalate to Interactive mode (force human review) |
| **Agent phase TTL** | 120 seconds | Watchdog transitions to `TIMED_OUT` |
| **Model API timeout** | 30 seconds | Retry once, then `FAILED` with provider error |
| **WebSocket heartbeat** | 15 seconds | Disconnect stale clients, release session lock |
| **Queue backpressure cap** | 100 messages | Overflow pushed to Dead-Letter Queue (DLQ) |

## Graceful Degradation
When external dependencies fail, Nexus does not crash — it degrades predictably:

| Failure | Response |
|---|---|
| **Model API down** | Retry 1x with exponential backoff → fallback to smaller model → if all fail, transition to `FAILED` with clear user notification |
| **Vector store unavailable** | Skip P5 archive retrieval, operate on P1-P4 only with warning |
| **Graph DB write failure** | Queue the write for retry, do NOT block the main pipeline |
| **WebSocket disconnect mid-task** | Task continues execution server-side. Results are buffered and delivered on reconnect |
| **Agent stalls (no output)** | Watchdog TTL fires → `TIMED_OUT` → Reflection logs the stall pattern |

## Roadmap 2.0
- **Phase 1** — Core Harness & WebSocket Infrastructure (Lowest latency routing, base Context/Token Ledgers, Initial Models).
- **Phase 2** — The Agent Suite & Safety Validation (FSM Sandboxes, Security Gates, Full Planner/Coder/Debugger loop).
- **Phase 3** — User Graph & Knowledge Ingestion (Persistent memory loops, automated reflection, "No to bad practices" pattern matching).
- **Phase 4** — Remote Accessibility Rollout (Web Framework UI, Mobile control clients).
