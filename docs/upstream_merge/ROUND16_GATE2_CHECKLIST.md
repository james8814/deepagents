# Round 16 Gate 2 红线测试 Checklist

**生成**：2026-05-05 Stage B 启动前（残留风险 #2 闭环）
**触发**：项目负责人 6 项裁决签署 + 多专家组 §三盲点建议 + ADR v5 #16 evidence-based
**用途**：Stage B Phase 2 全部完成后，Gate 2 红线测试 evidence 依据
**重要更新（2026-05-05 专家组裁决 + 项目负责人指令 \[4\] \[5\]）**：Phase 2 顺序重排 + 两个独立 Gate（Gate 1.5 + Phase 2b pre-condition）+ Path C scheduled cutover window。

> **Gate 拆分（深度审计 A1 修复）**：项目负责人指令 \[4\] 与 \[5\] 是**两个不同 Gate**，必须分开执行：
>
> - **Gate 1.5（§0）**：技术性 audit — Phase 2f 完成后、进 Phase 2b 之前，由委员会跑测试
> - **Phase 2b push 三重前置（§0'）**：协调 SLA — Gate 1.5 通过后、push 之前
>
> **执行先后**：Phase 2f → Gate 1.5 → Hold → 三重前置 → 预约窗口 push 2b → Gate 2

---

## 0. Gate 1.5 — 委员会 Audit（项目负责人指令 [4]，Phase 2f 完成后必跑）

**触发**：Phase 2a-2f 全部完成 + Stage B 进入 Hold 状态前。
**执行方**：委员会代表 + 质量团队（CTO 准备 evidence，但不能自我 audit）。
**通过条件**：三项 audit 全部 PASS，任一失败 → 不允许进 Phase 2b push。

### 0.1 11 项本地优越特性保护测试通过

- [ ] §1 表格 11 项保护断言全部 PASS（每项 a/b/c 子项：文件存在 + 签名不变 + 单测 PASS）
- [ ] evidence：`pytest -v -k "skills_v2 or state_schema or summarization_overwrite or converters or subagent_logging or permissions or harness_profile or tool_exclusion"` 输出留档

### 0.2 StateBackend read-your-writes 影响审计完成

- [ ] 新增 read-your-writes 测试 PASS（PR #2991）
- [ ] 既有 StateBackend 测试 100% PASS（无 regression）
- [ ] pmagent 端 audit：grep 57 处用法，标记任何"假设 write 后 read 看不到旧值"代码 — 清单空 = PASS

### 0.3 `_PermissionMiddleware` re-export 验证完成

- [ ] PR #3036 sync 后，`from deepagents.middleware.permissions import _PermissionMiddleware, FilesystemPermission` import 仍可工作
- [ ] pmagent 31 处 permission import 路径不变（fork 端验证）
- [ ] evidence：上方 §2.1 测试输出留档

### 0.4 Audit 结果落档

- [ ] 委员会出具 Gate 1.5 audit 报告（独立 markdown，含 PASS/FAIL 逐项 + 测试日志附件）
- [ ] 报告归档至 `docs/upstream_merge/ROUND16_GATE_1_5_AUDIT.md`
- [ ] **未通过 → CTO 不进 Phase 2b**，按指令 [7] 停止 + 回滚到 Gate 1 + 复盘 + 项目负责人授权后再进

---

## 0'. Phase 2b push 三重前置 Gate（项目负责人指令 [5]，push 瞬间前必须三项闭环）

**触发场景**：Gate 1.5 PASS 后，进入 "Hold at 2b" 状态，等三项闭环后才 push。
**执行方**：CTO（准备）+ pmagent（桶 2 sign-off）+ 项目负责人（窗口确认）。
**通过条件**：三项任一未闭环 → push 阻断（SLA 失败 = 业务停服延长）。

### 0'.1 pmagent 桶 2 V2 子类化完整验收（项目负责人 sign-off）

- [ ] pmagent 团队完成桶 2（summarization → skills → subagents V2 子类化，按 817b6ab audit 顺序）
- [ ] pmagent 主分支 invariant 测试 22/22 PASS
- [ ] pmagent 团队 ack 准备好接收 #2892 cutover
- [ ] **项目负责人本人 sign-off**（不接受 AI 代签）

### 0'.2 Path C 预约窗口确认

- [ ] 项目负责人本人与 CTO 协商出 2h 固定窗口（建议工作日 GMT+8 上午）
- [ ] 项目负责人本人在窗口内 on-call（**真人 in loop**，非 AI 代理）
- [ ] 窗口时间写入本文档 §0'.4
- [ ] 窗口外 push **NO-GO**

### 0'.3 cutover_dry_run.py baseline 通过

- [ ] cutover_dry_run.py 在 sync 分支 Phase 2f + Gate 1.5 PASS 状态下运行 PASS
- [ ] 11 + 8 处 import 切换路径预演无异常
- [ ] dry-run 输出留档作为窗口内 apply 的 baseline

### 0'.4 预约窗口（待项目负责人填写）

```yaml
预约窗口:
  日期: [TBD]
  开始: [TBD HH:MM GMT+8]
  结束: [TBD HH:MM GMT+8]
  项目负责人在线方式: [Slack handle / 电话 / 其他]
  CTO 在线方式: git push 通知 + 协调群
  应急回滚联络: [TBD]
```

**三项任一未闭环 → 2b 不 push。**

---

## 1. 11 项本地优越特性保护断言（核心红线）

每项需验证：(a) 文件存在 (b) 关键函数/类签名不变 (c) 行为单测 PASS。

| # | 特性 | 文件 | 关键断言 |
|---|---|---|---|
| 1 | SkillsMiddleware V2 (`load_skill`/`unload_skill`) | `libs/deepagents/deepagents/middleware/skills.py` | 行数 ≥ 1100；`expose_dynamic_tools` / `allowed_skills` / `skills_allowlist` 三参数仍在；V1 vs V2 prompt mutex 测试 PASS |
| 2 | `state_schema` 参数 | `libs/deepagents/deepagents/graph.py` | `create_deep_agent(state_schema=...)` 签名仍在；`test_state_schema_passed_to_create_agent` PASS |
| 3 | `skills_expose_dynamic_tools` 参数 | `libs/deepagents/deepagents/graph.py` | 签名仍在；V1/V2 路径分流测试 PASS |
| 4 | `create_summarization_middleware` factory | `libs/deepagents/deepagents/graph.py` | factory 函数仍可被外部 import；factory 接受 `truncate_args_settings` |
| 5 | Summarization Overwrite guard | `libs/deepagents/deepagents/middleware/summarization.py` | `isinstance(messages, Overwrite)` 分支仍在；测试 PASS |
| 6 | Converters (PDF/DOCX/XLSX/PPTX/Image/CSV/TXT/MD) | `libs/deepagents/deepagents/middleware/converters/` | 11 文件全部存在；`get_default_registry()` 返回 ≥ 7 converter；`detect_mime_type()` 正确路由 |
| 7 | `stream_writer` | （查找位置 — Gate 1.5 grep 验证） | stream_writer 实例化路径不变 |
| 8 | SubAgent logging gate | `libs/deepagents/deepagents/middleware/subagents.py` | `_ENABLE_SUBAGENT_LOGGING` env var 仍在；`_EXCLUDED_STATE_KEYS` 含 `subagent_logs / skills_loaded / skill_resources / _summarization_event` |
| 9 | `permissions` middleware | `libs/deepagents/deepagents/middleware/permissions.py` | `FilesystemPermission` dataclass 仍在；`_PermissionMiddleware` 类签名不变；67 单测 PASS |
| 10 | `harness_profiles` | `libs/deepagents/deepagents/profiles/_harness_profiles.py` | **⚠️ Phase 2b 重构点** — `_HarnessProfile` → `HarnessProfile` 重命名后，public API alias `_HarnessProfile = HarnessProfile` 必须存在以保兼容；fork 8 字段 → 7 字段重构通过 |
| 11 | `_ToolExclusionMiddleware` | `libs/deepagents/deepagents/middleware/_tool_exclusion.py` （class 在 line 31；导入由 `graph.py:32` 引用） | 被注入条件不变（A2 修复：原文档误写为 `profiles/__init__.py`） |

**Gate 2 通过条件**：11/11 全部 ✅。任一失败 = 阻塞合并。

---

## 2. 专家组追加加强项（§三盲点）

### 2.1 `_PermissionMiddleware` re-export 验证（PR #3036）

**背景**：upstream PR #3036 `fix(sdk): re-export filesystem permission for backwards compatibility` — pmagent 31 处 `_PermissionMiddleware`/`FilesystemPermission` import 必须 sync 后仍可工作。

**测试**：
```bash
cd libs/deepagents
python -c "
from deepagents.middleware.permissions import _PermissionMiddleware, FilesystemPermission
from deepagents import FilesystemPermission as FP_root  # re-export check
assert _PermissionMiddleware is not None
assert FilesystemPermission is not None
print('PR #3036 re-export OK')
"
```

**通过条件**：3 处 import 全部成功，无 `ImportError`。

### 2.2 `StateBackend` read-your-writes 行为审计（PR #2991）

**背景**：upstream PR #2991 `fix(sdk): support read-your-writes in StateBackend` — pmagent 57 处 `StateBackend` 用法可能依赖原行为。

**测试**：
```bash
# 单元测试：write 后立即 read 必须 visible
cd libs/deepagents && uv run pytest tests/unit_tests/middleware/test_state_backend.py -v -k "read_your_writes or write_then_read"
```

**通过条件**：
- 新增 read-your-writes 测试 PASS
- 既有 StateBackend 测试 100% PASS（无 regression）
- pmagent 端 audit：grep 57 处用法，标记任何"假设 write 后 read 看不到旧值"的代码（无则清单为空）

### 2.3 `graph.py` `state_schema` reducer 兼容性测试（LangGraph 专家追加）

**背景**：`graph.py` 在 master..upstream/main 有 19 次修改（最高频次），`state_schema` 参数是 fork 关键扩展点，reducer 行为变化会破坏跨 round 状态聚合。

**测试**：
```bash
cd libs/deepagents && uv run pytest tests/unit_tests/test_state_schema.py -v
# + integration: state_schema 跨 step reducer behavior
```

**通过条件**：
- `test_state_schema_passed_to_create_agent` PASS（Round 15 已晋升 mandatory）
- 自定义 `state_schema` 跨 step 状态合并行为不变

---

## 3. 测试运行 SOP

### 3.1 Venv 重建（深度审计 A7：当前 `/tmp/sdk-r15-venv` symlink 失效）

**Gate 1 / Gate 1.5 / Gate 2 启动前必做**：现有 `libs/deepagents/.venv` 是失效 symlink → `/tmp/sdk-r15-venv`（已不存在）。

```bash
# Pre-flight: 清理失效 symlinks + 重建 venv
cd "/Volumes/0-/jameswu projects/deepagents"

# 1) 清理 macOS exFAT 资源 fork（已知问题）
find .git/objects/pack -name "._*" -delete

# 2) 删除 5 个失效 symlinks
for pkg in libs/deepagents libs/cli libs/acp libs/evals libs/repl; do
  [ -L "$pkg/.venv" ] && [ ! -e "$pkg/.venv" ] && rm "$pkg/.venv"
done

# 3) 创建 round16 venv（外部 volume 用 /tmp 避免 ._* 污染）
uv venv --python 3.13 /tmp/round16-sdk-venv
ln -s /tmp/round16-sdk-venv libs/deepagents/.venv

# 4) Sync 依赖（UV_LINK_MODE=copy 避免 relink 问题）
cd libs/deepagents
UV_LINK_MODE=copy uv sync --reinstall --group test

# 5) Smoke check
uv run python -c "import deepagents; print(deepagents.__file__)"
```

**注意**：CLI/ACP/Evals/REPL 各包独立 venv，对应 Gate 1.5/2 测试范围（如需 CLI 测试需重复 1-4 在 libs/cli）。

### 3.2 Gate 2 红线全跑（Venv 就绪后）

```bash
# 1) Pre-flight: 确认在 sync 分支 + clean state
cd "/Volumes/0-/jameswu projects/deepagents"
git status  # 必须 clean
git rev-parse HEAD  # 必须 == Phase 2b push 完成的 commit

# 2) Gate 2 红线全跑
cd libs/deepagents
make test  # SDK 单测全跑（必须 0 fail）
cd ../cli && make test  # CLI 单测全跑
cd ../evals && make test  # Evals 单测全跑

# 3) 11 项保护点专项断言
cd "/Volumes/0-/jameswu projects/deepagents/libs/deepagents"
uv run pytest -v -k "skills_v2 or state_schema or summarization_overwrite or converters or subagent_logging or permissions or harness_profile or tool_exclusion"

# 4) 专家组追加 3 项
uv run pytest -v -k "permission_re_export or read_your_writes or state_schema_reducer"
```

**Gate 2 通过 = 11/11 + 3/3 + 全量 0 fail**

---

## 4. 失败处理

任一断言 FAIL：
1. 立即 `git revert` 引入失败的 Phase commit（per-phase rollback）
2. 在 sync 分支上调试，不动 master
3. 重跑 Gate 2 全套
4. 修复后再 push

---

## 5. Refs

- v3.2.1 §11 桶 3 验收标准
- 多专家组评审 §三 盲点（_PermissionMiddleware + StateBackend）
- ADR v5 #16 evidence-based audit
- Round 15 4 Phase + 2 Gate proven 模式
- pmagent 桶 1 验收报告 §6 atomic cutover SLA

**生成者**：CTO（deepagents fork）
**Stage B 启动**：6 项裁决签署后立即执行
