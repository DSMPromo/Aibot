# Codebase Structure
**Analysis Date:** 2026-01-29

## Directory Layout
```
Aibot/
├── .claude/                    # Claude Code configuration (linked)
├── .planning/                  # Planning artifacts directory
│   └── codebase/              # Codebase analysis docs
└── get-shit-done/             # Main GSD package
    ├── bin/                   # CLI entry point
    │   └── install.js         # npm installer (interactive/CLI)
    ├── agents/                # Specialized subagent definitions
    │   ├── gsd-planner.md
    │   ├── gsd-executor.md
    │   ├── gsd-verifier.md
    │   ├── gsd-debugger.md
    │   ├── gsd-project-researcher.md
    │   ├── gsd-phase-researcher.md
    │   ├── gsd-codebase-mapper.md
    │   ├── gsd-roadmapper.md
    │   ├── gsd-plan-checker.md
    │   ├── gsd-integration-checker.md
    │   └── gsd-research-synthesizer.md
    ├── commands/              # Slash command definitions
    │   └── gsd/               # /gsd:* namespace (27 commands)
    │       ├── new-project.md
    │       ├── plan-phase.md
    │       ├── execute-phase.md
    │       ├── verify-work.md
    │       ├── discuss-phase.md
    │       ├── quick.md
    │       ├── progress.md
    │       ├── help.md
    │       └── ...
    ├── get-shit-done/         # Core assets
    │   ├── templates/         # Document templates
    │   │   ├── project.md
    │   │   ├── requirements.md
    │   │   ├── roadmap.md
    │   │   ├── state.md
    │   │   ├── summary.md
    │   │   ├── context.md
    │   │   ├── phase-prompt.md
    │   │   ├── verification-report.md
    │   │   ├── UAT.md
    │   │   ├── codebase/      # Codebase mapping templates
    │   │   └── research-project/
    │   ├── workflows/         # Multi-step process definitions
    │   │   ├── execute-phase.md
    │   │   ├── execute-plan.md
    │   │   ├── verify-phase.md
    │   │   ├── verify-work.md
    │   │   ├── discuss-phase.md
    │   │   ├── complete-milestone.md
    │   │   └── ...
    │   └── references/        # Shared knowledge modules
    │       ├── checkpoints.md
    │       ├── verification-patterns.md
    │       ├── questioning.md
    │       ├── git-integration.md
    │       ├── model-profiles.md
    │       ├── tdd.md
    │       └── ui-brand.md
    ├── hooks/                 # Build hooks
    │   └── build-hooks.js
    ├── scripts/               # Runtime scripts
    │   ├── gsd-check-update.js
    │   └── gsd-statusline.js
    ├── assets/                # Visual assets
    ├── .github/               # GitHub workflows
    ├── package.json           # npm package definition
    ├── README.md              # Project documentation
    ├── CHANGELOG.md           # Version history
    ├── CONTRIBUTING.md        # Contributor guide
    ├── GSD-STYLE.md           # Style guide
    ├── MAINTAINERS.md         # Maintainer info
    └── LICENSE                # MIT license
```

## Directory Purposes

**`get-shit-done/bin/`:** Single Node.js installer script that handles interactive prompts, CLI flags, and file copying to target directories.

**`get-shit-done/agents/`:** Markdown-based agent definitions with YAML frontmatter. Each agent is a specialized subagent spawned by orchestrator commands. Contains role, philosophy, execution flow, and output specifications.

**`get-shit-done/commands/gsd/`:** Slash command definitions that users invoke. Commands act as orchestrators - they validate input, load context, spawn agents, and coordinate results. Lightweight to preserve context budget.

**`get-shit-done/get-shit-done/templates/`:** Template files for generated planning artifacts. Used by agents to create consistent PROJECT.md, ROADMAP.md, PLAN.md, SUMMARY.md, etc.

**`get-shit-done/get-shit-done/workflows/`:** Detailed multi-step process definitions. Referenced by commands via @-includes. Contains execution logic for complex operations.

**`get-shit-done/get-shit-done/references/`:** Reusable knowledge modules loaded by agents. Contains patterns, guidelines, and shared context (questioning techniques, verification patterns, git integration, etc.).

**`get-shit-done/hooks/`:** Build-time hooks for npm prepublish. Bundles assets using esbuild.

**`get-shit-done/scripts/`:** Runtime utility scripts (update checker, statusline).

## Key File Locations

**Entry Points:**
- npm install: `get-shit-done/bin/install.js`
- Commands: `get-shit-done/commands/gsd/*.md`
- Agents: `get-shit-done/agents/*.md`

**Configuration:**
- Package config: `get-shit-done/package.json`
- Project config (generated): `.planning/config.json`

**Core Commands:**
- `/gsd:new-project`: `get-shit-done/commands/gsd/new-project.md`
- `/gsd:plan-phase`: `get-shit-done/commands/gsd/plan-phase.md`
- `/gsd:execute-phase`: `get-shit-done/commands/gsd/execute-phase.md`
- `/gsd:verify-work`: `get-shit-done/commands/gsd/verify-work.md`

**Core Agents:**
- Planner: `get-shit-done/agents/gsd-planner.md`
- Executor: `get-shit-done/agents/gsd-executor.md`
- Verifier: `get-shit-done/agents/gsd-verifier.md`

## Where to Add New Code

**New Command:** `get-shit-done/commands/gsd/your-command.md`
- Use existing command as template
- Define frontmatter with name, description, allowed-tools
- Keep orchestrator thin, delegate to agents

**New Agent:** `get-shit-done/agents/gsd-your-agent.md`
- Use existing agent as template
- Define role, philosophy, execution flow
- Specify tools and output format

**New Workflow:** `get-shit-done/get-shit-done/workflows/your-workflow.md`
- Multi-step process definitions
- Referenced via @-includes in commands

**New Template:** `get-shit-done/get-shit-done/templates/your-template.md`
- Document templates for generated artifacts

**New Reference:** `get-shit-done/get-shit-done/references/your-reference.md`
- Reusable knowledge modules

---
*Structure analysis: 2026-01-29*
