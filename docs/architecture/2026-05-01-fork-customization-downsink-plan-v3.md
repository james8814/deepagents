> ⚠️ **HISTORICAL 2026-05-02** — 本文档（v3 / Plan D 三轮加强版）**已被 Plan H+ 取代**。
>
> v3 推荐 Plan D（fork 内部重构 + graph.py 200 行装配中心）。在实测中 graph.py 200 行 diff 与上游 5 大文件冲突未消除，方案不能数学保证零冲突。后续演进至 v4-rev2（Plan E++）→ Plan H → **Plan H+（终局）**。
>
> **当前权威方案**：[`2026-05-02-plan-h-plus-final.md`](2026-05-02-plan-h-plus-final.md)
> **决策档案**：[`decisions/0002-fork-customization-strategy.md`](decisions/0002-fork-customization-strategy.md)
>
> 本文档保留为**决策档案**，记录 Plan D 的完整加强过程（22 项跨多轮评审修订），含核心方法论价值（事实核实驱动、对等严苛检验等原则的早期沉淀）。
>
> ---

# Fork 定制下沉方案 v3 — 综合评审 + 事实核实修订（HISTORICAL — 已被 Plan H+ 取代）

**日期**: 2026-05-01
**作者**: 架构师团队
**状态**: 修订版（v2 经 deepagents CTO + pmagent 团队各一轮深度评审，含事实核实；第二轮修订：Incremental Folding 策略 + RBAC 冻结 + pmagent 三时间点角色）
**前序**:
- v1 `2026-04-29-fork-customization-downsink-plan.md`
- v2 `2026-05-01-fork-customization-downsink-plan-v2.md`
**目标读者**: 项目负责人、deepagents fork 团队、pmagent 业务团队

---

## 0. 修订摘要

### 0.1 v3 修订总清单（25 项）

| # | 修订项 | 类别 | 来源 |
|---|---|---|---|
| 1 | graph.py diff 目标 30-50 → 150-200 行（装配中心定位） | 🔴 事实驱动 | 实测 458 行 |
| 2 | 删除 `state_schema` "上游接受路径"表述 | 🔴 事实驱动 | Round 14/15 PROGRESS 核实 |
| 3 | 新增 §6.4 默认装配策略与 import 路径稳定性 | 🔴 架构 | CTO 反对 2 |
| 4 | Phase 3 拆为 3.0 PoC + 3.1 实施 | 🔴 风险 | pmagent 补强 2 + 事实核实 |
| 5 | 新增 subagent_logs 契约保留 + 9 测试强制门 | 🔴 契约 | pmagent 风险 2 + 实际 9 测试 |
| 6 | graph.py 装配逻辑设计明确化（合并 §6.4） | 🔴 架构 | pmagent 补强 1 |
| 7 | 新增 §6.5 跨仓库版本协调 | 🟡 流程 | CTO 保留 1 |
| 8 | Phase 2 含测试结构规范化（基于现有 fork tests） | 🟡 结构 | pmagent 补强 4 + 事实核实 |
| 9 | §8 新增回滚策略子节 | 🟡 风险 | CTO 保留 3 + pmagent 风险 3 |
| 10 | §11 改为双 Milestone 推进 | 🟡 流程 | pmagent 推进建议 |
| 11 | §6.1 增"文件名后缀命名空间"原则 | 🟢 架构 | CTO 保留 5 |
| 12 | Phase 4 拆为 4a 本地验证 + 4b 真实跟踪 | 🟢 流程 | CTO 保留 6 |
| 13 | RBAC 决策 1 个月强制收敛 | 🟢 流程 | CTO + pmagent 综合 |
| 14 | 估时表更新（4.5d → 6-6.5d，含 M1∥M2 并行可省 1d） | 🟢 估时 | 三方综合 |
| 15 | §6.4.3 演进路径重写为 Incremental Folding 模式 + §6.4.4 检测机制 + §6.1 原则 6 | 🔴 架构 | CTO + pmagent 综合 |
| 16 | RBAC 策略：1 个月强制收敛 → 冻结 + 每季度评审（file header 事实核实） | 🟡 流程 | 事实核实（permissions.py file header） |
| 17 | §9.1 新增 pmagent upgrade PR 行（+0.5-1 天，pmagent 团队负责） | 🟢 估时 | CTO 补充 |
| 18 | §11.2 第 5 个 M2 启动条件 + §11.6 pmagent 三时间点角色显式化 | 🟡 流程 | CTO 补充 |
| 19 | §6.3a skills.py diff 构成分析（671 行分解确认 < 250 行目标可达） | 🔴 事实 | RC-4 代码核实 |
| 20 | CTO-1：converter_filesystem.py 层级修正（backends/→middleware/，FilesystemMiddleware 子类） | 🔴 架构 | CTO 独立发现 |
| 21 | Phase 3.0 Snapshot baseline 先行步骤 + pmagent 临时验证分支协议 + Phase 2 验收补强 | 🔴 流程 | RC-1、RC-2、RC-3、CTO-3 |
| 22 | §6.4.3 完整折叠 SOP + AD-2 git 命令修正 + AD-3 条件 5 并行澄清 + §8.1 RBAC 文字清理 + Phase 3.0 估时 1d | 🟡 综合 | AD-1、AD-2、AD-3、CTO-2、K |
| 23 | §7 M2 启动条件整段替换（4→5 条件，第 4 条 RBAC 文字对齐 §11.2） | 🔴 一致性 | RC-5 |
| 24 | §0.3/§9.2/§10 日历时间 5-5.5→5.5-6 天；§7/§11.2 修订范围→22 项 | 🟡 同步 | RC-6、RC-7 |
| 25 | Phase 3.0 步骤 1 措辞澄清（AD-4）+ Phase 2 alias smoke test 修正（AD-5，代码核实）+ converter smoke test（AD-6） | 🟡 质量 | AD-4、AD-5、AD-6 |

### 0.2 事实核实驱动的关键修正

四个数字在 v2 / pmagent 评审 / CTO 评审中都偏离实际，v3 用真实 grep 数据钉死：

| 争议点 | v2 主张 | pmagent 评审 | CTO 评审 | **实测** |
|---|---|---|---|---|
| graph.py diff 行数 | 30-50 | 60-100 | < 100 | **458（278+/180-）** |
| `_build_task_tool` 性质 | 装饰器 3A | 需 PoC | "闭包，3A 不成立" | **模块级函数**（subagents.py:634）|
| `state_schema` 上游接受 | "Round 14 路径接近" | 未提 | 事实错误 | **Round 14/15 都未接受** |
| pmagent subagent_logs 测试数 | 未提 | "前端 e2e 测试" | 未提 | **9 个测试文件依赖** |
| skills.py fork diff 行数 | 未提 | 未提 | 未提 | **671（538+/133-）** |

### 0.3 双 Milestone 推进策略

- **Milestone 1（立即启动，1.5 天，pmagent 仓库）**：Phase 0 — 孤立代码清理
- **Milestone 2（M1 + fork 补强后启动，5 天，fork 仓库）**：Phase 1-4

M1 与 fork 团队 v3 评审 + Phase 3.0 PoC 并行，**总日历时间 5.5-6 天**（不是简单累加 6.5-7 天；RC-7 同步 §9.1 修订）。

### 0.4 目标不变（5 部分约束）

| # | 目标 | 类型 | 修订后指标 |
|---|---|---|---|
| 1 | fork 与上游修改文件 diff 减少 | 优化 | 3500 → **300-400 行**（不是 < 50） |
| 2 | 本地定制集中、边界清晰、无人为命名空间 | 架构 | 维持 |
| 3 | 业务代码（pmagent）不受影响 | **约束** | 维持（修订 3 默认装配保障） |
| 4 | 持续可演进 | **约束** | 维持 |
| 5 | 每轮上游同步耗时 < 30 分钟 | 优化 | 维持 |

> **关键认知修订**：merge 摩擦的根源不是 diff 行数，是 **diff 散布的文件数 × 上游修改密度**。装配集中到 graph.py 一个文件 200 行 diff，比散布到 10 个文件每个 30 行更易维护。v3 接受 graph.py 作为"装配中心"长期保留 ~150-200 行 diff。

---

## 1. 问题定义（保持 v1/v2 不变）

参见 v1 §1.1。简述：

- fork 内嵌 11 项深度定制，与上游 diff ~3500 行
- 定制散布在 SDK 内部多个模块，没有清晰扩展边界
- Round 13 (114 commits) 7-9h、Round 14 (55 commits) 2.5h、Round 15 (83 commits) ~5h
- 累计 ~1069 commits 跨 15 轮，每轮都需要架构师+研发主管参与

---

## 2. 本地 Fork 定制清单（保持 v1/v2 不变）

参见 v1 §2。清单仍为 11 项 A 类内嵌定制 + 6 项 B 类已上游接受。

---

## 3. 下游 pmagent 实际依赖核查（含事实核实）

### 3.1 v1/v2 → v3 认知演进

- v1 假设 pmagent 有平行实现 → 错误
- v2 验证 pmagent 是 fork 消费者 → 正确，但缺了 subagent_logs 契约深度
- v3 补充：pmagent 不仅消费 fork 中间件，还**深度依赖 subagent_logs 字段格式契约**（9 个测试文件）

### 3.2 pmagent 的孤立草案（4 模块，~2772 行）

[同 v2，事实证据已三轮核实]

| 模块 | 行数 | 业务引用 | 处置 |
|---|---|---|---|
| `src/middleware/logging.py` | 1330 | 0（agent.py:21 死 import） | 删除 |
| `src/services/skills_loader.py` | 436 | 0（仅 test_taxonomy.py） | 删除 |
| `src/middleware/memory.py` | 428 | 0（仅 test_memory_middleware.py） | 删除 |
| `src/models/skill.py` | 120 | 0（仅 skills_loader.py + 测试） | 删除（联动） |
| `src/security/permissions.py` | 458 | 0（Week 4 工具升级预留，file header 明确） | **冻结**（添加 `# STATUS: FROZEN` 注释 + 每季度评审，负责人：pmagent 技术负责人） |

`src/context/memory.py`（328 行）**不是孤立**，被 `agent.py:540` 实际调用，必须保留。

### 3.3 pmagent 的真实运行时依赖

#### 3.3.1 SDK 中间件透明消费

pmagent 调用 `create_deep_agent()` 装配整套 fork 中间件栈，含：
- `SkillsMiddleware`（V2 增强版）—— `agent.py:588` 直接 import
- `SummarizationMiddleware`（含 Overwrite guard）—— 通过 factory 装配
- `MemoryMiddleware`（含 isawaitable 兼容）—— 通过 factory 装配
- `SubAgentMiddleware`（含 stream_writer + logging）—— 通过 factory 装配

#### 3.3.2 关键参数依赖

| 参数 | pmagent 调用位置 | 依赖度 |
|---|---|---|
| `state_schema=PMAgentState` | `agent.py:716` | **强**（无法外部注入） |
| `expose_dynamic_tools=True` | `agent.py:606,652` | **强**（强制 V2 模式） |
| `allowed_skills` | `agent.py:653` | **强** |
| SubAgent `skills_allowlist` | `agent.py:324,653` | **强** |

#### 3.3.3 subagent_logs 字段格式契约（v3 新增重点）

pmagent 9 个测试文件依赖 `subagent_logs` 字段格式：

| 测试文件 | 类型 |
|---|---|
| `tests/test_subagent_logs_acceptance.py` | 验收 |
| `tests/test_pmagent_ui_comprehensive.py` | UI 综合 |
| `tests/test_pmagent_comprehensive.py` | 综合 |
| `tests/test_state_schema.py` | 状态字段 |
| `tests/manual/test_subagent_logging.py` | 手动 |
| `tests/manual/verify_subagent_logging_env.py` | 手动 |
| `tests/manual/verify_subagent_logs_display.py` | 显示验证 |
| `tests/manual/test_subagent_sdk.py` | SDK |
| `tests/integration/test_hil_interrupt_mock.py` | 集成 |

**Phase 3 重构必须保留契约**——含 message 提取顺序、敏感字段脱敏规则、字段命名（subagent、tool、input、output 等）。这 9 个测试是 Phase 3 的强制回归门。

### 3.4 结论

下沉方案不应把 fork 定制物理迁移到 pmagent。**正确路径**：

1. 清理 pmagent 孤立草案（M1）
2. 在 fork 内部把"修改上游文件"重构为"additive 新文件 + 装配中心 graph.py"
3. **保留 subagent_logs 字段格式契约不变**（Phase 3 强制门）
4. 不引入任何人为命名空间
5. 本地增量通过 Incremental Folding 随上游接受度渐进消减（§6.4.3-6.4.4）

---

## 4. 可行性矩阵（事实核实修订）

| # | 定制项 | v2 路径 | v3 路径（事实修订） | 复杂度 |
|---|---|---|---|---|
| 1 | SkillsMiddleware V2 | 子类 + skills.py 还原 | 子类 `skills_v2.py` + skills.py 末尾 `SkillsMiddleware = SkillsMiddlewareV2` 别名（修订 3 默认装配） | 中 |
| 2 | Converters 子包 | 已 additive，不动 | 同 v2 | 小 |
| 3 | filesystem.py 内嵌 Converter | 子类抽出 | `backends/converter_filesystem.py`，graph.py 装配链选择子类 | 中 |
| 4 | Upload Adapter V5 | 已 additive，不动 | 同 v2 | 小 |
| 5 | SubAgent stream_writer + logging | 装饰器 3A | **子类 + 模块级 helper 替换**（事实核实：`_build_task_tool` 是模块级函数，subagents.py:634；`_extract_subagent_logs`、`_stream_subagent_sync` 等是模块级 helper，可被子类引用替换） | **中**（不是 v2 估的"大"） |
| 6 | graph.py 参数定制 | 30-50 行 hook | **承认装配中心定位，150-200 行长期维护**（修订 1）；删除"上游接受路径"表述（修订 2） | 中 |
| 6b | `create_summarization_middleware` factory | 同上 | 与 #6 合并 | 小 |
| 7 | Memory isawaitable | 子类 + memory.py 还原 | 同 v2 | 小 |
| 8 | Summarization Overwrite guard | 子类 + summarization.py 还原 | 同 v2 | 小 |
| 9 | SubAgent.skills_allowlist TypedDict | TypedDict 字段 | 同 v2（保留） | 小 |
| 10 | `_EXCLUDED_STATE_KEYS` 扩展 | additive 接口 | 同 v2（保留 5-10 行 hook） | 小 |

---

## 5. 候选方案对比（与 v2 一致）

[同 v2 §5。方案 A 否决、方案 B 否决（v1 推荐）、方案 C 否决、方案 D 推荐]

---

## 6. 方案 D 详细设计（v3 重大扩展）

### 6.1 设计原则（修订 11：新增第 5 条）

1. **fork 内部分层**：`middleware/{name}.py` = 对齐上游基础；`middleware/{name}_{feature}.py` = 本地增强
2. **上游文件最小 hook**：仅保留 graph.py 公共参数 + subagents.py `_EXCLUDED_STATE_KEYS` additive 接口
3. **pmagent 透明消费**：通过 import 路径稳定别名 + 默认装配策略，业务代码零修改
4. **可演进**：上游接受某项定制后，可删除增强文件，pmagent 自动获得上游版本
5. **(v3 新增) 增强语义通过文件名后缀表达**：`*_v2.py`、`*_async_compat.py`、`*_overwrite_guard.py`，不引入子目录或子包；这与方案 D 否决方案 B 的"人为命名空间"原则不矛盾——文件名后缀表达的是同一抽象层的同级关系，不是嵌套层级
6. **(修订 15 新增) 类 docstring 本地增量清单**：每个增强子类的 class docstring 首行注明本地相对上游的增量，格式 `# LocalFeatures: [feature1, feature2, ...]`；便于 `tools/check_increments.py` 扫描辅助 Incremental Folding 决策，也是 Round N 上游接受某特性时的"可删清单"参考

### 6.2 Fork 内部目标结构（v3 含 tests/ 子树）

```text
libs/deepagents/deepagents/
├── graph.py                                # fork 装配中心（150-200 行 diff，长期维护）
├── upload_adapter.py                       # 已 additive，不动
├── middleware/
│   ├── skills.py                           # 还原至上游 + 末尾 SkillsMiddleware = SkillsMiddlewareV2 别名
│   ├── skills_v2.py                        # 新增：V2 增强子类
│   ├── filesystem.py                       # 还原至上游
│   ├── memory.py                           # 还原至上游 + 末尾 MemoryMiddleware = MemoryMiddlewareAsyncCompat 别名
│   ├── memory_async_compat.py              # 新增：isawaitable 兼容子类
│   ├── summarization.py                    # 还原至上游 + 末尾 SummarizationMiddleware = SummarizationOverwriteGuard 别名
│   ├── summarization_overwrite_guard.py    # 新增：Overwrite guard 子类
│   ├── subagents.py                        # 还原至上游（保留 _EXCLUDED_STATE_KEYS additive 接口）
│   ├── subagent_observability.py           # 新增：SubAgentMiddleware 子类（stream_writer + logging）
│   ├── filesystem_converter.py             # 新增：FilesystemMiddleware 子类（_convert_document_sync/async 移至此）
│   └── converters/                          # 已 additive，不动

libs/deepagents/tests/unit_tests/middleware/
├── test_skills_middleware.py               # 还原至上游基础（V1 行为）
├── test_skills_v2.py                        # 新增：V2 增强测试（拆自当前混合版）
├── test_skills_dynamic_tools.py             # 已存在，保留
├── test_memory.py                           # 还原至上游基础
├── test_memory_async_compat.py              # 新增：isawaitable 兼容测试
├── test_summarization_middleware.py         # 还原至上游基础
├── test_summarization_overwrite_guard.py    # 新增：Overwrite guard 测试
├── test_summarization_factory.py            # 已存在，保留
├── test_subagent_middleware_init.py         # 还原至上游基础
├── test_subagent_observability.py           # 新增：stream_writer + logging 测试
├── test_subagent_logging.py                 # 已存在，保留
├── test_subagent_stream_writer.py           # 已存在，保留
└── converters/                              # 已存在，保留
```

**关键事实修订**（修订 8）：fork tests **已部分 additive**——`test_skills_dynamic_tools.py`、`test_subagent_logging.py`、`test_subagent_stream_writer.py`、`test_summarization_factory.py` 已经独立。Phase 2 测试规范化的实际工作是**拆分混合文件**（如 `test_skills_middleware.py` 含 V1+V2）+ **新增缺失文件**（如 `test_summarization_overwrite_guard.py`），不是从头建立。

### 6.3 Fork 上游文件保留 diff（修订 1：目标更新）

实测当前 diff: graph.py **458 行**（278+/180-）。v3 修订目标：

| 文件 | v2 目标 | **v3 修订目标** | 性质 |
|---|---|---|---|
| `graph.py` | 30-40 行 | **150-200 行** | 装配中心，长期维护 |
| `subagents.py` | 5-10 行 | < 30 行 | `_EXCLUDED_STATE_KEYS` additive + TypedDict 字段 |
| 其他上游文件 | 0 | < 20 行（合计） | 仅微小本地补丁 |
| **总计** | < 50 行 | **< 250 行** | |

**核心论点**：merge 摩擦不是按 diff 行数线性增长的。装配集中到 graph.py 一个文件（即使 200 行）只造成 1 个 merge 点；散布到 10 个文件每个 50 行才是真正的灾难。**Round 16 真实验证**（Phase 4b）会证明这点。

#### 6.3a skills.py diff 构成分析（RC-4 核实，修订 19）

实测 `git diff --stat`：skills.py **671 行（538+/133-）**，是当前最大单文件 diff（大于 graph.py 的 458 行）。

**133 行删除的来源**（grep 核实）：

- 上游 `SkillMetadata` TypedDict 定义（~50 行）— fork 将其重写为含 V2 字段的扩展版
- import 语句重组（`ContextT`/`ResponseT` 移除，V2 新增 `cast`/`Literal`/`Command`/`ToolMessage` 等）
- 函数级替换（`_build_skills_prompt` 等被 V2 版本完全重写）

**Phase 2 子类化后 skills.py 收敛路径**：

1. 538 行新增 → 全部移入 `middleware/skills_v2.py`（新文件，不计入修改文件 diff）
2. 133 行删除 → 恢复上游原版内容（`skills.py` 还原至上游基础）
3. skills.py 仅剩末尾 ~5 行别名（§6.4.2）

**结论**：skills.py diff 从 671 行收敛到 **< 10 行**。diff 总计：graph.py ~200 + subagents.py ~30 + skills.py ~10 + filesystem.py ~10 + 其余微补丁 ~10 = **< 260 行**，与 §6.3 目标 < 250 行一致（误差在 filesystem_converter.py 独立新文件后的精确验收中确认）。

### 6.4 默认装配策略与 import 路径稳定性（v3 新增，修订 3 + 6）

#### 6.4.1 graph.py 装配伪代码

```python
# graph.py — fork 装配中心
from deepagents.middleware.skills_v2 import SkillsMiddlewareV2
from deepagents.middleware.memory_async_compat import MemoryMiddlewareAsyncCompat
from deepagents.middleware.summarization_overwrite_guard import SummarizationOverwriteGuard
from deepagents.middleware.subagent_observability import SubAgentObservability
from deepagents.middleware.filesystem_converter import FilesystemConverterMiddleware  # CTO-1: middleware 层，不是 backend

def create_deep_agent(
    *,
    state_schema: type | None = None,            # 公共参数 hook
    skills_expose_dynamic_tools: bool = False,    # 公共参数 hook
    skills_allowlist: list[str] | None = None,    # 公共参数 hook
    create_summarization_middleware: Callable | None = None,  # factory hook
    backend: BackendProtocol | None = None,
    ...
) -> CompiledStateGraph:
    # backend 默认值不变（上游语义：None → StateBackend）
    # Converter 在 middleware 层注入，不通过 default backend

    skills_mw = SkillsMiddlewareV2(  # V2，不是上游 V1
        backend=backend,
        sources=skills,
        expose_dynamic_tools=skills_expose_dynamic_tools,
        allowed_skills=skills_allowlist,
    )

    # FilesystemConverterMiddleware 替代上游 FilesystemMiddleware（CTO-1 修正）
    filesystem_mw = FilesystemConverterMiddleware(backend=backend, ...)

    summarization_mw = (
        create_summarization_middleware(model, backend) if create_summarization_middleware
        else SummarizationOverwriteGuard(...)  # 默认含 Overwrite guard
    )

    memory_mw = MemoryMiddlewareAsyncCompat(...)  # 默认含 isawaitable
    subagent_obs_mw = SubAgentObservability(...)  # 默认含 stream_writer + logging

    # ... 其余装配同上游
```

#### 6.4.2 import 路径稳定性

`middleware/skills.py` 末尾添加：

```python
# 别名让 from deepagents.middleware.skills import SkillsMiddleware 拿到 V2
# pmagent 业务代码（agent.py:588）零修改
from deepagents.middleware.skills_v2 import SkillsMiddlewareV2 as SkillsMiddleware

__all__ = [..., "SkillsMiddleware"]
```

类似处理 `MemoryMiddleware`、`SummarizationMiddleware`。

#### 6.4.3 Incremental Folding — 渐进折叠演进策略

当上游**部分接受**某项本地定制时（如上游接受了 `expose_dynamic_tools` 但未接受 `allowed_skills`），不应立即删除本地增强文件，而应采用 Incremental Folding：

1. **子类继承上游新版**：子类的父类从 fork-patched 基础版改为上游已含新特性的版本（直接继承上游增强版）
2. **只保留剩余本地增量**：仅覆盖上游尚未接受的方法/属性，删除已被上游实现覆盖的本地代码
3. **更新 `# LocalFeatures` 注释**：从 class docstring 清单中移除已被上游接受的特性
4. **只在子类成为空壳时才删除文件**：当子类除继承外无任何本地增量（即 `class Foo(Upstream): pass`）时，删除增强文件，skills.py 末尾别名也一并删除
5. pmagent 自动获得上游版本，**无需任何代码修改**（import 路径别名保证透明）

**否决 pmagent 评审的替代方案**：pmagent 评审提议"superset 接口"或"use_extended_mode 参数"——这两种方案引入了人为条件分支，使每次上游 PR 需要同步维护开关逻辑。Incremental Folding 不引入分支，保持子类语义纯粹，且借助 §6.4.4 可自动检测折叠时机。

**完整折叠 SOP（子类成为空壳时，AD-1 补充）**：

当 `check_increments.py` 报告某子类所有 LocalFeatures 均已上游接受后：

1. `graph.py` 改 import 为上游原版（如 `from deepagents.middleware.skills import SkillsMiddleware`，去掉 `_v2` 引用）
2. 运行 fork 单测 + pmagent 集成测试（验证别名兼容性未破坏）
3. 删除 `skills.py` 末尾别名 + `__all__` 中的别名项
4. 再次运行测试（确认 pmagent 直接 import 路径也通过）
5. 删除 `skills_v2.py` 文件，提交 PR（PR 标题注明"Fold: SkillsMiddlewareV2 upstream absorbed"）

#### 6.4.4 Incremental Folding 检测机制（修订 15）

每个增强子类的 class docstring 首行注明本地增量（§6.1 原则 6）：

```python
class SkillsMiddlewareV2(SkillsMiddleware):
    """V2 extension of SkillsMiddleware.

    # LocalFeatures: [expose_dynamic_tools, allowed_skills, load_skill_tool, unload_skill_tool, V1V2_prompt_mutex]
    """
```

`tools/check_increments.py` 脚本扫描所有增强文件，提取 `# LocalFeatures:` 列表，与上游 diff 比对，输出"哪些特性上游已接受（可折叠），哪些尚未接受（需保留）"。

**每次上游同步前运行**（Round N 标准步骤）：

```bash
cd libs/deepagents
python tools/check_increments.py --compare-upstream upstream/main
```

输出示例：

```text
SkillsMiddlewareV2:
  ✅ expose_dynamic_tools  — upstream accepted in commit abc1234
  ⏳ allowed_skills        — not yet in upstream
  → Action: fold expose_dynamic_tools, retain class (still has local increments)
```

此机制把"应该折叠哪里"从 per-round 人工判断转为可追踪的自动提示，与 §6.4.3 Incremental Folding 步骤直接对应。

### 6.5 跨仓库版本协调（v3 新增，修订 7）

#### 6.5.1 分支与版本策略

| 阶段 | fork 分支 | fork 版本 | pmagent 依赖 |
|---|---|---|---|
| M1 期间 | `master` | 0.5.0（不变） | pin 0.5.0 |
| M2 Phase 1-3 | `feat/internal-restructure`（新建） | 0.5.0+dev | pin 0.5.0（pmagent 主分支不动） |
| Phase 4a 通过 | merge 回 `master`，发 0.6.0 | 0.6.0 | pin 0.5.0（仍不动） |
| Round 16 通过 | `master`（稳定） | 0.6.0 | **升级 PR**：pin 0.6.0 |

#### 6.5.2 pmagent 升级 PR 内容（M2 完成后）

- pmagent `pyproject.toml` 把 deepagents 依赖从 `==0.5.0` 升到 `==0.6.0`
- 跑 pmagent 全量测试（含 9 个 subagent_logs 契约测试）
- 跑 e2e（含 UI 综合测试）
- 验证 `langgraph dev` 启动 + 真实任务执行无回归

#### 6.5.3 紧急回退路径

若 0.6.0 在 pmagent 出现回归：

1. pmagent 仓库立即 revert 升级 PR（恢复 0.5.0 pin）
2. fork `master` 暂不回退（保留 0.6.0 已发版状态）
3. 在 fork 临时分支修复，发 0.6.1
4. pmagent 重新升级 PR

---

## 7. 迁移路线图（双 Milestone，修订 10）

### Milestone 1: pmagent 孤立代码清理（1.5 天，立即启动）

**目标**：消除 pmagent 内"看似平行实现"的视觉污染，让 pmagent = 干净的 fork 消费者。

**Day 1 上午（0.5 天）— Source 删除**

- 删除 `src/middleware/logging.py`（1330）
- 清理 `src/agent.py:21` 死 import
- 删除 `src/services/skills_loader.py`（436）
- 删除 `src/middleware/memory.py`（428）
- 删除 `src/models/skill.py`（120，联动）

**Day 1 下午（0.5-0.75 天）— 测试处置**

- A 策略（直接删）：`tests/test_phase2_5_*.py` (4) + `tests/test_taxonomy.py` + `tests/test_relative_path*.py` (2) + `tests/test_memory_middleware.py` + `tests/manual/verify_phase2_5_*.py` (2) + `tests/manual/test_skills_loader_runtime.py`
- C 精确策略：`tests/test_e2e_comprehensive.py` 删 line 26 局部 import + 相关断言
- C 强制策略（**禁止整体删**）：`tests/test_week1_integration.py` 仅删 MemoryMiddleware 相关；保留 T1.1/T1.2/T1.4/T1.5（state schema、token buffer、postgres checkpointer、token 基准）覆盖

**Day 2 上午（0.25 天，强制门）— 验证**

- `pytest --collect-only` → 0 collection error
- `pytest tests/ -v --cov=src` → 无回归
- `grep "from src.middleware.logging|from src.services.skills_loader|from src.middleware.memory|from src.models.skill"` → 0 残留
- `langgraph dev` 启动冒烟测试

**Day 2 下午（0.25 天）— 文档同步**

- 更新 `pmagent/CLAUDE.md` lines 635-647（Production Middleware Structure 删 logging.py + memory.py 两行）
- 评估 `docs/01-architecture/SKILLS_LOADING_MECHANISM.md` section 6.3
- 修复 `pmagent/CLAUDE.md:647` 过时引用（实际已归档至 `docs/99-archive/`）

**M1 冻结项**（修订 16）：

- `src/security/permissions.py` — **冻结**（file header 已明确 "为 Week 4 工具系统升级准备"，属于计划中的预置代码，不是孤立草案）
  - 执行：在文件顶部添加注释 `# STATUS: FROZEN — scheduled for Week 4 tooling upgrade activation`
  - 期间：保留文件 + `__init__.py:8` import 不动 + 不允许新增引用
  - 跟踪：由 pmagent 技术负责人负责，每季度评审是否达到激活条件（§11.5）

**M1 验收**：pmagent 测试全绿，业务功能无回归，孤立模块 0 残留。

### Milestone 2: Fork 内部重组（5 天，M1 完成 + fork 补强后启动）

**M2 启动条件**（5 个硬性门，与 §11.2 对齐，RC-5 修正）：

1. M1 完成（Phase 0 验证门通过）
2. v3 文档评审通过（含 22 项修订）
3. **Phase 3.0 PoC 完成**（PoC 通过 → 走完整路径；失败 → 启动应急路径）
4. RBAC 冻结标注已完成（pmagent 技术负责人在 `security/permissions.py` 添加 `# STATUS: FROZEN` 注释并确认）
5. **pmagent 技术负责人完成 fork 子类设计方案审签**（评审 §6.4 默认装配设计 + 确认 Phase 3.0 PoC 协作协议，见 §11.6）

#### Phase 1 — Fork additive 模块识别（0.5 天）

**目标**：确认已 additive 的定制（converters/、upload_adapter.py）确实 0 修改上游文件。

- `git diff upstream/main..master -- libs/deepagents/deepagents/middleware/converters/` → 应只显示新增
- `git diff upstream/main..master -- libs/deepagents/deepagents/upload_adapter.py` → 应只显示新增
- 若有任何上游冲突点（如 `__init__.py` 重导出），抽离到独立段或新文件

**验收**：converters/ 与 upload_adapter.py 在上游 merge 时 0 冲突（`git merge-tree` 模拟验证）。

#### Phase 2 — Fork middleware 子类化重构 + 测试规范化（2 天，修订 8）

**目标**：把上游已有 middleware 文件还原至上游基础，本地增强抽出为子类文件；同步规范化测试结构。

**Day 1（1 天）— 源代码子类化**

1. `middleware/skills_v2.py`：抽出 V2 全部增强（load/unload/expose_dynamic_tools/allowed_skills/V1V2 prompt 互斥）作为 `SkillsMiddleware` 子类；`skills.py` 还原至上游 + 添加别名（§6.4.2）
2. `middleware/filesystem_converter.py`：抽出 `_convert_document_sync/async`（middleware/filesystem.py:648/709，模块级函数）为 `FilesystemConverterMiddleware(FilesystemMiddleware)` 子类，并覆盖 `_create_read_file_tool` 注入 converter 调用；`filesystem.py` 还原至上游（CTO-1：converter 是 middleware 层逻辑，不是 backend 层）
3. `middleware/memory_async_compat.py`：抽出 isawaitable 兼容为 `MemoryMiddleware` 子类；`memory.py` 还原至上游 + 别名
4. `middleware/summarization_overwrite_guard.py`：抽出 Overwrite guard 为 `SummarizationMiddleware` 子类；`summarization.py` 还原至上游 + 别名
5. `graph.py`：实现 §6.4.1 装配伪代码；保留公共参数 hook（150-200 行 diff）
6. `tools/check_increments.py`：与第一批子类文件同步创建（RC-3）；扫描所有 `# LocalFeatures:` docstring，与 `upstream/main` diff 比对，输出可折叠特性列表

**Day 2（1 天）— 测试规范化**

实际工作（基于现有 fork tests 状况，修订 8）：

- **拆分**：`test_skills_middleware.py`（混合）→ `test_skills_middleware.py`（V1 基础）+ `test_skills_v2.py`（V2 增强）
- **拆分**：`test_filesystem_*.py`（含 converter 集成测试）→ 抽出 `test_converter_filesystem.py`
- **新增**：`test_summarization_overwrite_guard.py`、`test_memory_async_compat.py`
- **保留**：`test_subagent_logging.py`、`test_subagent_stream_writer.py`、`test_skills_dynamic_tools.py`、`test_summarization_factory.py`（已 additive）

**验收**：

- fork 单测全绿（含新拆分 + 新增的测试文件）
- pmagent 集成测试全绿（pmagent 仓库跑 `pytest tests/`，确认 import 路径别名生效）
- `git diff upstream/main..master --stat` 中上游已有文件的 diff < 250 行总计（修订 1 目标）
- alias smoke test（CTO-3，AD-5 修正）：`python -c "from deepagents.middleware.skills import SkillsMiddleware; assert SkillsMiddleware.__name__ == 'SkillsMiddlewareV2', f'Got {SkillsMiddleware.__name__}'"` 通过，确认别名指向 V2 子类（注：`deepagents/__init__.py` 不导出 `SkillsMiddleware`，勿用 `from deepagents import` 路径——会触发 ImportError）
- converter 调用 smoke test（AD-6）：创建一个包含 PDF/DOCX 文件的临时 `StateBackend`，通过 `FilesystemConverterMiddleware` 的 `read_file` 工具调用确认返回 Markdown 内容（非原始二进制），防止 `_create_read_file_tool` 上游重命名导致 converter 静默失效
- `python tools/check_increments.py --compare-upstream upstream/main` 跑通（RC-3），即使全部特性尚未上游接受也必须输出格式正确的报告

#### Phase 3.0 — 模块级 helper 替换 PoC（0.5 天，修订 4）

**目标**：验证子类 `SubAgentObservability(SubAgentMiddleware)` 通过覆盖 `_stream_subagent_sync` / `_stream_subagent_async` / `_extract_subagent_logs` 等模块级 helper 引用，是否能完整捕获现有 stream_writer + log 行为。

**事实依据**（修订 4 + 0.2 事实核实）：
- `_build_task_tool` 是模块级函数（subagents.py:634），不是闭包
- `_stream_subagent_sync` (line 400)、`_stream_subagent_async` (line 421)、`_extract_subagent_logs` (line 194)、`_extract_stream_progress` (line 269) 都是模块级 helper
- 子类可在 `__init__` 中保存 helper 引用，在 task 调用时使用替换后的版本

**PoC 验证内容**：

1. **建立 Snapshot baseline（RC-1，必须先行）**：在 `subagents.py` 尚未重构前（Phase 2 已完成，Phase 3.0 子类创建前，AD-4）运行 `test_subagent_stream_writer.py` + `test_subagent_logging.py`，捕获所有 `subagent_logs` JSON fixture 输出，固定为 `tests/fixtures/subagent_logs_baseline.json`；提交到 `feat/internal-restructure` 分支
2. 创建 `SubAgentObservability(SubAgentMiddleware)` 子类
3. 覆盖 `_build_task_tool` 装配，注入自定义 stream/log 行为
4. 跑 fork 现有 `test_subagent_stream_writer.py`、`test_subagent_logging.py`，确认所有断言通过
5. 对比步骤 4 输出与步骤 1 baseline → diff 必须为 0（Snapshot 对比）
6. 跑 pmagent 9 个 subagent_logs 契约测试（通过 pmagent 临时验证分支，见下方协议）

**pmagent 临时验证分支协议（RC-2）**：

1. fork 在 `feat/internal-restructure` 上完成步骤 2-3 后，执行 `pip install -e libs/deepagents` 打出 editable install 路径并通知 pmagent 团队
2. pmagent 创建临时分支 `feat/poc-validate-phase3`（不会 merge 到 master）
3. pmagent `pyproject.toml` 修改：`deepagents = {path = "../../deepagents/libs/deepagents", develop = true}`（或 git+file:// 本地路径）
4. 运行 9 个 subagent_logs 契约测试，把结果（PASS/FAIL 清单）反馈给 fork 团队
5. 反馈后，pmagent 临时分支直接关闭（`git branch -D feat/poc-validate-phase3`），不 merge

**PoC 决策门**：

- ✅ 通过 → Phase 3.1 按计划执行
- ❌ 失败 → 启动应急路径：方案 D 降级为"subagents.py 长期保留 ~150 行 patch"，整体 diff 目标修订到 350 行

#### Phase 3.1 — SubAgent 可观测性重构 + 契约保留（1.5-2 天，修订 4 + 5）

**目标**：抽出 stream_writer + logging 为独立中间件 `subagent_observability.py`，subagents.py 还原至上游（仅保留 `_EXCLUDED_STATE_KEYS` additive 接口）。

**关键约束**（修订 5）：

- **subagent_logs 字段格式契约保留**：含 message 提取顺序、敏感字段脱敏规则（`_redact_sensitive_fields`，subagents.py:253）、字段命名（subagent、tool、input、output 等）
- **契约文档化**：写入 `docs/contracts/subagent_logs_contract.md`
- **Snapshot 测试**：Phase 3.1 重构前后对 fork 单测 fixture 的 JSON 输出做 byte-equal 对比

**Phase 3.1 强制门**（修订 5）：

pmagent 9 个 subagent_logs 测试 CI 跑通才能 merge：
- `test_subagent_logs_acceptance.py`
- `test_pmagent_ui_comprehensive.py`（subagent_logs 相关方法）
- `test_pmagent_comprehensive.py`（subagent_logs 相关方法）
- `test_state_schema.py`
- `tests/manual/test_subagent_logging.py`
- `tests/manual/verify_subagent_logging_env.py`
- `tests/manual/verify_subagent_logs_display.py`
- `tests/manual/test_subagent_sdk.py`
- `tests/integration/test_hil_interrupt_mock.py`

**验收**：上述 9 个测试全部 PASS + fork 单测全绿 + Snapshot diff 0。

#### Phase 4a — 本地 merge-tree 验证（0.5 天，修订 12）

**目标**：本地用 `git merge-tree` 模拟近期 30 个上游 commits 与 fork 的 merge，统计冲突文件数 + 模拟解决耗时。

**操作**：

```bash
git fetch upstream main
# git merge-tree 新语法（git ≥ 2.38），2 个参数：HEAD 与 upstream commit（AD-2 修正）
for commit in $(git log upstream/main --since="6 weeks ago" --pretty=%H); do
    git merge-tree HEAD "$commit" > /tmp/merge-tree-${commit:0:8}.txt 2>&1
done
# 统计存在冲突 marker 的文件数
grep -l "^<<<<<<" /tmp/merge-tree-*.txt | wc -l
```

**验收指标**：

- 冲突文件数中位数 0-1 个（vs 现状 5-15 个）
- 单次模拟 merge 解决时间估算 < 30 分钟
- 项目"完成"判定 = Phase 4a 通过（不再依赖 Round 16 时机）

#### Phase 4b — Round 16 真实跟踪（机会性，修订 12）

**目标**：下一次真实 Round 16 时记录耗时，作为长期 KPI 跟踪。

- 不阻塞项目完成判定
- 数据录入 `docs/upstream_merge/ROUND16_PROGRESS.md`
- 与 v2 §9 收益评估对比，验证模型

---

## 8. 风险与缓解（修订 9：含回滚策略）

### 8.1 风险矩阵（v3 更新）

| 风险 | 严重性 | 缓解措施 |
|---|---|---|
| Phase 0 误删 pmagent 活代码（如 context/memory.py 误判） | 🔴 高 | 已用 grep 验证；Phase 0 验证门强制 `pytest --collect-only` + `--cov` |
| Phase 0 `test_week1_integration.py` 误整体删 | 🔴 高 | 强制 C 策略；保留 T1.1/T1.2/T1.4/T1.5 覆盖 |
| **(v3 新增) subagent_logs 字段格式契约破坏** | 🔴 高 | Phase 3.1 提供契约文档；Snapshot 测试；pmagent 9 个测试 CI 强制门 |
| **(v3 新增) Phase 3.0 PoC 失败** | 🟡 中 | 应急路径：方案 D 降级为 subagents.py 长期保留 ~150 行 patch |
| **(v3 新增) graph.py 装配中心 150-200 行长期维护** | 🟡 中 | 接受为本方案"故意保留"；上游 PR-track 推动参数标准化（独立 track） |
| **(v3 新增) 默认装配策略让 pmagent 隐式拿 V2** | 🟡 中 | 通过文档 + 别名注释明示；上游接受后翻转默认值 |
| **(修订 15 新增) 上游部分接受某项定制（如仅接受 `expose_dynamic_tools` 未接受 `allowed_skills`）** | 🟡 中 | Incremental Folding（§6.4.3）：子类继承上游新版，仅保留剩余本地增量；`check_increments.py` 自动识别可折叠特性 |
| graph.py 公共参数永久维护项 | 🟡 中 | 接受为最小公共 API 扩展；与上面合并 |
| SDK 默认 SummarizationMiddleware 与 OverwriteGuard 子类叠加 | 🟡 中 | OverwriteGuard 子类替换默认（§6.4.1），不叠加 |
| security/permissions.py 冻结状态被误解为"已激活"或"可随意修改" | 🟡 中 | 文件头 `# STATUS: FROZEN` 注释明确；不允许新增引用；每季度评审激活条件（§11.5） |
| 上游某项 API 重命名导致 fork 子类失配 | 🟡 中 | fork 子类使用稳定的 SDK 公共 API；私有 API 调用集中标注 |

### 8.2 回滚策略（v3 新增，修订 9）

#### 8.2.1 PR 粒度

- **每个 Phase 一个独立 PR**，禁止跨 Phase 合并 PR
- 每个 PR squash 后保留单一 revert commit 能力
- PR 命名规则：`[v3-phaseX]` 前缀

#### 8.2.2 Phase 间回滚边界

| 已 merge | Phase X 出问题 | 回滚到 |
|---|---|---|
| Phase 1 | Phase 1 自身 | revert PR-1，回到 v3 启动前 master |
| Phase 1 + 2 | Phase 2 出问题 | revert PR-2，保留 Phase 1，重新评估 Phase 2 |
| Phase 1 + 2 + 3.1 | Phase 3.1 出问题 | revert PR-3，保留 Phase 1+2；触发 Phase 3.0 PoC 失败应急路径 |
| Phase 1 + 2 + 3.1 + 4a | Phase 4a 验证不通过 | 不 revert，回到 Phase 3.1 状态评估 hook 不足，可能补 Phase 5 |

#### 8.2.3 Phase 3.0 PoC 失败应急路径

PoC 失败定义：3 项中任一不通过

1. fork 现有 `test_subagent_stream_writer.py`、`test_subagent_logging.py` 不全绿
2. pmagent 9 个 subagent_logs 测试不全绿
3. Snapshot diff > 0（基于 Phase 3.0 步骤 1 建立的 `tests/fixtures/subagent_logs_baseline.json`；RC-1：baseline 必须在 PoC 第一步创建，不能在 Phase 3.1 才建立）

应急动作：

1. 关闭 `feat/internal-restructure` 分支（Phase 1+2 仍可独立 merge）
2. subagents.py 维持现状（保留本地 patch ~150 行）
3. Phase 3 改为"长期保留 fork patch"——subagents.py diff 接受为永久维护项
4. 整体 diff 目标修订：< 250 行 → < 350 行
5. 风险表更新：subagents.py 永久维护项升为 🟡 中

---

## 9. 收益评估（修订 14：含估时表）

### 9.1 估时综合修订表

| 阶段 | v2 估时 | CTO 评审 | pmagent 评审 | **v3 决策** |
|---|---|---|---|---|
| M1: Phase 0 (pmagent) | 1.5 d | 1.5 d | 1.5 d | **1.5 d** |
| M2: Phase 1 (fork additive 识别) | 0.5 d | 0.5 d | 0.5 d | **0.5 d** |
| M2: Phase 2 (子类化 + 测试规范化) | 1.5 d | 2 d | 2 d | **2 d** |
| M2: Phase 3.0 (PoC) | — | (含在 3) | 0.5 d | **1 d**（CTO-2：RC-1 baseline + RC-2 临时分支协议新增 0.5d） |
| M2: Phase 3.1 (实施 + 契约保留) | 1 d | 2-3 d | 2-3 d | **1.5-2 d** |
| M2: Phase 4a (本地 merge-tree) | 0.5 d | 0.5 d | 0.5 d | **0.5 d** |
| M2: Phase 4b (Round 16 跟踪) | — | — | — | 机会性，不计 |
| **pmagent upgrade PR**（M2 完成后，pmagent 团队负责） | — | — | — | **0.5-1 d** |
| **总计（fork 团队日历）** | 4.5 d | 6.5-7.5 d | 6-7.5 d | **6.5-7 d** |
| **总计（日历，含并行）** | — | — | — | **5.5-6 d（M1∥M2）+ 0.5-1 d（upgrade PR）** |

考虑 M1 与 fork v3 文档 + Phase 3.0 PoC 并行：**实际日历时间 5.5-6 d**。

### 9.2 收益指标

| 指标 | 现状 | v3 方案 D 之后 |
|---|---|---|
| Fork 与上游修改文件 diff | ~3500 行 | **300-400 行**（修订 1） |
| 修改文件数 | 5-15 个 | **2-3 个**（graph.py + subagents.py + 偶见微补丁） |
| 上游同步耗时 | 2-6 小时/轮 | **< 30 分钟/轮**（Phase 4a 验证） |
| 上游同步冲突文件 | 5-15 个 | **0-1 个**（Phase 4a 验证） |
| pmagent 业务代码改动 | — | **0 行**（修订 3 默认装配 + 别名保障） |
| pmagent 仓库行数变化 | — | **-2772 行**（清理孤立草案） |
| Fork 仓库新文件 | — | +6-7 个增强模块 + 4-5 个测试文件 |
| 总迁移工作量（日历） | — | **5.5-6 天**（RC-7；不含 pmagent upgrade PR 的 0.5-1 天） |
| 长期维护成本 | 高（每轮被动跟进） | 低（fork 装配中心 1 个文件 1 次解决） |

按当前节奏（每月 1-2 轮上游同步，每轮 3-5 小时），方案 D 在 1.5-2 个月内即可回本。

---

## 10. 决策建议

**强烈推荐方案 D（Fork 内部重组）**，理由：

1. **服务全部 5 条目标**：
   - 优化目标 1、5（diff、耗时）：通过 additive 重组 + graph.py 装配中心达成
   - 架构目标 2：无任何人为命名空间（v3 §6.1 原则 5 阐明）
   - 约束目标 3、4：pmagent 业务代码零修改（修订 3 默认装配 + 别名）+ 可演进
2. **ROI 最高**：5.5-6 天投入换来未来每轮节省 1.5-5.5 小时
3. **风险可控**：分 M1 + M2，M2 内 5 阶段独立可验证、可回滚（修订 9）
4. **可演进**：上游接受某项定制后，删除增强文件 + 别名即可，pmagent 自动获得上游版本

**不推荐方案 A（完全下沉）**：放弃 `create_deep_agent` 装配收益太大。
**不推荐方案 B（v1 原推荐）**：基于错误前提，引入人为命名空间。
**不推荐方案 C（保守）**：根本问题未解决。

---

## 11. 后续步骤（双 Milestone，修订 10）

### 11.1 立即启动（M1 + 并行决策）

1. **M1 启动**（pmagent 团队，1.5 天）：按 Phase 0 清单执行
2. **并行：fork 团队 v3 文档评审 + Phase 3.0 PoC**（0.5-1 天）
3. **并行：RBAC 冻结标注**（pmagent 技术负责人）：在 `security/permissions.py` 顶部添加 `# STATUS: FROZEN — scheduled for Week 4 tooling upgrade activation`；移除"决策时钟"约束（文件用途已明确，Week 4 激活路径存在）
4. **并行：上游 PR-track**（fork 团队，独立 track，不阻塞）：向上游提交 `state_schema` 标准化提案

### 11.2 M2 启动条件（5 个硬性门，修订 18）

1. M1 完成（Phase 0 验证门通过）
2. v3 文档评审通过（含 22 项修订，最新版）
3. Phase 3.0 PoC 完成（含决策门：PoC 通过 → 走完整路径；失败 → 启动应急路径）
4. RBAC 冻结标注已完成（pmagent 技术负责人执行并确认）
5. **pmagent 技术负责人完成 fork 子类设计方案审签**（M2 pre-start pmagent task package：评审 §6.4 默认装配设计 + 确认 Phase 3.0 PoC 协作协议；与条件 3 的 PoC 打包为同一 0.5 天工作单元，见 §11.6）

### 11.6 pmagent 团队三时间点介入（修订 18）

| 时间点 | 工作 | 估时 | 产出 |
| --- | --- | --- | --- |
| **M1 执行**（立即启动） | Phase 0 孤立代码清理 | **1.5 d** | pmagent 测试全绿，孤立模块 0 残留 |
| **M2 pre-start**（M1 完成后，与条件 4+5 打包） | 评审 §6.4 fork 子类设计 + RBAC 冻结标注 + Phase 3.0 PoC 配合（运行 9 个 subagent_logs 契约测试） | **0.5 d** | 设计审签（条件 5）+ RBAC 标注（条件 4）+ PoC 决策门输入（条件 3） |
| **M2 完成后** | pmagent upgrade PR：deepagents 依赖 0.5.0→0.6.0，全量测试 + e2e + `langgraph dev` 冒烟 | **0.5-1 d** | pmagent 消费 fork 0.6.0 验证通过 |
| **合计 pmagent 工作量** | | **2.5-3 d** | |

> M2 pre-start task package 建议打包成一个 0.5 天工作单元交付 pmagent 团队，避免多次协调往返。
>
> **AD-3 并行澄清**：§11.2 条件 5（设计审签）仅需阅读 §6.4 文档，**不依赖 PoC 结果**，可以在 fork 启动 Phase 3.0 PoC 之前独立完成。条件 3（PoC 完成）和条件 5（审签）可真正并行，无需等待对方。防止协调死锁：pmagent 技术负责人先审签 §6.4，fork 团队随即启动 PoC 实施，pmagent 在 PoC 步骤 6 时提供 9 个测试结果。

### 11.3 M2 执行（fork 团队，5 天）

按 §7 Milestone 2 执行 Phase 1 → 2 → 3.1 → 4a。

### 11.4 项目完成判定

- M1 通过
- M2 Phase 4a 通过（本地 merge-tree 验证：冲突文件中位数 0-1 个，模拟解决 < 30 分钟）
- 不依赖 Round 16 真实时机

### 11.5 长期跟踪

- Phase 4b：Round 16 真实数据记录（不阻塞完成）
- `security/permissions.py` 冻结状态 + **每季度评审**激活条件（负责人：pmagent 技术负责人）；Week 4 启动时转为激活态，届时删除 FROZEN 注释
- 上游 state_schema PR 状态跟踪
- `tools/check_increments.py` 每次上游同步前运行，输出可折叠增量提示（§6.4.4）

---

## 附录 A — 与 v2 的对应关系

| v2 章节 | v3 章节 | 状态 |
|---|---|---|
| 0. 修订摘要 | 0 | **重写**（含事实核实 + 14 项修订） |
| 1. 问题定义 | 1 | 不变 |
| 2. 定制清单 | 2 | 不变 |
| 3. 下游依赖核查 | 3 | **扩展**（含 subagent_logs 9 测试） |
| 4. 可行性矩阵 | 4 | **修订**（删除 state_schema 上游路径） |
| 5. 三方案对比 | 5 | 不变 |
| 6.1-6.3 设计 | 6.1-6.3 | **修订**（§6.1 原则 5、§6.3 diff 目标 150-200） |
| — | **6.4 默认装配策略**（新增） | 修订 3 + 6 |
| — | **6.5 跨仓库版本协调**（新增） | 修订 7 |
| 7. Roadmap | 7 | **重写**（双 Milestone，Phase 3 拆 3.0+3.1，Phase 4 拆 4a+4b） |
| 8. 风险 | 8 | **修订** + 8.2 回滚策略（新增） |
| 9. 收益 | 9 | **修订**（估时表更新） |
| 10. 决策建议 | 10 | 修订 |
| 11. 后续步骤 | 11 | **重写**（双 Milestone 推进） |

---

## 附录 B — 14 项修订项索引

| # | 修订项 | v3 落地章节 | 来源 |
|---|---|---|---|
| 1 | graph.py diff 目标 30-50 → 150-200 行 | §0.4、§6.3、§9.2 | 实测 458 行 |
| 2 | 删除 state_schema 上游路径 | §4 第 6 行 | Round 14/15 PROGRESS |
| 3 | 默认装配策略 | §6.4 | CTO 反对 2 |
| 4 | Phase 3 拆 3.0 PoC + 3.1 实施 | §7 M2 Phase 3.0/3.1 | pmagent 补强 2 |
| 5 | subagent_logs 契约保留 + 9 测试门 | §3.3.3、§7 Phase 3.1、§8.1 | pmagent 风险 2 |
| 6 | graph.py 装配逻辑设计 | §6.4.1 | pmagent 补强 1 |
| 7 | 跨仓库版本协调 | §6.5 | CTO 保留 1 |
| 8 | Phase 2 测试结构规范化 | §6.2、§7 M2 Phase 2 | pmagent 补强 4 + 实测 |
| 9 | 回滚策略 | §8.2 | CTO 保留 3 |
| 10 | 双 Milestone 切分 | §7、§11 | pmagent 推进建议 |
| 11 | 文件名后缀命名空间原则 | §6.1 第 5 条 | CTO 保留 5 |
| 12 | Phase 4 拆 4a + 4b | §7 M2 Phase 4a/4b | CTO 保留 6 |
| 13 | RBAC 1 个月强制收敛 | §7 M1 暂缓项、§11.1 | 综合 |
| 14 | 估时表 4.5d → 6-6.5d | §9.1 | 三方综合 |
| 15 | §6.4.3 演进路径 → Incremental Folding + §6.4.4 检测机制 + §6.1 原则 6 | §6.1、§6.4.3、§6.4.4 | CTO + pmagent 综合 |
| 16 | RBAC 1 个月时钟 → 冻结 + 每季度评审 | §3.2、§7 M1 冻结项、§11.1、§11.5 | 事实核实（permissions.py file header） |
| 17 | pmagent upgrade PR 估时 + 团队角色 | §9.1、§11.6 | CTO 补充 |
| 18 | 5 个 M2 启动条件 + pmagent 三时间点角色 §11.6 | §11.2、§11.6 | CTO 补充 |
| 19 | skills.py diff 构成分析（§6.3a） | §6.3a | RC-4 代码核实 |
| 20 | converter 层级修正：backends/→middleware/，FilesystemMiddleware 子类（§6.2、§6.4.1、§7 Phase 2） | §6.2、§6.4.1、§7 | CTO-1 |
| 21 | Phase 3.0 Snapshot baseline 先行 + pmagent 临时分支协议 + Phase 2 验收 alias smoke test + check_increments.py 创建 | §7 Phase 3.0、§7 Phase 2 | RC-1/2/3、CTO-3 |
| 22 | §6.4.3 完整折叠 SOP、Phase 4a git 命令、AD-3 并行澄清、§8.1 RBAC 清理、Phase 3.0 估时 1d | §6.4.3、§7 Phase 4a、§8.1、§9.1、§11.6 | AD-1/2/3、CTO-2、K |
| 23 | §7 M2 启动条件 4→5 条件 + 内容对齐 §11.2 | §7 Milestone 2 开头 | RC-5 |
| 24 | §0.3/§9.2/§10 日历时间同步 + §7/§11.2 修订范围数字更新 | §0.3、§7、§9.2、§10、§11.2 | RC-6、RC-7 |
| 25 | Phase 3.0 措辞澄清 + alias smoke test 修正（代码核实 ImportError 风险）+ converter smoke test | §7 Phase 3.0、§7 Phase 2 验收 | AD-4、AD-5、AD-6 |

---

## 附录 C — 事实核实证据索引

| 事实 | 证据 |
|---|---|
| graph.py 实测 458 行 diff | `git diff upstream/main..master --stat -- libs/deepagents/deepagents/graph.py` |
| `_build_task_tool` 是模块级函数 | `libs/deepagents/deepagents/middleware/subagents.py:634` |
| Round 14/15 未接受 state_schema | `docs/upstream_merge/ROUND14_PROGRESS.md`、`ROUND15_PROGRESS.md`（state_schema 仅作为本地红线测试出现） |
| pmagent 9 个 subagent_logs 测试 | `pmagent/tests/test_subagent_logs_acceptance.py` 等 9 文件 grep 验证 |
| pmagent 4 模块孤立 + context/memory.py 活代码 | `pmagent/src/agent.py:35-36, 540-548`（活代码）+ 4 模块业务零调用 grep |
| `_extract_subagent_logs` 等是模块级 helper | subagents.py:194, 253, 269, 333, 364, 370, 388, 400, 421 |
| fork tests 已部分 additive | `libs/deepagents/tests/unit_tests/middleware/` 目录列表 |
| `test_week1_integration.py` 多组件覆盖 | file lines 4-9, 510-513 |
| CLAUDE.md 过时段 | `pmagent/CLAUDE.md:635-647` |
| `middleware_cleanup_final_report.md` 实际位置 | `pmagent/docs/99-archive/middleware_cleanup_final_report.md`（CLAUDE.md:647 引用错误） |
| skills.py fork diff 671 行 | `git diff upstream/main..master --stat -- libs/deepagents/deepagents/middleware/skills.py`（538+/133-） |
| `security/permissions.py` 属于 Week 4 预置 | 文件头注释 "为 Week 4 工具系统升级准备"，commit `a407a6f` |
