# Codebase Concerns
**Analysis Date:** 2026-01-29

## Tech Debt

**Silent Error Handling:**
- Issue: Multiple try/catch blocks swallow exceptions silently with empty catch blocks
- Files: `get-shit-done/bin/install.js` (lines 183-185, 741, 774, 835), `get-shit-done/hooks/gsd-statusline.js` (lines 61, 74), `get-shit-done/hooks/gsd-check-update.js` (lines 41, 46)
- Impact: Failures in settings parsing, cache reading, and npm version checks go undetected; makes debugging difficult
- Fix approach: Add minimal logging or error reporting; at minimum, use `console.warn` for unexpected failures in non-critical paths

**Legacy Flag Support:**
- Issue: `--both` flag marked as "Legacy flag, keeps working" but creates maintenance burden
- Files: `get-shit-done/bin/install.js` (line 25)
- Impact: Undocumented behavior, confusing CLI surface area
- Fix approach: Add deprecation warning when used, document removal timeline, migrate to `--all`

**Hardcoded Paths:**
- Issue: Cache and config paths assume `~/.claude` directory structure even when detecting OpenCode/Gemini
- Files: `get-shit-done/hooks/gsd-check-update.js` (line 12-13), `get-shit-done/hooks/gsd-statusline.js` (lines 49, 67)
- Impact: Hooks may not work correctly for OpenCode/Gemini users; statusline and update checks fail silently
- Fix approach: Detect runtime context and use appropriate config paths (`~/.config/opencode` or `~/.gemini`)

**No Automated Testing:**
- Issue: Zero test files detected in codebase (`**/*.test.js` glob returned empty)
- Files: Entire codebase
- Impact: Regressions not caught before release; confidence in changes is low
- Fix approach: Add unit tests for install.js path logic, frontmatter conversion, hook functionality

## Known Bugs

**None identified**
- No open FIXME comments or explicitly documented bugs found in codebase
- Template references to bugs are example content, not actual issues

## Security Considerations

**Command Injection Surface:**
- Issue: `execSync('npm view get-shit-done-cc version')` executes shell command; while input is hardcoded here, pattern could be misused elsewhere
- Files: `get-shit-done/hooks/gsd-check-update.js` (line 45)
- Impact: Low risk currently (no user input), but pattern suggests security awareness gap
- Mitigation: Current implementation is safe; add comment noting security consideration

**Spawned Background Process:**
- Issue: `spawn(process.execPath, ['-e', ...])` runs inline code in background child process
- Files: `get-shit-done/hooks/gsd-check-update.js` (lines 25-56)
- Impact: Orphaned processes possible if parent terminates mid-execution; no cleanup mechanism
- Mitigation: `child.unref()` is called correctly; process is lightweight and self-terminates

**File Permission Handling:**
- Issue: No explicit permission checks before writing to user config directories
- Files: `get-shit-done/bin/install.js` (throughout file operations)
- Impact: Unclear error messages if write fails due to permissions
- Mitigation: Node.js will throw; existing try/catch may swallow these errors (see Tech Debt)

## Performance Bottlenecks

**Synchronous File Operations:**
- Issue: All file operations use synchronous API (`fs.readFileSync`, `fs.writeFileSync`, `fs.existsSync`)
- Files: `get-shit-done/bin/install.js` (entire file), `get-shit-done/hooks/gsd-statusline.js` (entire file)
- Impact: Blocks event loop during installation; may cause noticeable delay with many files
- Mitigation: Acceptable for CLI tool; would matter more in server context

**Directory Traversal:**
- Issue: `copyWithPathReplacement` recursively traverses and copies directories without streaming
- Files: `get-shit-done/bin/install.js` (lines 451-492)
- Impact: Memory usage scales with directory size; currently acceptable given small payload
- Mitigation: Current implementation is adequate for package size

## Fragile Areas

**Frontmatter Conversion Logic:**
- Files: `get-shit-done/bin/install.js` (lines 248-346, `convertClaudeToOpencodeFrontmatter`)
- Why fragile: Manual YAML parsing using string manipulation; does not use proper YAML parser
- Risk: Edge cases in YAML (multiline strings, special characters, comments) may break conversion

**Multi-Runtime Install Flow:**
- Files: `get-shit-done/bin/install.js` (lines 1230-1266, `installAllRuntimes`)
- Why fragile: Complex conditional logic for handling Claude, OpenCode, and Gemini together; statusline prompt shared across runtimes
- Risk: Changes to one runtime's setup may inadvertently affect others

**Settings.json Manipulation:**
- Files: `get-shit-done/bin/install.js` (lines 179-195, 515-555, 659-702)
- Why fragile: Multiple functions modify settings.json with different assumptions; cleanup logic depends on string matching
- Risk: Orphaned hook registrations if string patterns change

## Test Coverage Gaps

**No Test Infrastructure:**
- No test runner configured
- No test files exist
- No CI/CD configuration for automated testing

**Untested Critical Paths:**
- Installation: No tests for `install()`, `uninstall()`, or path detection functions
- Frontmatter conversion: No tests for `convertClaudeToOpencodeFrontmatter()` or `convertClaudeToGeminiToml()`
- Hooks: No tests for statusline rendering or update check behavior
- Settings manipulation: No tests for `readSettings()`, `writeSettings()`, or hook cleanup

**Recommended Test Priority:**
1. Path detection functions (`getGlobalDir`, `getOpencodeGlobalDir`)
2. Frontmatter conversion (many edge cases)
3. Settings.json manipulation (data integrity risk)
4. Hook functionality (user-facing features)

---
*Concerns audit: 2026-01-29*
