---
description: Refactoring or configuring internal Nexus Agent settings
---

# Nexus Internal Sub-agent Customization
When asked to customize the Nexus system agents (Planner, Coder, Reviewer, etc.), adhere to these principles.

## 1. Configuration Modularity
Agent definitions live in `config/agents/`.
- Planner.yaml `[PLAN]`
- Coder.yaml `[CODE]`
- Reviewer.yaml `[REVW]`
- Debugger.yaml `[DBUG]`
- Researcher.yaml `[RSCH]`
- Memory_Scribe.yaml `[MEM]`

To add a new agent, create a corresponding YAML file there, and update the schemas.

## 2. Agent Scope and Capabilities
When updating agents or adding new ones, remember they only hold partial read scopes and can only trigger mapped tools:
- **Planner:** Cannot write code. Only does file tree read and memory read.
- **Coder:** File read/write via the FSM. Never reads the full codebase. Uses LSP.
- **Reviewer:** Follows semantic review, compares code against user styles from the User Graph Memory. Uses AST.
- **Debugger:** Driven exclusively by error traces, executes terminal commands via the sandbox.
- **Researcher:** Web search, local MCP doc ingestion.
- **Memory Scribe:** Exclusively Graph DB updates.

## 3. Customizing the System Config
Adjustments to global parameters such as Token Budget tracking (e.g., system persona token allocation of 300 tokens, Graph summary 500, etc.) should be directed to `config/system.toml`.

## 4. Updating Agent Contracts
If a core capability is added or removed from an agent:
1. Update `config/agents/[name].yaml`.
2. Update the logic inside `agents/[name].py` making sure it extends `BaseAgent` and overrides `handle_task()` correctly.
3. Keep the token constraint rigid and ensure no uncertified packages or paths are directly accessed bridging security policies (such as raw I/O without the Sandbox constraint).
