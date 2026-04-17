# Round 14 上游合并进度

**日期**: 2026-04-17
**分支**: `upstream-sync-round14`
**范围**: `a9e6e4f7..51f15324` (55 upstream commits)

## 总结

| 指标 | 值 |
|------|-----|
| 上游 commits 总数 | 55 |
| 已合并 | 52 |
| 跳过 (release) | 3 |
| 冲突解决 | 2 文件 |
| 本地修复 commits | 3 |
| 新增测试 | +123 (4584→4707) |

## 执行顺序

### Phase 1a: Deps bump (28 commits) ✅
cryptography, langsmith 0.7.31, pytest 9.0.3, pillow 12.2.0, python-multipart 0.0.26, uv groups

### Phase 1b: CLI/REPL (10 commits, skip 1) ✅
- user scoped memory (+534 行 deploy 增强)
- O(1) MessageStore lookups
- inline argument hints
- throttle update notification
- REPL foreign object interface + tool runtime

### Phase 1c: Evals/ACP/CI (10 commits + 1 fix) ✅
- more complex tool usage tasks
- remove old integration tests
- ACP upper bound
- CI integration test workflow

### Gate 1 ✅
- SDK 1251p / CLI 3064p / Evals 239p / ACP 76p / REPL 69p
- langsmith sandbox import smoke: OK
- uv lock --check: OK
- 修复: conftest.py 添加 `_register_theme_variables` + `_provide_app_context` (textual 8.2.3 CSS 变量需要)
- 修复: completion test `/re` → `/rem` (避免 /reload vs /remember 歧义)

### Phase 2: SDK 核心 (4 commits) ✅
- A1: `149df415` model=None deprecation warning (graph.py + pyproject.toml filterwarnings)
- A2: `6e57731f` SubAgent response_format (TypedDict + JSON 序列化)
- A4: `48696454` xfail langsmith sandbox tests
- A3: `badc4d39` skill prompt limit=1000 (auto-merge, 无冲突)

冲突解决:
- subagents.py: 合并 imports (local logging/os/warnings + upstream dataclasses/json)
- test_subagent_middleware.py: 接受上游版本

## 最终测试结果

| 包 | 通过 | 跳过 | xfailed | xpassed | 失败 |
|----|------|------|---------|---------|------|
| SDK | 1258 | 73 | 12 | 3 | 0 |
| CLI | 3065 | 1 | 0 | 0 | 0 |
| Evals | 239 | 0 | 0 | 0 | 0 |
| ACP | 76 | 0 | 0 | 0 | 0 |
| REPL | 69 | 0 | 1 | 0 | 0 |
| **合计** | **4707** | **74** | **13** | **3** | **0** |

## 新增上游特性

1. SubAgent `response_format` — 结构化输出 (ToolStrategy/ProviderStrategy/AutoStrategy)
2. CLI user scoped memory — per-user writable AGENTS.md in deploy
3. `model=None` DeprecationWarning — 未来将要求显式指定 model
4. Skill loading limit=1000 — prompt 指导 agent 读 SKILL.md 时增大行数
5. REPL foreign object interface + `+/-` operators
6. CLI inline argument hints for slash commands
7. O(1) MessageStore lookups (性能优化)
