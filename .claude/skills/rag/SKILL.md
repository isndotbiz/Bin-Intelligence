---
name: rag
description: Search and ingest content in the curated RAG knowledge base on TrueNAS. Use when looking up past solutions, project docs, or storing new knowledge.
---

# RAG Knowledge Base Skill

Search and manage the curated RAG knowledge base (TrueNAS, 26+ collections, 10K+ documents).

## Commands

### `/rag search <query>`
Search the knowledge base for relevant documents.

Use `mcp__plugin_compound-engineering_rag__rag_search` with:
- `query`: What to search for
- `collection` (optional): Specific collection (e.g. `infrastructure`, `security-research`, `opportunity-bot`)
- `top_k` (optional): Max results (default 5)

### `/rag collections`
List all available collections with document counts.

Use `mcp__plugin_compound-engineering_rag__rag_collections`.

### `/rag ingest`
Store new content in the knowledge base.

Use `mcp__plugin_compound-engineering_rag__rag_ingest` with:
- `collection`: Target collection
- `content`: Text to store
- `title` (optional): Document title
- `source` (optional): Source URL or file path

## Collections (Key Ones)

| Collection | Docs | What's In It |
|-----------|------|-------------|
| infrastructure | 374 | Machine configs, services, cross-project knowledge |
| security-corpus | 1713 | Security research corpus |
| security-research | 1575 | LLM security findings |
| spiritatlas-taxonomy | 1740 | SpiritAtlas spiritual taxonomy |
| opportunity-bot | 156 | Business opportunity research |
| rag-system | 195 | RAG system docs |
| orchestrator-research | 4 | Orchestrator curated outputs |

## When to Use

- Before starting work: search for existing solutions
- After solving a problem: ingest the solution for future reference
- When onboarding to a project: search its collection for context
- When researching: search across all collections for prior art
