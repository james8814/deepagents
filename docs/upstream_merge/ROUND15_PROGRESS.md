# Round 15 上游合并进度

**日期**: 2026-04-27
**分支**: `upstream-sync-round15`
**范围**: `51f15324..95f845d2` (83 upstream commits)

## 总结

| 指标 | 值 |
|------|-----|
| 上游 commits | 83 |
| 已合并 | 79 |
| 跳过 (release) | 4 (deepagents-cli 0.0.39/0.0.40/0.0.41 + acp 0.0.6) |
| 冲突文件 | 5 (subagents.py × 2, graph.py, skills.py, agent.py) |
| 本地修复 commits | 3 |
| 新增 Gate 2 红线测试 | 5 (1 wiring + 4 V1/V2 mutex) |

## 执行顺序

### Phase 1a: Deps bumps (12 commits) ✅

langchain-openai 1.1.14, langchain-text-splitters 1.1.2, python-dotenv 1.2.2, python-multipart 0.0.26, nbconvert 7.17.1, langsmith floor 0.7.35

### Phase 1b: CLI/REPL features (36 commits) ✅

- `/agents` switcher
- `[auth]` config
- `--startup-cmd`, `--max-turns`
- inline argument hints
- Custom kitty terminal shift+enter
- REPL benchmarks
- update notification rework
- Skip `482f3810` (CLI version bump)

### Phase 1c: Evals/ACP/CI (22 commits) ✅

ACP v0.9 schema bump, Opus 4.7 in demo, GPT-5.5/Kimi models, integration test workflow

### Gate 1 ✅

- SDK 1258 → CLI 3633 → Evals 263 → ACP 81 → REPL 79
- langsmith.sandbox import OK
- uv lock --check OK
- Fixes: SDK version 0.5.3→0.5.0, restore COLORS dict, sort COMMANDS, MagicMock import, hex color markers

### Phase 2a: SDK low-conflict (4 commits, NOT touching graph.py/skills.py) ✅

- A8 `87644b78` patch_tool_calls perf
- A4 `3bcc51a9` ls_agent_type configurable tag (Generator import added)
- A5 `bd6ec6bc` subagent tagging via configurable (replaced tracing context)
- A6 `291aebe2` CRLF preserve in sandbox edit

冲突解决: 合并 stream_writer + 新 configurable approach（保留双方价值）

### Phase 2b: graph.py + skills.py 簇 + harbor (5 commits) ✅

按"每个文件只解决一次冲突"原则排序：

- A3 `1699f3ae` MemoryMiddleware cache breakpoint (graph.py +10)
- A1 `eb9fab96` graph.py 参数重排（最后碰 graph.py）
- A7 `e1c1d502` Windows backslash + skills _list_skills 重写 (skills.py +127)
- A2 `f7e37721` labelled skill sources (skills.py +141, 最后碰 skills.py)
- D5 `082b9008` LangSmith env snapshots

### Gate 2 红线 ✅

**红线 1**: graph.py wiring (7 tests)

- 6 既有测试 + 1 新增 `test_state_schema_passed_to_create_agent`

**红线 2**: skills.py V1/V2 prompt mutex (4 new tests, Round 14 P1 防回归)

- V1 mode 不出现 `load_skill(`
- V2 mode 不出现 `read_file`/`limit=1000`
- V1/V2 per-skill hints 互斥

**License separator** (本轮上游变更): `;` → `,` (测试更新)

## 最终测试结果

| 包 | 通过 | 跳过 | xfailed | xpassed | 失败 |
|----|------|------|---------|---------|------|
| SDK | 1311 | 84 | 12 | 3 | 0 |
| CLI | 3635 | 3 | 0 | 0 | 0 |
| Evals | 264 | 0 | 0 | 0 | 0 |
| ACP | 81 | 0 | 0 | 0 | 0 |
| REPL | 79 | 0 | 0 | 1 | 0 |
| **合计** | **5370** | **87** | **12** | **4** | **0** |

## 新增上游特性

1. **SkillSource labelled tuple** — `(path, label)` 用于消歧 user vs project `.claude/skills`
2. **`/agents` switcher** — CLI 命令
3. **CLI custom auth `[auth]`** — deploy 配置
4. **`--startup-cmd`, `--max-turns`** — 非交互模式标志
5. **`ls_agent_type` configurable tag** — LangSmith subagent 追踪
6. **MemoryMiddleware cache breakpoint** — Anthropic prompt cache 优化（~16% 成本降低）
7. **Sandbox CRLF preserve** — Windows 文件编辑修复
8. **Windows path normalization** — backslash → forward slash
9. **LangSmith snapshots migration** — harbor + CLI 沙箱迁移
10. **REPL foreign object + benchmarks**

## 本地优越特性保护 11/11 ✅

- state\_schema, skills\_expose\_dynamic\_tools, skills\_allowlist
- create\_summarization\_middleware, Overwrite guard
- Converters, stream\_writer, subagent\_logging
- permissions, harness\_profiles, tool\_exclusion

## 累计合并

**~1069 commits across 15 rounds (Round 0-15)**
