# Round 9 上游合并复盘

**日期**: 2026-03-29
**范围**: 42 upstream commits + 2 local fixes = 44 total
**耗时**: 方案制定 ~2h + 实施 ~3h + 修复验收 ~1.5h = ~6.5h

---

## 一、Round 8 vs Round 9 对比

| 维度 | Round 8 | Round 9 | 变化 |
|------|---------|---------|------|
| upstream commits | 10 | 42 | 4.2x |
| 冲突文件 | 6 | 9 | 1.5x |
| fix commits | 2 | 2 | 持平 |
| 方案迭代轮数 | 7 | 2 | **大幅改善** |
| 严重误报 | 1 (evals 假绿) | 0 | **根治** |
| 架构师复验轮数 | 3 | 2 | 改善 |
| SDK 测试 | 1018→1019 | +1 | |
| CLI 测试 | 2608→2744 | +136 | |
| Evals 测试 | 158→158 | 不变 | |

### 关键改善

1. **方案迭代从 7 轮降到 2 轮** — 执行了"最多 3 轮"的原则
2. **venv 假绿不再发生** — 每个 Phase 首次用 `--reinstall` 验证
3. **evals 被纳入标准门禁** — 不再遗漏
4. **SHA 映射表** — 架构师建议后补入，提升了审计可追溯性

---

## 二、Round 9 新发现的教训

### 教训 1: 依赖升级可能破坏测试假设

`langchain-core` 从 1.2.21 升到 1.2.22 时，`baseten` 被加入内置 provider registry。
这导致 `test_explicit_models_list_skips_auto_discovery` 失败 — 测试假设 baseten 不在 registry 中。

**方法论提炼**: 依赖 bump 不是"只改 lockfile 的低风险操作"。当依赖包的**内部数据**（如 provider registry、默认配置）发生变化时，可能破坏依赖这些数据的测试假设。

**应对**: 依赖 bump 后的测试不应只看"是否编译通过"，还要跑完整测试套件。当前 skill 将 deps bump 标为 🟢 低风险是不够的 — 应区分"纯 lockfile"和"可能改变运行时行为的依赖"。

### 教训 2: Cherry-pick 跨 commit 的 import 依赖容易遗漏

上游 commit 18 (`agent-friendly UX`) 引入了 `theme.MUTED` 的使用，但 `from deepagents_cli import theme` 在上游是通过更早的 commit 引入的。Cherry-pick 时如果两个 commit 不在同一批次，import 会缺失。

**方法论提炼**: Cherry-pick 不同于 merge — 它不保证 import 依赖链完整。每个 cherry-pick 后必须跑 lint（不只是语法检查），因为 lint 能发现 F821 (undefined name) 和 F401 (unused import) 这类跨 commit 遗漏。

**应对**: 在 L1 持续验证中，lint 应该是强制项而非可选项。

### 教训 3: "技术债提醒测试" 会变成持久的假失败

`TestLsEntriesShim` 是一个"SDK >=0.5.0 就删除 shim"的提醒测试。但 shim 已被上游清理，提醒测试本身忘了删。这导致测试永远失败。

**方法论提炼**: 提醒测试（assert version < threshold 形式）有保质期。一旦条件满足但无人执行清理，它就变成假噪声。合并时遇到这类测试，应该执行清理而非 xfail。

### 教训 4: 文档数据必须与代码同步更新

MERGE_LOG 中写 "43 total" 但实际是 44（多了一个架构师 review 修复 commit）。
CLI 测试标"待确认"但实际已完成。

**方法论提炼**: 每次追加 fix commit 后，必须同步更新 merge log 的统计数据。

### 教训 5: command_registry 排序是 monorepo 特有的冲突类型

当本地有 `/upload` 而上游加了 `/auto-update` 时，不只是"两者都保留"，还需要维护字母排序、去重、help body 同步。这是 monorepo fork 中命令注册表的特有问题。

---

## 三、Round 8+9 累计成果

| 指标 | 数据 |
|------|------|
| 总 upstream commits 合并 | 52 (R8: 10 + R9: 42) |
| 总 fix commits | 4 (R8: 2 + R9: 2) |
| 总冲突解决 | 15 (R8: 6 + R9: 9) |
| 本地优越特性 | 8/8 完好 |
| 累计合并 (Round 0-9) | ~739 commits |
| SDK 测试趋势 | 1009 → 1018 → 1019 |
| CLI 测试趋势 | 2618 → 2608 → 2744 |

---

## 四、Skill 改进分析

### 当前 Skill 在 Round 9 中的表现

| Skill 环节 | 是否被遵循 | 效果 |
|------------|-----------|------|
| 进度持久化 (PROGRESS.md) | ✅ 创建了 | 但未逐 commit 更新（用 TodoWrite 代替了细粒度追踪） |
| 方案迭代上限 (3 轮) | ✅ 遵循 | 从 R8 的 7 轮改善到 2 轮 |
| 干净 venv 验证 | ✅ 执行 | 无假绿误报 |
| 全包测试 | ✅ SDK+CLI+Evals | 无遗漏 |
| 架构师验收协议 | ✅ 遵循 | 2 轮复验后通过 |
| Import 冲突指导 | ✅ 有效 | 但跨 commit import 遗漏是新场景 |
| 回滚策略 | 未使用 | 无需回滚 |

### 需要改进的 5 个方面

#### 改进 1: L1 验证中 lint 应为强制项

**现状**: L1 只列了语法检查和导入检查，lint 是 L3 才做。
**问题**: Round 9 中 F821 (undefined `theme`) 在 L1 就该发现，而不是等到最终验证。
**建议**: L1 改为：语法检查 + 导入检查 + **lint 检查**。

#### 改进 2: 依赖 bump 风险分级需细化

**现状**: deps bump 统一标为 🟢 低风险。
**建议**: 增加"运行时行为影响"维度：
```
- lockfile-only (patch version): 🟢 低风险
- 可能改变运行时数据/registry (minor version): 🟡 中风险，需跑完整测试
- 可能改变 API/ABI (major version): 🔴 高风险
```

#### 改进 3: 新增"跨 commit import 依赖检查"

**现状**: 冲突解决只关注单个 commit 内部。
**问题**: Cherry-pick 打破了 commit 间的 import 依赖链。
**建议**: 在 commit 合并流程 step 5 中增加：
```
5b. 跨 commit import 检查（cherry-pick 特有）：
    - 新代码使用了 X.Y → 确认 X.Y 的 import 是否已存在
    - 如果 import 来自未来的 commit → 提前手动添加
```

#### 改进 4: merge log 统计数据必须在每次追加 commit 后同步

**现状**: 无明确要求。
**建议**: 在"记录时机"表中增加：
```
| 追加 fix commit 后 | 同步更新 merge log 头部统计（总数、文件数、增删行数）|
```

#### 改进 5: 新增"命令注册表冲突"快速判断

**现状**: 只有 import 冲突的快速判断。
**建议**: 增加 CLI/命令型项目的特有冲突模式：
```
命令注册表冲突决策：
1. 两侧各加了新命令 → 两者都保留 + 字母排序 + help body 同步
2. 上游改了命令属性（如 bypass_tier）→ 接受上游 + 删除旧重复
3. 新命令名含连字符（如 /auto-update）→ 确认 help body 解析正则支持连字符
```
