---
name: setup
description: Configure the compound engineering plugin for a project. Run when first installing the plugin or reconfiguring it. Sets up review agents and required MCP servers (context7, git-mcp).
disable-model-invocation: true
---

# Compound Engineering Setup

Interactive setup that configures two things:
1. `compound-engineering.local.md` — which review agents run during `/workflows:review` and `/workflows:work`
2. `.mcp.json` — required MCP servers (context7, git-mcp)

---

## Step 1: Check Existing Config

Read `compound-engineering.local.md` in the project root. If it exists, display current settings summary and use AskUserQuestion:

```
question: "Settings file already exists. What would you like to do?"
header: "Config"
options:
  - label: "Reconfigure"
    description: "Run the interactive setup again from scratch"
  - label: "View current"
    description: "Show the file contents, then stop"
  - label: "Cancel"
    description: "Keep current settings"
```

If "View current": read and display the file, then stop.
If "Cancel": stop.

## Step 2: Detect and Ask

Auto-detect the project stack:

```bash
test -f Gemfile && test -f config/routes.rb && echo "rails" || \
test -f Gemfile && echo "ruby" || \
test -f tsconfig.json && echo "typescript" || \
test -f package.json && echo "javascript" || \
test -f pyproject.toml && echo "python" || \
test -f requirements.txt && echo "python" || \
echo "general"
```

Use AskUserQuestion:

```
question: "Detected {type} project. How would you like to configure?"
header: "Setup"
options:
  - label: "Auto-configure (Recommended)"
    description: "Use smart defaults for {type}. Done in one click."
  - label: "Customize"
    description: "Choose stack, focus areas, and review depth."
```

### If Auto-configure, use defaults:

- **Rails:** `[kieran-rails-reviewer, dhh-rails-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]`
- **Python:** `[kieran-python-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]`
- **TypeScript:** `[kieran-typescript-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]`
- **General:** `[code-simplicity-reviewer, security-sentinel, performance-oracle, architecture-strategist]`

### If Customize, go to Step 3

## Step 3: Customize (3 questions)

**a. Stack:**

```
question: "Which stack should we optimize for?"
header: "Stack"
options:
  - label: "{detected_type} (Recommended)"
  - label: "Rails"
  - label: "Python"
  - label: "TypeScript"
```

**b. Focus areas (multiSelect):**

```
question: "Which review areas matter most?"
header: "Focus"
multiSelect: true
options:
  - label: "Security"      (security-sentinel)
  - label: "Performance"   (performance-oracle)
  - label: "Architecture"  (architecture-strategist)
  - label: "Code simplicity" (code-simplicity-reviewer)
```

**c. Depth:**

```
question: "How thorough should reviews be?"
header: "Depth"
options:
  - label: "Thorough (Recommended)"  — stack + selected focus areas
  - label: "Fast"                     — stack + code-simplicity only
  - label: "Comprehensive"            — all above + git-history-analyzer, data-integrity-guardian, agent-native-reviewer
```

## Step 4: Write compound-engineering.local.md

```markdown
---
review_agents: [{computed agent list}]
plan_review_agents: [{stack reviewer}, code-simplicity-reviewer]
---

# Review Context

Add project-specific review instructions here.
These notes are passed to all review agents during /workflows:review and /workflows:work.
```

## Step 5: Configure .mcp.json

The compound engineering plugin requires two MCP servers. Detect OS, then merge them into `.mcp.json` (create if missing, preserve existing entries).

### Detect OS

```bash
uname -s 2>/dev/null || echo "Windows"
```

Output `Darwin` or `Linux` = Unix. Anything else = Windows.

### MCP servers to add

**context7** (library docs — used by plan and work commands):

Windows:
```json
"context7": {
  "command": "cmd",
  "args": ["/c", "npx", "-y", "@upstash/context7-mcp@latest"]
}
```

Unix/Mac:
```json
"context7": {
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp@latest"]
}
```

**git** (git history — used by git-history-analyzer agent):

Windows (ask user for their workspace parent dir, default `D:/workspace`):
```json
"git": {
  "command": "cmd",
  "args": ["/c", "npx", "-y", "@cyanheads/git-mcp-server@latest"],
  "env": {
    "MCP_TRANSPORT_TYPE": "stdio",
    "GIT_BASE_DIR": "D:/workspace"
  }
}
```

Unix/Mac (default `/home`):
```json
"git": {
  "command": "npx",
  "args": ["-y", "@cyanheads/git-mcp-server@latest"],
  "env": {
    "MCP_TRANSPORT_TYPE": "stdio",
    "GIT_BASE_DIR": "/home"
  }
}
```

Read existing `.mcp.json`, merge in both servers, write back. Never delete existing entries.

## Step 6: Confirm

```
Setup complete!

Stack:        {type}
Review depth: {depth}
Agents:       {count} configured
              {agent list, one per line}

MCP servers written to .mcp.json:
  context7   — library docs (plan/work commands)
  git        — git history (review agents)

Files:
  compound-engineering.local.md  (review config)
  .mcp.json                      (MCP servers — add to .gitignore if paths are machine-specific)
```
