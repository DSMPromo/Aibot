# Architecture
**Analysis Date:** 2026-01-29

## Pattern Overview
**Overall:** Multi-Agent Orchestration System with Meta-Prompting
**Key Characteristics:**
- Orchestrator/Subagent pattern for context isolation
- Markdown-based prompt engineering (commands as prompts)
- XML-structured task definitions for Claude execution
- Wave-based parallel execution with fresh context per agent
- Spec-driven development with verification loops

## Layers

**CLI/Installation Layer:**
- Purpose: Package installation and runtime setup (Claude Code, OpenCode, Gemini CLI)
- Location: `get-shit-done/bin/install.js`

**Commands Layer (User Interface):**
- Purpose: Slash commands that users invoke (orchestrators)
- Location: `get-shit-done/commands/gsd/`
- Pattern: Thin orchestrators that spawn specialized agents

**Agents Layer (Execution):**
- Purpose: Specialized subagents that perform actual work
- Location: `get-shit-done/agents/`
- Key Agents:
  - `gsd-planner.md` - Creates executable phase plans
  - `gsd-executor.md` - Executes plans with atomic commits
  - `gsd-verifier.md` - Verifies implementation against goals
  - `gsd-debugger.md` - Systematic debugging
  - `gsd-project-researcher.md` - Domain research
  - `gsd-codebase-mapper.md` - Existing code analysis
  - `gsd-roadmapper.md` - Phase/roadmap creation

**Workflows Layer (Process Definitions):**
- Purpose: Multi-step process definitions referenced by commands
- Location: `get-shit-done/get-shit-done/workflows/`

**Templates Layer (Document Structures):**
- Purpose: Templates for generated planning artifacts
- Location: `get-shit-done/get-shit-done/templates/`

**References Layer (Shared Knowledge):**
- Purpose: Reusable knowledge modules loaded by agents
- Location: `get-shit-done/get-shit-done/references/`

**Hooks Layer (Build-Time):**
- Purpose: Pre-publish hooks for npm package
- Location: `get-shit-done/hooks/`

## Data Flow

```
User Command (/gsd:*)
       |
       v
+------------------+
| Command (Orchest)|  <-- Thin orchestrator, stays at ~15% context
+------------------+
       |
       | spawn via Task tool
       v
+------------------+
| Specialized Agent|  <-- Fresh 200k context per agent
+------------------+
       |
       | reads templates, references
       v
+------------------+
| Workflow/Process |  <-- Multi-step process definitions
+------------------+
       |
       | creates/updates
       v
+------------------+
| .planning/ Docs  |  <-- PROJECT.md, ROADMAP.md, PLAN.md, STATE.md
+------------------+
```

**Core Workflow Cycle:**
1. `/gsd:new-project` - Question -> Research -> Requirements -> Roadmap
2. `/gsd:discuss-phase N` - Capture implementation decisions (CONTEXT.md)
3. `/gsd:plan-phase N` - Research -> Plan -> Verify loop (PLAN.md files)
4. `/gsd:execute-phase N` - Parallel wave execution (SUMMARY.md files)
5. `/gsd:verify-work N` - User acceptance testing (UAT.md)
6. Repeat for each phase, then `/gsd:complete-milestone`

## Entry Points

**npm Install:** `get-shit-done/bin/install.js` - Interactive installer for Claude/OpenCode/Gemini
**Commands:** `get-shit-done/commands/gsd/*.md` - 27 slash commands
**Agents:** `get-shit-done/agents/*.md` - 11 specialized subagents

## Key Architectural Decisions

**Context Isolation:**
- Orchestrators stay lean (~15% context)
- Each subagent gets fresh 200k token context
- Prevents "context rot" quality degradation

**Plans as Prompts:**
- PLAN.md files ARE the prompts, not documents transformed into prompts
- XML-structured tasks with verification criteria
- Atomic commits per task

**Wave-Based Parallelization:**
- Plans grouped by wave number
- Independent plans execute in parallel
- Sequential only when dependent

**Model Profiles:**
- quality: Opus for planning, Opus for execution
- balanced (default): Opus for planning, Sonnet for execution
- budget: Sonnet for planning, Sonnet for execution

---
*Architecture analysis: 2026-01-29*
