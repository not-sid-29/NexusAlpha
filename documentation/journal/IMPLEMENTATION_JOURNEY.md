# Nexus Alpha: The Implementation Journey

This document captures the evolution of Nexus Alpha from a prototype harness into a production-grade, deterministic **State Engine**. It details the architectural pivots, hidden challenges, and the rigorous testing regimen used to validate the system.

## 🏁 Phase 1: The Immovable Harness
**Goal**: Transition from "loose orchestration" to "state-enforced execution."

### 🔹 The FSM Breakthrough
Early testing showed that agents could get stuck in infinite retry loops.
*   **Challenge**: Nondeterministic agent "wandering."
*   **Resolution**: Implemented a **11-state Finite State Machine (FSM)**. Every session has a dedicated lifecycle enforced by a strict `TRANSITION_TABLE`. If an agent tries to skip a step (e.g., Coding → Completion without Review), the harness raises an `InvalidStateTransition` and halts.

### 🔹 High-Concurrency Messaging (TOON Bus)
*   **Challenge**: Message loss during peak load (e.g., 10+ concurrent sessions).
*   **Resolution**: Hardened the `AsyncDispatcher` with:
    *   **Backpressure**: Bounded queues (max 100) per subscriber.
    *   **DLQ (Dead Letter Queue)**: Dropped messages are tracked for audit, never lost.
    *   **Graceful Draining**: The system ensures all queues are empty before shutdown.

---

## 🏗️ Phase 2: Infrastructure & Security Hardening
**Goal**: Build the "Immune System" and "Memory Banks."

### 🔹 The "Memory Scribe" Logic
*   **Challenge**: `SQLITE_BUSY` errors. SQLite was locking the entire DB when multiple agents tried to write logs and session data simultaneously.
*   **Resolution**: **Single-Writer Pattern**. We decoupled the DB from the agents. Agents publish `MEMORY_WRITE` messages to the bus; the `MemoryScribe` service consumes them sequentially, ensuring zero lock contention even under high stress.

### 🔹 Layered Defense-in-Depth
*   **Challenge**: Preventing agents from reading sensitive system files or leaking API keys.
*   **Resolution**: Implemented a **5-Layer Security Guard**:
    1.  **Input Guard**: Regex-based blocking of path traversal (`../`).
    2.  **Permission Matrix**: Real-time checking if a specific Agent (e.g., Planner) is allowed to call a Tool (e.g., Shell).
    3.  **State Gating**: FSM-level blocking.
    4.  **Output Guard**: AST-based Python syntax validation.
    5.  **Secret Scrubbing**: Automatic redaction of OpenAI/GitHub keys before they hit logs or WebSockets.

### 🔹 Reversible Interactions (FSM Tool)
*   **Challenge**: Brittle `write_file` calls could break the project files.
*   **Resolution**: 
    *   **Diff-Patching**: Switched to a line-based Unified Diff applier.
    *   **Checkpoints**: Every mutation creates a `.bak` file in `.nexus/checkpoints/` before the change is applied, making every agent action fully reversible.

---

## 🧪 Rigorous Testing Suite
The integrity of Nexus Alpha is verified by **35+ production-grade tests**:

| Category | Test Scenario | Outcome |
| :--- | :--- | :--- |
| **FSM** | Illegal jump from PLANNING → COMPLETED | **Blocked** (InvalidStateTransition) |
| **Bus** | Reaching max queue size (100 msgs) | **Shunted to DLQ** (Zero crash) |
| **Security** | Planner calling `executor.shell` | **Blocked** (PermissionError) |
| **Security** | Prompting for `../../../etc/passwd` | **Blocked** (ValueError) |
| **Safety** | Broken Python syntax in Coder `RESULT` | **FSM Transition to DEBUGGING** |
| **Memory** | 200 simultaneous writes to SQLite | **Success** (Serialized via Scribe) |

## 💡 Lessons Learned
1.  **Enforcement > Instruction**: Don't tell the agent to "be safe"—don't give it a tool that lets it be dangerous.
2.  **State is Truth**: By externalizing session state from the agent's memory, we can survive agent reloads and model failures without losing progress.
3.  **Concurrency is Tricky**: Always assume agents will hammer the DB faster than it can lock/unlock; the Single-Writer queue is non-negotiable for SQLite.

---
*Documentation current as of Nexus Alpha v0.1 (Phase 2 completion).*
