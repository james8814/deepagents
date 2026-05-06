# Round 16 Gate 1.5 Audit Template — 委员会审查准备清单

**触发**：项目负责人 EOD §1 [5] Network 不依赖工作 + 指令 [4] Gate 1.5 audit (5-11 Mon 12:00 due)
**生成时间**：2026-05-06 EOD
**用途**：Phase 2f 完成后、Phase 2b push 之前的委员会 audit 提交模板

---

## 1. Gate 1.5 Audit 范围（项目负责人指令 [4]）

按 ROUND16_GATE2_CHECKLIST.md §0 Gate 1.5 三项：

| # | Audit 项 | 失败处置 |
|---|---|---|
| 1 | 11 项本地优越特性保护测试 | 任一失败 → 停止 + 不进 Phase 2b |
| 2 | StateBackend read-your-writes 影响审计 | 同上 |
| 3 | `_PermissionMiddleware` re-export 验证 | 同上 |

**Gate 1.5 通过 = 4 项 audit（含 §0.4 audit 报告落档）全部 PASS**。

---

## 2. 11 项本地优越特性保护断言 — 测试清单

### 2.1 测试运行 SOP

```bash
# 1) Pre-flight: venv 重建（按 ROUND16_GATE2_CHECKLIST §3.1）
cd "/Volumes/0-/jameswu projects/deepagents/libs/deepagents"
[ -L .venv ] && rm .venv
uv venv --python 3.13 /tmp/round16-sdk-venv
ln -s /tmp/round16-sdk-venv .venv
UV_LINK_MODE=copy uv sync --reinstall --group test

# 2) 11 项保护点测试（pytest -k 过滤）
uv run pytest tests/unit_tests -v -k "skills_v2 or state_schema or summarization_overwrite or converters or subagent_logging or permissions or harness_profile or tool_exclusion or upload_adapter or memory_isawaitable"
```

### 2.2 11 项保护断言模板

| # | 特性 | 文件 | 关键断言 | 测试命令 |
|---|---|---|---|---|
| 1 | SkillsMiddleware V2 | `middleware/skills.py` | 行数 ≥ 1100; `_create_load_skill_tool` + `_create_unload_skill_tool` 存在; `expose_dynamic_tools`/`allowed_skills`/`skills_allowlist` 三参数 | `pytest -k skills_v2_dynamic_loading` |
| 2 | `state_schema` 参数 | `graph.py:475` | `create_deep_agent(state_schema=...)` 签名仍在 | `pytest -k test_state_schema_passed_to_create_agent` |
| 3 | `skills_expose_dynamic_tools` 参数 | `graph.py` | 5 处 grep 匹配; V1/V2 路径分流测试 PASS | `pytest -k v1_v2_path_split` |
| 4 | `create_summarization_middleware` factory | `summarization.py:1104` | factory 函数可外部 import + 接受 `truncate_args_settings` | `pytest -k summarization_factory` |
| 5 | Summarization Overwrite guard | `summarization.py:517` | `isinstance(messages, Overwrite)` 分支仍在; 测试 PASS | `pytest -k overwrite_guard` |
| 6 | Converters | `middleware/converters/` | 11 .py 文件全部存在; `get_default_registry()` 返回 ≥ 7 converter; `detect_mime_type()` 正确路由 | `pytest -k converters` |
| 7 | `stream_writer` | （Gate 1.5 grep 验证位置） | 实例化路径不变 | `grep stream_writer middleware/` |
| 8 | SubAgent logging gate | `middleware/subagents.py` | `_ENABLE_SUBAGENT_LOGGING` env var 仍在; `_EXCLUDED_STATE_KEYS` 完整 | `pytest -k subagent_logging` |
| 9 | `permissions` middleware | `middleware/permissions.py` | `FilesystemPermission` dataclass + `_PermissionMiddleware` 类签名不变; 67 单测 PASS | `pytest -k permissions and not re_export` |
| 10 | `harness_profiles` | `profiles/_harness_profiles.py` | 8 字段保留; **⚠️ Phase 2b 重构后** public alias `_HarnessProfile = HarnessProfile` 必须存在 | `pytest -k harness_profile` |
| 11 | `_ToolExclusionMiddleware` | `middleware/_tool_exclusion.py:31` | class 仍存在; 由 `graph.py:32` 导入; 注入条件不变 | `pytest -k tool_exclusion` |

---

## 3. 专家组追加 2 项加强断言

### 3.1 StateBackend read-your-writes 审计（PR #2991）

**测试**：
```bash
cd libs/deepagents
uv run pytest tests/unit_tests/middleware/test_state_backend.py -v -k "read_your_writes or write_then_read"
```

**通过条件**：
- 新增 read-your-writes 测试 PASS
- 既有 StateBackend 测试 100% PASS（无 regression）
- pmagent 端 audit：grep 57 处用法（pmagent 责任）→ 标记任何"假设 write 后 read 看不到旧值"代码 → 清单空 = PASS

### 3.2 `_PermissionMiddleware` re-export 验证（PR #3036）

**测试**：
```bash
uv run python -c "
from deepagents.middleware.permissions import _PermissionMiddleware, FilesystemPermission
from deepagents import FilesystemPermission as FP_root
assert _PermissionMiddleware is not None
assert FilesystemPermission is not None
print('PR #3036 re-export OK')
"
```

**通过条件**：3 处 import 全部成功，无 `ImportError`。

---

## 4. Audit 报告输出格式

### 4.1 Gate 1.5 Audit Report（落档至 `docs/upstream_merge/ROUND16_GATE_1_5_AUDIT.md`）

模板：

```markdown
# Round 16 Gate 1.5 Audit Report — 委员会审查结果

**Audit 时间**：YYYY-MM-DD
**Audit 执行**：CTO（准备 evidence）+ 委员会代表（独立 audit）+ 质量团队
**Phase 2f 完成 commit**：HEAD = SHA
**Audit baseline**：sync 分支 + venv `/tmp/round16-sdk-venv`

## 1. 11 项保护测试结果

| # | 特性 | 测试结果 | 备注 |
|---|---|---|---|
| 1 | SkillsMiddleware V2 | ✅ PASS | N tests |
| ... | ... | ... | ... |
| 11 | _ToolExclusionMiddleware | ✅ PASS | N tests |

## 2. 专家组追加 2 项加强

| # | 项 | 测试结果 |
|---|---|---|
| 2.1 | StateBackend read-your-writes | ✅/❌ |
| 2.2 | _PermissionMiddleware re-export | ✅/❌ |

## 3. 全量回归测试

- SDK unit tests: X PASS / Y SKIP / Z FAIL
- CLI unit tests: ...
- Evals unit tests: ...

## 4. Audit 决议

- ✅ Gate 1.5 PASS → 进入 Hold at 2b
- ❌ Gate 1.5 FAIL → 停止 + 回滚 + 项目负责人授权后再进
```

---

## 5. CTO 自检 4 项（Phase 2b push 前最后 last-mile）

按项目负责人 §9 三层 Production Scope 防线 L3：

- [ ] Production middleware stack 已切到 V2（pmagent 桶 2.5.3 production swap 完成）
- [ ] `agent.py:603, 651-658` 已切到 V2 factory（pmagent 桶 2.5 + 桶 2.6 NEW v6）
- [ ] cutover-state 模拟测试 PASS（pmagent 桶 2.5.5 cutover-state validation 完成）
- [ ] pmagent L1 报告含 production callsite 追溯

任一未通过 → Phase 2b push 阻断。

---

## 5A. Multi-source Measurement 强制（立规 §2.8 v2 + §2.9 适用）

**触发**：项目负责人 EOD 5-6 §2 APPROVE Track B B4 关键发现 + 立规 §2.7 即时全量生效。
**作用域**：Gate 1.5 audit 中任何 LOCKED baseline 类测量（PASS count / V2 invocation / 性能基准等）。

### 5A.1 立规 §2.8 v2 — Multi-source Measurement 4 项强制

**强制 1**：全 baseline 覆盖（NEW）

- 11 项本地特性保护测试 + StateBackend RYW + `_PermissionMiddleware` re-export 测试中
- 任一 LOCKED baseline 必须用 ≥2 measurement methods 验证
- 不允许选择性应用（如只测 11 项保护而不测加强项）

**强制 2**：Method consistency

- 同次 audit 中所有 baselines 必须用同一 method
- **Gate 1.5 推荐 Method**：pytest count + pytest-cov coverage % + ast.parse class/function count（三 source 三角实证）
- 避免 mixed method（如部分用 pytest count 部分用 grep）

**强制 3**：Sanity check ratios（基于 pmagent 11th round 2:1 实证）

- 跨方法测量必须报告 method 间比例
- 比例非 1:1 时必须 escalate 调查（baseline 是否含 noise）
- 推荐 sanity ratio：pytest -v count vs ast.parse function/class count vs pytest -k filtered count

**强制 4**：First-triangulation lock

- Multi-source 三角实证完成 → baseline LOCKED
- 后续 audit re-run 不允许 silent re-baseline
- LOCKED baseline 修正诉求 → 项目负责人书面 escalate（按 §2.9）

### 5A.2 立规 §2.9 — Anomaly vs Baseline 调查协议适用

Gate 1.5 audit baseline LOCK 后：

| 场景 | 处置 |
|---|---|
| A：测量值偏离 LOCKED baseline | 立即 stop + 报告（不允许"先调查再报警"） |
| B：测量值偏离但怀疑 baseline 错 | LOCK 前可 fast-track investigation ≤10 min；**LOCK 后场景 B 不再适用** — 只允许 stop + 报告 |
| LOCK 后 baseline 修正 | 必须项目负责人书面 escalate，不允许 silent re-baseline |

### 5A.3 CTO Gate 1.5 audit 提交前 4 项自检

按 §2.8 v2 + §2.9 强制：

- [ ] 每个 baseline 来源 method 已 inline（如 "Skills V2 protection: pytest -v count = N1, ast.parse class count = N2, pytest-cov line% = N3, sanity ratio 1:1:_"）
- [ ] 多 source 测量值已对照（method 间比例 inline + sanity check passed）
- [ ] baseline LOCK 时点已记录（commit hash + datetime）
- [ ] §2.4 v2 RED/AMBER 5 维度首次必含已遵守（任何 audit 中 RED/AMBER finding 含发现 + 修复 + 来源 + 可追溯 + 严重度）

### 5A.4 Audit 报告输出格式增补（§4.1 模板补充）

```markdown
## 1. 11 项保护测试结果（含 multi-source baseline）

| # | 特性 | pytest count | ast.parse | pytest-cov % | Sanity ratio | LOCKED at |
|---|---|---|---|---|---|---|
| 1 | SkillsMiddleware V2 | N1 | N2 | %1 | 1:1:_ ✅ | commit / datetime |
| ... | ... | ... | ... | ... | ... | ... |

**Multi-source consistency**：全部 11 项 sanity ratio 1:1:_ 内 → baseline LOCKED
**§2.9 LOCK 后限制**：自此 audit 报告 commit 起，silent re-baseline 禁止
```

---

## 6. Audit 时序 SLA

```text
T-72h (5-10 Sun 10:00 GMT+8): Pre-flight Gate (pmagent 桶 2.5.4 soak 进行中)
T-48h (5-11 Mon 10:00 GMT+8): Gate 1.5 audit 提交 due ⭐ ← CTO 责任
  ├── CTO 完成 Phase 2c-2f
  ├── 跑 §2.1 测试 SOP
  ├── 输出 ROUND16_GATE_1_5_AUDIT.md
  └── 委员会 24h audit 响应窗口
T-24h (5-12 Tue 10:00 GMT+8): Final Go/No-Go
T-30min (5-13 Wed 09:30 GMT+8): Window-ready
T+0 (5-13 Wed 10:00 GMT+8): ⚛️ Atomic cutover ⚡
```

**Gate 1.5 audit 截止**：项目负责人 §7.1 给出 5-11 Mon 12:00 GMT+8（含 24h response window，**实际反推 5-11 Mon 10:00 — 详见 GOVERNANCE.md §5 timeline**）。CTO 保守按 5-11 Mon 10:00 准备。

---

## 7. CTO 准备清单（network 恢复前可做）

- [x] 模板生成（本文档）
- [ ] 11 项保护断言 grep 路径预检（network 恢复后跑 pytest 前）
- [ ] StateBackend RYW + `_PermissionMiddleware` re-export 测试模拟
- [ ] Audit 报告 boilerplate 起草
- [ ] 与 pmagent 协调（Phase 2d/2e push 时 ping）

---

## 8. Refs

- ROUND16_GATE2_CHECKLIST.md §0 Gate 1.5 + §3.1 venv 重建 SOP
- 项目负责人 ULTRATHINK 裁决 §Q1 + §7.1 + §9 三层防线
- 立规 §2.4 双轨 + §2.5 三维度 + §2.7 即时全量 + §2.8 multi-source measurement

**生成者**：CTO（deepagents fork）
**前缀**：`docs(round16-progress):` 类（audit 准备模板）
