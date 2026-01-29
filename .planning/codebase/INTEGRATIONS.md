# External Integrations
**Analysis Date:** 2026-01-29

## APIs & External Services
| Service | Purpose | Location |
|---------|---------|----------|
| **npm Registry** | Version checking via `npm view get-shit-done-cc version` | `get-shit-done/hooks/gsd-check-update.js` |
| **GitHub** | Repository hosting, issue tracking | `https://github.com/glittercowboy/get-shit-done` |
| **Discord** | Community server | `https://discord.gg/5JJgD5svVS` |

## AI Runtime Integrations
This is a meta-prompting system that integrates with multiple AI coding assistants:

| Runtime | Config Location | Command Format |
|---------|-----------------|----------------|
| **Claude Code** | `~/.claude/` | `/gsd:command` (nested) |
| **OpenCode** | `~/.config/opencode/` | `/gsd-command` (flat) |
| **Gemini CLI** | `~/.gemini/` | `/gsd:command` (nested) |

## Data Storage
| Type | Location | Format |
|------|----------|--------|
| **Project State** | `.planning/` | Markdown files |
| **Configuration** | `settings.json` | JSON |
| **Update Cache** | `~/.claude/cache/gsd-update-check.json` | JSON |
| **Todo Tracking** | `~/.claude/todos/` | JSON files per session |
| **Version Tracking** | `get-shit-done/VERSION` | Plain text |

## Authentication & Identity
**None** - Tool operates locally with no authentication required

## CI/CD & Deployment
| Platform | Purpose |
|----------|---------|
| **npm** | Package distribution via `npx get-shit-done-cc` |
| **GitHub Actions** | CI/CD (implied by `.github/` directory) |

## Environment Variables
| Variable | Purpose | Runtime |
|----------|---------|---------|
| `CLAUDE_CONFIG_DIR` | Override default Claude Code config location | Claude Code |
| `OPENCODE_CONFIG_DIR` | Override OpenCode config directory | OpenCode |
| `OPENCODE_CONFIG` | Alternative config path (uses parent dir) | OpenCode |
| `XDG_CONFIG_HOME` | XDG base directory for OpenCode | OpenCode |
| `GEMINI_CONFIG_DIR` | Override Gemini config directory | Gemini |

## Git Integration
- Atomic commits per task during execution
- Conventional commit format: `type(phase): description`
- Milestone tagging on completion
- `.planning/` directory tracking (configurable)

---
*Integration audit: 2026-01-29*
