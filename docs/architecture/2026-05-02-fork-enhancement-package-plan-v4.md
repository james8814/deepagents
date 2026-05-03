> ⚠️ **SUPERSEDED 2026-05-02** — 本文档（Plan E++ / v4-rev2）**已被 Plan H+ 取代**。
>
> Plan E++ 包含 monkey-patch 设计（在 enhanced 包内），保留 fork 仓库依赖。在 8 次方向探索后，团队识别出：
> - pmagent 6-12 月需要 harness 层主权（用户明确表达）
> - fork 仓库无独立组织价值（james8814/deepagents 个人仓库）
> - Plan H 的"装配代码"实质是上游 graph.py 的拷贝 + V2 替换（非新写）
> - **Plan H+ 是 Plan H 的逻辑终局**：消除 fork、pmagent 全主权、私有 API 治理纪律
>
> **当前权威方案**：[`2026-05-02-plan-h-plus-final.md`](2026-05-02-plan-h-plus-final.md)
> **决策档案**：[`decisions/0002-fork-customization-strategy.md`](decisions/0002-fork-customization-strategy.md)（Draft，等三方签字）
>
> 本文档保留为**决策档案**，记录 v4-rev2 / Plan E++ 设计的完整推理过程，供未来翻盘评估或方法论复盘。
>
> ---

# Fork 定制下沉方案 v4-rev2 — Plan E + 路径 B + Option M（已被 Plan H+ 取代，保留为决策档案）

**日期**: 2026-05-02
**作者**: deepagents 项目技术总监 + 架构师团队
**状态**: 取代 v3 Plan D 的根本性方案重选；含 pmagent 两轮评审 11 项修订（v4-rev2）
**前序**:

- v1 `2026-04-29-fork-customization-downsink-plan.md` (Plan B 否决版)
- v2 `2026-05-01-fork-customization-downsink-plan-v2.md` (Plan D 提出版)
- v3 `2026-05-01-fork-customization-downsink-plan-v3.md` (Plan D 三轮加强版)
- v4 草稿（Plan E + 路径 B 初版，AsyncCompatBackend wrapper）
- v4-rev1：含 pmagent 第一轮评审修订（RC-1/2/3 + AD-1/2/3）+ Option M 替换 AsyncCompatBackend
- **v4-rev2（当前）**：含 pmagent 第二轮评审修订（RC-4/5 + AD-4/5 + LR-1/2/3）+ mutate-in-place patch

**目标读者**: 项目负责人、deepagents fork 团队、pmagent 业务团队

**v4 → v4-rev1 修订摘要**（pmagent 第一轮评审驱动）：

| 修订项 | 原 v4 | v4-rev1 |
| --- | --- | --- |
| RC-1 | SummarizationMiddleware 未 patch（致命漏洞） | §5.3 含 dual-target patch（Skills/SubAgent in graph + Summarization in module） |
| RC-2 | CI 命令 `git diff upstream/main..HEAD` 方向错误 | §5.2 改为 `git log MERGE_BASE..HEAD --no-merges` |
| RC-3 | AsyncCompatBackend wrapper 破坏 12 处 isinstance | §6.2 替换为 **Option M：in-place 方法 patch** |
| AD-1 | Phase 3.0 PoC 0.5d 范围太窄 | §8 扩展为 **1d**，6 项验证清单 |
| AD-2 | BinaryDocConverter 位置 §5.3 与 §6.4 不一致 | §5.3 改为 prepend（在用户 middleware 之前） |
| AD-3 | 缺 invariant 持续守护 | §B.4 新增 `test_invariant_v2_assembled.py` 设计 |

**v4-rev1 → v4-rev2 修订摘要**（pmagent 第二轮评审驱动）：

| 修订项 | v4-rev1 问题 | v4-rev2 修复 |
| --- | --- | --- |
| RC-4 | §8 Phase 1 残留旧 CI 命令（与 §5.2 不一致） | line 942 改为引用 §5.2 的正确命令 |
| RC-5 | `_EXCLUDED_STATE_KEYS` reassignment 模式有引用捕获风险（前瞻性）| §5.4 切换为 **mutate-in-place via `set.update()`**；Phase 3.0 新增第 7 项验证 |
| AD-4 | §9.1 风险表 PoC 失败行 🔴 高，与 §9.3 已规避矛盾 | §9.1 该行改为 🟢 低 + 备注更新 |
| AD-5 | §B.4 invariant 测试用 `__name__` 字符串比较（脆弱） | 改用类身份比较 `type(m) is V1` |
| LR-1 | §9.1 lazy import 缓解归因到 startup assertion（错） | 改为归因到 §B.4 invariant 测试（运行时防线） |
| LR-2 | enhanced 包跨大版本升级（0.7+）维护未跟踪 | §11.4 新增长期维护清单 |
| LR-3 | check_increments.py 触发时机未明确 | §11.4 显式列入"每轮上游 sync 前强制跑" |

---

## 0. 摘要

### 0.1 v4 与 v3 的根本性差异

v3 推荐 **Plan D（fork 内部重构）**，目标"fork 内部 diff < 250 行 + 装配中心 graph.py 长期维护"。
v4 推荐 **Plan E（独立 enhancement 包）+ 路径 B（最大化 additive）**，目标"fork **完全 0 修改上游文件** + shadow 风险压到最低 2 项"。

| 关键指标 | v3 (Plan D) | v4 (Plan E + 路径 B) |
| --- | --- | --- |
| Fork 修改上游文件 | graph.py 200 行 + 末尾 alias × 4 + subagents.py 10 行 | **0 行**（仅 pyproject.toml 版本号偶冲突）|
| 实测 merge 冲突 | **5 大文件冲突**（graph.py, subagents.py, skills.py, filesystem.py, summarization.py） | **数学保证 0 冲突** |
| Shadow 风险数 | 5 项（#1, #3, #5, #7, #8） | **2 项**（仅 #1 Skills V2、#5 SubAgent obs） |
| pmagent 改动 | 0 行（透明） | **1 行 import**（一次性） |
| 总投入（日历，M1∥M2 并行） | 6-6.5 d | **6.5-7 d**（多 0.5-1 d 换零冲突 + 60% shadow 削减；含 v4-rev1 PoC 扩展 0.5 d） |
| 长期每轮 sync | 5-30 分钟解决冲突（焦虑常态化） | **< 5 分钟**（fast-forward + 可选 review） |

### 0.2 推动 v4 的实证数据（v3 之后才采集）

**实测一**（`git merge-tree HEAD upstream/main`）：当前 master 合并 upstream/main 的 SDK 部分**5 大冲突**：
```
CONFLICT (content): libs/deepagents/deepagents/graph.py
CONFLICT (content): libs/deepagents/deepagents/middleware/filesystem.py
CONFLICT (content): libs/deepagents/deepagents/middleware/skills.py
CONFLICT (content): libs/deepagents/deepagents/middleware/subagents.py
CONFLICT (content): libs/deepagents/deepagents/middleware/summarization.py
```

**实测二**（最近 100 commits 修改频率）：
- graph.py 改动 3 次
- subagents.py 改动 2 次
- skills.py 改动 2 次
- filesystem.py 改动 0 次
- summarization.py / memory.py 少数次

**实测三**（上游 graph.py 修改区域分布）：近 10 commits 修改 hunk 覆盖 line 1-600 几乎全部，包括 fork 修改的中间件实例化区（445-580）。

**实测四**（`awrap_tool_call` API 可用性）：
- deepagents 自身 2 处生产使用（`permissions.py:344`、`filesystem.py:1953`）
- 完整测试覆盖（`test_middleware.py`、`test_permissions.py`）
- 同步 + 异步双版本

**实测五**（**Plan E 物理可行性 PoC，2026-05-02 已通过**）：

PoC #1 — 4 个中间件类的 monkey-patch 替换（`/tmp/plan_e_poc.py`）：

| 测试 | 结果 |
| --- | --- |
| Test 1 — 不打 patch 时上游用 V1（baseline）| ✅ |
| Test 2 — 打 patch 时上游用 V2（核心）| ✅ Skills V2: 2 实例、Filesystem V2: 2、Memory V2: 1、SubAgent V2: 1 |
| Test 3 — context manager exit 后引用还原 | ✅ |
| Test 4 — exit 后再次调用不再用 V2，无 patch 泄漏 | ✅ |

PoC #2 — Summarization factory 注入（`/tmp/plan_e_poc2_summarization.py`）：

| 测试 | 结果 |
| --- | --- |
| Test 5 — baseline factory 返回上游 `_DeepAgentsSummarizationMiddleware` | ✅ |
| Test 6 — monkey-patch summarization 模块 class → factory 返回 V2 | ✅ `isinstance(mw, V2) is True` |
| Test 7 — full `create_deep_agent` 装配 V2 Summarization | ✅ 2 实例（主 agent + 通用 subagent） |

**关键技术结论**：

- `_patched_middleware_classes` 在 fork 仓库内 100% 工作（Test 2）
- 主 agent + general-purpose subagent **共享同一份被 patch 的 graph 模块引用**（Skills/FS/Summarization 各 2 实例都是这个原因）—— monkey-patch 自动覆盖主 agent 和 subagent 全部装配路径
- Summarization 通过 module-level class swap（不是 graph module）注入——两种 patch 模式协同工作
- patch 范围严格局限在 `with` 块内，无运行时副作用

**实测六**（**Option M backend 方法 patch PoC，2026-05-02**）：

为响应 pmagent 第二轮评审 RC-3（AsyncCompatBackend wrapper 破坏 12 处 isinstance 检查），实测了 **Option M：in-place 方法 patch**（不创建 wrapper 类，直接替换 backend 实例上的 `adownload_files`）。

PoC 脚本：`/tmp/option_m_poc.py`

| 测试 | 结果 |
| --- | --- |
| Test 1 — StateBackend（proper async）→ no-op 跳过 | ✅ |
| Test 2 — Buggy 同步 backend → patch 后 `await` 工作正确 | ✅ |
| Test 3 — **isinstance 完整保留**（StateBackend、FilesystemBackend、CompositeBackend、BackendProtocol 全部 True） | ✅ |
| Test 4 — 幂等性（多次 patch 调用安全） | ✅ |
| Test 5 — fork 既有测试场景 `_FakeBackendSyncAdownload` 在 Option M 下通过 | ✅ |

**实测七**（Option H 反向验证：还原 fork memory.py 到上游版本，跑 fork 单测）：

```
FAILED tests/unit_tests/middleware/test_memory.py::test_abefore_agent_tolerates_sync_adownload_files
1 failed, 12 passed
```

失败的测试用例 `_FakeBackendSyncAdownload` 类内注释明示："Intentionally synchronous 'async' API to simulate buggy/legacy backends"——证明 #7 isawaitable 是**有测试守护的活防御代码，不可移除**。Option H 否决。

**Option M 决策**：替代原 v4 §6.2 的 AsyncCompatBackend wrapper 设计（详见 §6.2 修订）。

**实测八**（**v4-rev1 扩展 Phase 3.0 PoC，2026-05-02 全部通过**）：

为响应 pmagent AD-1 评审（PoC 范围太窄，0.5d 估时不够），执行了**扩展集成 PoC**，覆盖 6 项验证维度。脚本：`/tmp/v4_rev1_phase3_extended_poc.py`

| 测试 | 验证维度 | 实测结果 |
| --- | --- | --- |
| Test 1 | 三类同时 patch（Skills + SubAgent + Summarization） | ✅ 单次 enhanced.create_deep_agent 调用产生 V2: 2、SubAgentObs: 1、SummGuard: 2 实例 |
| Test 2 | Contextmanager 退出还原 | ✅ 3 个引用全部还原 |
| Test 3 | Sequential + 异常路径 | ✅ 3 次顺序调用产生 6 V2 实例；异常 path 通过 finally 块完整还原；后续 unpatched 调用 0 V2 泄漏 |
| Test 4 | Option M isinstance 保留 | ✅ StateBackend / FilesystemBackend / CompositeBackend × BackendProtocol = 6/6 isinstance 通过 |
| Test 5 | Buggy backend 端到端 | ✅ `_BuggyBackend` class 不变，Memory 正确加载内容（无 await TypeError） |
| Test 6 | BinaryDocConverter 链位置 | ✅ 拦截上游调用实测：`["BinaryDocConverterStub", "_UserMiddlewareStub"]` — prepend 生效 |

**累计 PoC 验证统计（4 个脚本，18 个测试）**：

| PoC 脚本 | 测试数 | 通过 | 用途 |
| --- | --- | --- | --- |
| `plan_e_poc.py` | 4 | 4 | 基础 monkey-patch（Skills/SubAgent/FS/Memory）|
| `plan_e_poc2_summarization.py` | 3 | 3 | Summarization factory 注入 |
| `option_m_poc.py` | 5 | 5 | Option M backend 方法 patch |
| `v4_rev1_phase3_extended_poc.py` | 6 | 6 | 扩展集成（AD-1 全部 6 项）|
| **累计** | **18** | **18 (100%)** | — |

**结论**：v4-rev1 设计在 fork 仓库内**100% 物理可行**。M2 启动条件 #3"Phase 3.0 PoC 决策门"提前完成，**0 失败 / 0 浪费**。剩余 M2 启动条件仅需流程协调（M1 完成 + 文档评审 + RBAC 标注 + pmagent 审签），无技术风险阻塞。

**PoC 脚本归档（M2 回归测试种子）**：
4 个 PoC 脚本将在 M2 Phase 1（enhanced 包脚手架）完成后移植到 `libs/deepagents-enhanced/tests/` 作为持续守护测试套件。invariant 测试设计见 §B.4。

### 0.3 v4 的核心收益（按用户初衷重排）

| 用户优先级 | v4 表现 |
| --- | --- |
| 🔴 P0 上游同步**冲突概率接近 0** | ✅ **数学保证 0 冲突**（fork 不修改任何上游文件）|
| 🔴 P1 不增加 pmagent 难度/风险 | ✅ 仅一次性 1 行 import 修改，无概念负担、无维护负担 |
| 🟢 P2 ROI 最高、风险最低、效率最高 | ✅ 多 2-2.5 d 投入换长期每轮零冲突 + shadow 60% 削减 |
| ⚪ N/A fork 无需"完全干净" | ⚠️ v4 比 v3 更干净（fork 0 修改），但这不是目标，是副产物 |

### 0.4 v4 的硬约束（基于用户多轮澄清）

1. **fork 不修改上游文件**（数学保证零冲突的唯一手段）
2. **不依赖上游 PR**（不可控）
3. **pmagent 装配责任不能外推**（约束目标 3）
4. **路径 B 子项 #3/#7/#8 重构是补强，不是核心**（Plan E 已经达成 P0 目标，路径 B 进一步降低 shadow 风险）

---

## 1. 问题定义

### 1.1 现状

- fork 内嵌 11 项深度定制，与上游 diff ~3500 行
- 累计 ~1069 commits 跨 15 轮合并
- 每轮上游同步 2-7 小时（Round 13: 7-9h、Round 14: 2.5h、Round 15: ~5h）

### 1.2 v3 走 Plan D 后未解决的问题

实测 (§0.2) 表明：即使 v3 Phase 2 后还原大部分文件到上游，**graph.py 200 行装配 diff 在最新 upstream 同步时仍是确定冲突源**。"装配中心长期维护"在数学上无法做到"接近 0 冲突"。

### 1.3 v4 的破局思路

**数学定理**：merge 冲突的充要条件是双方修改同一文件的同一区域。**fork 完全不修改上游任何文件 → 上游同步必然 0 冲突。**

只有放弃"fork 内部修改上游文件"这条路径，转向"fork 提供独立 enhancement 包 + pmagent 改导入入口"，才能数学保证零冲突。

---

## 2. 11 项定制按"上游干扰风险"重新分类（v4 视角）

| # | 定制项 | v3 类别 | v4 类别（路径 B 后） | shadow 风险 |
| --- | --- | --- | --- | --- |
| 2 | Converters 子包 | 纯 additive | **纯 additive** | ✅ 0 |
| 4 | Upload Adapter V5 | 纯 additive | **纯 additive** | ✅ 0 |
| 9 | `_EXCLUDED_STATE_KEYS` 扩展 | 子类覆盖 | **永久 monkey-patch（union 扩展）** | ✅ 0 |
| 10 | SubAgent TypedDict 字段 | 子类覆盖 | **TypedDict 扩展（语义 additive）** | ✅ 0 |
| 6 | graph.py 参数与装配 | 子类覆盖 | **临时 monkey-patch 类引用 + **kwargs 透传** | ✅ 0 |
| 8 | Summarization Overwrite guard | 子类覆盖 | **augment + super() 模式** | ✅ 0 |
| 7 | Memory isawaitable | 子类覆盖 | **Option M：in-place 方法 patch（路径 B 重构，v4-rev1）** | ✅ 0 |
| 3 | Filesystem Converter | 子类覆盖 | **BinaryDocConverterMiddleware（路径 B 重构）** | ✅ 0 |
| 1 | SkillsMiddleware V2 | 子类覆盖 | **子类覆盖（不可避免）** | ⚠️ 中-高 |
| 5 | SubAgent stream_writer + logging | 子类覆盖 | **子类覆盖（不可避免）** | ⚠️ 高 |
| 11 | SubAgent 敏感字段脱敏 | 含在 #5 | 含在 #5 | ⚠️ 同 #5 |

**统计**：
- v3 状态：5 项 shadow 风险
- v4 状态：**2 项** shadow 风险（仅 #1 Skills V2 和 #5 SubAgent obs）
- 削减：**60%**

---

## 3. 上游冲突实证数据（决策驱动）

### 3.1 当前 master 合并最新 upstream 的实测冲突清单

执行 `git merge-tree HEAD upstream/main`（395 个未合并 commits，最新一次实测）：

| 文件类别 | 冲突数 |
| --- | --- |
| SDK 核心 (`libs/deepagents/deepagents/`) | **5 大文件**（graph.py、filesystem.py、skills.py、subagents.py、summarization.py） |
| CLI (`libs/cli/`) | 多处（CLI 团队各自处理） |
| ACP / Examples / Workflows | 少数 |

**SDK 5 大冲突文件正好对应 fork 11 项定制的核心文件**——这不是巧合，是因为 fork 在这些文件上做了重型修改。

### 3.2 上游对这些文件的修改频率（近 100 commits）

| 文件 | 修改次数 | 频率 |
| --- | --- | --- |
| graph.py | 3 | 3% |
| subagents.py | 2 | 2% |
| skills.py | 2 | 2% |
| filesystem.py | 0 | 0% |
| summarization.py | 少数 | < 5% |
| memory.py | 少数 | < 5% |

**关键观察**：单次 commit 修改频率不高，但 fork 的修改区域分布广，**累计冲突几乎必然发生**。

### 3.3 v3 Plan D 之后预期冲突的剩余分析

| 文件 | Phase 2 后 fork diff | 上游热度 | 预期冲突 |
| --- | --- | --- | --- |
| graph.py | ~200 行（中间件实例化区） | 改动覆盖 line 1-600 几乎全部 | 🔴 几乎每次都冲突 |
| subagents.py | ~10 行（_EXCLUDED_STATE_KEYS + TypedDict）| `_build_task_tool` 大重构（commit 83cc8762） | 🟡 部分冲突 |
| skills.py | ~5 行（末尾 alias） | 2 次 | 🟢 概率低但非零 |
| memory.py / summarization.py / filesystem.py | ~5 行各 | 部分 | 🟢 概率低但非零 |

**结论**：v3 Plan D 实施后**仍达不到"接近 0 冲突"目标**。

---

## 4. 方案对比（v4 视角全面修订）

| 方案 | fork 修改上游文件 | 数学保证 0 冲突 | pmagent 难度 | 总投入 | 长期每轮 sync |
| --- | --- | --- | --- | --- | --- |
| Plan A 完全下沉到 pmagent | 0 | ✅ | 🔴 高（pmagent 接管装配） | — | — |
| Plan B 引入 deepagents_ext/ namespace | 部分 | ❌ | 🟡 中 | — | — |
| Plan C 完全保守（不动） | 已有 ~3500 行 | ❌ | 0 | 0 | 🔴 2-7 小时 |
| **Plan D (v3 推荐)** | graph.py 200 + alias × 4 + subagents 10 | ❌（实测仍冲突）| 0 | 6-6.5 d | 🟡 5-30 分钟 |
| Plan Q (pmagent 接管装配) | _EXCLUDED_STATE_KEYS 1 行 | 🟢 接近 | 🔴 +150 行装配永久维护 | 7-8 d | 🟢 < 5 分钟 |
| Plan R (全局 monkey-patch) | 0 | 🟢 | 🟡 import order 概念负担 | 5.5-6.25 d | 🟢 < 5 分钟 |
| **Plan E (v4-rev1 推荐) + 路径 B + Option M** | **0** | **🟢 数学保证** | **1 行 import（一次性）** | **6.5-7 d 日历** | **🟢 < 5 分钟** |

**为什么 Plan E + 路径 B 是最优**：
1. 数学保证零冲突（独有特性，仅 Plan A/Plan E/Plan Q/Plan R 可能达成）
2. pmagent 一次性 1 行 import（远低于 Plan A 的"接管装配"和 Plan Q 的"+150 行"）
3. 路径 B 把 #3/#7/#8 三项 shadow 风险消除，剩 2 项必须保留的子类
4. 上游升级红利继承能力强（**kwargs 透传 + 子类继承 + 调上游 graph.py）

---

## 5. Plan E 架构详细设计

### 5.1 仓库布局（v4 关键变化）

```text
libs/deepagents/                                   # ⬆️ 上游镜像，fork 0 修改
└── deepagents/
    ├── __init__.py                                # 完全上游
    ├── graph.py                                   # 完全上游
    ├── middleware/
    │   ├── skills.py                              # 完全上游
    │   ├── filesystem.py                          # 完全上游
    │   ├── memory.py                              # 完全上游
    │   ├── summarization.py                       # 完全上游
    │   └── subagents.py                           # 完全上游
    └── ...

libs/deepagents-enhanced/                          # 🆕 fork 增强独立包
├── pyproject.toml                                 # 依赖 deepagents>=0.5.0,<0.7
└── deepagents_enhanced/
    ├── __init__.py                                # 自动应用 _patches + 导出 create_deep_agent
    ├── _patches.py                                # 永久 monkey-patch（仅 _EXCLUDED_STATE_KEYS）
    ├── _assertions.py                             # startup assertion（防止上游重命名静默失效）
    ├── graph.py                                   # 增强版 create_deep_agent（含临时 monkey-patch）
    ├── middleware/
    │   ├── skills_v2.py                           # SkillsMiddleware 子类（v3 设计保留）
    │   ├── subagent_observability.py              # SubAgentMiddleware 子类（v3 设计保留）
    │   ├── summarization_overwrite_guard.py       # SummarizationMiddleware 子类（augment + super 模式）
    │   ├── binary_doc_converter.py                # 🆕 路径 B：post-processing middleware
    │   └── (memory_async_compat 删除 — 改用 backend wrapper)
    ├── backends/
    │   └── async_compat.py                        # 🆕 路径 B：add_async_compat() in-place 方法 patch（Option M，v4-rev1）
    ├── converters/                                # 从 deepagents/middleware/converters/ 移过来
    │   ├── __init__.py
    │   ├── pdf.py / docx.py / xlsx.py / pptx.py
    │   ├── registry.py
    │   └── ...
    ├── upload_adapter.py                          # 从 deepagents/upload_adapter.py 移过来
    └── tools/
        ├── check_increments.py                    # 子类覆盖方法 vs 上游修改对比
        └── verify_upstream_compat.py              # startup 兼容性自检脚本
```

### 5.2 deepagents/（上游镜像）— 0 修改约定

**约定**：fork master 分支对 `libs/deepagents/` 子树的修改 = **仅允许 ff-merge upstream/main**。

**保护机制**（RC-2 修正：merge-base 方向校验）：

```bash
# CI 脚本：找 fork 与上游的最近共同祖先，检查 fork 自己的非 merge commits
# 是否触碰过 libs/deepagents/ 子树
MERGE_BASE=$(git merge-base HEAD upstream/main)
git log "$MERGE_BASE..HEAD" --no-merges --name-only -- libs/deepagents/
# 期望输出：空（fork 自己未修改任何上游文件）
# 唯一豁免：libs/deepagents/pyproject.toml 版本号 bump（fork 发版需要）
```

> **为什么不用 `git diff upstream/main..HEAD`**：当 fork 落后上游时，`git diff` 会把"上游有但 fork 缺失"的内容也展示出来——CI 在 fork 还未合并最新上游时永远失败。`git log MERGE_BASE..HEAD --no-merges` 只看 fork 自己的 commits，与上游进度无关，正确反映"fork 是否对上游做了独立修改"。

### 5.3 deepagents-enhanced 包的核心：临时 monkey-patch（**已通过 PoC 验证**）

**两种 patch 协同模式**（PoC 实测，详见 §0.2 实测五）：

| 中间件 | 上游 import 模式 | Patch 目标模块 | Patch 方式 |
| --- | --- | --- | --- |
| SkillsMiddleware | `from deepagents.middleware.skills import SkillsMiddleware` | `deepagents.graph` | swap 类引用 |
| FilesystemMiddleware | `from deepagents.middleware.filesystem import FilesystemMiddleware` | `deepagents.graph` | swap 类引用（路径 B 后**不再需要**——见 §6.3） |
| MemoryMiddleware | `from deepagents.middleware.memory import MemoryMiddleware` | `deepagents.graph` | swap 类引用（路径 B 后**不再需要**——见 §6.2） |
| SubAgentMiddleware | `from deepagents.middleware.subagents import SubAgentMiddleware` | `deepagents.graph` | swap 类引用 |
| SummarizationMiddleware | factory `create_summarization_middleware(model, backend)`，factory 内部 `return SummarizationMiddleware(...)` | `deepagents.middleware.summarization` | swap 类引用（拦截 factory 返回值） |

**最终需要 patch 的中间件（路径 B 简化后）**：仅 SkillsMiddleware、SubAgentMiddleware、SummarizationMiddleware（**3 个**），其余通过 backend wrapper 或 post-processing middleware 实现。

```python
# libs/deepagents-enhanced/deepagents_enhanced/graph.py
"""Enhanced create_deep_agent: V2 middleware injected via dual-target monkey-patch."""
from contextlib import contextmanager
from typing import Any
import deepagents.graph as _upstream_graph
import deepagents.middleware.summarization as _upstream_summ
from deepagents.graph import create_deep_agent as _upstream_create_deep_agent

from deepagents_enhanced.middleware.skills_v2 import SkillsMiddlewareV2
from deepagents_enhanced.middleware.subagent_observability import SubAgentObservability
from deepagents_enhanced.middleware.summarization_overwrite_guard import SummarizationOverwriteGuard
from deepagents_enhanced.middleware.binary_doc_converter import BinaryDocConverterMiddleware
from deepagents_enhanced.backends.async_compat import add_async_compat


@contextmanager
def _patched_middleware_classes():
    """Temporarily swap upstream middleware references — dual-target.

    Target 1: `deepagents.graph` module namespace
        - SkillsMiddleware → V2
        - SubAgentMiddleware → Observability

    Target 2: `deepagents.middleware.summarization` module namespace
        - SummarizationMiddleware → OverwriteGuard
          (intercepts factory's `return SummarizationMiddleware(...)`)

    All other customizations (Filesystem #3, Memory #7) are routed through
    backend wrapper (§6.2) or post-processing middleware (§6.3) — no patch needed.
    """
    graph_originals = {
        "SkillsMiddleware": _upstream_graph.SkillsMiddleware,
        "SubAgentMiddleware": _upstream_graph.SubAgentMiddleware,
    }
    summ_original = _upstream_summ.SummarizationMiddleware

    # Target 1: graph module
    _upstream_graph.SkillsMiddleware = SkillsMiddlewareV2
    _upstream_graph.SubAgentMiddleware = SubAgentObservability

    # Target 2: summarization module (factory returns this class)
    _upstream_summ.SummarizationMiddleware = SummarizationOverwriteGuard

    try:
        yield
    finally:
        for name, cls in graph_originals.items():
            setattr(_upstream_graph, name, cls)
        _upstream_summ.SummarizationMiddleware = summ_original


def create_deep_agent(*, backend=None, middleware=None, **kwargs: Any):
    """Enhanced create_deep_agent.

    - In-place patches backend.adownload_files for async compat (路径 B #7 — replaces Memory subclass; **Option M**)
    - Injects BinaryDocConverterMiddleware at front of user middleware (路径 B #3 — replaces Filesystem subclass; AD-2 修正)
    - Swaps Skills/SubAgent/Summarization → V2 via dual-target monkey-patch
    - Forwards all other kwargs to upstream

    pmagent calls this enhanced version via `from deepagents_enhanced import create_deep_agent`.
    All upstream parameters / new middlewares automatically inherited via **kwargs.
    """
    # 路径 B #7 (Option M): in-place method patch — preserves backend's class &
    # all 12 isinstance checks within deepagents (no wrapper class created).
    if backend is not None:
        add_async_compat(backend)

    # 路径 B #3: prepend post-processing middleware (AD-2 修正：BinaryDocConverter
    # 在用户 middleware 之前，使用户 middleware 看到的是已转换的 Markdown)
    user_middleware = [BinaryDocConverterMiddleware(backend=backend)] + list(middleware or [])

    # Plan E core: dual-target monkey-patch during upstream call
    with _patched_middleware_classes():
        return _upstream_create_deep_agent(
            backend=backend,
            middleware=user_middleware,
            **kwargs,
        )
```

**PoC 验证矩阵**（2026-05-02 实测）：

| Patch 目标 | 测试场景 | 实测结果 |
| --- | --- | --- |
| `_upstream_graph.SkillsMiddleware` | 主 agent + subagent 装配 | ✅ V2 创建 2 实例 |
| `_upstream_graph.SubAgentMiddleware` | 主 agent 装配 | ✅ V2 创建 1 实例 |
| `_upstream_summ.SummarizationMiddleware` | factory 注入 | ✅ 主 agent + subagent 共 2 V2 实例，`isinstance(mw, V2) is True` |
| context exit 后还原 | 引用恢复 | ✅ 4 个引用全部还原 |
| 多次调用无泄漏 | exit 后再调用不创建 V2 | ✅ |

### 5.4 永久 monkey-patch（仅 1 处：_EXCLUDED_STATE_KEYS）

```python
# libs/deepagents-enhanced/deepagents_enhanced/_patches.py
"""Permanent module-level patches applied at package import time.

Only patches what cannot be done via subclass — namely, the module-level
_EXCLUDED_STATE_KEYS set in deepagents.middleware.subagents.

v4-rev2 (RC-5 修订): mutate-in-place instead of reassignment.

Why mutate-in-place:
  Previous v4-rev1 used reassignment: `_EXCLUDED_STATE_KEYS = old | extra`.
  This works for current upstream code (subagents.py:343/383 use module-level
  runtime lookup, verified empirically — see /tmp/rc5_excluded_keys_poc.py).
  But if upstream ever introduces capture pattern like:
      class Foo: _vars = _EXCLUDED_STATE_KEYS  # captured at class body
  then reassignment silently fails (captured ref points to old set).

  set.update() mutates the original object in place — captured references
  see the new keys because they still point to the same set object.

  Bonus: if upstream switches type to frozenset, .update() raises
  AttributeError — fail-loud instead of silent fail.
"""
import deepagents.middleware.subagents as _subagents

# Fork-extended state keys (跟 v3 §3.3.3 9 个测试契约保持一致)
_FORK_EXTRA_EXCLUDED = frozenset({
    "subagent_logs",
    "skills_loaded",
    "skill_resources",
    "_summarization_event",
})

# Idempotent + mutate-in-place: safe against future capture patterns
if not _FORK_EXTRA_EXCLUDED.issubset(_subagents._EXCLUDED_STATE_KEYS):
    _subagents._EXCLUDED_STATE_KEYS.update(_FORK_EXTRA_EXCLUDED)
```

### 5.5 启动 assertion 保护（防止上游重命名静默失效）

```python
# libs/deepagents-enhanced/deepagents_enhanced/_assertions.py
"""Startup assertions: fail fast if upstream renames key APIs."""
import inspect
import deepagents.graph as _graph
import deepagents.middleware.subagents as _subagents


def assert_upstream_compatible():
    """Run at package import. Loud failure if upstream incompatible."""
    # 1a. Required class references in graph.py module (monkey-patch targets)
    graph_required = ["SkillsMiddleware", "FilesystemMiddleware", "MemoryMiddleware", "SubAgentMiddleware"]
    for name in graph_required:
        if not hasattr(_graph, name):
            raise ImportError(
                f"deepagents.graph no longer exports '{name}' — "
                f"upstream renamed/removed; update deepagents_enhanced to match."
            )

    # 1b. SummarizationMiddleware lives in summarization module (factory pattern)
    import deepagents.middleware.summarization as _summ
    if not hasattr(_summ, "SummarizationMiddleware"):
        raise ImportError(
            "deepagents.middleware.summarization.SummarizationMiddleware missing — "
            "upstream restructured factory; update enhanced/graph.py monkey-patch target."
        )
    if not hasattr(_summ, "create_summarization_middleware"):
        raise ImportError(
            "create_summarization_middleware factory missing — "
            "upstream may have inlined factory into graph.py; update Plan E."
        )

    # 2. _EXCLUDED_STATE_KEYS still exists (for permanent patch)
    if not hasattr(_subagents, "_EXCLUDED_STATE_KEYS"):
        raise ImportError(
            "deepagents.middleware.subagents._EXCLUDED_STATE_KEYS missing — "
            "upstream restructured; update _patches.py."
        )
    if not isinstance(_subagents._EXCLUDED_STATE_KEYS, (set, frozenset)):
        raise ImportError(
            "_EXCLUDED_STATE_KEYS type changed — verify union logic."
        )

    # 3. wrap_tool_call hook still exists in middleware framework
    from langchain.agents.middleware.types import AgentMiddleware
    sig = inspect.getmembers(AgentMiddleware, predicate=callable)
    method_names = {n for n, _ in sig}
    if "wrap_tool_call" not in method_names and "awrap_tool_call" not in method_names:
        raise ImportError(
            "LangChain AgentMiddleware no longer supports wrap_tool_call — "
            "BinaryDocConverterMiddleware needs alternative approach."
        )
```

### 5.6 enhanced 包 __init__.py

```python
# libs/deepagents-enhanced/deepagents_enhanced/__init__.py
"""Deep Agents Fork Enhancement Package.

This package provides fork-local enhancements over upstream deepagents:
1. SkillsMiddlewareV2 (load/unload tools, expose_dynamic_tools, allowed_skills)
2. SubAgentObservability (stream_writer + logging + redaction)
3. SummarizationOverwriteGuard (Overwrite type compat)
4. BinaryDocConverterMiddleware (PDF/DOCX/XLSX/PPTX → Markdown auto-convert)
5. add_async_compat() — in-place backend method patch (third-party backend async tolerance, Option M)
6. _EXCLUDED_STATE_KEYS extension (subagent_logs, skills_loaded, etc.)

Usage:
    from deepagents_enhanced import create_deep_agent
    agent = create_deep_agent(model="...", state_schema=MyState, ...)
"""
from deepagents_enhanced._assertions import assert_upstream_compatible
from deepagents_enhanced import _patches  # noqa: F401 - apply permanent patches
from deepagents_enhanced.graph import create_deep_agent

# Run startup assertions (loud failure if upstream incompatible)
assert_upstream_compatible()

__all__ = ["create_deep_agent"]
__version__ = "0.6.0"
```

### 5.7 pmagent 接入

**唯一一行修改**（一次性，永久生效）：

```python
# pmagent/src/agent.py（旧）
from deepagents import create_deep_agent

# pmagent/src/agent.py（新）
from deepagents_enhanced import create_deep_agent

# 其他所有调用方式不变
agent = create_deep_agent(
    state_schema=PMAgentState,
    skills_expose_dynamic_tools=True,
    skills_allowlist=[...],
    subagents=[...],
    # ... 全部参数不变，**kwargs 透传保证
)
```

**pmagent 升级 PR**：
1. `pyproject.toml` 添加依赖 `deepagents-enhanced = "0.6.0"`
2. `agent.py:18` 修改 import
3. 跑全量测试 + 9 个 subagent_logs 契约测试
4. 跑 e2e + `langgraph dev` 冒烟

---

## 6. 路径 B 重构详细设计

### 6.1 #8 Summarization: augment + super() 模式（额外工作量 0d）

**核心洞察**：v3 当前实现已经 OK——只是认知上把它误归为"高 shadow 风险"。重新结构化为 augment + super() 让 shadow 风险归零。

```python
# libs/deepagents-enhanced/deepagents_enhanced/middleware/summarization_overwrite_guard.py
"""Augment-only subclass: zero shadow risk."""
from langgraph.types import Overwrite
from deepagents.middleware.summarization import SummarizationMiddleware


class SummarizationOverwriteGuard(SummarizationMiddleware):
    """Adds Overwrite-unwrap defensive guard before delegating to upstream.

    # LocalFeatures: [overwrite_unwrap]
    # ShadowRisk: ZERO — does not reimplement method body
    """

    def _get_effective_messages(self, messages, event):
        # AUGMENT: unwrap if Overwrite wrapper
        if isinstance(messages, Overwrite):
            messages = messages.value
        # DELEGATE: full method body inherited from upstream via super()
        return super()._get_effective_messages(messages, event)
```

**继承能力**：
- 上游修改 `_get_effective_messages` 方法体的任何逻辑 → super() 自动继承
- 上游加新方法到 SummarizationMiddleware → 子类自动继承
- 上游扩展 `_get_effective_messages` 签名（加新参数）→ V2 需手工同步签名（同 v3 风险）

**验证测试**：
```python
def test_overwrite_guard_delegates_to_upstream():
    """非 Overwrite 输入应走完上游完整逻辑。"""
    from langchain_core.messages import HumanMessage
    guard = SummarizationOverwriteGuard(model="test")
    messages = [HumanMessage("hi")]
    result = guard._get_effective_messages(messages, event=None)
    # 上游的 list(messages) 行为应被继承
    assert isinstance(result, list)


def test_overwrite_guard_unwraps():
    """Overwrite 输入应被解包后传给上游。"""
    from langgraph.types import Overwrite
    from langchain_core.messages import HumanMessage
    guard = SummarizationOverwriteGuard(model="test")
    wrapped = Overwrite(value=[HumanMessage("hi")])
    result = guard._get_effective_messages(wrapped, event=None)
    assert len(result) == 1
```

### 6.2 #7 Memory async: in-place 方法 patch（**Option M**，额外 0.5d）

**v4-rev1 关键变更**：原 v4 方案"AsyncCompatBackend wrapper"经实测验证**不可用**——会破坏 deepagents 内部 12 处 `isinstance(backend, X)` 检查（涉及 upload_adapter、composite、filesystem、summarization、permissions 等模块的关键路由逻辑）。改用 **Option M：in-place 实例方法 patch**——不创建包装类，仅替换 backend 实例的 `adownload_files` 引用。

**重构动机**（与原 v4 保持）：v3 把 isawaitable 兼容写在 MemoryMiddleware 子类内部 → 上游对 `abefore_agent` 任何修改都 shadow。重构到 backend 层 → MemoryMiddleware 完全不动。

```python
# libs/deepagents-enhanced/deepagents_enhanced/backends/async_compat.py
"""In-place backend method patch: preserves isinstance compatibility (Option M).

Why not a wrapper class:
  AsyncCompatBackend(inner) was the original design but breaks 12 isinstance
  checks within deepagents (upload_adapter routing, composite sandbox detection,
  filesystem artifact root, permissions composite/protocol checks). The wrapper
  is not isinstance(_, FilesystemBackend) etc. → silent misroutes.

Option M: don't wrap; replace the bound method on the instance. Class is
unchanged → all isinstance checks pass.
"""
import functools
import inspect
from typing import Any


def add_async_compat(backend: Any) -> Any:
    """Add async tolerance to backend.adownload_files — in-place, idempotent.

    Behavior:
      - Backend with proper async adownload_files (StateBackend, FilesystemBackend, etc.):
        no-op skip — preserves the bound method untouched
      - Buggy/legacy backend with sync adownload_files:
        replaces backend.adownload_files with an awaitable wrapper

    # LocalFeatures: [async_compat_adownload]
    # ShadowRisk: ZERO — does not subclass MemoryMiddleware nor change backend class
    """
    if backend is None:
        return backend
    fn = getattr(backend, "adownload_files", None)
    if fn is None:
        return backend
    # Already proper async coroutine function → no patch needed
    if inspect.iscoroutinefunction(fn):
        return backend
    # Already patched (idempotency marker)
    if getattr(fn, "_async_compat_patched", False):
        return backend

    @functools.wraps(fn)
    async def compat(paths):
        result = fn(paths)
        return await result if inspect.isawaitable(result) else result
    compat._async_compat_patched = True
    backend.adownload_files = compat
    return backend
```

**装配**（在 `enhanced.create_deep_agent` 中）：
```python
def create_deep_agent(*, backend=None, ...):
    if backend is not None:
        add_async_compat(backend)  # in-place patch — class unchanged
    ...
```

**Option M PoC 实测验证（5/5 通过，2026-05-02）**：

| 测试 | 结果 |
| --- | --- |
| StateBackend（proper async）→ no-op 跳过 | ✅ |
| Buggy 同步 backend → patch 后 `await` 工作 | ✅ |
| **isinstance 全保留**（StateBackend / FilesystemBackend / CompositeBackend / BackendProtocol）| ✅ |
| 幂等性（多次调用安全） | ✅ |
| Fork 既有测试 `_FakeBackendSyncAdownload` 场景在 Option M 下通过 | ✅ |

**继承能力**：
- 上游对 MemoryMiddleware 任何修改 → 100% 透明继承（fork 不再有 MemoryMiddleware 子类）
- 上游对其他 middleware（FilesystemMiddleware、SkillsMiddleware）的 `adownload_files` 调用 → 也获得 async compat 保护
- deepagents 内部 12 处 `isinstance(backend, X)` 检查 → **全部正常工作**（class 没换）

**唯一副作用**：mutates backend instance 上的 `adownload_files` 引用。
- 文档中明示
- 幂等性保证多次 patch 安全
- 用户传给 enhanced 的 backend 实例如在外部复用，行为是 superset（兼容更好）—— 通常更优

**与 Option H/Option K 的对比**：

| 选项 | 可行 | shadow 风险 | isinstance 兼容 | 状态 |
| --- | --- | --- | --- | --- |
| Option H 删除 #7 | ❌ 测试 `test_abefore_agent_tolerates_sync_adownload_files` 失败 | — | — | 否决 |
| Option K AsyncCompatBackend wrapper | ❌ 12 处 isinstance 破坏 | 0 | 🔴 全破 | 否决（原 v4 设计） |
| Option I MemoryMiddleware 子类（v3 设计） | ✅ | 🟡 abefore_agent 整方法覆盖 | ✅ | 备选 |
| **Option M in-place 方法 patch** | **✅ 实测通过** | **0** | **✅ 全保留** | **采纳** |

### 6.3 #3 Filesystem Converter: BinaryDocConverterMiddleware（额外 1.5-2d）

**重构动机**：v3 把 converter 嵌入 FilesystemMiddleware 子类的 `_create_read_file_tool` 中 → 上游对 `_create_read_file_tool` 任何修改都 shadow。重构为独立的 post-processing middleware → FilesystemMiddleware 完全不动。

#### API 验证依据

实测 `awrap_tool_call` API 在 deepagents 中的两处生产使用：
- `permissions.py:344, 372`：pre-check 拒绝 + post-filter
- `filesystem.py:1953, 1973`：post-process 大结果驱逐

签名稳定：`(self, request: ToolCallRequest, handler) -> ToolMessage | Command`。

#### 设计

```python
# libs/deepagents-enhanced/deepagents_enhanced/middleware/binary_doc_converter.py
"""Post-tool-call middleware: convert binary doc read_file results to Markdown.

Pre-empts FilesystemMiddleware's read_file when target is a binary document
(PDF, DOCX, XLSX, PPTX). Falls through to upstream read_file on any failure.
"""
from collections.abc import Awaitable, Callable
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from deepagents_enhanced.converters import (
    detect_mime_type,
    is_binary_doc_path,
    registry,
)


class BinaryDocConverterMiddleware(AgentMiddleware):
    """Convert binary doc read_file results to Markdown.

    # LocalFeatures: [pdf_to_md, docx_to_md, xlsx_to_md, pptx_to_md, page_offset]
    # ShadowRisk: ZERO — never subclasses FilesystemMiddleware
    """

    def __init__(self, *, backend, max_token_threshold: int = 20000):
        self._backend = backend
        self._max_tokens = max_token_threshold

    def wrap_tool_call(self, request, handler):
        # Filter: only intercept read_file on binary doc paths
        if not self._should_intercept(request):
            return handler(request)
        try:
            args = request.tool_call.get("args", {})
            md = self._convert_sync(args["file_path"], args.get("offset", 0))
            return ToolMessage(
                content=md,
                tool_call_id=request.tool_call["id"],
                name="read_file",
            )
        except Exception:
            # Fall back to upstream read_file behavior
            return handler(request)

    async def awrap_tool_call(self, request, handler):
        if not self._should_intercept(request):
            return await handler(request)
        try:
            args = request.tool_call.get("args", {})
            md = await self._convert_async(args["file_path"], args.get("offset", 0))
            return ToolMessage(
                content=md,
                tool_call_id=request.tool_call["id"],
                name="read_file",
            )
        except Exception:
            return await handler(request)

    def _should_intercept(self, request) -> bool:
        if request.tool_call["name"] != "read_file":
            return False
        file_path = request.tool_call.get("args", {}).get("file_path", "")
        return is_binary_doc_path(file_path)

    def _convert_sync(self, file_path: str, offset: int) -> str:
        # 移植自当前 deepagents/middleware/filesystem.py:648-707 (_convert_document_sync)
        files = self._backend.download_files([file_path])
        # ... mime detection + registry.get + converter.convert ...
        return md

    async def _convert_async(self, file_path: str, offset: int) -> str:
        # 移植自当前 filesystem.py:709-770 (_convert_document_async)
        files = await self._backend.adownload_files([file_path])
        # ...
        return md
```

#### 中间件链顺序

通过将 BinaryDocConverter 放入 `middleware` kwarg（用户中间件位置，FilesystemMiddleware 之后、PermissionMiddleware 之前），其 `wrap_tool_call` 在调用链中处于 FS middleware 与 Permissions 之间：

```
Permissions.wrap_tool_call(req)
  └→ pre-check denial?
  └→ handler() = FilesystemMiddleware.wrap_tool_call
       └→ handler() = BinaryDocConverter.wrap_tool_call
            └→ for read_file on binary: pre-empt, return MD
            └→ for other: handler() = real read_file tool
```

二进制文件预 empt → FS 看到 Markdown 文本 → 不会触发大结果驱逐（除非 MD 仍超 20k）。
非二进制文件 → 透传 handler() → 正常 read_file → FS 决定驱逐。

#### 测试迁移

当前 `tests/unit_tests/middleware/converters/test_converter_integration.py` 23 个测试需要：
- 更新 fixture 使用 `BinaryDocConverterMiddleware` 装配
- 验证 wrap_tool_call 行为（mock handler）
- 端到端通过 `enhanced.create_deep_agent` 实例化 agent + 调 read_file

### 6.4 中间件链顺序设计总览（路径 B 后）

```
[默认上游栈]
TodoListMiddleware
SkillsMiddleware (→ V2 via monkey-patch)
FilesystemMiddleware (上游原样)
SubAgentMiddleware (→ Observability via monkey-patch)
SummarizationMiddleware (→ OverwriteGuard via subclass，augment + super)
PatchToolCallsMiddleware
AsyncSubAgentMiddleware (optional)

[用户位置 — enhanced 注入]
BinaryDocConverterMiddleware  ← 路径 B #3 新增

[用户传入的 middleware]
...

[尾部固定]
AnthropicPromptCachingMiddleware
MemoryMiddleware (上游原样，backend.adownload_files 已被 in-place patch — class 不变)
HumanInTheLoopMiddleware
_PermissionMiddleware (must be last)
```

---

## 7. 上游升级红利继承能力

### 7.1 12 类上游升级 × Plan E + 路径 B 继承能力矩阵

| # | 上游升级类型 | 例子 | Plan E + 路径 B | 备注 |
| --- | --- | --- | --- | --- |
| 1 | `create_deep_agent` 新参数 | `max_turns=N` | ✅ 自动 | **kwargs 透传 |
| 2 | 默认中间件栈新增 | 加 `RateLimitMiddleware` | ✅ 自动 | 调上游 graph.py |
| 3 | 装配顺序优化 | SubAgent 移到 Memory 后 | ✅ 自动 | 调上游 graph.py |
| 4 | 默认模型升级 | claude-sonnet-4-6 → 4-7 | ✅ 自动 | 上游 default |
| 5 | Skills V1 bug 修复（V2 未覆盖区） | 修 `_parse_skill_md` | ✅ 自动 | V2 子类继承 |
| 6 | Skills V1 bug 修复（V2 已覆盖区） | 修 V2 也覆盖了的方法 | 🟡 需同步 | 共有风险（仅 #1） |
| 7 | 新工具加入 | 加 `web_search` 默认工具 | ✅ 自动 | 调上游装配 |
| 8 | 新 backend | 加 `WeaviateBackend` | ✅ 自动 | pmagent 直接 import |
| 9 | 新 state 字段 | 加 `tool_invocations` | ✅ 自动 | 上游处理 |
| 10 | `_EXCLUDED_STATE_KEYS` 新增键 | 加 `tool_traces` | ✅ 自动 | union 保留 |
| 11 | 性能优化 | 加 caching | ✅ 自动 | 上游内部 |
| 12 | 中间件签名扩展 | `SkillsMiddleware(backend, sources, new_arg=...)` | ✅ 自动 | V2 继承父类 __init__ |
| 13 | FilesystemMiddleware 修改 | 上游加新 read_file 选项 | ✅ 自动 | 路径 B #3 不再 subclass FS |
| 14 | MemoryMiddleware 修改 | 上游优化 abefore_agent | ✅ 自动 | 路径 B #7 不再 subclass Memory |
| 15 | SummarizationMiddleware 修改 | 上游优化 _get_effective_messages | ✅ 自动 | 路径 B #8 augment + super |
| 16 | SubAgent _build_task_tool 修改 | 上游重构内部装配 | 🔴 需同步 | 共有风险（仅 #5） |
| 17 | SkillsMiddleware 重命名 | SkillsMiddleware → SkillsHandler | 🔴 startup assertion 报错 | loud failure |
| 18 | 上游废弃 wrap_tool_call API | 改为新 hook 名 | 🔴 startup assertion 报错 | loud failure |

### 7.2 仅剩 2 项 shadow 风险（透明清单）

| # | 项 | 不可避免原因 |
| --- | --- | --- |
| #1 | SkillsMiddlewareV2 covered methods | V2 是产品功能必须（load/unload/expose_dynamic_tools/allowed_skills），无法 augment + super 因为这些是新增方法链 |
| #5 | SubAgentObservability covered methods | 依赖 5+ 模块级 helper（`_extract_subagent_logs` 等），无法 wrap_tool_call 替代（observability 是 SubAgent 内部行为） |

### 7.3 自动检测工具

```bash
# tools/check_increments.py 周期性运行
$ python libs/deepagents-enhanced/tools/check_increments.py --compare-upstream upstream/main

SkillsMiddlewareV2:
  Covered methods: 8
  ✅ _parse_skill_md          — upstream unchanged since last sync
  ⚠️ _build_skills_prompt     — upstream MODIFIED at commit abc1234 (line 234-256)
                                  → review V2 override for sync
  ✅ load_skill_tool          — V2-only method
  ...

SubAgentObservability:
  Covered methods: 4
  ✅ _build_task_tool         — upstream unchanged
  ⚠️ _redact_sensitive_fields — upstream MODIFIED at commit def5678 (line 253)
                                  → review override
```

每轮上游 sync 前运行此工具，识别需 review 的 V2 方法。

---

## 8. 双 Milestone 推进路线图

### Milestone 1: pmagent 孤立代码清理（1.5 天，立即启动）

**与 v3 完全一致**，详见 v3 §7 Milestone 1。摘要：
- Day 1：删除 logging.py（1330）、skills_loader.py（436）、memory.py（428）、models/skill.py（120），清理 dead imports + 测试
- Day 2：验证（pytest --collect-only + langgraph dev）+ 文档同步
- 冻结项：`security/permissions.py` 加 `# STATUS: FROZEN` 注释

**M1 不依赖 M2 方案选择**——无论最终走 v3 Plan D 还是 v4 Plan E，pmagent 孤立代码清理都是公共前置。

### Milestone 2: deepagents-enhanced 包构建（5.5-6 天 fork 团队工时；6.5-7 天日历，v4-rev1）

#### Phase 1: enhanced 包脚手架（0.5 天）

- 创建 `libs/deepagents-enhanced/pyproject.toml`
- 创建 `deepagents_enhanced/__init__.py`、`_assertions.py`、`_patches.py`
- 写最小可 import 通路（pip install -e + assert_upstream_compatible() 通过）
- CI 配置：每次 push 用 `git log $(git merge-base HEAD upstream/main)..HEAD --no-merges --name-only -- libs/deepagents/` 校验 = 空（详见 §5.2 命令；RC-4 修订：原版 `git diff upstream/main..HEAD` 方向错误，会在 fork 落后上游时永远失败）

#### Phase 2: 子类与 additive middleware 抽取（2.5 天）

**Day 1（1 天）**：纯 additive 项 + 简单子类
1. 移动 `deepagents/middleware/converters/` → `deepagents_enhanced/converters/`
2. 移动 `deepagents/upload_adapter.py` → `deepagents_enhanced/upload_adapter.py`
3. 创建 `middleware/skills_v2.py`（抽出 SkillsMiddlewareV2 全部 V2 增强）
4. 创建 `middleware/summarization_overwrite_guard.py`（augment + super 模式）
5. 创建 `backends/async_compat.py`（路径 B #7 `add_async_compat()` in-place 方法 patch，Option M）
6. 创建 `tools/check_increments.py`（v3 §6.4.4 设计）

**Day 2（1 天）**：BinaryDocConverter 重构（路径 B #3）
- 移植 `_convert_document_sync/async` 逻辑到 `middleware/binary_doc_converter.py`
- 写 wrap_tool_call / awrap_tool_call 实现
- 中间件链顺序设计验证

**Day 2.5（0.5 天）**：测试规范化
- 把 fork tests 移植 / 适配到 enhanced 包
- 23 个 converter 集成测试更新为 BinaryDocConverter 接口
- 新增 `test_async_compat_backend.py`、`test_overwrite_guard.py`

#### Phase 3.0: Plan E 物理可行性 PoC（**1 天**，关键决策门，AD-1 修订）

**目标**：完整验证 v4-rev1 设计在 fork 仓库内的物理可行性，覆盖 6 个核心维度。

**当前状态（截至 v4-rev1）**：基础 PoC #1+#2+ Option M PoC 已通过（详见 §0.2 实测五/六），核心 monkey-patch 与 backend 方法 patch 已验证。Phase 3.0 在此基础上做**集成扩展验证**。

**扩展验证清单（AD-1 修订，6 项必须）**：

1. **三类同时 patch 都生效**（已部分验证）：
   - `_upstream_graph.SkillsMiddleware` → SkillsMiddlewareV2
   - `_upstream_graph.SubAgentMiddleware` → SubAgentObservability
   - `_upstream_summ.SummarizationMiddleware` → SummarizationOverwriteGuard
   - 集成测试：单次 `enhanced.create_deep_agent` 调用同时验证三个 V2 实例创建
2. **退出 contextmanager 后类引用还原**（已验证 PoC #1 Test 3）
3. **多次 sequential 调用状态机正确性**：
   - 连续 3 次 `enhanced.create_deep_agent`，每次都正确创建 V2，无状态泄漏
   - 异常路径（patch 应用过程中抛异常）后还原是否完整（finally 块覆盖）
4. **isinstance 兼容性扫描**（RC-3 必做）：
   - `grep -rn "isinstance.*[Bb]ackend"` 实测：12 处命中
   - 验证 Option M backend 方法 patch 后所有 12 处 isinstance 检查继续通过
5. **路径 B #7 Option M 集成验证**（AD-1 + RC-3 衍生）：
   - 用 buggy backend（同步 adownload_files）跑 enhanced.create_deep_agent
   - 验证 Memory middleware 正确加载内容（不抛 await TypeError）
   - 验证 backend.adownload_files 被 in-place patch（class 未变）
6. **路径 B #3 BinaryDocConverter 中间件链位置**（AD-2 衍生）：
   - 验证在 user middleware **之前**插入（prepend，不是 append）
   - 用一个二进制 PDF 测试文件 + read_file 工具调用，验证 wrap_tool_call 拦截路径正确
   - 用一个用户 middleware 在 BinaryDocConverter 之后注册，验证它看到的是已转换的 Markdown ToolMessage
7. **`_EXCLUDED_STATE_KEYS` 扩展真实生效**（v4-rev2 RC-5 衍生）：
   - 应用 `_patches.py` 永久 patch（mutate-in-place via `set.update()`）
   - 通过实际 SubAgent task 调用，构造包含 fork 扩展键的父 state（含 `subagent_logs`、`skills_loaded`、`skill_resources`、`_summarization_event`）
   - 验证子代理实际接收的 state **不包含**这 4 个扩展键（即 fork 扩展键真的被状态隔离过滤）
   - 静态验证：AST 扫描确认 subagents.py 无 `= _EXCLUDED_STATE_KEYS` 引用捕获模式（避免未来上游引入）

**决策门**：

- ✅ 7 项全部通过 → Phase 3.1 + 3.2 按计划执行
- ❌ 任一失败 → 应急路径（见 §9.3；若 RC-5 失败则切换 mutate 实现策略而非降级方案 D）

**估时上调原因**（0.5 d → 1 d）：

- v4 原 PoC 范围只覆盖第 1-2 项
- pmagent RC-1/RC-3、AD-1/AD-2 的修订带来新验证维度（第 4、5、6 项）
- 路径 B #3 端到端测试涉及实际 PDF/DOCX 解析，需要时间
- v4-rev2 新增第 7 项 `_EXCLUDED_STATE_KEYS` 真实生效验证（RC-5），约 0.25 d

#### Phase 3.1: SubAgent observability 子类（1.5-2 天）

**与 v3 §7 Phase 3.1 一致**：
- 抽出 stream_writer + logging 为 `SubAgentObservability(SubAgentMiddleware)`
- 保留 subagent_logs 字段格式契约
- 写 Snapshot 测试（baseline 在 Phase 3.0 PoC 时已建立）

**Phase 3.1 强制门**：pmagent 9 个 subagent_logs 测试 CI 跑通才能 merge（v3 §3.3.3 9 测试）：
- `test_subagent_logs_acceptance.py`、`test_pmagent_ui_comprehensive.py`、`test_pmagent_comprehensive.py`、`test_state_schema.py`、`tests/manual/*` (4)、`tests/integration/test_hil_interrupt_mock.py`

#### Phase 3.2: pmagent 临时验证分支协议（同 Phase 3.1 并行执行）

与 v3 §7 Phase 3.0 步骤 5 一致：
1. fork enhanced 包发 editable install
2. pmagent 创建临时分支 `feat/poc-validate-phase3`
3. pmagent `pyproject.toml`: `deepagents-enhanced = {path = "../../deepagents/libs/deepagents-enhanced", develop = true}`
4. pmagent agent.py 修改 import 为 `from deepagents_enhanced import create_deep_agent`
5. 跑 9 个 subagent_logs 契约测试 + e2e
6. 反馈结果给 fork 团队，临时分支关闭

#### Phase 4a: 实证 merge 验证（0.5 天）

```bash
git fetch upstream main
# 模拟近 30 个上游 commits 与 enhanced 包 fork 的合并
for commit in $(git log upstream/main --pretty=%H | head -30); do
    git merge-tree HEAD "$commit" 2>&1 | grep -q "^<<<<<<" && echo "CONFLICT: $commit"
done
# 期望输出：仅 pyproject.toml 偶发版本冲突，0 SDK 文件冲突
```

**验收指标**：
- libs/deepagents/ 子树冲突数 = **0**
- libs/deepagents-enhanced/ 子树冲突数 = 0（新加的，不可能与上游冲突）
- 单次模拟 merge 解决时间 < 5 分钟

#### Phase 4b: Round 16 真实跟踪（机会性，不阻塞）

- 不阻塞项目完成判定
- 数据录入 `docs/upstream_merge/ROUND16_PROGRESS.md`
- 验证 v4 模型：实际每轮 sync 时间应 < 30 分钟（vs v3 Plan D 实测 1-3 小时）

#### pmagent upgrade PR（M2 完成后，0.5-1 天，pmagent 团队执行）

1. `pyproject.toml` 添加 `deepagents-enhanced = "0.6.0"` 依赖
2. `agent.py` 修改 import（1 行）
3. 跑全量 + 9 个契约测试
4. e2e + `langgraph dev`
5. 合并到 pmagent master

---

## 9. 风险与回滚

### 9.1 风险矩阵（v4 视角）

| 风险 | 严重性 | 缓解 |
| --- | --- | --- |
| ~~Phase 3.0 PoC 失败~~（monkey-patch 不工作）（**v4-rev2 AD-4 已规避**）| 🟢 低 | **已规避** — Plan E 物理可行性 PoC 18/18 通过（§0.2 实测五/六/八）；§B.4 invariant 测试持续守护，每轮上游 sync 后强制跑 |
| 上游某天改用函数内 lazy import（破坏 graph 模块替换） | 🟡 中 | **§B.4 invariant 测试是真正防线**（运行时验证 V2 实例真的被装配）；startup assertion **不能** 检测 lazy import（已知静态检查局限，LR-1 修订）|
| **(v4-rev2 RC-5 衍生) 上游引入 `_EXCLUDED_STATE_KEYS` 引用捕获模式（如类级捕获）** | 🟢 低 | §5.4 已切换为 `set.update()` mutate-in-place — 任何捕获引用都看到新键；上游若改为 frozenset 会触发 AttributeError 而非 silent fail；Phase 3.0 PoC 第 7 项实测扩展键过滤生效（`/tmp/rc5_excluded_keys_poc.py`）|
| `awrap_tool_call` API 上游废弃 | 🟡 中 | startup assertion 检测；deepagents 自己使用 → 不太可能短期废弃 |
| ~~AsyncCompatBackend 与 isinstance 不兼容~~（v4-rev1 已规避）| 🟢 低 | **方案变更为 Option M（in-place 方法 patch）**：不创建 wrapper 类，backend 实例 class 不变，12 处 isinstance 检查全部正常工作（PoC 实测验证，§0.2 实测六）|
| SubAgent 9 个 subagent_logs 契约破坏 | 🔴 高 | Phase 3.1 强制门 + Snapshot baseline + 契约文档 |
| pmagent 1 行 import 修改影响其他 import | 🟢 低 | grep 验证 pmagent 仅 1 处 import；其他 `from deepagents import X` 不变 |
| enhanced 包独立版本管理引入摩擦 | 🟢 低 | 标准 pyproject.toml；deepagents-enhanced 0.6.0 依赖 deepagents>=0.5.0,<0.7 |
| Skills V2 / SubAgent obs 已覆盖方法上游修改 shadow | 🟡 中 | check_increments.py 周期性扫描 + 季度 review |

### 9.2 回滚策略

**Phase 间 PR 粒度**（与 v3 §8.2.1 一致）：每个 Phase 一个独立 PR，可单独 revert。

**回滚边界表**：

| 已 merge | Phase X 出问题 | 回滚到 |
| --- | --- | --- |
| Phase 1 | Phase 1 自身 | revert PR-1，回到 v3 启动前 master |
| Phase 1 + 2 | Phase 2 出问题 | revert PR-2，保留 Phase 1，重新评估 |
| Phase 1 + 2 + 3.0 PoC 失败 | Phase 3.0 失败 | 启动 §9.3 应急路径 |
| Phase 1 + 2 + 3.1 | Phase 3.1 出问题 | revert PR-3，保留 Phase 1+2 |
| Phase 1 + 2 + 3.1 + 4a 验证不通过 | Phase 4a 不达标 | 不 revert，回到 Phase 3.1 评估 monkey-patch 范围是否需扩展 |

### 9.3 Phase 3.0 PoC 失败应急路径（**2026-05-02 已规避**）

**当前状态**：✅ **已规避**——Plan E 物理可行性 PoC 已于 2026-05-02 全部通过（详见 §0.2 实测五），无需触发应急路径。本节作为**历史决策档案**保留，供未来上游若发生 import 风格重大变化时参考。

**PoC 失败定义（已规避）**：物理 monkey-patch 不能让 `_upstream_create_deep_agent` 装配 V2

**已实证的反面**（PoC 数据）：
- ✅ 上游 graph.py 当前用 module-level `from deepagents.middleware.skills import SkillsMiddleware`（非 lazy import）
- ✅ graph 模块的 SkillsMiddleware/FilesystemMiddleware/MemoryMiddleware/SubAgentMiddleware 类引用可被替换
- ✅ Summarization 通过 `create_summarization_middleware` factory 注入，可通过 module-level class swap 拦截
- ✅ 主 agent + general-purpose subagent 共享同一 patch 上下文

**未来若 PoC 反例出现的应急动作**（仅作为档案）：
1. 关闭 `feat/enhancement-package` 分支
2. 退回 v3 Plan D 路径（`feat/internal-restructure`）
3. v3 Plan D 投入：6-6.5 d（Phase 1+2 已完成的工作可复用）
4. 项目降级至"v3 Plan D 接受 graph.py 200 行 diff"

**最坏情况投入估计**（已规避）：v4 Phase 1+2 投入 3 d 浪费 + v3 Plan D 投入 6-6.5 d = 总 9.5 d。

**当前实际状态**：PoC 已通过 → v4-rev1 主线 6.5-7 d 日历，**0 浪费**。

---

## 10. 工作量与 ROI

### 10.1 工作量分解

| 阶段 | 工作量 | 责任团队 |
| --- | --- | --- |
| M1: pmagent Phase 0 清理 | 1.5 d | pmagent |
| M2 P1: enhanced 包脚手架 | 0.5 d | fork |
| M2 P2: 子类 + additive 抽取 + 测试 | 2.5 d | fork |
| M2 P3.0: monkey-patch PoC + 6 项验证（决策门） | **1 d**（v4-rev1 AD-1：从 0.5d 上调） | fork |
| M2 P3.1: SubAgent observability | 1.5-2 d | fork |
| M2 P3.2: pmagent 临时分支验证 | 0.5 d | pmagent（与 P3.1 并行） |
| M2 P4a: 实证 merge 验证 | 0.5 d | fork |
| M2 P4b: Round 16 跟踪 | — | 机会性 |
| pmagent upgrade PR | 0.5-1 d | pmagent |
| **fork 团队总计** | **5.5-6 d**（M2 P1+P2+P3.0+P3.1+P4a，含 PoC 扩展） | |
| **pmagent 团队总计** | **2.5-3 d**（M1+P3.2+upgrade PR） | |
| **日历时间（M1∥M2 并行）** | **6.5-7 d**（含路径 B +2.5 d 与 v4-rev1 PoC 扩展 +0.5 d） | |

### 10.2 ROI 计算

**一次性投入**：6.5-7 d（日历）

**长期收益**（按当前节奏：每月 1-2 轮上游 sync）：

| 指标 | v3 Plan D | v4 Plan E + 路径 B |
| --- | --- | --- |
| 单轮 sync 冲突解决时间 | 5-30 分钟（实测 graph.py 必冲突） | < 5 分钟（仅 pyproject.toml 偶冲突） |
| 单轮 sync review 工作 | shadow 风险 5 项 manual review | shadow 风险 2 项 + check_increments.py 自动报告 |
| 心理负担 | 每轮焦虑（不知道几处冲突） | 零冲突，确定性 |

**回本周期**：v4-rev1 比 v3 多投入 0.5-1 d 日历（多 2.5-3.5 d 团队工时），每月节省 0.5-2 小时 → **3-6 个月内回本**，之后是纯收益。

### 10.3 收益指标对比表

| 指标 | 现状 | v3 Plan D 之后 | **v4 Plan E + 路径 B 之后** |
| --- | --- | --- | --- |
| Fork 与上游修改文件 diff | ~3500 行 | 300-400 行 | **0 行**（仅 pyproject.toml） |
| 修改文件数 | 5-15 个 | 2-3 个 | **0 个** |
| 上游同步耗时 | 2-7 小时/轮 | < 30 分钟/轮（部分轮次仍长） | **< 5 分钟/轮**（数学保证） |
| 上游同步冲突文件 | 5-15 个 | 1-2 个（graph.py + subagents.py） | **0 个** |
| pmagent 业务代码改动 | — | 0 行 | **1 行 import**（一次性） |
| Shadow 风险项 | 11 项内嵌 | 5 项 | **2 项** |
| 长期维护成本 | 高 | 中 | **低** |
| 总迁移工作量（日历） | — | 5-5.5 天 | **6.5-7 天**（v4-rev1，多 1-1.5 天换零冲突 + 60% shadow 削减）|

---

## 11. pmagent 团队三时间点介入

| 时间点 | 工作 | 估时 | 产出 |
| --- | --- | --- | --- |
| **M1 执行**（立即） | Phase 0 孤立代码清理 | 1.5 d | pmagent 测试全绿，孤立模块 0 残留 |
| **M2 pre-start**（M1 完成后，与 P3.0 PoC 并行） | 评审 §5 Plan E 设计 + RBAC 冻结标注 + 临时验证分支跑 9 测试 | 0.5 d | 设计审签 + RBAC 标注 + PoC 决策门输入 |
| **M2 完成后** | upgrade PR：依赖 deepagents-enhanced 0.6.0 + agent.py 1 行 import 修改 + 全量测试 + e2e | 0.5-1 d | pmagent 消费 fork enhancement 包验证通过 |
| **合计** | | **2.5-3 d** | |

### M2 启动条件（5 个硬性门）

1. M1 完成（Phase 0 验证门通过）
2. v4 文档评审通过
3. **Phase 3.0 monkey-patch PoC 通过**（决策门：通过 → 走 Plan E；失败 → 退回 v3 Plan D）
4. RBAC 冻结标注已完成（`# STATUS: FROZEN`）
5. pmagent 技术负责人完成 §5 Plan E 设计方案审签

### 11.4 长期维护清单（v4-rev2 LR-2/LR-3 新增）

| 任务 | 触发时机 | 责任团队 | 估时 |
| --- | --- | --- | --- |
| **每轮上游 sync 前** 跑 `tools/check_increments.py` | 每次上游 sync 前（自动化或手动）| fork | 5 min |
| **每轮上游 sync 后** 跑 `test_invariant_v2_assembled.py`（§B.4） | 每次 sync merge 完成后强制跑 | fork | 5 min |
| 每轮上游 sync 后跑 RC-5 `test_excluded_keys_extension_takes_effect`（§B.4） | 同上 | fork | 5 min |
| **deepagents 上游升级到 0.7+ 时**：升级 enhanced 版本约束 + 全量回归 + 发新版（LR-2）| deepagents 跨大版本升级 | fork | 0.5-1 d |
| 季度评审 `security/permissions.py` 是否激活（v3 RBAC 冻结跟踪）| 每季度 | pmagent 技术负责人 | 0.25 d / 季 |
| 季度评审 V2 子类（#1 Skills、#5 SubAgent obs）覆盖方法是否需要 sync upstream | 每季度（基于 check_increments.py 输出）| fork | 0.5 d / 季 |

**关键节奏**：

- 每轮上游 sync = 上游 sync 前 + 后 共 ~15 min 的额外操作（自动化 CI 后可压到 0）
- 季度维护 = ~1 d/季
- 跨大版本升级 = ~1 d，每年 1-2 次

总长期维护成本 < 6 d/年，远低于 v3 Plan D 的"每轮 5-30 分钟解决冲突 × 12-24 轮/年" = 1-12 d/年 + 不确定性焦虑成本。

---

## 12. 决策建议

### 12.1 强烈推荐 v4 Plan E + 路径 B 完整版

**理由（按用户初衷优先级）**：

1. **🔴 P0 上游同步冲突概率 ≈ 0**：唯一数学保证零冲突的方案。其他方案（v3 Plan D / Plan Q / Plan R）都有不同程度的冲突源。
2. **🔴 P1 pmagent 难度不增加**：仅一次性 1 行 import 修改。比 v3 Plan D 的 0 行多了 1 行，但比 Plan Q 的 +150 行装配代码低 2 个数量级。
3. **🟢 P2 ROI 最高**：6.5-7 天日历投入（v4-rev1），3-6 个月回本，长期纯收益。
4. **🟢 P2 风险最低**：startup assertion 提供 fail-fast 保护；shadow 风险从 5 项压到 2 项。
5. **🟢 P2 效率最高**：每轮 sync < 5 分钟（vs Plan D 的 5-30 分钟）。
6. **额外好处**：fork 仓库结构清晰（上游镜像 + enhancement 包分离），enhanced 包独立可发布版本。

### 12.2 不推荐的方案及理由（重申）

| 方案 | 不推荐理由 |
| --- | --- |
| Plan A 完全下沉到 pmagent | 违反约束 P1（pmagent 接管装配） |
| Plan B 引入 deepagents_ext/ namespace | v1 已否决，引入人为命名空间 |
| Plan C 完全保守 | 不解决任何问题 |
| **Plan D (v3)** | 实测仍有 5 大文件冲突；shadow 风险 5 项；不能数学保证零冲突 |
| Plan Q | 违反约束 P1（pmagent 永久维护 +150 行装配） |
| Plan R 全局 monkey-patch | 概念负担大，import order 风险高 |

### 12.3 决策路径

**第 1 步（立即）**：批准 v4 文档 + 启动 M1（pmagent Phase 0 清理）。M1 与方案选择正交，不阻塞任何决策。

**第 2 步（与 M1 并行，关键）**：执行 Phase 3.0 monkey-patch PoC（0.5 d）。物理验证 `_patched_middleware_classes` 在 fork 仓库内能让 `_upstream_create_deep_agent` 装配 V2。

**第 3 步（M1 + PoC 完成后）**：
- PoC 通过 → 启动 M2 完整版（Phase 1-4a），6-7 天日历完成
- PoC 失败 → 退回 v3 Plan D 路径，已投入 0.5 d PoC 浪费但及早发现

---

## 附录 A — v3 → v4 演进对应表

| v3 章节 | v4 章节 | 状态 |
| --- | --- | --- |
| 0.1 22 项修订清单 | 0.1 v4 vs v3 根本差异 | **重写** |
| 0.2 事实核实 | 0.2 推动 v4 的实证数据 | **更新**（含 5 大文件冲突实测）|
| 1. 问题定义 | 1. 问题定义 | **修订**（增 v3 后未解决问题） |
| 2. 11 项定制清单 | 2. 11 项定制重新分类 | **重写**（按 v4 视角） |
| 3. pmagent 依赖 | （并入 §11 pmagent 三时间点） | 简化 |
| 4. 可行性矩阵 | 4. 方案对比 | **重写**（含 Plan E）|
| 5. 候选方案对比 | 4. 同上 | 合并 |
| 6.1-6.5 方案 D 设计 | 5. Plan E 架构详细设计 | **完全重写**（独立包结构） |
| — | 6. 路径 B 重构详细设计 | **新增**（v4 独有） |
| — | 7. 上游升级红利继承 | **新增**（v4 独有） |
| 7. 双 Milestone 路线图 | 8. 双 Milestone | **保留 M1 + 重写 M2** |
| 8. 风险与回滚 | 9. 风险与回滚 | **更新**（v4 风险） |
| 9. 收益评估 | 10. 工作量与 ROI | **重写** |
| 10. 决策建议 | 12. 决策建议 | **重写** |
| 11. 后续步骤 | 12.3 决策路径 | 简化 |

---

## 附录 B — Plan E 实施细节

### B.1 deepagents-enhanced/pyproject.toml 草稿

```toml
[project]
name = "deepagents-enhanced"
version = "0.6.0"
description = "Local fork enhancements over upstream deepagents"
requires-python = ">=3.11"
dependencies = [
    "deepagents>=0.5.0,<0.7",
    "pdfplumber>=0.10",
    "python-docx>=1.0",
    "openpyxl>=3.1",
    "python-pptx>=0.6",
]

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.21"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["deepagents_enhanced"]
```

### B.2 startup assertion 完整清单

- 类引用：SkillsMiddleware、FilesystemMiddleware、MemoryMiddleware、SummarizationMiddleware、SubAgentMiddleware
- 模块属性：`deepagents.middleware.subagents._EXCLUDED_STATE_KEYS`
- 类型校验：`_EXCLUDED_STATE_KEYS` 是 set/frozenset
- API 钩子：`AgentMiddleware.wrap_tool_call` / `awrap_tool_call`

### B.3 check_increments.py 简要设计

```python
# 扫描 deepagents_enhanced/middleware/*.py
# 提取每个子类的 # LocalFeatures: 和 # ShadowRisk: 注释
# 解析每个子类的 def 方法名
# 与 git log upstream/main --since="last sync" 对比
# 输出：哪些 V2 覆盖方法上游近期被改了
```

### B.4 Invariant 测试 — 持续守护 V2 装配（AD-3）

**动机**：startup assertion 是静态检查，无法发现"上游某天改用 lazy import 或重构 graph 内部装配，导致 monkey-patch 不再生效但不报错"这种 silent failure。

**对策**：在 enhanced 包加 invariant 集成测试，每次 enhanced 包 CI 都跑：

```python
# libs/deepagents-enhanced/tests/test_invariant_v2_assembled.py
"""Invariant: enhanced.create_deep_agent must produce V2 middleware instances.

If this test ever fails after upstream sync, it means either:
- Upstream changed graph.py internals (e.g. lazy import) and our patch no longer
  reaches the right scope
- Upstream renamed/restructured a middleware
- Something in the enhanced package broke
"""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from deepagents_enhanced import create_deep_agent
from deepagents_enhanced.middleware.skills_v2 import SkillsMiddlewareV2
from deepagents_enhanced.middleware.subagent_observability import SubAgentObservability
from deepagents_enhanced.middleware.summarization_overwrite_guard import SummarizationOverwriteGuard
from deepagents_enhanced.middleware.binary_doc_converter import BinaryDocConverterMiddleware


def _list_middleware(agent):
    """Extract middleware instances from compiled agent."""
    # Implementation detail — varies by LangGraph version
    return list(getattr(agent, "middleware", []))


def test_skills_v2_actually_assembled():
    """SkillsMiddlewareV2 must replace upstream V1 in assembled stack."""
    agent = create_deep_agent(
        model=FakeListChatModel(responses=["ok"]),
        skills=["/tmp/poc/x"],
    )
    types = [type(m).__name__ for m in _list_middleware(agent)]
    assert "SkillsMiddlewareV2" in types, \
        f"V2 not assembled — upstream may have changed import pattern. Got: {types}"


def test_subagent_observability_actually_assembled():
    agent = create_deep_agent(model=FakeListChatModel(responses=["ok"]))
    types = [type(m).__name__ for m in _list_middleware(agent)]
    assert "SubAgentObservability" in types, \
        f"SubAgent observability not assembled. Got: {types}"


def test_summarization_overwrite_guard_actually_assembled():
    agent = create_deep_agent(model=FakeListChatModel(responses=["ok"]))
    types = [type(m).__name__ for m in _list_middleware(agent)]
    assert "SummarizationOverwriteGuard" in types, \
        f"Summarization guard not assembled — factory injection broken. Got: {types}"


def test_binary_doc_converter_at_correct_position():
    """BinaryDocConverter should be BEFORE user middleware (AD-2)."""
    class _UserMiddleware:
        pass
    agent = create_deep_agent(
        model=FakeListChatModel(responses=["ok"]),
        middleware=[_UserMiddleware()],
    )
    middlewares = _list_middleware(agent)
    types = [type(m).__name__ for m in middlewares]
    bdc_idx = next((i for i, t in enumerate(types) if t == "BinaryDocConverterMiddleware"), -1)
    user_idx = next((i for i, t in enumerate(types) if t == "_UserMiddleware"), -1)
    assert bdc_idx >= 0 and user_idx >= 0
    assert bdc_idx < user_idx, \
        f"BinaryDocConverter should be BEFORE user middleware. BDC@{bdc_idx} User@{user_idx}"


def test_no_v1_middlewares_leaked():
    """Ensure no upstream V1 middleware leaked through (would mean V2 swap incomplete).

    AD-5 修订: 用类身份比较 (`type(m) is V1`) 而非 `__name__` 字符串。
    避免上游/其他子类碰巧重名导致假阳性。
    """
    from deepagents.middleware.skills import SkillsMiddleware as V1Skills
    from deepagents.middleware.subagents import SubAgentMiddleware as V1SubAgent
    from deepagents.middleware.summarization import SummarizationMiddleware as V1Summ
    agent = create_deep_agent(
        model=FakeListChatModel(responses=["ok"]),
        skills=["/tmp/poc/x"],
    )
    middlewares = _list_middleware(agent)
    # SkillsMiddlewareV2 inherits from V1, so isinstance(_, V1Skills) is True for V2 too;
    # check exact class identity (type() is) instead of isinstance() or __name__
    for m in middlewares:
        if type(m) is V1Skills:
            pytest.fail("Upstream SkillsMiddleware V1 leaked — monkey-patch failed somewhere")
        if type(m) is V1SubAgent:
            pytest.fail("Upstream SubAgentMiddleware V1 leaked")
        if type(m) is V1Summ:
            pytest.fail("Upstream SummarizationMiddleware V1 leaked — factory injection failed")
```

**触发时机**：
- enhanced 包 CI 每次 push 必跑
- 每轮上游 sync 后强制跑（fork master CI）
- pmagent upgrade PR 跑

**fail-fast 价值**：上游 import 风格改变、enhanced 包打包问题、subagent 装配脱节等所有"silent failure"路径都会在这一层被立即捕获。

---

## 附录 C — 实证数据索引

| 事实 | 证据来源 |
| --- | --- |
| 当前 master 合并 upstream 5 大文件冲突 | `git merge-tree HEAD upstream/main` 实测 |
| 上游 graph.py 近 100 commits 修改 3 次 | `git log upstream/main --pretty=%H | head -100 | xargs -I X git diff --name-only X^ X | grep graph.py | wc -l` |
| 上游 graph.py 修改区域覆盖 line 1-600 | 近 10 commits @@hunk 实测 |
| `_convert_document_sync/async` 是模块级函数 | `grep -n "def _convert_document" filesystem.py` → line 648/709 |
| `_EXCLUDED_STATE_KEYS` 当前 fork 加 4 键 | `subagents.py:310` 实测：subagent_logs / skills_loaded / skill_resources / _summarization_event |
| 上游 `_EXCLUDED_STATE_KEYS` 5 键 | `git show upstream/main:subagents.py` → messages / todos / structured_response / skills_metadata / memory_contents |
| `awrap_tool_call` API 稳定 | `permissions.py:344, 372`、`filesystem.py:1953, 1973` 生产使用 |
| 上游 graph.py 用 module-level import | `git show upstream/main:graph.py | grep "^from deepagents"` 实测 |
| Plan E monkey-patch 物理可行 | `/tmp/plan_e_poc.py`（4/4 测试通过，2026-05-02） |
| SummarizationMiddleware factory 注入可行 | `/tmp/plan_e_poc2_summarization.py`（3/3 测试通过，2026-05-02） |
| 主 agent + subagent 共享 patch 上下文 | PoC #1 Test 2 实测：Skills V2 创建 2 实例 |
| Summarization factory 实际返回 `_DeepAgentsSummarizationMiddleware` | PoC #2 Test 5 实测发现（fork 内部子类） |

---

## 附录 D — 关键代码片段索引

| 内容 | 位置 |
| --- | --- |
| Plan E 临时 monkey-patch 完整实现 | §5.3 `_patched_middleware_classes` |
| 永久 monkey-patch（_EXCLUDED_STATE_KEYS） | §5.4 `_patches.py` |
| Startup assertion | §5.5 `_assertions.py` |
| enhanced 包 __init__ | §5.6 `deepagents_enhanced/__init__.py` |
| 路径 B #8 augment + super | §6.1 `summarization_overwrite_guard.py` |
| 路径 B #7 add_async_compat (Option M) | §6.2 `backends/async_compat.py` |
| 路径 B #3 BinaryDocConverterMiddleware | §6.3 `binary_doc_converter.py` |
| 中间件链顺序 | §6.4 |

---

**v4 状态**：等待 Phase 3.0 monkey-patch PoC 物理验证。PoC 通过即可全面启动 M2。
