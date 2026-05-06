# Round 16 Phase 2 Conflict 预审查（network 不依赖工作）

**触发**：项目负责人 EOD §1 [5] Network 不依赖工作可立即继续 + 立规 §2.4 Track B comparative-driven
**生成时间**：2026-05-06 EOD
**用途**：Phase 2 启动前提前识别冲突点 + 预定决策路径

---

## 1. 10 个 Phase 2 关键 PR 影响清单

| Phase | PR | 主题 | 主要文件 | upstream commits | 复杂度 |
|---|---|---|---|---|---|
| 2a | #2991 | read-your-writes StateBackend | `state.py` | 2 files / 55+/8- | 🟢 低 |
| 2a | #2980 | UTF-8 boundary truncation | `filesystem.py`/`sandbox.py` | 2 files / 90+/2- | 🟡 中 |
| 2a | #3031 | EOF newline mismatch | `filesystem.py` + 4 tests | 5 files / 246+/44- | 🟡 中 |
| 2c | #3035 | filesystem symlink hardening | `filesystem.py` + tests | 7 files / 581+/78- | 🔴 高（含 V2 父类风险） |
| 2c | #3036 | permission re-export | `permissions.py` | 1 file / 5+ | 🟢 低 |
| 2d | #2976 | skill module frontmatter | empty commit / 仅 description | 0 行实际 | 🟢 极低（empty commit 预案）|
| 2e | #3045 | CompiledSubAgent name | `subagents.py` + tests | 3 files / 275+/4- | 🟡 中 |
| 2f | #2695 | langsmith sandbox | `langsmith.py`/`sandbox.py` | 4 files / 449+/31- | 🔴 高 |
| **2b** | **#2892** | **profiles API 重构** | `profiles/*` 大规模重构 | **31 files / 6504+/870-** | 🔴🔴 **极高 (atomic cutover trigger)** |
| 2b | #3082 | GPT-5.5 profile | `profiles/_openai.py` | 2 files / 54+ | 🟡 中（依赖 #2892） |

---

## 2. 🔴🔴 Phase 2b #2892 — Atomic Cutover Trigger 深度分析

### 2.1 Upstream 重构架构

```text
fork master state:
  profiles/_harness_profiles.py (283 lines, 8 字段 _HarnessProfile single class)

upstream after #2892:
  profiles/__init__.py (refactored)
  profiles/_builtin_profiles.py (NEW, 233 lines)
  profiles/_keys.py (NEW, 42 lines)
  profiles/_openai.py (modified)
  profiles/harness/__init__.py (NEW, 22 lines)
  profiles/harness/harness_profiles.py (NEW, 1287 lines) ← 主体
  profiles/harness/_anthropic_haiku_4_5.py (NEW, 52 lines)
  profiles/harness/_anthropic_opus_4_7.py (NEW, 56 lines)
  profiles/harness/_anthropic_sonnet_4_6.py (NEW, 52 lines)
  profiles/harness/_openai_codex.py (NEW, 68 lines)
  profiles/provider/__init__.py (NEW, 15 lines)
  profiles/provider/_openai.py (NEW, 24 lines)
  profiles/provider/_openrouter.py (moved from profiles/_openrouter.py, 53 changes)
  profiles/provider/provider_profiles.py (NEW, 454 lines)
```

### 2.2 Fork 8 字段 vs Upstream 双 class 拆分

| Fork `_HarnessProfile` 字段 | Upstream 位置 | 字段保留 |
|---|---|---|
| `init_kwargs` | `HarnessProfile` 或 `ProviderProfile` | ✅ 保留 (58 处匹配) |
| `pre_init` | 同上 | ✅ (37) |
| `init_kwargs_factory` | 同上 | ✅ (29) |
| `base_system_prompt` | 同上 | ✅ (24) |
| `system_prompt_suffix` | 同上 | ✅ (34) |
| `tool_description_overrides` | 同上 | ✅ (30) |
| `excluded_tools` | 同上 | ✅ (16) |
| `extra_middleware` | 同上 | ✅ (22) |

**关键洞察**：upstream 拆分为 `HarnessProfile`（agent harness）+ `ProviderProfile`（model provider）双 class，每个 class 含部分 fork 8 字段子集。**Cherry-pick #2892 时需要在两个 class 之间分配 fork 字段**——这是 atomic cutover 的核心技术挑战。

### 2.3 Phase 2b Cutover 检查清单

- [ ] Cherry-pick #2892 前：pmagent 11 处 `_HarnessProfile` import + 8 处 `_resolve_extra_middleware` 全部 ready 切换
- [ ] Cherry-pick #2892 中：处理 `_harness_profiles.py` deletion conflict（fork 自定义版本）
- [ ] Cherry-pick #2892 后：8 字段全部在 HarnessProfile / ProviderProfile 中可访问
- [ ] Cherry-pick #3082 自动应用（依赖 #2892 完成）
- [ ] pmagent 立即触发 ≤30 min cutover SLA

---

## 3. Phase 2c #3035 — Filesystem Symlink Hardening

### 3.1 影响分析

- 7 files / 581+/78- — 大改动
- 含 `filesystem.py` + `permissions.py` + `protocol.py` + 多个 tests
- **与 fork `_convert_document_sync` 路径关联**（fork 在 filesystem.py 加 binary doc converter 路径）

### 3.2 预测冲突点

| fork 文件位置 | 与 #3035 冲突可能性 |
|---|---|
| `filesystem.py:414-570` (`_convert_document_sync` / `_convert_document_async`) | 🟡 中 — 不同 line 段，但同函数族 |
| `filesystem.py` 其他 read/write 路径 | 🔴 高 — #3035 改 line 1/168/180 含 imports + resolve 路径 |
| `permissions.py` | 🟡 中 — 与 fork `_PermissionMiddleware` 关联 |

### 3.3 预定决策路径

1. **优先**：手动 merge fork 既有 `_convert_document_sync` 与 upstream symlink hardening
2. **备选**：take theirs 接受 upstream 改动，fork 端 audit 是否仍兼容
3. **fallback**：skip + 记入 DEFERRED_BACKLOG Group A（与 #2978/#2992 等其他 SDK 主线一并）

---

## 4. Phase 2d #2976 — Skill Module Frontmatter (Empty Commit 预案)

### 4.1 实证

`git diff 2a9cd44f^ 2a9cd44f --stat` 返回空（commit object 存在但 0 文件 diff）。

### 4.2 预定路径

按 #2451 (Phase 1a) 同模式：`git cherry-pick --skip` + 落档到 PROGRESS.md Phase 2d 行（`docs(round16-progress):` 前缀）。

---

## 5. Phase 2 整体冲突预测总览

| Phase | 预期 cherry-pick 比 | 主要风险 | Buffer 建议 |
|---|---|---|---|
| 2a | 90%+ (3/3) | filesystem.py 跨 PR 冲突 (#3031) | 估时 1h（无 +50%）|
| 2c | 50%+ (1-2/2) | filesystem.py 与 fork _convert_document_sync 冲突 | **+50% buffer** = 1.5h |
| 2d | 100% (0/0 实际, empty commit) | empty commit 预案 | 估时 0.25h |
| 2e | 100% (1/1) | subagents.py 与 fork _ENABLE_SUBAGENT_LOGGING 关联 | **+100% buffer** = 1h（含 ping pmagent）|
| 2f | 80%+ (1/1) | langsmith sandbox 大改动 | 估时 0.5h |
| **2b** | **手动 merge** (1-2/2) | **profiles API 大重构 + atomic cutover** | **2-3h** |

**Phase 2 总估时**：6.5h（v3.2.1 估时一致）

---

## 6. Track B Comparative-driven 预警

### 6.1 跨 Phase filesystem.py 多重触动

- Phase 2a #2980 改 filesystem.py
- Phase 2a #3031 改 filesystem.py
- Phase 2c #3035 改 filesystem.py
- **Comparative gap 风险**：3 个 PR 在 filesystem.py 不同行段，但 cherry-pick 顺序影响 merge 难度
- **预定策略**：按 v3.2.1 §6.3 顺序 2a → 2c，监控每次 cherry-pick 是否 auto-merge
- **失败 fallback**：保留 fork `_convert_document_sync` (line 414-570) + 手动 merge upstream 改动

### 6.2 V2 父类 PR (#2976 / #3045) 与 pmagent 桶 2.5 协调

- Phase 2d (#2976) 修改 skills.py — pmagent 桶 2.3 V2 父类
- Phase 2e (#3045) 修改 subagents.py — pmagent 桶 2.4 V2 父类
- **Comparative gap 风险**：CTO push 后必须立即 ping pmagent 重跑 Drift Gate Dim 2
- **协调协议**：项目负责人 §3.1 已落档（push + Slack ping ≤5 min + pmagent 重跑 ≤T+5min）

---

## 7. Refs

- 项目负责人 EOD 5-6 §1 [5] Network 不依赖工作
- 立规 §2.4 Track B Comparative-driven
- 立规 §2.5 三维度 Drift Gate
- ROUND16_RISK_ASSESSMENT.md §6.2 依赖审视 + §6.3 跨 Phase filesystem.py flag
- ROUND16_DEFERRED_BACKLOG.md §1/§5 Group A 后置 PR

**生成者**：CTO（deepagents fork）
**前缀**：`docs(round16-progress):` 类（预审查报告）
