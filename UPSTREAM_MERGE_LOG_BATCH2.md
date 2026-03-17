# Upstream Merge Log — Batch 2 (2026-03-17)

## Summary

Cherry-picked 59 upstream commits (post-SDK 0.4.11) from `langchain-ai/deepagents` (main).
Plus 1 local adaptation commit for type system compatibility.

- **Total commits**: 60 (59 upstream + 1 local fix)
- **Conflicts**: 2 (filesystem.py, skills.py) — both manually resolved
- **Local superiority**: 10/10 features preserved
- **SDK version**: 0.5.0

## Key Changes

### Pivot A: FileData + Backend.read return type (`6fb4ede8`)
- +2394/-456 lines across 31 files
- New `ReadResult` type with multimodal support (images as base64)
- Conflict in `filesystem.py`: resolved by keeping binary doc conversion (Converters), delegating image handling to upstream's `_handle_read_result`

### Pivot B: Backend return types for ls/glob/grep (`23cf264d`)
- +907/-580 lines across 24 files
- New `LsResult`, `GlobResult`, `GrepResult` types with deprecation shims
- Conflict in `skills.py`: resolved by adapting V2's `_discover_resources` to handle `LsResult`

### Pivot C: SDK version 0.5.0 (`ab242c34`)
- Version bump + dependency updates
- No conflicts

### AsyncSubAgentMiddleware (`0c5d5010`)
- New `async_subagents.py` module (1860 lines)
- Auto-merged cleanly into `graph.py` and `__init__.py`

## Conflicts Resolved

| File | Conflict | Resolution |
|------|----------|------------|
| `middleware/filesystem.py` | Imports + read_file sync/async | Keep Converter imports + binary doc branch; remove image branch (upstream handles better); delegate to `_handle_read_result` |
| `middleware/skills.py` | `ls_info()` return type | Adapt V2's `_discover_resources` and `_scan_skills` to handle `LsResult` type |

## Post-merge Adaptation

Committed as `fix(sdk): adapt local features to upstream type system`:
- Removed image handling branch from filesystem.py (upstream's `ReadResult` handles images via multimodal content blocks)
- Fixed 6 `ls_info()`/`als_info()` call sites in skills.py to handle `LsResult` type

## Local Features Preserved (10/10)

| Feature | Status |
|---------|--------|
| Memory isawaitable | Preserved |
| SubAgent logging | Preserved |
| SkillsMiddleware V2 (1193 lines) | Preserved + adapted for LsResult |
| Summarization factory | Preserved |
| state_schema param | Preserved |
| async_subagents param | NEW (from upstream) |
| upload_files exported | Preserved |
| AsyncSubAgent exported | NEW (from upstream) |
| Converters directory | Preserved |
| async_subagents.py | NEW (from upstream) |

## Test Results

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| SDK unit tests | 957 | 0 | 73 |
| CLI unit tests | 2354 | 0 | 1 |
| Daytona tests | 5 | 0 | 0 |
| **Total** | **3316** | **0** | **74** |
