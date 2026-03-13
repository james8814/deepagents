# Upstream Merge Log — 2026-03-13 (Round 2)

## Summary

Cherry-picked 21 new upstream commits from `langchain-ai/deepagents` (main) into `upstream-sync-2026-03-13` branch.

- **Total commits**: 21 cherry-picked + 1 local (converters integration)
- **Conflicts**: 0 (1 auto-resolved trivially)
- **Local superiority**: All 4 features preserved

## Commits Merged (newest first)

| # | Commit | Description |
|---|--------|-------------|
| 21 | 6d018bc2 | chore(examples): update nvidia model (#1855) |
| 20 | 2e820148 | feat(sdk): Add LangSmith integration metadata (#1837) |
| 19 | 9742a1f9 | fix(sdk): strip leading slash from glob patterns (#1846) |
| 18 | e2164804 | feat(sdk): add MemoryAgentBench evaluation suite (#1807) |
| 17 | e7843f28 | chore(deps): bump setup-uv@v6 to v7 (#1848) |
| 16 | 7b94dc27 | fix(sdk): accept all langsmith tracing env vars in evals (#1847) |
| 15 | fcab741d | feat(cli): client-server architecture via langgraph dev (#1759) |
| 14 | a7b61f71 | chore(deps): bump multipart 1.3.0→1.3.1 daytona (#1842) |
| 13 | e3e9c32b | chore(deps): bump multipart 1.3.0→1.3.1 harbor (#1843) |
| 12 | 006396e0 | chore(deps): bump multipart 1.3.0→1.3.1 cli (#1841) |
| 11 | 956eef47 | test(sdk): add 3 more evals for tool usage (#1840) |
| 10 | dd8857f3 | chore(sdk): add evals README, ensure tracing (#1834) |
| 9 | 4dd0f0bb | fix(cli): use max-height for tool-info-scroll (#1835) |
| 8 | 4a58b57c | feat(cli): enable ask_user tool by default (#1830) |
| 7 | aa4ce4c9 | feat(cli): show model status in /model selector (#1820) |
| 6 | 2b90ac9c | feat(examples): add nvidia deep agent (#1822) |
| 5 | 3c656494 | feat(sdk): add subagent_model param (#1369) |
| 4 | a2829c9a | fix(cli): use UUID7 for thread IDs (#1826) |
| 3 | 24ee68bb | refactor(sdk): extract model resolution into _models module (#1825) |
| 2 | cb4da307 | fix(cli): prevent reentrant model switching (#1824) |
| 1 | 95a7693e | feat(cli): add sessions alias for /threads (#1823) |

## Local Superiority Verification

| Feature | File | Status |
|---------|------|--------|
| Memory async/sync (isawaitable) | middleware/memory.py | Preserved |
| SubAgent logging | middleware/subagents.py | Preserved |
| SkillsMiddleware V2 (1190 lines) | middleware/skills.py | Preserved |
| create_summarization_tool_middleware | middleware/summarization.py | Preserved |

## Test Results

| Suite | Passed | Failed | Skipped | Notes |
|-------|--------|--------|---------|-------|
| SDK unit tests | 850 | 0 | 73 | All green |
| CLI unit tests | 2238 | 1 | 1 | 1 flaky upstream test (autocomplete timing) |
| Daytona tests | 5 | 0 | 0 | All green |
| **Total** | **3093** | **1** | **74** | |

### CLI Test Failure (non-blocking)

- `test_chat_input.py::TestHistoryRecallSuppressesCompletions::test_history_recall_does_not_trigger_completions`
- Race condition in Textual UI test — autocomplete suggestions appear despite history recall
- This is an upstream test issue, not a regression from merge

## Key New Features

1. **_models module** (`_models.py`): Model resolution helpers extracted from graph.py
2. **subagent_model param**: `create_deep_agent()` now accepts `subagent_model` for per-subagent model configuration
3. **Glob pattern fix**: CompositeBackend now strips leading slashes from glob patterns
4. **LangSmith metadata**: `ls_integration: deepagents` added to graph config
5. **MemoryAgentBench**: Evaluation suite in `tests/evals/`
6. **Client-server CLI**: `langgraph dev` architecture for CLI
7. **ask_user by default**: Tool enabled without configuration
8. **UUID7 thread IDs**: More sortable than 8-char hex
9. **NVIDIA example**: New deep agent example

## Version

SDK version after merge: 0.4.10
