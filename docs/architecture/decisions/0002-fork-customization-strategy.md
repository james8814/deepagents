# ADR-0002: Fork 定制策略 — 推荐 Plan H+（消除 fork + pmagent 全主权 + 私有 API 治理）

## 文档状态

**状态**: 🟢 **ACCEPTED v3** — 三方签字完成 2026-05-02（v2 ACCEPTED → v3 命名修订版 2026-05-03 自动继承签字）

**签字完成**：以下三方全部签字，本 ADR 由 Draft 转为 Accepted，**Phase A + Phase 1.0-1.4 立即可启动**。

| 角色 | 状态 | 日期 | 备注 |
| --- | --- | --- | --- |
| deepagents CTO（起草人）| ✅ 已起草 Plan H+ 版 | 2026-05-02 | 提供分析与推荐，不代行决策 |
| pmagent 技术总监 | ✅ APPROVE（在 pmagent 接受副本 §6.1 签字）| 2026-05-02 | 见 `pmagent/docs/decision-records/0002-fork-customization-strategy-acceptance.md` |
| 项目负责人 | ✅ **同意** | 2026-05-02 | 直接回复"同意"批准（CTO 受权代为 mark） |

**版本演进**：
- v1（v4-rev2 / Plan E++ 推荐版）— 已废弃
- v2（Plan H+ 推荐版）— 经 8 次方向探索后收敛，2026-05-02 三方签字 ACCEPTED
- **v3（命名修订版，当前）** — 2026-05-03 实施层 namespace collision bug 修订

**v2 → v3 changelog（2026-05-03）**：

- **触发原因**：pmagent Phase 1.1 实施时发现 `src/agent.py`（业务入口模块）与 `src/agent/`（装配代码包）在 Python import 系统中物理不可共存（package 优先级 > module，导致 `agent.py` 被遮蔽）。完整 343 行 bug 报告：`pmagent/docs/bug_fixes/ADR_0002_NAMESPACE_COLLISION_BUG_REPORT.md`
- **修订内容**：所有 `src/agent/` → `src/agent_assembly/`（4 处：§4.1 仓库布局、§6.2 invariant 测试代码示例、§9.2 Phase 1 任务清单 task 1.1 + 1.2）
- **架构决策不变**：仅命名修订，Plan H+ 全部架构决策（消除 fork、pmagent 全主权、私有 API 治理 4 纪律、8 装配不变量）继续生效
- **签字延续**：v2 三方签字（deepagents CTO + pmagent 技术总监 + 项目负责人，2026-05-02）继承至 v3，**不重启会签流程**
- **方法论沉淀（ADR 评审 checklist v1，2026-05-03）**：未来所有 ADR 评审必须满足：
  1. ✅ **仓库布局图配实测脚本**（mkdir + python import 验证）
  2. ✅ **命名修订配三套共存测试**（既验证新建目录可用，又验证现有业务代码零回归 — 由 pmagent 技术总监 v3 unblock 实证沉淀）
  3. ✅ **"已修订 N 处"声明配 grep 验证清单**（避免不验证就声称完成）
  4. ✅ **设计决策配 Python import test**（架构图不能仅靠 review 阅读，必须实证）

  **v3 unblock 流程实证**：从 namespace bug 发现到 Phase 1.1 unblock 全流程 ~1.5 h（deepagents v3 修订 15 min + pmagent 同步实证 25 min + 跨团队签字延续 30 min），印证了"实施层发现 ADR 设计 bug → 轻量修订 → 签字延续 → unblock"的完整 ADR 工程闭环。

  **ADR 评审 checklist v2 增补（2026-05-03 由 pmagent Phase 1.1 spike 模板 bug 沉淀，延续 v1 编号 #1-#4）**：

  - **#5** ✅ **任何归档/废弃决策必须配可执行回滚预案**（限时窗口、命令清单、预期输出 — 由 D-1 fork 归档 SOP 设计沉淀）
  - **#6** ✅ **所有 spike / reference template 代码必须配 3 层验证**（不能仅靠图纸 review）：
    - **Layer 1 — Import 实测**：`python -c "from <template_module> import *"` 必须 0 错误
    - **Layer 2 — 签名验证**：对所有外部依赖函数跑 `inspect.signature(fn)` 验证模板调用与实际签名匹配（特别是位置参数 vs keyword 参数差异、参数数量、可选参数）
    - **Layer 3 — 变量解析验证**：用 `ast.parse + visit` 或 ruff/pyflakes 检查模板中所有变量名是否在作用域内定义（`model_for_summarization` 类 NameError 防御）
    - **历史 bug 触发本条 SOP**：pmagent Phase 1.1 + 1.2 实测发现 spike step 2 模板共 5 处 bug：3 处 import 路径（`deepagents.middleware.{todo_list, anthropic_prompt_caching, human_in_the_loop}` → `langchain.agents.middleware` + `langchain_anthropic.middleware.prompt_caching`）+ 1 处 `_get_harness_profile` 签名错误（应用 `_harness_profile_for_model` 包装）+ 1 处 `model_for_summarization` 未定义变量。全部于 2026-05-03 修订。

  **同源教训**：v3 namespace collision + spike 模板 5 处 bug 都是"图纸 review 不可见、实施第一步触发"的同源问题。**任何代码 / 路径 / 接口决定都必须配实证脚本**，无例外。Layer 1+2+3 验证应作为 ADR / spike 文档评审的强制门。

  **ADR 评审 checklist v4 增补（2026-05-03 由 CTO 第二次失误 — Phase 1.7 SOP + P2 验收 PASS 错误 — 沉淀）**：

  - **#16** ✅ **任何技术文档（SOP / 调查报告 / 验收报告）的关键 claim 必须配 fact-check checklist + 引用 source 文件具体行号**（CTO 验收 SOP 时未读 pmagent pyproject.toml 实证，导致漏判 PEP 440 vs git submodule 致命错误）
  - **#17** ✅ **"内部一致性 cross-validate" 不等于"与真实代码 fidelity 量化"** — 验收必须实测对照真实代码 / log / 文档；CTO PASS 验收 SOP "11/11 一致 + 15/15 一致" 是 SOP↔ADR 内部一致，不是 SOP↔pmagent 真实代码一致
  - **#18** ✅ **CTO 验收也需要被 review** — 三方专家 / 项目负责人有权对 CTO 验收提质疑；CTO 不是 quality first 的豁免者；本会话 CTO 两次重大失误（D-2 v1 设计错误 + Phase 1.7+P2 PASS 验收错误）都由 review 团队 / 项目负责人校正
  - **#19** ✅ **继承自其他文档的 claim（如 P0 working notes → P2）必须独立 fact-check**，不能因为来源权威就传播；P2 直接继承 P0 "qwen3-max 是 reasoning model" 70%→85% 置信度跃升，未做独立验证（Qwen 命名约定 / dashscope 文档 / log 字段实证）

  **CTO 失误根因总结**：CTO 未严格应用自己确立的 ADR checklist（#3 grep 验证、#4 import test、#7 fidelity 量化）。两次失误根因相同。沉淀 = **CTO 推荐 / 验收都必须被实证检验，没有豁免**。

  **ADR 评审 checklist v4 → v5 增补（2026-05-04 由 CTO 第 3/4/6 次失误沉淀）**：

  - **#20** ✅ **任何"prerequisite / 触发条件 / 角色职责"声明必须 fact-check 各角色实际权限边界**（如 PyPI 发布权、git push 权、approval 权），不假设"软件供应链一般直觉"成立 — CTO 第 3 次失误（错误声明"deepagents 团队 release to PyPI"，实际 fork 团队 james8814 无 PyPI deepagents 包发布权 — 由 langchain-ai 持有；PyPI 当前已是 0.5.6，pmagent 可直接 pip install）
  - **#21** ✅ **CTO 不应把"等授权"当默认模式** — 低成本 fact-check（< $1 / < 1 h / 无副作用 / 可回滚）应授权实施团队自主决策；outcome 推进 > process 完美；governance 是工具不是目的 — CTO 第 4 次失误（把 $0.04 dashscope benchmark 当 governance 阻塞，制造虚构 process 摩擦，实际应让 pmagent 自主决策）
  - **#22** ✅ **fact-check 必须含对照实验（control group），不能用单一条件下的多次重复代替对照** — CTO 第 6 次失误 + pmagent 5 次同型失误的根因防御。

    完整定义：

    ```text
    验证某 capability/property 不存在 / 某 condition 是 baseline 时，
    必须配对照实验 (control group)，不能用单一条件下的多次重复代替：

    - 多次同条件重复仅能排除 randomness（max/P50, σ/μ）
    - 不能推断 "baseline"（需 trivial control 对照）
    - 不能推断 "capability 不存在"（需 enabled control 对照）
    - 不能推断变量影响（需固定其他变量做斜率测量）

    实证反例（v1.3 P2 case，v1.5 已修订）:
    - V1 测 enable_thinking=False 单条件 → 错推 "qwen3-max 无 thinking 能力"
      正解：需 enable_thinking=True 对照 (Q1A 实证 reasoning_content 出现)
    - V4 测复杂 prompt × 10 → 错推 "baseline 28-30s"
      正解：需 trivial prompt 对照 (Q2 实证 baseline ~2s)
    ```

    **#22 与 #16-#21 的区别**：

    - #16-#19 防御 fact-check **缺失**（数据没看 / 没引用 source）
    - #20 防御角色权限**不查**（如假设 PyPI release 自动可用）
    - #21 防御 governance **摩擦**（如不必要的微 governance 等授权）
    - **#22 防御实验设计 design flaw（数据真实但设计未覆盖结论范围）**

    **应用 SOP**：

    - 实验 spec **必须**列出对照组（control group）
    - 三方 review 默认 checklist 加"是否有对照实验"
    - CTO 验收 benchmark / 实验数据时，必须先问"实验设计能支撑这个结论吗"，再问"数据是否真实"

    **沉淀根因**: 本会话累计 5+1 次同型失误（pmagent 5 次 + CTO 1 次第 6 次失误）— v1.0 → v1.5 P2 调查 5 次迭代后由项目负责人 Q1+Q2 挑战 catch；详见 `pmagent/docs/bug_fixes/PHASE_A_P2_SLOW_RESPONSE_INVESTIGATION.md` v1.5 §6.A + §6.C。

  **CTO 第 3/4/6 次失误共同根因**：CTO 评估时**只看数据真伪，不看设计或权限边界**。三次失误都被项目负责人挑战 catch。沉淀 = **CTO 评估能力的边界扩展**：fact-check 数据真伪 + fact-check 角色权限边界 + fact-check 实验设计完整性。

  **元层观察（2026-05-04，非 checklist 强制项）**：CTO 第 5 次"失误"（"pmagent 主导 quality first 文化"评价偏移）由 pmagent 技术总监校正。这次校正提示 quality first 文化是**三方相互校正的产物**（CTO 失误催生 ADR / pmagent 实证翻盘 / 项目负责人挑战触发器，三者循环），不是任何单方主导。本观察价值在评价语言准则，但**不作为强制 checklist 项**（评价语言准则不是 reproducible 失误模式，与 #16-#22 性质不同）。

---

## 1. 决策摘要（待批准）

**推荐采纳 Plan H+（待三方签字）：消除 fork 仓库，pmagent 全主权（装配 + V2 子类 + 私有 API 治理）**

> 注：本 ADR 为 Draft，"采纳" 语义在三方签字 + 用户接受私有 API 治理责任后生效。
> 在 Draft 状态下，本节为**推荐方案描述**，不是已生效决议。

| 关键决策 | 描述 |
| --- | --- |
| **架构方向** | pmagent 直接依赖上游 `deepagents` pip 包（无 fork） |
| **装配 ownership** | pmagent 拥有完整装配代码（拷贝自上游 graph.py + V2 替换 + pmagent 适配） |
| **V2 子类位置** | pmagent 仓库（`pmagent/src/agent_assembly/middleware/`）|
| **Monkey-patch** | 0（pmagent 不依赖任何 monkey-patch）|
| **私有 API 治理** | pmagent 团队承担（4 项纪律见 §6）|
| **fork 仓库** | **彻底消除**（保留为历史档案）|

---

## 2. 业务背景

### 2.1 用户的核心诉求（按优先级）

| # | 诉求 | 真实底线 |
| --- | --- | --- |
| L1 | 上游同步零冲突 | "希望 deepagents fork 可以随时同步上游...不希望任何代码合并冲突" |
| L2 | 务实工程经济学 | "投入产出比最高，风险最低，效率最高" |
| L3 | 不增加 pmagent 负担 | "不要因 pmagent 难度提升而失去意义" |
| L4 | 管理 monkey-patch | "对 monkey-patch 掌握其缺点，避免成为瓶颈" |
| L5 | 长期演进自由 | "成熟的商业产品...未来发展性" |
| L6 | 装配主权 | "deepagents 是基础设施...自主掌控装配和定制能力" |
| L7 | 深度定制能力 | "更深的优化和垂直发展" |
| L8 | **harness 层能力建设**（关键揭示） | "异步执行优化、多 agent 并行、agent 团队协作、自我学习进化、pmagent 的 harness 能力" |
| L9 | 接受 fork 团队长期合作 | "deepagents 是基础设施" |

**Plan H+ 对所有 L1-L8 完全满足**。L9 与 Plan H+ 不冲突——pmagent 与 deepagents 上游建立**直接依赖关系**，跳过 fork 中间层。

### 2.2 业务路线图（pmagent 6-12 个月）

| 能力 | 性质 |
| --- | --- |
| 异步执行机制优化 | **当前急需**（"现在存在严重的问题"，需诊断）|
| 持续增强知识库 | 路线图项 |
| 记忆机制（已有 ContextMiddleware）| 当前在用 |
| 长时间持续工作 | 路线图项 |
| Skill 机制（已有 V2）| 当前在用 |
| 多 agent 并行工作 | 路线图项 |
| Agent 团队协作 | 路线图项 |
| Agent 自我学习进化 | 路线图项 |

这是 harness 层能力建设。Plan H+ 提供完整 harness 层主权支撑这些能力。

---

## 3. 评估过的方案（全谱）

| 方案 | 简述 | 状态 |
| --- | --- | --- |
| Plan A | **完全自写装配**（pmagent 不复用上游 graph.py 任何代码，重写整个装配逻辑） | 否决（当时仅按 L3 判断；L8 harness 主权浮现后被 Plan H+ 重新激活——区别在 H+ 是拷贝而非重写） |
| Plan B | deepagents_ext/ namespace | 否决（人为命名空间） |
| Plan C | 完全保守（不动）| 否决（不解决问题） |
| Plan D (v3) | Fork 内部重构 + graph.py 200 行装配中心 | 否决（实测仍 5 大文件冲突，违反 L1）|
| Plan Q | pmagent 接管装配（带 fork extras）| 演进为 Plan H |
| Plan R | 全局 monkey-patch | 否决（概念负担）|
| Plan E | 独立 enhancement 包 + monkey-patch | 演进为 Plan E++ |
| Plan E++ | v4-rev2 + thin wrapper（保留 monkey-patch in enhanced）| 否决（不满足 L8 harness 主权）|
| Plan H | pmagent 装配 + fork extras 包 | 演进为 Plan H+（fork 被证明无独立价值）|
| **Plan H+ (当前推荐)** | **pmagent 复用上游 graph.py（拷贝 + V2 替换，~75%）+ pmagent 业务适配（~25%）+ 0 fork + 私有 API 治理**。具体数值见 §4.3。区别于 Plan A：Plan H+ **不重写**，而是**复用上游代码 + 增量适配**。 | **推荐采纳（待签字）** |

---

## 4. Plan H+ 核心架构

### 4.1 仓库布局

```text
（fork 不再存在！）

pmagent/                                # 唯一项目仓库
├── pyproject.toml                      # deepagents ~= 0.5.0 (PEP 440 兼容范围：允许 0.5.x patch，禁止 0.6.x minor)
└── src/
    ├── agent.py                        # 业务入口（调 create_pmagent_agent）
    └── agent/                          # 装配 + 增强 + 治理
        ├── assembly.py                 # create_pmagent_agent（拷贝自上游 graph.py + V2 替换 + pmagent 适配，~280-380 行）
        ├── builders.py                 # _build_gp_middleware / _build_subagent_middleware / _build_main_middleware
        ├── middleware/
        │   ├── skills_v2.py            # SkillsMiddlewareV2 子类
        │   ├── subagent_observability.py # SubAgentObservability 子类（含 _EXCLUDED_STATE_KEYS extension）
        │   ├── summarization_overwrite_guard.py  # augment + super 子类
        │   └── binary_doc_converter.py # 独立 post-processing middleware
        ├── backends/
        │   └── async_compat.py         # add_async_compat() in-place 方法 patch
        ├── invariants.py               # 装配 invariant 测试 + 8 个不变量文档
        └── _private_api_imports.py     # 私有 API import 集中管理 + 治理文档

upstream deepagents (PyPI)              # pmagent 直接依赖
```

### 4.2 V2 增强清单（5 项，全部住 pmagent）

| # | 增强 | 实现 | 私有 API 依赖 |
| --- | --- | --- | --- |
| 1 | `SkillsMiddlewareV2` | `class V2(SkillsMiddleware)` 子类 | 公开 API |
| 2 | `SubAgentObservability` | `class V2(SubAgentMiddleware)` 子类 | ⚠️ `_extract_subagent_logs`, `_stream_subagent_sync` 等 5+ 模块级 helper |
| 3 | `SummarizationOverwriteGuard` | augment + super 子类 | 公开 API |
| 4 | `BinaryDocConverterMiddleware` | 独立 middleware（`awrap_tool_call` 模式）| 公开 API |
| 5 | `add_async_compat()` | in-place backend 方法 patch | 公开 API |

加上模块级 patch：
| # | Patch | 实现 |
| --- | --- | --- |
| 6 | `_EXCLUDED_STATE_KEYS` 扩展 | `set.update()` mutate-in-place（在 V2 子类 `__init__` 或独立 patches.py） |

### 4.3 装配代码本质 — "拷贝 + 替换 + 适配"

pmagent 装配代码 = 上游 `graph.py:218-639` 的复制粘贴 + V2 类替换 + pmagent 业务适配。

**总行数估算**（基于 spike 步骤 2/3 实测）：

| 组件 | 行数 | 拷贝率 |
| --- | --- | --- |
| `_build_gp_middleware` | 35 | ~85% 拷贝自 upstream graph.py:443-475 |
| `_build_subagent_middleware` | 50 | ~85% 拷贝自 upstream graph.py:482-543 |
| `_build_main_middleware` | 60 | ~90% 拷贝自 upstream graph.py:551-606 |
| `_split_subagents` / `_ensure_general_purpose` / `_build_system_prompt` | 38 | ~95% 拷贝 |
| `create_pmagent_agent` 主入口 | 70 | ~60% 拷贝 + 40% pmagent 适配 |
| **基础装配合计** | **~280** | **~80% 拷贝** |
| pmagent 业务适配（PMAgentState、harness profiles、multi-model、6+ subagents、HIL、双 backend）| **~80-100** | 0%（全新写）|
| **总计** | **~360-380 行** | — |

---

## 5. 实证支撑（22 个 PoC 测试 + spike 三步走）

| 实证 | 出处 | 结论 |
| --- | --- | --- |
| 实测一：当前 master 合并 upstream/main 5 大文件冲突 | `git merge-tree HEAD upstream/main` | Plan D 不可行 |
| 实测二：上游近 100 commits 修改频率（graph.py 3 次、subagents.py 2 次等）| git log 实测 | 数据基础 |
| 实测三：上游 graph.py 修改区域分布 | hunk 分析 | 装配区是热点 |
| 实测四：`awrap_tool_call` API 稳定性 | 上游生产用 | BinaryDocConverter 设计可行 |
| 实测五：基础 monkey-patch PoC（4/4） | `/tmp/plan_e_poc.py` | 监督 v4-rev2 已废弃方案 |
| 实测六：Option M backend 方法 patch（5/5） | `/tmp/option_m_poc.py` | Plan H+ 复用 |
| 实测七：Summarization factory 注入（3/3） | `/tmp/plan_e_poc2_summarization.py` | 监督 v4-rev2 已废弃方案 |
| 实测八：扩展集成 PoC（6/6） | `/tmp/v4_rev1_phase3_extended_poc.py` | Plan H+ 复用部分 |
| 实测九：RC-5 mutate-in-place（3/3）| `/tmp/rc5_excluded_keys_poc.py` | Plan H+ 复用 |
| **Spike 步骤 1**（上游装配分支文档）| `docs/architecture/spike/2026-05-02-planh-step1-upstream-assembly-branches.md` | Plan H+ 装配 reference |
| **Spike 步骤 2**（参考模板）| `docs/architecture/spike/2026-05-02-planh-step2-reference-template.py` | Plan H+ 直接拷贝起点（283 行） |
| **Spike 步骤 3**（pmagent 适配 + 量化）| pmagent 仓库步骤 3 文档 | Plan H+ 实施 baseline（309 行 + 32 分支 + 8 不变量）|

---

## 6. 私有 API 治理纪律（pmagent 团队责任）

### 6.1 风险背景

Plan H+ 让 pmagent 装配代码直接 import 上游私有 API（约 10 项 `_` 前缀符号）：

```python
# 装配代码必须的私有 API import 清单
from deepagents._models import resolve_model
from deepagents.graph import (
    BASE_AGENT_PROMPT,
    _resolve_extra_middleware,
    _apply_tool_description_overrides,
)
from deepagents.profiles import _HarnessProfile, _get_harness_profile
from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware
from deepagents.middleware.permissions import _PermissionMiddleware
from deepagents.middleware.subagents import _EXCLUDED_STATE_KEYS, GENERAL_PURPOSE_SUBAGENT
```

**风险**：上游不承诺 `_` 前缀 API 的稳定性。任何 minor release 可重命名/删除/重构，pmagent 升级时可能 break。

### 6.2 4 项强制治理纪律（pmagent 团队承担）

#### 纪律 1：版本锁定（最关键）

```toml
# pmagent/pyproject.toml
dependencies = [
    "deepagents ~= 0.5.0",  # 🔒 PEP 440 兼容范围：允许 0.5.x patch（CVE/bug fix），禁止 0.6.x minor
]
```

**理由（v2 修订，RC-3）**：
- 私有 API 不承诺稳定性，但 **patch release（0.5.x）** 通常只 fix bug 不破坏接口
- `==0.5.0` 死锁会让 pmagent 错过上游 CVE 修复 + 触发新机器 pip install 警告
- `~=0.5.0` 允许 patch release 自动 pip up，**禁止** minor/major 版本升级
- minor/major 升级（如 0.6.0）必须手动改 pyproject.toml + 跑 `tools/check_private_api.py` 验证

#### 纪律 2：私有 import 全部文档化（每个含 rationale）

```python
# pmagent/src/agent_assembly/_private_api_imports.py
"""集中管理 deepagents 私有 API import + 升级 review rationale。

每个 _ 前缀 import 必须有：
- rationale: 为什么使用这个私有 API
- alternative: 是否有公开 API 可替代
- upgrade_review: 升级时检查什么
"""
from deepagents._models import resolve_model
"""rationale: 模型字符串 → BaseChatModel 解析。
   alternative: 无公开 API 替代。
   upgrade_review: 检查 resolve_model(spec: str) -> BaseChatModel 签名不变。"""

from deepagents.graph import _resolve_extra_middleware
"""rationale: profile 系统的 middleware 注入点。
   alternative: 重新实现 profile 加载（需 ~50 行 + 与上游同步）。
   upgrade_review: 检查 _resolve_extra_middleware(profile) 接口契约。"""

# ... 全部 10 项 import 必须文档化
```

#### 纪律 3：升级 SOP 强制门

```markdown
# pmagent/docs/operations/deepagents-upgrade-sop.md

## 升级 deepagents 版本前必须完成

1. [ ] 阅读 deepagents changelog（关注 BREAKING CHANGES 或 internal API）
2. [ ] 跑 `pmagent/tools/check_private_api.py`：
       验证 10 项私有 API 仍存在 + 签名兼容
3. [ ] 跑 invariant 测试套件（`tests/test_assembly_invariants.py`）
4. [ ] 跑 9 个 subagent_logs contract 测试
5. [ ] e2e + langgraph dev 烟测
6. [ ] 更新 pmagent/pyproject.toml pin 版本
7. [ ] PR review 必须含 SDK 装配工程师签字

任一步骤 fail → 不升级，先排查。
```

#### 纪律 4：Invariant 测试持续守护

```python
# pmagent/tests/test_assembly_invariants.py
def test_private_apis_still_exist():
    """Fail loudly if upstream renamed/removed private APIs."""
    from deepagents.graph import _resolve_extra_middleware, _apply_tool_description_overrides
    from deepagents.profiles import _HarnessProfile, _get_harness_profile
    from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware
    from deepagents.middleware.permissions import _PermissionMiddleware
    from deepagents.middleware.subagents import _EXCLUDED_STATE_KEYS, GENERAL_PURPOSE_SUBAGENT
    # 全部 10 项 import 必须可用


def test_v2_classes_correctly_assembled():
    """SkillsMiddlewareV2 / SubAgentObservability / SummarizationOverwriteGuard 装配生效。"""
    agent = create_pmagent_agent(model=FakeListChatModel(...), skills=[...])
    middlewares = _list_middleware(agent)
    types = {type(m).__name__ for m in middlewares}
    assert "SkillsMiddlewareV2" in types
    assert "SubAgentObservability" in types


def test_skills_middleware_signature_compat():
    """V2 子类必须接受 V1 父类相同 __init__ 参数。"""
    import inspect
    from deepagents.middleware.skills import SkillsMiddleware
    # Note: 实际 import path 取决于 pmagent 包配置（pyproject.toml `packages` 设置）
    # 默认 src layout 用 `from src.agent.middleware.skills_v2 import SkillsMiddlewareV2`
    from src.agent.middleware.skills_v2 import SkillsMiddlewareV2
    parent_sig = inspect.signature(SkillsMiddleware.__init__)
    child_sig = inspect.signature(SkillsMiddlewareV2.__init__)
    # 父类必需参数都被子类接受
    for name, param in parent_sig.parameters.items():
        if param.default == inspect.Parameter.empty and name != "self":
            assert name in child_sig.parameters


def test_excluded_state_keys_extended():
    """fork 扩展的 4 个键真的被状态隔离过滤。"""
    import deepagents.middleware.subagents as _subagents
    expected_keys = {"subagent_logs", "skills_loaded", "skill_resources", "_summarization_event"}
    assert expected_keys.issubset(_subagents._EXCLUDED_STATE_KEYS)


def test_binary_doc_converter_assembled():
    """BinaryDocConverter prepend 在用户 middleware 之前。"""
    user_mw = _UserMiddleware()
    agent = create_pmagent_agent(middleware=[user_mw], ...)
    middlewares = _extract_middleware_order(agent)
    bdc_idx = next(i for i, m in enumerate(middlewares) if type(m).__name__ == "BinaryDocConverterMiddleware")
    user_idx = next(i for i, m in enumerate(middlewares) if type(m).__name__ == "_UserMiddleware")
    assert bdc_idx < user_idx


# v2 修订 RC-5：第 6 项 — 行为契约测试
def test_v2_class_behavior_contract():
    """V2 子类的关键行为契约不被上游内部修改打破（fixture-based）。

    签名兼容（test 3）只检查接口；本测试检查内部行为。
    例：上游 SkillsMiddleware._build_skills_prompt 从 .md 改为 .yml 文件读取
        → 签名不变但行为变 → V2 子类继承的逻辑可能错 → silent failure。
    每个 V2 子类至少 1 个核心行为契约 fixture-based test。
    """
    # 1. SkillsMiddlewareV2: 加载 .md 文件 → 返回 SkillMetadata
    skill_md_fixture = "/tmp/test_skills/sample/SKILL.md"
    skills = SkillsMiddlewareV2(backend=..., sources=[skill_md_fixture])
    metadata = skills.discover_skills()  # 或对应 V2 方法
    assert "sample" in {m["name"] for m in metadata}, "Skills V2 行为契约破坏"

    # 2. SubAgentObservability: state["subagent_logs"] 字段格式
    # （已在 9 个 contract 测试中覆盖；此处确认入口）
    assert _verify_subagent_logs_contract_format(), "SubAgent obs 字段契约破坏"

    # 3. SummarizationOverwriteGuard: Overwrite 包装解包
    from langgraph.types import Overwrite
    guard = SummarizationOverwriteGuard(model=..., backend=...)
    wrapped = Overwrite(value=[HumanMessage("hi")])
    result = guard._get_effective_messages(wrapped, event=None)
    assert len(result) == 1, "OverwriteGuard 解包行为契约破坏"

    # 4. BinaryDocConverter: PDF → Markdown
    pdf_fixture = "/tmp/test_docs/sample.pdf"
    converter = BinaryDocConverterMiddleware(backend=...)
    md_result = converter._convert_sync(pdf_fixture, offset=0)
    assert md_result.startswith("# "), "BinaryDocConverter 输出 Markdown 契约破坏"

    # 5. add_async_compat: sync backend → awaitable
    sync_backend = _make_sync_backend_fixture()
    add_async_compat(sync_backend)
    import asyncio
    result = asyncio.run(sync_backend.adownload_files(["x"]))
    assert isinstance(result, list), "Option M async compat 行为契约破坏"
```

每次 CI 跑。任何升级 break 立即 fail loud。

---

## 7. 否决其他方案的理由

### 7.1 为什么否决 v4-rev2 / Plan E++

- ❌ Monkey-patch 工程债（运行时 silent failure 风险）
- ❌ 不满足 L8 harness 层主权（pmagent 装配仍在 enhanced 包黑盒中）
- ❌ 调试边界跨越 monkey-patch
- ❌ 第三方集成（LangSmith 等）兼容性未知
- ❌ 商业产品工程审计困难

### 7.2 为什么否决 Plan H（保留 fork extras）

- 🟡 Fork 没有独立组织价值（pmagent 是唯一 consumer，fork 实际是 pmagent 延伸）
- 🟡 Fork extras 的私有 API "buffer" 仅覆盖 V2 层 20%（装配层 80% 私有 API 仍在 pmagent）
- 🟡 多一层依赖增加协调成本（pmagent 等 fork 发版）
- 🟡 不符合"vendor independence"诉求

### 7.3 实证：8 次方向探索的轨迹

| # | 立场 | 是否合理 |
| --- | --- | --- |
| v3 → v4 Plan E（独立 enhancement 包）| ✅ 实测 5 文件冲突 |
| v4 → 推 Plan H（CTO ultrathink）| ❌ overcorrection |
| 反推回 v4-rev2 | ✅ pmagent 元评审正确 |
| spike 数据强化 v4-rev2 | ✅ 实证 |
| Plan E++ thin wrapper 收敛 | ✅ 装配主权符号化 |
| pmagent 推 Plan H | ❌ overcorrection（基于推测）|
| Q1+Q4 后走 Plan H | ✅ 新业务事实 + 拷贝认知修正 |
| **H → H+** | ✅ **逻辑精化（fork 无独立价值）** |

**4-5 次必要更新 + 2 次 overcorrection + 1 次精化（H→H+）= 收敛在 Plan H+**。

---

## 8. 前置条件（v2 RC-10 新增）

Phase A + Phase 1 启动前必须满足：

| # | 前置条件 | 状态 | 引用 |
| --- | --- | --- | --- |
| 1 | pmagent 孤立模块清理（M1-mini 完成 + RBAC FROZEN 标注）| ✅ 已完成 | ADR-0001 |
| 2 | 异步执行问题初步范围识别（Phase A 启动条件）| ⏳ Phase A 完成 | 本 ADR §9.1 |
| 3 | pmagent 接受副本 Draft 创建（含私有 API 治理责任声明 + 8 项 invariant 维护责任）| ⏳ pmagent 团队 | 本 ADR §13 |
| 4 | 三方签字（CTO + pmagent 技术总监 + 项目负责人）| ⏳ 等待 | 本 ADR §13 |
| 5 | spike 步骤 3 文档归档到 pmagent 仓库（v2 AD-1）| ⏳ pmagent 团队 | pmagent `docs/architecture/spike/2026-05-02-planh-step3-*.md` 或 `docs/decision-records/0002-spike-step3.md`（pmagent 自决路径）|

任一前置条件未满足 → Phase A + Phase 1 不得启动。

### 8.1 8 项不变量清单（v2 AD-4 新增）

pmagent 团队拥有装配代码后必须长期持有的 8 项不变量（来自上游 deepagents 装配设计）：

| # | 不变量 | 来源（上游 graph.py 行）| pmagent 维护责任 |
| --- | --- | --- | --- |
| 1 | **TodoListMiddleware 永远首位** | gp:443 / main:551 | 装配时确保第 1 位 |
| 2 | **`_PermissionMiddleware` 必须每个栈最后一位** | gp:465 / sub:521 / main:606 | 不能用 `list.extend` 插中间；最后 append |
| 3 | **AnthropicPromptCachingMiddleware 无条件加** | gp:462 / main:591 | 即使非 Anthropic 模型；middleware 内部判断 |
| 4 | **MemoryMiddleware 必须在 user middleware + extra_middleware 之后** | main:592-601 | 否则破坏 prompt cache 前缀（注释明示）|
| 5 | **SkillsMiddleware 在 gp 是 #5，在 main 是 #2** | gp:452-453 / main:553-555 | 位置不对称；不要用同一函数装配 gp + main |
| 6 | **Subagent 用自己的 `_subagent_profile`，不是父 `_profile`** | sub:497, 514, 517 | 每 subagent 独立 profile 解析；6+ subagents 意味着 6+ 次 profile 查找 |
| 7 | **`interrupt_on` 主 agent 走 HITL middleware，subagent 走 spec["interrupt_on"]** | main:602-603 / sub:523 | 两条不同路径；Round 11 opt-out 必须正确实现 |
| 8 | **inline_subagents 第一位是 default GP**（用户未显式定义同名时）| main:546-549 | `list.insert(0, ...)` 不是 `append` |

**关键风险**：违反任一不变量都可能导致 silent failure（如违反 #4 → prompt cache miss 率从 70%+ 跌至 0% → API 账单暴涨）。

每个新加入 pmagent 装配工程的开发人员必须 onboarding 时学习这 8 项不变量。

---

## 9. 实施计划

### 9.1 Phase A：异步问题诊断（与 Phase 1 并行）

| 工作 | 估时 | 责任 | 输出 |
| --- | --- | --- | --- |
| 诊断 pmagent 异步执行"严重问题"具体是什么 | 0.5-1 d | pmagent | 诊断报告（pmagent 业务代码 / LangGraph dispatch / SubAgent 调度 / 其他）|

诊断结果作为 Phase 1 的装配设计输入。

### 9.2 Phase 1：pmagent 装配实施（**7-10 d**，v2 修订 RC-4）

**估时校正（RC-4）**：原 5-8 d 偏紧。实际代码量 ~1100 行（assembly + builders + 5 V2 类 + patches + 治理 + 9 测试 + 工具），加上 8 不变量内化 + 集成调试 + e2e，合理为 7-10 d。

| 步骤 | 工作 | 估时 |
| --- | --- | --- |
| **1.0** | **私有 API manual test**（AD-3 新增）：跑 `tools/check_private_api.py` 早期版本，确认 10 项私有 API 在 deepagents 0.5.0 中**全部可 import + 签名匹配**。任一项失效或不匹配 → 暂停 + 升级 ADR | **0.25 d** |
| 1.1 | 拷贝 spike 步骤 2 reference template 到 `pmagent/src/agent_assembly/assembly.py` + `builders.py` | 0.5 d |
| 1.2 | 实现 5 个 V2 类到 `pmagent/src/agent_assembly/middleware/` | 1.5-2 d |
| 1.3 | 实现 `add_async_compat()` + `_EXCLUDED_STATE_KEYS` patch | 0.25-0.5 d |
| 1.4 | 创建 `_private_api_imports.py` 集中管理 + 文档化 10 项私有 API（纪律 2）| 0.5 d |
| 1.5 | pmagent 业务适配（PMAgentState、harness profiles、multi-model、6+ subagents、HIL、双 backend、Alt E pattern）— **必须在 Phase A 异步诊断完成后启动**（RC-8）| 2-3 d |
| 1.6 | invariant 测试（**6 项**含行为契约测试，RC-5）+ 9 contract 测试 | 0.75-1 d |
| 1.7 | 升级 SOP 文档（纪律 3）+ check_private_api.py 工具完善 | 0.5 d |
| 1.8 | 集成调试 + e2e + langgraph dev 烟测 | 1-1.5 d |
| **小计** | | **7-10 d** |

### 9.3 Phase 2：Migration 收尾（1 d）

| 步骤 | 工作 | 估时 |
| --- | --- | --- |
| 2.1 | 修改 `pmagent/pyproject.toml`：deepagents 直接依赖 `~=0.5.0`（纪律 1，PEP 440 兼容范围）| 0.25 d |
| 2.2 | 删除/归档 fork 仓库（保留为历史档案，加 README 说明）| 0.25 d |
| 2.3 | pmagent 业务代码 import 替换（`create_deep_agent` → `create_pmagent_agent`）| 0.25 d |
| 2.4 | 全量回归测试 + 文档定稿 | 0.25 d |
| **小计** | | **1 d** |

### 9.4 总日历（v2 修订 RC-4 + RC-8 + AD-2）

**串行口径**（保守上限）：
- Phase A 0.5-1 d + Phase 1 7-10 d + Phase 2 1 d = **8.5-12 d**

**并行口径**（含 RC-8 sequencing 约束）：
- Phase A（0.5-1 d）与 Phase 1.0-1.4（基础装配，3-4 d）**可并行**
- Phase A **必须先于 Phase 1.5**（pmagent 业务适配，2-3 d）启动
- Phase 1.5+ 之后串行：1.6-1.8（2.5-4 d）+ Phase 2（1 d）
- 并行口径日历 = max(Phase A, Phase 1.0-1.4) + Phase 1.5 + Phase 1.6-1.8 + Phase 2
- = max(1, 3-4) + 2-3 + 2.5-4 + 1 = **8.5-12 d**

**结论**：串行/并行口径接近，因 Phase A 较短，并行带来的 saving 有限。**建议给 9-12 d buffer**。

| 阶段 | 估时 | 备注 |
| --- | --- | --- |
| Phase A（异步诊断，与 1.0-1.4 并行；必须先于 1.5）| 0.5-1 d | pmagent |
| Phase 1（装配实施，含 1.0 manual test 前置）| **7-10 d** | pmagent |
| Phase 2（migration 收尾）| 1 d | pmagent |
| **日历总计**（含并行）| **9-12 d** | 全部 pmagent 团队（RC-4 修订估时 + 含 buffer）|

### 9.5 Sequencing 约束（v2 RC-8 强化）

```text
[Phase 0]（前置条件，签字前完成）
  ├─ ADR-0001 M1-mini 完成（pmagent 孤立模块标记）
  ├─ 异步问题初步范围识别
  └─ pmagent 接受副本 Draft 创建

       ↓ 三方签字 + pmagent 接受私有 API 治理责任

[Phase A] 异步问题深度诊断（0.5-1 d）  ←──┐
                                          │ 并行
[Phase 1.0] 私有 API manual test（0.25 d）│
[Phase 1.1] 拷贝 reference template (0.5 d)│
[Phase 1.2] 5 V2 类（1.5-2 d）            │
[Phase 1.3] patches + async_compat (0.25-0.5 d)│
[Phase 1.4] _private_api_imports.py (0.5 d)──┘

       ↓ Phase A + 1.0-1.4 全部完成（不可跳过 sequencing 约束）

[Phase 1.5] pmagent 业务适配 (2-3 d)
       ↓
[Phase 1.6] invariant 测试 + 9 contract 测试 (0.75-1 d)
[Phase 1.7] SOP + check_private_api.py 完善 (0.5 d)
[Phase 1.8] 集成 + e2e + langgraph dev 烟测 (1-1.5 d)

       ↓

[Phase 2] Migration 收尾（1 d）
  ├─ pyproject.toml 改为 ~=0.5.0（RC-3）
  ├─ fork 归档 SOP 4 步走（§9.6）
  ├─ pmagent import 替换
  └─ ADR-0002 转 Accepted（三方签字后）
```

**关键约束**：
- Phase A 输出（异步问题根因）作为 Phase 1.5 的设计输入
- 如 Phase A 揭示需要替换 SubAgentMiddleware 装配方式 → ADR 修订 → Phase 1.5 重排
- Phase 1.0 manual test 任一失败 → 暂停 + 重新评估方案

### 9.6 Fork 归档 SOP（v2 RC-9 新增）

Phase 2.2 "删除/归档 fork" 具体执行：

| 步骤 | 操作 | 时机 |
| --- | --- | --- |
| 1 | fork master 分支添加 README ARCHIVED banner（含演进路径 + 当前权威方案 Plan H+ 链接 + ADR-0002 链接）| Phase 2.2 启动时 |
| 2 | GitHub repo "Archive this repository" 操作 — 转只读，保留全部 commit 历史不可修改 | Phase 2.2 |
| 3 | pmagent 旧分支 / examples / docs 扫描 + import path 更新 — 删除任何 `from deepagents-extras` / `from deepagents-enhanced` 引用 | Phase 2.2 |
| 4 | 6 个月后评估是否彻底 delete repo（默认保留以备 forensic 价值）| 2026-11-02 季度评审 |

---

## 10. 决策的正向后果

**对比 Plan E++（v4-rev2）**：日历持平或略多，但**消除 monkey-patch 工程债 + 完整 harness 主权**。具体收益量化：

| 收益 | 量化 |
| --- | --- |
| 上游同步冲突 | 数学保证 0（pmagent 0 修改上游，仅 pip 升级时 review）|
| Monkey-patch 工程债 | **完全消除** |
| Harness 层主权 | **完全主权**（装配 + V2 + 治理）|
| Vendor independence | 完全（仅依赖上游 pip 包）|
| 调试体验 | 标准 Python（无 patch 边界）|
| 第三方集成兼容 | 无 patch 风险 |
| Pmagent 业务代码改动 | 1 行 import 替换 |
| 长期年度维护 | 1.5-3 h/年（升级时 review）|

---

## 11. 决策的负向后果（已识别 + 已缓解）

| 工程债项 | 严重性 | 缓解 |
| --- | --- | --- |
| 私有 API 依赖（10 项）| 🟡 中 | 4 项治理纪律（§6）|
| pmagent 团队需掌握 8 个不变量 | 🟡 中 | 用户已承诺培养 SDK 装配工程能力；invariants.py 文档化 |
| 上游 graph.py 升级时需 review | 🟢 低 | 实测频率 3 次/100 commits；升级 SOP 强制门 |
| 装配代码 long-lived 维护 | 🟢 低 | 80% 是上游拷贝；pmagent 主动定制驱动增长 |
| 跨大版本升级（0.7+）| 🟢 低 | 1-2 d/年，纪律 3 SOP 处理 |

---

## 12. 翻盘条件（未来重新评估的触发场景）

| # | 触发条件 |
| --- | --- |
| 1 | pmagent 出现具体业务需求要求 deepagents 装配不能支持的能力（必须附具体场景描述）|
| 2 | 上游 deepagents 重大重构使私有 API 完全不可用（≥ 50% 私有 API 失效）|
| 3 | 异步执行问题诊断后发现需要 deepagents fork 才能解决 |
| 4 | pmagent wrapper 自然增长 > 800 行（异常增长信号）|
| 5 | 业务模型转变（如 pmagent 转向其他 agent 框架）|

**翻盘评估强制要求**：任何翻盘评估必须**重新做完整 spike**（步骤 1+2+3），不接受用 2026-05 数据做未来决策。

---

## 13. 决策档案签发状态

**当前状态**：🟢 **Accepted** —— 详见文档顶部 "## 文档状态" 节签字状态表（避免冗余）

**已生效（三方签字完成 2026-05-02）**：

- ✅ Phase A + Phase 1.0-1.4 立即可启动
- ✅ 季度评审起算（首次评审 2026-08-02）
- ✅ 翻盘条件每季度检查
- ✅ ADR-0002 可作为后续决策依据被引用

**历史 Draft 状态约束已解除**（已生效，约束自动失效）。

---

## 14. 决策档案位置

- **deepagents 主档案**（本文档）：`/Volumes/0-/jameswu projects/deepagents/docs/architecture/decisions/0002-fork-customization-strategy.md`
- **pmagent 仓库 spike 步骤 3 文档**（v2 AD-1 明示路径，pmagent 团队产出）：建议归档到 `/Volumes/0-/jameswu projects/langgraph_test/pmagent/docs/architecture/spike/2026-05-02-planh-step3-pmagent-adaptation.py` + `2026-05-02-planh-step3-quantification-report.md`（pmagent 自决路径，但应在接受副本中 link 引用）
- **pmagent 接受副本**（pmagent 团队需创建）：`/Volumes/0-/jameswu projects/langgraph_test/pmagent/docs/decision-records/0002-fork-customization-strategy-acceptance.md`
  - 内容：`pmagent 接受 deepagents ADR-0002 Plan H+` 声明 + 链接到主档案 + 私有 API 治理责任接受书 + 8 项 invariant 维护责任接受书
  - **创建时机（v2 RC-6 修订）**：ADR Draft 起草后**立即**，作为签字流程的一部分（不是事后行为）
  - **签字载体**：pmagent 技术总监在接受副本签字（含治理责任）；项目负责人在 deepagents 主档案签字（决策批准）
  - **正确签字流程**：
    1. ✅ deepagents CTO 起草 Plan H+ 主档案 + ADR Draft（已完成）
    2. ✅ pmagent 团队创建接受副本 Draft（含治理责任声明）（已完成）
    3. ✅ pmagent 技术总监 review 双 Draft → 在接受副本签字 APPROVE（2026-05-02）
    4. ✅ 项目负责人 review 双 Draft + pmagent 签字 → **同意批准（2026-05-02）**
    5. ✅ 双方文档同步转 **Accepted**

---

## 15. 历史文档归档

本 ADR 推荐 Plan H+ 取代 Plan E++（v4-rev2）。已被取代的历史文档保留为决策档案：

| 文档 | 状态 |
| --- | --- |
| `docs/architecture/2026-04-29-fork-customization-downsink-plan.md`（v1）| HISTORICAL（早期 Plan B 探索）|
| `docs/architecture/2026-05-01-fork-customization-downsink-plan-v2.md`（v2）| HISTORICAL（Plan D 提出）|
| `docs/architecture/2026-05-01-fork-customization-downsink-plan-v3.md`（v3）| HISTORICAL（Plan D 三轮加强）|
| `docs/architecture/2026-05-02-fork-enhancement-package-plan-v4.md`（v4-rev2）| **SUPERSEDED**（被 Plan H+ 取代）|
| `docs/architecture/2026-05-02-plan-h-plus-final.md`（Plan H+ 主设计）| **CURRENT**（与本 ADR 配套）|
| `docs/architecture/spike/*`（spike 三步走文档）| 实证档案（Plan H+ 复用其数据）|

---

## 附录 A: 核心方法论收获（与 ADR 决策同等重要）

8 次方向反转中的 4-5 次必要更新 + 2 次 overcorrection 留下的方法论沉淀：

1. **业务真实需求清单**是架构决策的最高锚点（不是理论价值）
2. **对等严苛实证**是反转的合法性门槛（不能只用框架重定义结论）
3. **角色分离**是商业产品 ADR 的形式化要求（架构师不代行决策机构）
4. **外科手术更新**优于全面重构（保留决策可追溯）
5. **业务全景路线图**比"当前需求"更能驱动决策（Plan H+ 的关键揭示）
6. **每次反转必须先核查"业务事实是否变化"**（不是"框架是否更新"）

这些原则已固化为后续重大架构决策的 SOP。

## 附录 B: 关键 spike 输出文件

Plan H+ 决策的实证基础来自 spike 三步走：

- [`docs/architecture/spike/2026-05-02-planh-step1-upstream-assembly-branches.md`](../spike/2026-05-02-planh-step1-upstream-assembly-branches.md) — **步骤 1：上游装配分支文档化**。映射上游 `graph.py` 的 9 节装配逻辑（gp 栈 / subagent 栈 / main 栈 + sequencing 约束），是 pmagent 装配代码的拷贝 reference。
- [`docs/architecture/spike/2026-05-02-planh-step2-reference-template.py`](../spike/2026-05-02-planh-step2-reference-template.py) — **步骤 2：reference template**（283 行 Python 模板）。Plan H+ Phase 1.1 直接拷贝起点，含 `_build_gp_middleware` / `_build_subagent_middleware` / `_build_main_middleware` + V2 类替换示例。
- pmagent 仓库：`docs/architecture/spike/2026-05-02-planh-step3-pmagent-adaptation.py` — **步骤 3：pmagent 实测装配**（309 行）。基于步骤 2 模板适配 pmagent 实际配置（PMAgentState、6+ subagents、双 backend 等），量化 32 条件分支 + 8 不变量真实存在。
- pmagent 仓库：`docs/architecture/spike/2026-05-02-planh-step3-quantification-report.md` — **步骤 3：量化报告**。30 维度决策矩阵（行数 / 分支数 / 不变量数 / shadow risk），是 §3 否决 Plan E++ + 选择 Plan H+ 的实证依据。

## 附录 C: 主设计文档

- [`docs/architecture/2026-05-02-plan-h-plus-final.md`](../2026-05-02-plan-h-plus-final.md) — **Plan H+ 完整技术设计与实施细则**。配套本 ADR 的可执行设计文档，含 10 节：仓库布局 / 装配代码核心设计（含 `create_pmagent_agent` 完整 Python 示例）/ 5 V2 增强类详细实现 / 私有 API 治理 / 实施计划 / 测试策略 / 实证基础 / 风险缓解 / 与本 ADR 关系 / 历史方案归档。本 ADR 是**决策档案**（why & what），主设计是**技术档案**（how）。

---

**ADR 状态**：🟢 **Accepted**（三方签字完成 2026-05-02）
**签字记录**：
- deepagents CTO ✅ 起草 Plan H+ 版（2026-05-02）
- pmagent 技术总监 ✅ APPROVE（在接受副本 §6.1 签字，2026-05-02）
- 项目负责人 ✅ **同意**（2026-05-02）

**生效行动**：
- Phase A 异步问题诊断 + Phase 1.0-1.4 基础装配 **立即可启动**
- 季度评审起算（首次评审 **2026-08-02**）
- 翻盘条件每季度检查（5 项触发条件见 §12）
