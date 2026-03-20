# Upstream Merge Log — Round 4 (2026-03-20)

## Summary

Cherry-picked 89 upstream commits from `langchain-ai/deepagents` (main), post-626fb6fb.
Plus 1 local adaptation commit.

- **Total commits**: 90 (89 upstream + 1 local fix)
- **Conflicts**: 5 (skills.py, uv.lock, conftest.py, ci.yml, graph.py)
- **Local superiority**: All features preserved
- **Test results**: SDK 978 / CLI 2506 / Daytona 5 — all passing

## Key Changes

### Backend method rename (`7665066c`)
- `ls_info()` → `ls()`, `grep_raw()` → `grep()`, `glob_info()` → `glob()`
- Old names kept as deprecation shims
- Skills V2 updated to use new method names (6 call sites)

### Subagents parameter merge (`233d3f59`)
- `async_subagents` parameter removed from `create_deep_agent()`
- Merged into `subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent]`
- Discrimination via `"graph_id" in spec`

### Middleware order change (`def526b9`)
- `AnthropicPromptCachingMiddleware` and `MemoryMiddleware` moved after user middleware
- Prevents memory updates from invalidating prompt cache prefix

### LangSmithSandbox (`dfff6e7d`)
- New `backends/langsmith.py` — ported from CLI to SDK

### CLI updates
- `/update` command and auto-update lifecycle
- Unified slash-command registry
- Keybinding fixes, connecting banner
- Harbor terminal bench + command injection fix

## Conflicts Resolved

| # | File | Resolution |
|---|------|------------|
| 1 | `middleware/skills.py` | Updated `ls_info`→`ls`, `als_info`→`als` (6 call sites) |
| 2 | `uv.lock` | Accept theirs |
| 3 | `cli/conftest.py` | Merged TYPE_CHECKING import with existing content |
| 4 | `ci.yml` | Accept theirs |
| 5 | `graph.py` | Keep V2 features (expose_dynamic_tools, allowed_skills) + accept new middleware order |

## Post-merge Fix

- Registered `/upload` command in `command_registry.py` (bypass frozenset drift test)

## Test Results

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| SDK unit tests | 978 | 0 | 73 |
| CLI unit tests | 2506 | 0 | 1 |
| Daytona tests | 5 | 0 | 0 |
| **Total** | **3489** | **0** | **74** |
