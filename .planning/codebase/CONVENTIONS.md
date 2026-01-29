# Coding Conventions

**Analysis Date:** 2026-01-29

## Naming Patterns

**Files:**
- kebab-case for all JavaScript files (`install.js`, `gsd-check-update.js`, `gsd-statusline.js`)
- kebab-case for markdown files (`execute-phase.md`, `gsd-codebase-mapper.md`)
- Hooks prefixed with `gsd-` (`gsd-check-update.js`, `gsd-statusline.js`)

**Functions:**
- camelCase for all functions (`expandTilde`, `readSettings`, `writeSettings`)
- Descriptive verb-noun naming (`getGlobalDir`, `parseConfigDirArg`, `buildHookCommand`)
- No special prefix for async functions

**Variables:**
- camelCase for local variables (`selectedRuntimes`, `configDirIndex`, `targetDir`)
- UPPER_SNAKE_CASE for constants and color codes (`HOOKS_DIR`, `DIST_DIR`)
- camelCase for module-level variables (`cyan`, `green`, `yellow`, `reset`)

**Types:**
- No TypeScript in codebase - pure JavaScript with CommonJS
- JSDoc comments for complex function documentation

## Code Style

**Formatting:**
- No Prettier/ESLint configuration detected
- 2-space indentation consistently used
- Single quotes for strings
- Semicolons required
- ~100 character line length (flexible)

**Linting:**
- No linting tools configured
- esbuild used for build tooling only (`devDependencies`)

## Import Organization

**Order:**
1. Node.js built-in modules (`fs`, `path`, `os`, `readline`, `child_process`)
2. Local modules (`../package.json`)

**Grouping:**
- No blank lines between imports in same category
- All requires at top of file

**Path Aliases:**
- None used - relative paths only (`../package.json`, `./external`)

## Error Handling

**Patterns:**
- Try/catch for JSON parsing with fallback to empty object
- Silent failures with empty catch blocks for non-critical operations
- `process.exit(1)` for fatal errors with user-facing message
- Console error messages with colored output (`${yellow}Error message${reset}`)

**Error Types:**
- No custom error classes
- Direct console.error for user-facing errors
- Silent catch for optional file operations (e.g., VERSION file reading)

## Logging

**Framework:**
- Console output with ANSI color codes
- Colors defined as variables: `cyan`, `green`, `yellow`, `dim`, `reset`

**Patterns:**
- Checkmark symbols for success: `${green}done${reset}`
- Warning symbols: `${yellow}warning${reset}`
- No logging framework - direct console output
- ASCII art banner for CLI branding

## Comments

**When to Comment:**
- JSDoc-style block comments for function documentation
- Inline comments explain "why" for complex logic
- Comments for section headers in large functions

**JSDoc/TSDoc:**
- Used for function parameter documentation
- `@param {type} name - description` format
- `@returns {type}` for return values

**TODO Comments:**
- Not observed in codebase

## Function Design

**Size:**
- Functions range 10-80 lines
- Large functions (`install`, `uninstall`) broken into logical sections
- Helper functions extracted for reusable logic

**Parameters:**
- 1-3 parameters typical
- Default values via `= null` or `= 'claude'`
- Callback pattern for async prompts (`callback` parameter)

**Return Values:**
- Object returns for multi-value results (`{ settingsPath, settings, statuslineCommand, runtime }`)
- Implicit undefined for side-effect functions
- Early returns for guard clauses and error conditions

## Module Design

**Exports:**
- CommonJS (`module.exports` not used - scripts are entry points)
- All code in single files per script
- No barrel files or index.js patterns

**Barrel Files:**
- Not used - each script is self-contained

---

*Convention analysis: 2026-01-29*
*Update when patterns change*
