---
name: orchestrator
description: Dispatch prompts to local/cheap LLMs via the orchestrator. Use when offloading research, code review, generation, or validation to avoid expensive Claude subagent calls.
---

# Orchestrator Skill

Route work to cheap/local LLMs (GLM, TabbyAPI, OpenRouter, CLI agents) instead of spawning Claude subagents.

## Commands

### `/orchestrator dispatch <prompt>`
Send a prompt to the best available worker. Auto-routes by task type.

Use `mcp__orchestrator__orchestrator_dispatch` with:
- `prompt`: The work to dispatch
- `task_type` (optional): `coding`, `research`, `generation`, `review`, `validation`, `uncensored`
- `include_rag` (optional): `true` to inject RAG context

### `/orchestrator swarm <prompt>`
Fan out to ALL workers in parallel, get multiple perspectives, pick the best.

Use `mcp__orchestrator__orchestrator_swarm` with:
- `prompt`: The question to send to all workers

### `/orchestrator health`
Check which workers are up and provider status.

Use `mcp__orchestrator__orchestrator_health`.

### `/orchestrator spend`
Check spend tracking across providers.

Use `mcp__orchestrator__orchestrator_spend` with:
- `period` (optional): `1h`, `1d`, `7d`, `30d`

## When to Use

| Use orchestrator for... | Use Claude for... |
|------------------------|-------------------|
| Research questions | Complex multi-step reasoning |
| Code review / linting | Architecture decisions |
| Generating boilerplate | Nuanced refactoring |
| Validation / fact-checking | Tasks needing tool access |
| Getting multiple perspectives (swarm) | Tasks needing conversation context |
| Uncensored / unfiltered output | Safety-critical decisions |

## Examples

- "Dispatch to orchestrator: summarize this README"
- "Swarm this: what are the best practices for Python logging?"
- "Use the orchestrator to review this diff for bugs"
- "Check orchestrator health"

## Routing

The orchestrator auto-detects task type from the prompt. Override with `task_type`:
- **coding**: Routes to code-specialized workers
- **research**: Routes to broad-knowledge workers
- **generation**: Routes to creative workers
- **review**: Routes to analytical workers
- **validation**: Routes to fact-checking workers
- **uncensored**: Routes to unfiltered workers (OpenRouter abliterated models)
