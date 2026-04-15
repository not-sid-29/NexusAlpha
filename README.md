# 🌌 Nexus Alpha (v0.1)
> **The Deterministic State Engine for Autonomous Coding Agents.**

![Nexus Alpha Hero](nexus_alpha_hero_banner.png)

Nexus Alpha is a production-grade orchestration harness designed to transform experimental AI agents into reliable, production-safe cognitive systems. It enforces strict session lifecycles, multi-tenant isolation, and a zero-trust security model.

---

## 🏗️ The 5-Plane Architecture
Nexus Alpha operates on a strictly isolated 5-layer design to ensure zero data-bleed and deterministic execution:

1.  **Transport Plane (TOON Bus)**: A hardened, async message bus with backpressure and Dead-Letter Queues (DLQ).
2.  **Executive Plane (FSM Engine)**: A per-session Finite State Machine enforcing 11 distinct lifecycle stages.
3.  **Security Plane (The Armour)**: Multi-layer guards for Input Scrubbing, Permission Matrix (Agent-Tool API), and Secret Masking.
4.  **Memory Plane (The Reservoir)**: High-concurrency SQLite (WAL mode) and ChromaDB vector storage with user-scoped isolation.
5.  **Interaction Plane (FSM Tool)**: Reversible file-system mutations using Unified Diffs and automated checkpoints.

## 🚀 Key Features
*   **🛡️ Production-Safe Guards**: Real-time redaction of API keys and protection against path traversal.
*   **🔄 Self-Healing Loops**: Integrated Refine-and-Retry cycles with automatic escalation to interactive mode on failure.
*   **🧵 Multi-Tenant Isolation**: Cryptographic session scoping ensuring zero data leakage between client traces.
*   **📊 Token Ledger**: Fine-grained monitoring of token consumption and budget enforcement.

## 🛠️ Getting Started

### Prerequisites
*   Python 3.10+
*   Virtual Environment established in `./nxsVenv`

### Installation
```powershell
# Setup environment
python -m venv nxsVenv
.\nxsVenv\Scripts\activate
pip install -r requirements.txt
```

### Running the Engine
```python
from core.engine import NexusEngine
from bus.dispatcher import AsyncDispatcher

# Initialize the state engine
dispatcher = AsyncDispatcher()
engine = NexusEngine(dispatcher)
await engine.start()
```

## 🧪 Verification
Nexus Alpha is backed by a rigorous suite of **35+ production tests** covering:
*   [x] FSM State Violations
*   [x] TOON Bus Backpressure & DLQ
*   [x] Multi-tenant DB Contention (SQLite WAL/Scribe)
*   [x] Agent-Tool Permission Matrix
*   [x] Secret Redaction & Input Guarding

## 📖 Documentation
Detailed technical documentation can be found in the `/documentation` directory:
*   [System Architecture](documentation/SYSTEM_ARCHITECTURE.md)
*   [Implementation Journey](documentation/journal/IMPLEMENTATION_JOURNEY.md)
*   [Product Requirements (PRD)](documentation/NexusPRD.md)

---
*Developed with ❤️ by the Nexus Engineering Team.*
