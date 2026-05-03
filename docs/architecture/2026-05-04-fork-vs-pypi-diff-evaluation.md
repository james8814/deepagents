# Fork master vs PyPI deepagents diff 评估 spec — fork 归档真实 prerequisite

**起草日期**: 2026-05-04
**起草人**: deepagents CTO
**性质**: ADR-0002 v3 "消除 fork" 承诺真实落地的 prerequisite spec
**触发**: CTO 第 7 次失误识别（fork e2e PASS ≠ PyPI e2e PASS）+ A5 finding（fork-diff-A1：缺可执行评估方法）+ ADR v5 #23 应用（spec 必须含 verification 章节）

---

## 1. 背景与问题

### 1.1 当前实施现实 vs ADR-0002 v3 承诺

| 项 | 现状 | ADR v3 承诺 |
|---|---|---|
| pmagent `pyproject.toml` | `deepagents @ file://third_party/deepagents` (git submodule)| `deepagents ~= 0.5.0` (PyPI) |
| `third_party/deepagents` 引用 | `james8814/deepagents` fork (master, SDK 0.5.0) | 不应依赖 fork |
| upstream/main SDK | 0.5.3（CTO 上次评估时数据；PyPI 可能 0.5.6+）| pmagent 应直接装 |
| Plan H+ "消除 fork" | 🔴 **未真实落地** | ✅ 实施完成 |

### 1.2 fork master 含 substantial 独有代码

CTO 2026-05-03 评估 (commit 1c3a85a6 phase-1-7-p2-cto-recantation.md §2.3) 实证：

```
fork master vs upstream/main (libs/deepagents/deepagents/ 仅 SDK 子集):
  +3,798 insertions / -579 deletions / 21 files changed
```

**fork 独有文件**（PyPI 切换会丢失）：

| 类别 | 文件 | 行数 |
|---|---|---|
| Binary doc converters | `middleware/converters/` (11 files) | 1,444 |
| Universal upload | `upload_adapter.py` | 689 |

**fork 增强的上游文件**（PyPI 切换会丢失增强部分）：

| 文件 | fork 增强行数 | Plan H+ 对应 |
|---|---|---|
| `graph.py` | +458 | state_schema / skills_expose_dynamic_tools / summarization factory |
| `skills.py` | +671 | SkillsMiddlewareV2 完整实现 |
| `subagents.py` | +466 | SubAgent observability + AsyncSubAgent + _ENABLE_SUBAGENT_LOGGING |
| `filesystem.py` | +425 | 大文件 eviction + binary doc 路由 |
| `memory.py` | +14 | isawaitable async/sync compat |
| `summarization.py` | +7 | Overwrite guard |
| `__init__.py` | +3 | extra exports |

### 1.3 CTO 第 7 次失误（fork-diff-A1 触发原因）

我先前反复声明：

> "pmagent 不依赖 fork local features 的实证：pass-through SkillsMiddlewareV2 + e2e PASS"

**实际盲点**：pass-through `class SkillsMiddlewareV2(SkillsMiddleware): pass` **继承的是 fork master 的 SkillsMiddleware（含 +671 行 V2 增强）**，不是 PyPI 0.5.x 的上游版。**e2e 在 fork submodule 上跑 PASS，不能等同 PyPI e2e PASS**。

---

## 2. 评估目标（应用 ADR v5 #22 + #23）

### 2.1 核心问题

**pmagent 切换 `deepagents @ file://third_party/deepagents` → `deepagents ~= 0.5.x` (PyPI) 后**：

1. 哪些 fork features 仍被 pmagent 实际依赖？
2. 哪些可以丢失？
3. 必需保留的 features 应实现为 V2 additive subclass（路径 B，与 SkillsMiddlewareV2 同模式）

### 2.2 不能用什么方法（反例 — 应用 #22）

| 错误方法 | 为什么错 |
|---|---|
| ❌ "看 pmagent 业务代码 import 了哪些 deepagents 符号" | 静态分析无法捕获 runtime 行为差异（如 SkillsMiddleware V2 vs V1 的 hook 差异）|
| ❌ "CTO 主观判断 pmagent 是否需要某 feature" | CTO 不掌握 pmagent 业务全貌，违反 #22（无对照实验）|
| ❌ "用 fork e2e PASS 推断 PyPI e2e PASS" | CTO 第 7 次失误模式（环境等同假设）|

---

## 3. 评估方法（可执行 — 应用 #22 对照实验 + #23 verification）

### 3.1 测试驱动评估（替代主观判断）

**核心思路**：实证测试 = 唯一可靠的"是否依赖"判定。

```text
1. 切换 pyproject.toml: file:// → ~=0.5.x (PyPI 实际版本)
   ↓
2. 重装依赖: uv pip install -e .
   ↓
3. 跑 SOP v1.2 三强制门:
   - 门 1: tools/check_private_api.py (11/11 私有 API 检查)
   - 门 2: pytest test_assembly_invariants.py + test_opdca_workflow_invariants.py (15 项 invariants)
   - 门 3: pytest test_e2e.py + test_e2e_v2.py + test_e2e_comprehensive.py (67 项 e2e)
   ↓
4. 失败的测试 = pmagent 实际依赖该 feature
   通过的测试 = pmagent 不依赖
```

### 3.2 失败 → V2 子类化决策树

```text
某测试 fail (因 PyPI 缺 fork feature):
   ↓
分析 failure 信号:
   ├─ AttributeError: PyPI 上游缺某 method/class
   │     ↓
   │   评估: 此 method/class 是否为 pmagent 业务核心？
   │     ├─ 是 → 实现 V2 additive subclass (与 SkillsMiddlewareV2 同模式)
   │     └─ 否 → 评估业务可否接受丢失（如 Universal upload 可能不需要）
   │
   ├─ 行为差异（数值不同 / 顺序不同）: PyPI vs fork 行为差
   │     ↓
   │   评估: 行为差是否影响业务正确性？
   │     ├─ 是 → V2 子类 override 修复行为
   │     └─ 否 → 接受行为变化
   │
   └─ ImportError: 某 module 路径不存在
         ↓
       check 是否私有 API 路径变化（在 _private_api_imports.py 修订）
```

### 3.3 V2 子类化已知模板

| Fork feature | V2 子类化路径 | 估时 |
|---|---|---|
| SkillsMiddlewareV2（已 pass-through 试水）| 已实施，需补 V2 增强逻辑（如需要）| 0.5-1 d |
| SubAgentObservability（_ENABLE_SUBAGENT_LOGGING + log 提取）| 继承 PyPI SubAgentMiddleware override `task` tool | 0.5 d |
| SummarizationOverwriteGuard | 继承 PyPI summarization middleware 加 isinstance(messages, Overwrite) guard | 0.25 d |
| BinaryDocConverterMiddleware | 完全独立 V2 类（基于 langchain wrap_tool_call）| 1-2 d |
| upload_adapter V5 | 完全独立 V2 类 | 1 d（视复杂度）|
| Memory isawaitable | 继承 PyPI MemoryMiddleware override 异步路径 | 0.25 d |
| graph.py 增强（state_schema / skills_expose_dynamic_tools / summarization factory）| 已在 pmagent builders.py 拷贝实现 | 已完成 |

---

## 4. 评估流程 spec（pmagent 团队执行）

### 4.1 步骤 1: PyPI 版本确认（10 min）

```bash
# 实证 PyPI 当前 deepagents 版本
pip index versions deepagents
# 或
curl -s https://pypi.org/pypi/deepagents/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
```

记录 PyPI 当前版本（设 = X.Y.Z）。

### 4.2 步骤 2: 创建评估分支（5 min）

```bash
cd pmagent
git checkout -b evaluate/pypi-X.Y.Z-switch
```

### 4.3 步骤 3: 切换 pyproject.toml（5 min）

```bash
# 修改 pyproject.toml:
# 删除: "deepagents @ file:///.../third_party/deepagents"
# 添加: "deepagents ~= 0.5.0"  (按 ADR v3 §3.1 锁定 0.5.x patch)

uv pip install -e . 2>&1 | tee /tmp/pypi-switch-install.log
```

### 4.4 步骤 4: 跑 SOP v1.2 三强制门（30-60 min）

```bash
# 门 1: 私有 API 检查
python tools/check_private_api.py 2>&1 | tee /tmp/pypi-check-private.log

# 门 2: invariants
pytest tests/test_assembly_invariants.py tests/test_opdca_workflow_invariants.py -v 2>&1 | tee /tmp/pypi-invariants.log

# 门 3: e2e
pytest tests/test_e2e.py tests/test_e2e_v2.py tests/test_e2e_comprehensive.py -v 2>&1 | tee /tmp/pypi-e2e.log
```

### 4.5 步骤 5: 分析 fail 信号（30 min - 1 h）

```bash
# 提取 failures
grep -E "FAIL|ERROR|AttributeError|ImportError" /tmp/pypi-*.log | sort | uniq -c

# 对每个 failure，按 §3.2 决策树分类
```

### 4.6 步骤 6: 输出评估报告（30 min）

格式参考：

```markdown
## PyPI 切换评估报告

**PyPI 版本**: X.Y.Z
**测试日期**: YYYY-MM-DD
**SOP v1.2 三强制门**: ✅ Pass / ❌ Fail (具体 N 项)

### 失败测试 → 依赖 features 映射

| 测试 | failure 信号 | 推断依赖 | V2 子类化路径 | 估时 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

### 决策建议

- 必需 V2 子类化: ... (合计 X d)
- 可丢失 features: ... (评估业务可接受性)
- 切换可行性: 🟢 / 🟡 / 🔴
```

---

## 5. Verification 章节（应用 ADR v5 #23）

| 客观判定标准 | 验证方法 | 失败可观察信号 | 责任 |
|---|---|---|---|
| pmagent 切换 PyPI 后 SOP v1.2 三强制门 PASS | 跑 §4.4 三测试套件 | 任一测试 fail → 进入 §4.5 分析 | pmagent 团队（实施）|
| 失败测试映射到具体 fork feature | 对每个 fail 应用 §3.2 决策树 | 失败信号无法归因 → 需更深入 debug | pmagent 团队（分析）|
| V2 子类化路径可行 | 对必需保留的 features 写出 V2 子类 prototype | V2 子类无法实现等价行为 → 翻盘评估 | pmagent + CTO（review）|
| 评估报告含明确决策建议 | 报告含 §4.6 表格 + 决策 | 仅"主观判断 OK"无量化 | pmagent 技术总监（签字）|

**evaluation 时机**：在 D-1 fork 归档 SOP 启动**之前**必须完成。

**3 种可能结论**：

1. 🟢 **绿灯**：所有测试 PASS → 直接切换 PyPI + 启动 D-1 fork 归档
2. 🟡 **黄灯**：部分 fail 但可 V2 子类化 → 实施 V2 子类（B 组工作）→ 重测 → 切换 → D-1
3. 🔴 **红灯**：fail 无法 V2 子类化 → 翻盘评估 ADR-0002 v3（罕见，5 d 重做 spike）

---

## 6. 估时与责任

| 阶段 | 工作 | 责任 | 估时 |
|---|---|---|---|
| 评估准备 | §4.1-4.3（PyPI 版本 + 分支 + 切换）| pmagent | 20 min |
| 评估执行 | §4.4 跑 SOP v1.2（三强制门）| pmagent | 30-60 min |
| 评估分析 | §4.5 分析 fail 信号 + §4.6 报告 | pmagent + CTO 咨询 | 1-2 h |
| **合计** | | | **2-3 h**（绿灯）/ **+1-3 d V2 子类化（黄灯）**|

---

## 7. 应用的 ADR checklist

| # | 应用 |
|---|---|
| #16 关键 claim 配 source 行号引用 | §1.2 fork diff 数据来自 commit 1c3a85a6 phase-1-7-p2-cto-recantation.md §2.3 |
| #17 内部一致性 ≠ fidelity 量化 | §2.2 反例明示"主观判断"不可用，必须实证测试 |
| #20 角色权限边界 | pmagent 持有 evaluation 主权，CTO 仅咨询 |
| #21 outcome 推进 > process 完美 | §6 估时 2-3 h（绿灯）— 不制造 governance 摩擦 |
| #22 fact-check 必须含对照实验 | §3.1 测试驱动评估 = 对照实验（PyPI vs fork 同测试套件）|
| #23 spec 必须含 verification | §5 完整 verification 章节 |

---

**文档状态**: 🟢 spec final（applied #23 — 含 verification 章节）
**deepagents CTO 签字**: ✅ 2026-05-04
**触发条件**: 项目负责人启动 fork 归档时 → pmagent 团队按本 spec 执行
**预期产出**: PyPI 切换评估报告 + 决策建议（绿/黄/红 灯）→ D-1 fork 归档 SOP 启动判定

**配套文档**:

- [ADR-0002 v3](decisions/0002-fork-customization-strategy.md) §0 v5 changelist v5 #23
- [Phase 1.7 SOP v1.2](pmagent/docs/operations/deepagents-upgrade-sop.md)
- [D-1 Fork 归档 SOP](2026-05-03-d1-fork-archive-sop.md)
- [Phase 1.7+P2 CTO Recantation](2026-05-03-phase-1-7-p2-cto-recantation.md) §2.3 fork diff 实证
