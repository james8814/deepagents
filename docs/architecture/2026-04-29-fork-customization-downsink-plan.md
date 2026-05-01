# Fork 定制下沉方案 — 让 deepagents fork 与上游实时同步

**日期**: 2026-04-29
**作者**: 架构师团队
**状态**: 待决策
**目标读者**: 项目负责人、架构师、研发主管、pmagent 业务团队

---

## 摘要

当前 `james8814/deepagents` fork 内嵌 11 项深度定制（与上游 diff ~3500 行），每轮上游同步耗时 2-6 小时。本方案把绝大部分定制下沉到下游 `pmagent` 项目（作为 `src/deepagents_ext/` 扩展模块），让 fork 与上游 diff 缩到 **< 50 行**，每轮同步耗时降至 **< 30 分钟**。预计 2-3 天完成迁移。

---

## 1. 问题定义（根因分析）

### 1.1 当前架构问题

- fork 内嵌 11 项深度定制（SkillsMiddleware V2、Converters、Upload Adapter V5、SubAgent stream_writer/logging、graph.py 参数扩展等）
- 定制散布在 SDK 内部多个模块，没有清晰的扩展边界
- 上游每次新增 commit 都可能与本地修改冲突
- Round 13 (114 commits) 耗时 7-9h，Round 14 (55 commits) 耗时 2.5h，Round 15 (83 commits) 耗时 ~5h
- 累计已合并 ~1069 commits 跨 15 轮，每轮都需要架构师+研发主管参与

### 1.2 期望状态

- fork 与上游 ~100% 同步（diff < 50 行）
- 本地定制集中在下游 pmagent 项目内
- 通过 LangChain/LangGraph/DeepAgents 提供的扩展机制实现（custom middleware / backend / state schema）
- 每轮上游同步成本降至 < 30 分钟（仅同步 hook 点的 trivial 冲突）

---

## 2. 本地 Fork 定制清单（精确盘点）

### 2.1 A 类 — 深度内嵌定制（fork 修改）

通过 `git diff upstream/main..master -- libs/deepagents/deepagents/` 实测：

| # | 定制项 | 位置 | Diff 行数 | 类型 |
| --- | --- | --- | --- | --- |
| 1 | **SkillsMiddleware V2** (load_skill / unload_skill / expose_dynamic_tools / allowed_skills / skill_resources / V1V2 prompt 互斥) | `middleware/skills.py` | 673 行 | 整类替换（1362 vs 上游 ~834） |
| 2 | **Converters 子包** (PDF/DOCX/XLSX/PPTX/CSV/image/text + registry + base + utils) | `middleware/converters/` 11 文件 | 整目录新增 | 全新模块 |
| 3 | **filesystem.py read_file 内嵌 Converter 调用** | `middleware/filesystem.py` | 427 行 | 内部分支注入 |
| 4 | **Upload Adapter V5** | `upload_adapter.py` | 691 行 | 全新模块 |
| 5 | **SubAgent stream_writer + 进度事件** + **logging + 敏感字段脱敏** + **TypedDict 扩展 (`skills_allowlist`)** | `middleware/subagents.py` | 468 行 | 内部逻辑增强 + TypedDict 扩展 |
| 6 | **graph.py 参数与装配定制** (`state_schema`, `skills_expose_dynamic_tools`, `skills_allowlist` wiring, `create_summarization_middleware` factory) | `graph.py` | 458 行 | 主入口签名+装配 |
| 7 | **Memory isawaitable 兼容** | `middleware/memory.py` | 少量 | 异步兼容 hack |
| 8 | **Summarization Overwrite guard** | `middleware/summarization.py` | 9 行 | 防御性修复 |
| 9 | **`_EXCLUDED_STATE_KEYS` 扩展** | `middleware/subagents.py` | ~5 键 | 状态隔离 |

### 2.2 B 类 — 已上游接受（无需关心）

permissions、harness_profiles、_ToolExclusionMiddleware（Round 13）、SubAgent.response_format（Round 14）、model=None deprecation（Round 14）、SkillSource labelled（Round 15）。

---

## 3. 下游 pmagent 实际依赖核查

通过 grep 对 `/Volumes/0-/jameswu projects/langgraph_test/pmagent` 实测：

| Fork 特性 | 下游使用位置 | 依赖度 |
| --- | --- | --- |
| `state_schema=PMAgentState` | `agent.py:716` | **强** — 没它无法注入 PMAgentState 自定义字段 |
| `expose_dynamic_tools=True` | `agent.py:606,652` | **强** — 强制 V2 模式 |
| `allowed_skills` | `agent.py:653` | **强** |
| SubAgent `skills_allowlist` 字段 | `agent.py:324,653` | **强** — TypedDict 字段 |
| `subagent_logs` 状态字段 | `state/__init__.py:129` | **强** — 依赖 fork stream_writer 写入 |
| `upload_files` / `UploadResult` | `tools/ppt/save_image.py:77`, `cli/memory_manager.py:139`, `agents/deep_research/nodes.py:1611` | **强** |
| `FilesystemBackend`, `StateBackend`, `CompositeBackend` | `config.py` 多处 | 中 |

**结论**：下游对 fork 定制有**深度依赖**。下沉方案必须保证下游业务代码不被破坏。

---

## 4. 可行性矩阵（每项定制的下沉路径）

| # | 定制项 | 下沉机制 | 可行性 | 复杂度 |
| --- | --- | --- | --- | --- |
| 1 | SkillsMiddleware V2 | 整类移植到 `pmagent/src/deepagents_ext/skills_v2.py`，作为独立 `AgentMiddleware` 子类 | ✅ 完全可行 | 中 |
| 2 | Converters 子包 | 整目录复制到 `pmagent/src/deepagents_ext/converters/` | ✅ 完全可行 | 小 |
| 3 | filesystem.py read_file 内嵌 Converter | `PMFilesystemBackend(FilesystemBackend)` 子类，重写 `download_files` / `adownload_files`，在返回前判定 + 调用 converter | ✅ 完全可行（BackendProtocol 多态） | 中 |
| 4 | Upload Adapter V5 | 直接复制为独立模块 | ✅ 完全可行 | 小 |
| 5 | SubAgent stream_writer / logging | `PMSubAgentMiddleware(SubAgentMiddleware)` 子类重写 `task` / `atask`，或自己装配 SubAgent 调用链 | ⚠️ 部分可行（SDK 内部是闭包，需重新装配） | 大 |
| 6 | graph.py 参数定制 | `state_schema`：上游已支持；其他参数（`skills_expose_dynamic_tools` / `skills_allowlist`）通过**直接构造 SkillsMiddleware 实例 + middleware=[]** 注入（pmagent 已经这么用） | ✅ 已可行 | 小 |
| 6b | `create_summarization_middleware` factory | 不通过 SDK 自动装配，自己构造 `PMSummarizationMiddleware` 通过 `middleware=` 传入 | ⚠️ 副作用：会与 SDK 默认 `SummarizationMiddleware` 重复 | 中 |
| 7 | Memory isawaitable | `PMMemoryMiddleware(MemoryMiddleware)` 子类重写异步分支 | ✅ 完全可行 | 小 |
| 8 | Summarization Overwrite guard | `PMSummarizationMiddleware(SummarizationMiddleware)` 子类（同 #6b 副作用） | ⚠️ 同上 | 小 |
| 9 | SubAgent.skills_allowlist TypedDict | `PMSubAgent(SubAgent)` 子 TypedDict（运行时是 dict，SDK 不校验额外字段） | ✅ 完全可行 | 小 |
| 10 | `_EXCLUDED_STATE_KEYS` 扩展 | **必须留 fork**（SDK 内部常量，影响 subagent 状态隔离；外部无法注入） | ❌ 不可下沉 | — |

---

## 5. 三个候选方案对比

### 方案 A — 完全下沉（激进）

- pmagent 不调用 `create_deep_agent`，自己用 `create_agent + middleware list` 装配
- 所有 PM 定制 middleware 都在 pmagent 内
- fork 完全跟上游同步
- **代价**：失去 `create_deep_agent` 提供的开箱即用 + 持续接收上游对装配逻辑的优化（如 Round 13 的 `_PermissionMiddleware` 自动 append）
- **工作量**：3-5 天

### 方案 B — 分层下沉（务实，推荐）

- 大部分定制下沉到 `pmagent/src/deepagents_ext/`
- fork 仅保留必要的"hook 点"（约 30-50 行）：`_EXCLUDED_STATE_KEYS` 扩展
- 上游同步成本：从每轮数小时降到 < 30 分钟
- **工作量**：2-3 天

### 方案 C — 仅下沉独立模块（保守）

- 只下沉 converters（独立子包）和 upload_adapter（独立模块）
- 其他定制保留在 fork
- 上游同步成本：略减少，但仍是数小时
- **工作量**：0.5-1 天

**强烈推荐方案 B** — ROI 最高、风险可控、可演进。

---

## 6. 推荐方案（方案 B）— 详细设计

### 6.1 设计原则

1. **fork 保留最小 hook**：只留无法外部注入的 SDK 内部常量/类型/装配代码
2. **下沉为 deepagents 扩展模块**：在 pmagent 中建立 `deepagents_ext/` 包，集中所有定制
3. **业务代码不受影响**：通过 facade 保持 import 路径稳定，下游业务零修改（仅替换 `from deepagents` 为 `from src.deepagents_ext`）
4. **持续可演进**：未来上游接受某项定制（如 Round 14 接受 `state_schema`），可平滑从 ext 移除该项

### 6.2 目标结构

```text
pmagent/src/deepagents_ext/                    # 新增
├── __init__.py                                 # 暴露 facade API
├── skills_v2.py                                # 整类移植 SkillsMiddleware V2
├── converters/                                 # 整目录移植
│   ├── __init__.py, base.py, registry.py
│   ├── pdf.py, docx.py, xlsx.py, pptx.py
│   ├── csv.py, image.py, text.py, utils.py
├── filesystem.py                               # PMFilesystemBackend(FilesystemBackend)
│                                               # 重写 download_files 调用 converters
├── subagent_observability.py                   # stream_writer + logging 装配辅助
│                                               # 提供 with_subagent_observability(subagents) 函数
├── summarization.py                            # PMSummarizationMiddleware (Overwrite guard)
├── memory.py                                   # PMMemoryMiddleware (isawaitable)
├── upload_adapter.py                           # V5 直接复制
└── factory.py                                  # create_pm_deep_agent() 包装 create_deep_agent
                                                # 自动注入 PMFilesystemBackend、V2 SkillsMiddleware 等
```

### 6.3 Fork 简化目标（< 50 行 diff）

仅保留：

```python
# libs/deepagents/deepagents/middleware/subagents.py
_EXCLUDED_STATE_KEYS = {
    "messages", "todos", "structured_response",
    "skills_metadata", "memory_contents",
    # === 本地扩展（pmagent 状态隔离）===
    "subagent_logs",          # 5 keys for downstream state isolation
    "skills_loaded",
    "skill_resources",
    "_summarization_event",
    "context_layers",         # pmagent Context 模块
    "retrieval_traces",
    "memory_candidates",
}
```

这是唯一无法外部注入的 hook 点（其他都可下沉）。

---

## 7. 迁移路 Roadmap（4 阶段，2-3 天）

### Phase 1 — 独立模块下沉（半天）

**目标**：B 类独立模块直接复制（无依赖、零副作用）

- [ ] Copy `converters/` → `pmagent/src/deepagents_ext/converters/`
- [ ] Copy `upload_adapter.py` → `pmagent/src/deepagents_ext/upload_adapter.py`
- [ ] 在 pmagent 中替换所有 `from deepagents.upload_adapter import ...` → `from src.deepagents_ext.upload_adapter import ...`
- [ ] 同步 fork 删除 `converters/`、`upload_adapter.py`（这两块不再依赖 fork）

**验收**：pmagent 测试全绿，fork 单测仍通过（converters 相关测试需迁移到 pmagent）。

### Phase 2 — Middleware 包装层（1 天）

**目标**：把 SkillsMiddleware V2、PMSummarizationMiddleware、PMMemoryMiddleware 移植成独立 middleware

- [ ] 移植 `skills.py` 1362 行 → `pmagent/src/deepagents_ext/skills_v2.py`
  - 保留所有 V2 特性（load_skill/unload_skill/expose_dynamic_tools/allowed_skills/V1V2 prompt 互斥）
  - 状态字段使用 PrivateStateAttr（与上游 SkillsMiddleware 共存）
- [ ] 创建 `PMSummarizationMiddleware`（Overwrite guard）
- [ ] 创建 `PMMemoryMiddleware`（isawaitable 兼容）
- [ ] 创建 `PMFilesystemBackend(FilesystemBackend)` — 重写 `download_files`/`adownload_files`，在返回前调用 converter

**验收**：pmagent 业务测试全绿，新 middleware 单测覆盖。

### Phase 3 — SubAgent 可观测性下沉（1 天，最棘手）

**目标**：stream_writer + logging 不再依赖 fork

**方案选择**:

- **方案 3A（推荐）**：在 pmagent 直接用 `create_agent + 自定义装配` 替代 `create_deep_agent`，把 SubAgent 调用逻辑放在 pmagent 内，完全控制 stream/log。代价：失去 SDK 自动装配的便利。
- **方案 3B**：`PMSubAgentMiddleware(SubAgentMiddleware)` 子类重写 task/atask（需深度理解 SDK 内部）。代价：未来 SDK 重构 task 内部时仍需跟进。

建议先用 **3A**（更彻底，未来维护成本低）。

**验收**：subagent_logs 状态字段写入正常，前端 SubAgent 进度展示无回归。

### Phase 4 — Fork 反向清理（半天）

**目标**：fork 删除所有已下沉的代码，diff 缩到 < 50 行

- [ ] 在 fork 中（新分支 `feat/minimize-fork`）：
  - 删除 `converters/`
  - 删除 `upload_adapter.py`
  - 还原 `skills.py` 到上游版本
  - 还原 `filesystem.py` 到上游版本（删除 converter 内嵌）
  - 还原 `subagents.py` 到上游版本（删除 stream_writer/logging）—— 但**保留 `_EXCLUDED_STATE_KEYS` 扩展**
  - 还原 `graph.py` 到上游版本（删除参数扩展，恢复 `SummarizationMiddleware` 直接构造）
  - 还原 `memory.py`、`summarization.py`
- [ ] 跑测试：确保 fork 与上游兼容（除 `_EXCLUDED_STATE_KEYS` 5 行 diff 外）
- [ ] 验证 pmagent 完整业务链路（端到端测试）
- [ ] Round 16 时间预算：< 30 分钟

**验收**：`git diff upstream/main..master` 行数 < 50；pmagent 端到端测试全绿。

---

## 8. 风险与缓解

| 风险 | 严重性 | 缓解措施 |
| --- | --- | --- |
| Phase 3 SubAgent 重写引入回归 | 🔴 高 | 全面集成测试 + 灰度切换（保留 fork 备份分支） |
| `_EXCLUDED_STATE_KEYS` 仍需 fork 维护 | 🟡 中 | 这 5 行是不可避免的最小 hook，可接受 |
| SDK 自动装配的默认 SummarizationMiddleware 与 pmagent 自己的 PM 版本叠加 | 🟡 中 | 在 PM agent factory 中显式禁用 SDK 默认（如可能）或确保 PM 版本幂等 |
| 下游业务代码大量依赖 fork API 路径 | 🟡 中 | 通过 `deepagents_ext.__init__.py` facade 保持 import 路径稳定 |
| 移植后状态字段（subagent_logs 等）reducer 行为变化 | 🟡 中 | Phase 2/3 时严格按现有 reducer 复制，不优化 |
| 上游某项 API 重命名导致 ext 模块失配 | 🟢 低 | ext 模块使用稳定的 SDK 公共 API；私有 API 调用集中标注 |

---

## 9. 收益评估

| 指标 | 现状 | 方案 B 之后 |
| --- | --- | --- |
| Fork 与上游 diff | ~3500 行 | **< 50 行** |
| 上游同步耗时 | 2-6 小时/轮 | **< 30 分钟/轮** |
| 上游同步冲突文件 | 5-15 个 | **0-1 个** |
| 下游业务代码改动 | — | 仅 import 路径替换，约 30 处 |
| 总迁移工作量 | — | 2-3 天 |
| 长期维护成本 | 高（每轮被动跟进） | 低（fork 几乎自动同步，定制独立演进） |

按当前节奏（每月 1-2 轮上游同步，每轮 3-5 小时），方案 B 在 1-2 个月内即可回本，之后每轮节省 1.5-5.5 小时。

---

## 10. 决策建议

**强烈推荐方案 B**，理由：

1. **ROI 最高**：2-3 天投入换来未来每轮节省 1.5-5.5 小时
2. **架构清晰**：定制与上游解耦，符合关注分离原则
3. **可演进**：上游接受某项定制后，可平滑从 ext 移除
4. **风险可控**：分 4 阶段，每阶段独立可验证、可回滚

**不推荐方案 A（完全下沉）**：放弃 `create_deep_agent` 装配收益太大，未来跟随上游改进会变难。

**不推荐方案 C（保守）**：减负有限，根本问题（SkillsMiddleware V2 + graph.py 定制）未解决。

---

## 11. 后续步骤

- [ ] 项目负责人审批本方案
- [ ] 研发主管分配 Phase 1-4 工作量
- [ ] 启动 Phase 1（独立模块下沉，半天）
- [ ] Phase 1 完成后评估，决定是否继续 Phase 2-4
- [ ] 全部完成后，Round 16 用真实上游同步验证耗时下降效果

---

## 附录 A — 关键引用

- Fork 与上游差异统计：`git diff upstream/main..master --stat`（实测 ~3500 行）
- 下游依赖位置：通过 grep `state_schema|skills_allowlist|expose_dynamic_tools|upload_files|subagent_logs` 定位
- 历轮上游合并耗时：见 `docs/upstream_merge/ROUND{13,14,15}_PROGRESS.md`
- 11 项本地优越特性清单：见 `MEMORY.md` 中"Local Superiority Features"章节
