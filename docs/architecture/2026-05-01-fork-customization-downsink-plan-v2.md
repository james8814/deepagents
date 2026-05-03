> ⚠️ **HISTORICAL 2026-05-02** — 本文档（v2 / Plan D 提出版）**已被 Plan H+ 取代**。
>
> v2 提出 Plan D（fork 内部重构）作为 Plan B 的替代。后续演进至 v3（三轮加强）→ v4-rev2（Plan E++）→ Plan H → **Plan H+（终局）**。
>
> **当前权威方案**：[`2026-05-02-plan-h-plus-final.md`](2026-05-02-plan-h-plus-final.md)
> **决策档案**：[`decisions/0002-fork-customization-strategy.md`](decisions/0002-fork-customization-strategy.md)
>
> 本文档保留为**早期决策档案**。

---

# Fork 定制下沉方案 v2 — 经核实修订（HISTORICAL — 已被 Plan H+ 取代）

**日期**: 2026-05-01
**作者**: 架构师团队
**状态**: 修订版（v1 已与 deepagents 研发团队、pmagent 团队各评审一轮）
**v1 文档**: `2026-04-29-fork-customization-downsink-plan.md`
**目标读者**: 项目负责人、架构师、研发主管、pmagent 业务团队、deepagents fork 团队

---

## 0. 修订摘要

v1 在两个团队评审 + 实地代码核查后，发现**两个前提需要修订**。本 v2 在保留 v1 目标不变的前提下，调整了方案选型与执行路径。

### 0.1 v1 与 v2 的差异

| 维度 | v1 假设 | 核实后事实 |
|---|---|---|
| pmagent 与 fork 关系 | pmagent 已有平行实现，方案是"把 fork 能力合进 pmagent" | pmagent 是 fork 的**纯消费者**；4 个看似平行的模块（~2772 行）实为**孤立死代码**，仅测试引用 |
| 推荐方案 | 方案 B：下沉到 pmagent `src/deepagents_ext/` 命名空间 | **方案 D：在 fork 内部重组**（无任何人为命名空间） |
| 主要风险 | Phase 3 重写 SubAgent 引入回归 | + Phase 0 清理 pmagent 孤立代码不能误删活代码（已识别 1 处） |
| 工作量 | 2-3 天 | **4.5 天**（pmagent 1.5 天 + fork 3 天） |

### 0.2 目标不变（4 部分约束）

| # | 目标 | 类型 |
|---|---|---|
| 1 | fork 与上游修改文件 diff < 50 行 | 优化 |
| 2 | 本地定制集中、边界清晰、无人为命名空间 | 架构 |
| 3 | 业务代码（pmagent）不受影响 | **约束** |
| 4 | 持续可演进（上游接受某项后可平滑移除） | **约束** |
| 5 | 每轮上游同步耗时 < 30 分钟 | 优化 |

第 3、4 条是**约束目标**——未达成 = 整方案失败。前置验证（如 `test_week1_integration` 精确处理、`context/memory.py` 误判修正）服务的就是这两条。

---

## 1. 问题定义（保持 v1 不变）

参见 v1 section 1.1。简述：

- fork 内嵌 11 项深度定制，与上游 diff ~3500 行
- 定制散布在 SDK 内部多个模块，没有清晰扩展边界
- Round 13 (114 commits) 7-9h、Round 14 (55 commits) 2.5h、Round 15 (83 commits) ~5h
- 累计 ~1069 commits 跨 15 轮，每轮都需要架构师+研发主管参与

---

## 2. 本地 Fork 定制清单（保持 v1 不变）

参见 v1 section 2。清单仍为 11 项 A 类内嵌定制 + 6 项 B 类已上游接受。

---

## 3. 下游 pmagent 实际依赖核查（重大修订）

### 3.1 v1 的认知 vs 实际

v1 通过 grep 列出了 pmagent 对 fork 定制的依赖位置（state\_schema、skills\_allowlist、subagent\_logs 等），结论是"下游对 fork 定制有深度依赖"——这部分**正确**。

但 v1 隐含一个未明说的假设：**pmagent 内已经存在与 fork 定制平行的成熟实现**。这个假设在 pmagent 团队实地调查后被证伪。

### 3.2 pmagent 的孤立草案（4 模块，~2772 行）

实地 grep 验证（业务代码引用 = 0，仅测试 + 死 import）：

| 模块 | 行数 | 状态 |
|---|---|---|
| `src/middleware/logging.py` | 1330 | `agent.py:21` 死 import；`agent.py:485` 注释明确"已选用 fork SubAgent logging 替代之" |
| `src/services/skills_loader.py` | 436 | 仅 `tests/test_taxonomy.py` 引用 |
| `src/middleware/memory.py` | 428 | 仅 `tests/test_memory_middleware.py` 引用 |
| `src/models/skill.py` | 120 | 仅被 skills\_loader.py + 测试引用，联动死亡 |
| `src/security/permissions.py` | 458 | 业务零调用；可能为待启用 RBAC（**产品决策待定**） |

注：`src/context/memory.py`（328 行）**不是孤立**，被 `agent.py:540` 实际调用，必须保留。

### 3.3 pmagent 的真实运行时依赖

pmagent **是 fork 的透明消费者**：

1. 调用 `create_deep_agent()` 装配整套 fork 中间件栈（含 SkillsMiddleware V2、SummarizationMiddleware、MemoryMiddleware、SubAgentMiddleware 等）
2. 直接 import `SkillsMiddleware`、`FilesystemBackend`、`StateBackend`、`StoreBackend`、`CompositeBackend`、`upload_files`、`UploadResult`
3. 通过参数（`state_schema=PMAgentState`、`expose_dynamic_tools=True`、`allowed_skills`、SubAgent `skills_allowlist`）控制 fork 行为
4. 间接消费 fork 内部补丁（`SummarizationMiddleware` Overwrite guard、`MemoryMiddleware` isawaitable 兼容）——通过 `create_deep_agent` 装配链

### 3.4 结论的修订

v1 结论："下游对 fork 定制有深度依赖" → **正确**。
v1 推论（隐含）："因此把 fork 定制物理迁移到 pmagent" → **错误**——物理迁移会让 pmagent 失去 `create_deep_agent` 的装配收益（v1 自己在 Phase 3A 风险中也提到了），且违反"customization 与 SDK 同仓维护"原则。

**正确的方向**：保留定制在 fork 内，但**在 fork 内部重组**——把"修改上游文件"的定制重构为"additive 新文件 + 上游文件最小 hook"。这样：

- 上游同步时，additive 新文件不参与 merge → 0 冲突
- 上游文件 hook 仅 < 50 行 diff → trivial 解决
- pmagent 透明消费链路不变 → 业务代码零修改
- 不引入任何人为命名空间（既不在 fork 加 `deepagents-ext/`，也不在 pmagent 加 `src/deepagents_ext/`）

---

## 4. 可行性矩阵（按"在 fork 内重组"路径修订）

| # | 定制项 | v1 路径 | v2 路径 | 复杂度 |
|---|---|---|---|---|
| 1 | SkillsMiddleware V2 | 整类移植到 pmagent | **fork 内**：拆为 `middleware/skills.py`（基础，对齐上游）+ `middleware/skills_v2.py`（V2 增强子类） | 中 |
| 2 | Converters 子包 | 整目录移植到 pmagent | **fork 内**：已是 additive `middleware/converters/` 目录，**无需移动**，只需确认 0 修改上游文件 | 小 |
| 3 | filesystem.py read\_file 内嵌 Converter | 子类化到 pmagent | **fork 内**：抽出为 `backends/converter_filesystem.py`（FilesystemBackend 子类），`filesystem.py` 还原至上游 | 中 |
| 4 | Upload Adapter V5 | 复制到 pmagent | **fork 内**：已是 additive `upload_adapter.py`，**无需移动** | 小 |
| 5 | SubAgent stream\_writer + logging | 子类化到 pmagent (3A) | **fork 内**：抽出为 `middleware/subagent_observability.py`（SubAgentMiddleware 子类或装饰器），`subagents.py` 还原至上游（除 `_EXCLUDED_STATE_KEYS` 增量接口） | 大 |
| 6 | graph.py 参数定制 | 在 pmagent 替代 `create_deep_agent` | **fork 内**：保留 `state_schema` / `skills_expose_dynamic_tools` / `skills_allowlist` 作为公共参数 hook（约 30-50 行 diff，是不可避免的最小公共 API 扩展） | 小 |
| 6b | `create_summarization_middleware` factory | pmagent 自己装配 | **fork 内**：保留为 graph.py 的可注入 hook（与 #6 同源） | 小 |
| 7 | Memory isawaitable 兼容 | 子类化到 pmagent | **fork 内**：抽出为 `middleware/memory_async_compat.py`（MemoryMiddleware 子类），`memory.py` 还原至上游 | 小 |
| 8 | Summarization Overwrite guard | 子类化到 pmagent | **fork 内**：抽出为 `middleware/summarization_overwrite_guard.py`（SummarizationMiddleware 子类），`summarization.py` 还原至上游 | 小 |
| 9 | SubAgent.skills\_allowlist TypedDict | pmagent 子 TypedDict | **fork 内**：保留 TypedDict 字段扩展（运行时是 dict，与 #6 hook 同源） | 小 |
| 10 | `_EXCLUDED_STATE_KEYS` 扩展 | 必须留 fork | **fork 内**：改为 additive 接口（`extra_excluded_keys` 参数），让 pmagent 注入额外 keys | 小 |

**关键差别**：v2 的所有 #1-#10 都在 fork 内完成，pmagent **零代码迁移**（除清理孤立草案）。

---

## 5. 候选方案对比（新增方案 D，重新推荐）

### 方案 A — 完全下沉到 pmagent（同 v1，否决）

放弃 `create_deep_agent`，pmagent 自己装配。代价过大，未来跟随上游改进困难。

### 方案 B — 下沉到 pmagent `src/deepagents_ext/`（v1 推荐，本 v2 否决）

**v1 推荐理由**：ROI 高、风险可控、可演进。

**v2 否决理由**：

1. **前提错误**：v1 假设 pmagent 有平行实现可作为下沉目标，实际不存在
2. **物理迁移代价**：pmagent 失去 `create_deep_agent` 装配收益（v1 Phase 3A 已识别）
3. **架构噪声**：在 pmagent 引入人为命名空间，违反"模块归属业务领域"原则——pmagent 团队会承担 ~2700 行非业务代码维护负担
4. **路径不必要**：fork 内部重组（方案 D）能用更小代价达成同样目标

### 方案 C — 仅下沉独立模块（同 v1，否决）

减负有限，根本问题（SkillsMiddleware V2 + graph.py）未解决。

### 方案 D — Fork 内部重组（v2 推荐）✅

**核心动作**：

- 保留所有 11 项定制在 fork 内
- 把"**修改上游文件**" → "**additive 新文件 + 上游文件最小 hook（~50 行总 diff）**"
- pmagent 继续 import / 调用 fork（路径基本不变）
- pmagent 仅清理孤立草案（4 模块，1.5 天）

**优点**：

- 上游修改文件 diff 趋近 0 → merge 冲突趋近 0
- pmagent 业务代码零修改（除清理孤立模块外）
- 保留 `create_deep_agent` 装配收益与上游持续优化
- 定制与 SDK 同仓维护，演进同步
- **不引入任何人为命名空间**（无 `deepagents_ext/`、无 `deepagents-ext/`）

**代价**：

- fork 仓库本身仍是 fork（与上游 1:1 同步 ≠ 100% 一致）
- additive 新文件存在但不冲突——这与"diff < 50 行"目标不矛盾，因为 merge friction 是按**修改文件**计算，不是按**新增文件**计算

**工作量**：~3 天（fork 重组）+ 1.5 天（pmagent 孤立代码清理） = **4.5 天**

---

## 6. 方案 D 详细设计

### 6.1 设计原则（修订）

1. **fork 内部分层**：`middleware/{name}.py` = 对齐上游基础；`middleware/{name}_{feature}.py` = 本地增强（子类/装饰器/独立中间件）
2. **上游文件最小 hook**：仅保留 graph.py 公共参数（~30-50 行 diff）+ subagents.py `_EXCLUDED_STATE_KEYS` additive 接口
3. **pmagent 透明消费**：import 路径基本稳定，业务代码零修改
4. **可演进**：上游接受某项定制后，可删除 fork 增强文件，pmagent 自动获得上游版本

### 6.2 Fork 内部目标结构

```text
libs/deepagents/deepagents/
├── graph.py                                # 上游对齐 + 30-50 行公共参数 hook
├── upload_adapter.py                       # 已 additive，保持不动
├── middleware/
│   ├── skills.py                           # 还原至上游基础
│   ├── skills_v2.py                        # 新增：V2 增强子类（load/unload/expose_dynamic_tools/allowed_skills）
│   ├── filesystem.py                       # 还原至上游
│   ├── memory.py                           # 还原至上游
│   ├── memory_async_compat.py              # 新增：isawaitable 兼容子类
│   ├── summarization.py                    # 还原至上游
│   ├── summarization_overwrite_guard.py    # 新增：Overwrite guard 子类
│   ├── subagents.py                        # 还原至上游（除 _EXCLUDED_STATE_KEYS additive 接口）
│   ├── subagent_observability.py           # 新增：stream_writer + logging
│   └── converters/                          # 已 additive，保持不动
└── backends/
    └── converter_filesystem.py              # 新增：FilesystemBackend 子类，集成 converter 调用
```

### 6.3 Fork 上游文件保留 diff（< 50 行总）

仅以下两处保留必要 diff：

**graph.py**（约 30-40 行）：公共参数 hook
- `state_schema` 参数（已被 Round 14 上游接受路径接近）
- `skills_expose_dynamic_tools` / `skills_allowlist` 参数
- `create_summarization_middleware` 工厂注入

**subagents.py**（约 5-10 行）：状态隔离 additive 接口
- `_EXCLUDED_STATE_KEYS` 改为 `_DEFAULT_EXCLUDED_STATE_KEYS` + `extra_excluded_keys` 参数
- TypedDict `SubAgent.skills_allowlist` 字段（无运行时行为）

---

## 7. 迁移路线图（Phase 0-4）

### Phase 0 — pmagent 孤立代码清理（1.5 天，pmagent 仓库）

**目标**：消除 pmagent 内"看似平行实现"的视觉污染，让 pmagent = 干净的 fork 消费者。

**Day 1 上午（0.5 天）— Source 删除**
- 删除 `src/middleware/logging.py`（1330）
- 清理 `src/agent.py:21` 死 import (`create_event_logging_middleware`)
- 删除 `src/services/skills_loader.py`（436）
- 删除 `src/middleware/memory.py`（428）
- 删除 `src/models/skill.py`（120，联动）

**Day 1 下午（0.5-0.75 天）— 测试处置**
- A 策略（直接删）：`tests/test_phase2_5_*.py` (4) + `tests/test_taxonomy.py` + `tests/test_relative_path*.py` (2) + `tests/test_memory_middleware.py` + `tests/manual/verify_phase2_5_*.py` (2) + `tests/manual/test_skills_loader_runtime.py`
- C 精确策略：`tests/test_e2e_comprehensive.py` 删 line 26 局部 import + 相关断言
- C 强制策略（**禁止整体删**）：`tests/test_week1_integration.py` 仅删 MemoryMiddleware 相关 import / fixture / 测试方法 / 字典字面量；保留 T1.1/T1.2/T1.4/T1.5（state schema、token buffer、postgres checkpointer、token 基准）覆盖

**Day 2 上午（0.25 天，强制门）— 验证**
- `pytest --collect-only` → 0 collection error
- `pytest tests/ -v --cov=src` → 无回归
- `grep "from src.middleware.logging|from src.services.skills_loader|from src.middleware.memory|from src.models.skill"` → 0 残留
- `langgraph dev` 启动冒烟测试

**Day 2 下午（0.25 天）— 文档同步**
- 更新 `pmagent/CLAUDE.md` lines 635-647（Production Middleware Structure 删 logging.py + memory.py 两行）
- 评估 `docs/01-architecture/SKILLS_LOADING_MECHANISM.md` section 6.3（重写为指向 fork SkillsMiddleware V2 或归档）
- 修复 `pmagent/CLAUDE.md:647` 过时引用（指向 `docs/middleware_cleanup_final_report.md`，实际已归档至 `docs/99-archive/`）

**暂缓项**：
- `src/security/permissions.py` 等 RBAC 产品决策；期间保留文件 + `__init__.py:8` import 不动 + 不允许新增引用

**验收**：pmagent 测试全绿，业务功能无回归，孤立模块清单 0 残留。

### Phase 1 — Fork additive 模块识别（半天，fork 仓库）

**目标**：确认已 additive 的定制（converters/、upload_adapter.py）确实 0 修改上游文件。

- `git diff upstream/main..master -- libs/deepagents/deepagents/middleware/converters/` → 应只显示新增
- `git diff upstream/main..master -- libs/deepagents/deepagents/upload_adapter.py` → 应只显示新增
- 若有任何上游冲突点（如 `__init__.py` 重导出），抽离到独立 `__init__.py` 段或新文件

**验收**：converters/ 与 upload_adapter.py 在上游 merge 时 0 冲突（git merge-tree 模拟验证）。

### Phase 2 — Fork middleware 子类化重构（1.5 天）

**目标**：把 `middleware/skills.py`、`filesystem.py`、`memory.py`、`summarization.py` 还原至上游基础，把本地增强抽出为新的子类文件。

具体步骤：

1. `middleware/skills_v2.py`：抽出 V2 全部增强（load/unload/expose_dynamic_tools/allowed_skills/V1V2 prompt 互斥）作为 `SkillsMiddleware` 子类；`skills.py` 还原至上游
2. `backends/converter_filesystem.py`：抽出 `_convert_document_sync/async` 为 `FilesystemBackend` 子类；`filesystem.py` 还原至上游
3. `middleware/memory_async_compat.py`：抽出 isawaitable 兼容为 `MemoryMiddleware` 子类；`memory.py` 还原至上游
4. `middleware/summarization_overwrite_guard.py`：抽出 Overwrite guard 为 `SummarizationMiddleware` 子类；`summarization.py` 还原至上游
5. `graph.py`：保留公共参数 hook（state_schema、skills_expose_dynamic_tools、skills_allowlist、create_summarization_middleware）；其他装配逻辑还原至上游

**验收**：fork 单测全绿，pmagent 集成测试全绿，`git diff upstream/main..master` 中上游已有文件的 diff < 50 行。

### Phase 3 — Fork SubAgent 可观测性重构（1 天，最棘手）

**目标**：抽出 stream_writer + logging 为独立中间件 `subagent_observability.py`，`subagents.py` 还原至上游（仅保留 `_EXCLUDED_STATE_KEYS` additive 接口）。

**关键挑战**：上游 `SubAgentMiddleware._build_task_tool` 是闭包，不可外部 hook。可选路径：

- **3A 方案**：装饰器模式——封装 `create_deep_agent` 返回的中间件栈，在 SubAgent task 调用前后注入观测
- **3B 方案**：子类重写 `_build_task_tool`——风险是上游内部重构会破坏

倾向 **3A**（装饰器）：与 SDK 内部实现耦合更低。

**验收**：`subagent_logs` 状态字段写入正常，pmagent 前端 SubAgent 进度展示无回归。

### Phase 4 — Fork 上游同步成本验证（半天）

**目标**：用真实上游同步验证 merge friction 下降效果。

- 等待下一轮上游有 commits（或人为创建测试 merge）
- `git merge upstream/main` → 测量冲突文件数 + 解决耗时
- 对比 Round 13/14/15 基线
- 如冲突仍 > 10 分钟，回到 Phase 2/3 评估剩余 hook

**验收**：上游同步耗时 < 30 分钟；冲突文件 0-1 个。

---

## 8. 风险与缓解（修订）

| 风险 | 严重性 | 缓解措施 |
|---|---|---|
| Phase 0 误删 pmagent 活代码（如 context/memory.py 误判） | 🔴 高 | 已用 grep 验证；Phase 0 验证门强制 `pytest --collect-only` + `--cov` |
| Phase 0 `test_week1_integration.py` 误整体删 | 🔴 高 | 强制 C 策略，禁止"或整体删"；保留 T1.1/T1.2/T1.4/T1.5 覆盖 |
| Phase 3 SubAgent 装饰器重构引入回归 | 🔴 高 | 3A 装饰器优先于 3B 子类；全面集成测试 + 灰度切换（保留 fork 备份分支） |
| graph.py 公共参数 hook（30-50 行）成为永久维护项 | 🟡 中 | 这是不可避免的最小公共 API 扩展；上游 Round 14 已接受 state_schema 路径，其他参数可逐步上游化 |
| SDK 自动装配的默认 SummarizationMiddleware 与 OverwriteGuard 子类叠加 | 🟡 中 | OverwriteGuard 子类替换默认（在 graph.py hook 中切换），不叠加 |
| security/permissions.py 暂缓状态被误读为"半启用" | 🟡 中 | 显式约束：保留文件 + 保留 `__init__.py:8` import + 不允许新增引用；产品决策超过 1 个月后强制收敛 |
| 上游某项 API 重命名导致 fork 子类失配 | 🟡 中 | fork 子类使用稳定的 SDK 公共 API；私有 API 调用集中标注 |

---

## 9. 收益评估（目标不变，路径不同）

| 指标 | 现状 | v2 方案 D 之后 |
|---|---|---|
| Fork 与上游修改文件 diff | ~3500 行 | **< 50 行** |
| 上游同步耗时 | 2-6 小时/轮 | **< 30 分钟/轮** |
| 上游同步冲突文件 | 5-15 个 | **0-1 个** |
| pmagent 业务代码改动 | — | **0 行**（除清理 4 个孤立模块） |
| pmagent 仓库行数变化 | — | **-2772 行**（清理孤立草案） |
| Fork 仓库新文件 | — | +6-7 个增强模块（additive，不冲突） |
| 总迁移工作量 | — | 4.5 天（pmagent 1.5d + fork 3d） |
| 长期维护成本 | 高（每轮被动跟进） | 低（fork 几乎自动同步，定制独立演进） |

按当前节奏（每月 1-2 轮上游同步，每轮 3-5 小时），方案 D 在 1.5-2 个月内即可回本。

---

## 10. 决策建议

**强烈推荐方案 D（Fork 内部重组）**，理由：

1. **服务全部 5 条目标**：
   - 优化目标 1、5（diff、耗时）：通过 additive 重组达成
   - 架构目标 2：无任何人为命名空间
   - 约束目标 3、4：pmagent 业务代码零修改 + 可演进
2. **ROI 最高**：4.5 天投入换来未来每轮节省 1.5-5.5 小时
3. **风险可控**：分 Phase 0-4，每阶段独立可验证、可回滚
4. **可演进**：上游接受某项定制后，删除 fork 增强文件即可，pmagent 自动获得上游版本

**不推荐方案 A（完全下沉）**：放弃 `create_deep_agent` 装配收益太大。
**不推荐方案 B（v1 原推荐）**：基于错误前提，引入人为命名空间且让 pmagent 承担非业务代码。
**不推荐方案 C（保守）**：根本问题未解决。

---

## 11. 后续步骤

1. **本文档评审**：项目负责人 + deepagents fork 团队 + pmagent 团队各一轮（重点对齐方案 D）
2. **并行启动 Phase 0**：pmagent 团队按 Phase 0 清单执行（1.5 天）
3. **并行启动产品决策**：RBAC roadmap 决策（决定 `security/permissions.py` 命运）
4. **Phase 0 完成后**：deepagents fork 团队启动 Phase 1（半天）→ Phase 2（1.5 天）→ Phase 3（1 天）→ Phase 4（半天验证）
5. **下一轮上游同步**：用 Round 16 验证 merge friction 下降效果

---

## 附录 A — 与 v1 的对应关系

| v1 章节 | v2 章节 | 状态 |
|---|---|---|
| 1. 问题定义 | 1 | 不变 |
| 2. 定制清单 | 2 | 不变 |
| 3. 下游依赖核查 | 3 | **重大修订** |
| 4. 可行性矩阵 | 4 | 修订（路径改为 fork 内重组） |
| 5. 三方案对比 | 5 | **新增方案 D，否决 B** |
| 6. 推荐方案设计 | 6 | **重写**（方案 D 设计） |
| 7. Roadmap | 7 | **新增 Phase 0；Phase 1-4 重构** |
| 8. 风险 | 8 | 修订 |
| 9. 收益 | 9 | 目标不变，指标补充 |
| 10. 决策建议 | 10 | 修订 |
| 11. 后续步骤 | 11 | 修订 |

---

## 附录 B — 核实证据索引

- pmagent 孤立模块 grep 结果：本对话 2026-05-01 核实记录
- `context/memory.py` 活代码证据：`pmagent/src/agent.py:35-36, 540-548`
- `agent.py:485` SubAgent logging 决策注释：原文记录
- `test_week1_integration.py` 多组件覆盖证据：file lines 4-9, 510-513
- CLAUDE.md 过时段：`pmagent/CLAUDE.md:635-647`
- `middleware_cleanup_final_report.md` 实际位置：`pmagent/docs/99-archive/middleware_cleanup_final_report.md`
