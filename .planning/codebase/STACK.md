# Technology Stack
**Analysis Date:** 2026-01-29

## Languages
**Primary:** JavaScript (Node.js) - CommonJS modules

## Runtime
**Environment:** Node.js >= 16.7.0
**Package Manager:** npm

## Frameworks
**Core:** None (pure Node.js) - CLI tool with no framework dependencies

## Key Dependencies
**Production:** None - zero runtime dependencies
**Development:** `esbuild` ^0.24.0 - used for build tooling (hooks bundling)

## Source Files
| File | Purpose |
|------|---------|
| `get-shit-done/bin/install.js` | CLI installer (1300+ lines) - handles installation for Claude Code, OpenCode, Gemini |
| `get-shit-done/hooks/gsd-statusline.js` | Claude Code statusline hook - displays model, task, context usage |
| `get-shit-done/hooks/gsd-check-update.js` | Background update checker - spawns child process to query npm registry |
| `get-shit-done/scripts/build-hooks.js` | Build script - copies hooks to dist/ for distribution |

## Node.js Built-in Modules Used
- `fs` - File system operations
- `path` - Path manipulation
- `os` - OS-level info (homedir, platform)
- `readline` - Interactive prompts
- `child_process` - spawn/execSync for background processes

## Configuration
- **Package:** `get-shit-done/package.json`
- **Installation locations:**
  - Claude Code: `~/.claude/` (global) or `./.claude/` (local)
  - OpenCode: `~/.config/opencode/` (XDG spec)
  - Gemini: `~/.gemini/`
- **Settings:** `settings.json` in respective config directories
- **Hooks:** Registered in `settings.json` under `hooks.SessionStart` and `statusLine`

## Build Process
```bash
npm run build:hooks  # Copies hooks to hooks/dist/
npm run prepublishOnly  # Runs build:hooks before npm publish
```

## Distribution
- Published to npm as `get-shit-done-cc`
- Installed via `npx get-shit-done-cc`
- No bundling required - pure Node.js with zero dependencies

---
*Stack analysis: 2026-01-29*
