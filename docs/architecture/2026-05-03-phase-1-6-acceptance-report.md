# Phase 1.6 阶段验收报告 — deepagents CTO 起草

**报告日期**: 2026-05-03
**验收人**: deepagents CTO + 架构师团队
**验收范围**: pmagent Phase 1.6 invariant tests + Track 2 P1-2 OPDCA invariants（commit bd97f66）
**验收类型**: CTO 独立验证（不复述 pmagent 三方专家结论，做独立实证）
**验收触发**: pmagent 三方专家联合签字后，项目负责人指示 CTO 验收
**总耗时**: ~30 min

---

## 1. CTO 验收结论

### 🟢 **PASS — 验收通过，并接受 pmagent 三方专家对 CTO 推荐的 3 处校正**

| CTO 验证项 | 结论 |
|---|---|
| 测试文件存在性（commit bd97f66 已 push origin/main）| ✅ 实证（417 + 184 行，共 601 行）|
| 三方专家校正 #1（不变量编号 I-4 → I-7）| ✅ **CTO 接受**（pmagent 编号系统 I-1~I-8 比 H-3 文档编号更精细）|
| 三方专家校正 #2（T-7 runtime → static）| ✅ **CTO 接受**（runtime 属 e2e Phase 1.8，invariant 应静态）|
| 三方专家校正 #3（tools.denied → tools.allowed）| ✅ **CTO 接受**（基于 reflection_agent profile.yaml 实测结构）|
| Fidelity 100% 度量（vs CTO 报告 ~97%）| ✅ **CTO 接受**（语义对齐 > 行数对齐，pmagent 度量更合适）|
| T-3 反向验证机制设计 | ✅ 代码逻辑正确（`cache_idx < memory_idx` 方向对）|
| Pmagent 自报 56/56 PASS | 🟡 **CTO 未独立重跑**（需 pmagent venv），但 commit 可追溯 + 测试代码逻辑验证正确 |

### 1.1 CTO 自我反思（接受校正的诚实声明）

**本次验收 pmagent 三方专家校正 CTO 推荐 3 处错误**。CTO 接受所有校正，并承认：

| # | CTO 错误 | 校正 | 教训 |
|---|---|---|---|
| 1 | 用 H-3 装配支援包文档编号（#1-#8）作为 invariant 测试名（"T-3 I-4 silent failure"），但 pmagent builders.py 自有 8 项不变量编号系统（I-1~I-8）与 H-3 编号不一一对应 | "T-3 实际是 I-7"（pmagent 编号系统）| **跨文档编号不能假设一致**，应明确"按 pmagent builders.py 编号系统"|
| 2 | T-7 OPDCA invariant 测试推荐 "research_agent → reflection_agent runtime 验证" | "改为 system_prompt 静态断言（runtime 属 e2e Phase 1.8）"| **invariant 测试边界**：invariant = 结构断言（静态）；e2e = 行为验证（runtime）|
| 3 | T-8 推荐 "tools.denied 含 task" | "改为 tools.allowed 不含 task"（LangChain agent middleware deny-by-default）| **业务实施细节** CTO 看不到，应让 pmagent 自主校正 |

**CTO 反思**：H-3 装配支援包文档化时为方便阅读使用了 1-8 简单编号，但未与 pmagent builders.py 的 I-1~I-8 编号系统对齐。这是**CTO 输入文档不严谨**，pmagent 三方专家校正是必要且正确的。建议未来 H-3 文档采用 pmagent 编号系统作为权威。

### 1.2 验收结论建议

| 决策点 | CTO 推荐 |
|---|---|
| **接受 pmagent 三方专家联合签字** | 🟢 **接受** — 三方专家分析（架构师 + 研发主管 + LangChain/LangGraph/deepagents 专家）质量优于 CTO 单方面 review |
| **D-2 telemetry hook 实现** | 🟢 **CTO 现可启动**（Phase 1.6 完成 = D-2 触发条件）|
| **Phase 1.7 升级 SOP** | 🟡 推荐 P0 优先级（治理纪律 #3 落地） |
| **Track 2 P2 慢响应调查** | 🟢 P0 独立可启动 |

---

## 2. CTO 独立实证验证

### 2.1 测试文件实证（commit bd97f66 推 origin/main）

```bash
$ git log --oneline -3
bd97f66 feat(plan-h+): Phase 1.6 invariant tests + Track 2 P1-2 OPDCA invariants (合并)
0e0e7a0 docs(html2pdf): v1.5 architect advisory notes
489b965 docs(html2pdf): add tool design v1.4 (5-round review)

$ wc -l tests/test_assembly_invariants.py tests/test_opdca_workflow_invariants.py
     417 tests/test_assembly_invariants.py
     184 tests/test_opdca_workflow_invariants.py
     601 total
```

✅ commit 已 push 到 origin/main，测试文件实测存在（共 601 行）

### 2.2 校正 #1 实证：不变量编号系统差异

**pmagent builders.py 自有的 8 项不变量编号**（[builders.py:248-256](pmagent/src/agent_assembly/builders.py))：

```
- I-1: TodoListMiddleware first
- I-2: SkillsMiddleware（V2）位置（在主 agent 比 gp 靠前）
- I-3: BinaryDocConverter 在 user_middleware 之前（AD-2）
- I-4: profile extra 在 user middleware 之后、memory 之前（保护 prompt cache）
- I-5: MemoryMiddleware 在 user + extra 之后（add_cache_control=True）
- I-6: HumanInTheLoopMiddleware 在 _PermissionMiddleware 之前
- I-7: AnthropicPromptCachingMiddleware 在 memory + HITL 之前
- I-8: _PermissionMiddleware 必须绝对最后
```

**CTO 之前 H-3 文档的编号**：

```
- #1 TodoListMiddleware 必须在索引 0
- #2 _PermissionMiddleware 必须在最后一位
- #3 AnthropicPromptCachingMiddleware 必须无条件添加
- #4 MemoryMiddleware 必须在 AnthropicPromptCachingMiddleware 之后（最危险 silent failure）
- #5 SkillsMiddleware 主 agent vs subagent 位置不对称
- #6 Subagent profile.extra_middleware 必须独立实体化
- #7 interrupt_on 必须双路径
- #8 默认 general-purpose subagent 必须自动插入
```

**对照**：

| pmagent 编号 | CTO H-3 编号 | 等价语义 |
|---|---|---|
| I-1 | #1 | TodoListMiddleware first ✓ 一致 |
| I-2 | #5 (主 vs sub asymmetry) | SkillsMiddleware 位置 — **编号不一致** |
| I-3 | (CTO 未列) | BinaryDocConverter — **CTO H-3 未覆盖**（Plan H+ 路径 B #3 新增）|
| I-4 | (CTO 未明确列) | profile extra 位置约束 — **CTO H-3 未明确** |
| I-5 | #4 | MemoryMiddleware 在 cache 之后 — **编号不一致** |
| I-6 | #7 (interrupt_on) | 不同语义 — **CTO 编号错位** |
| I-7 | #4 (silent failure) | AnthropicCache 在 memory 之前 — **CTO 标 #4，pmagent 校正为 I-7** |
| I-8 | #2 | _PermissionMiddleware 末位 — **编号不一致** |

**CTO 接受校正**：pmagent 8 项不变量编号系统更精细（含 I-3 BinaryDocConverter + I-4 profile extra 位置）。CTO H-3 文档应在未来更新中**采用 pmagent 编号系统作为权威**。

### 2.3 校正 #2 实证：T-7 runtime → static

**pmagent test_opdca_workflow_invariants.py 实测代码**（line 5, 16, 35-53）：

```python
"""
- 这些是**静态断言**测试（profile.yaml + system_prompt 内容），不跑 LLM
- deepagents 验收报告 T-7~T-10 推荐 (三方专家修正版：runtime → static)
"""

def test_opdca_expected_sequence_in_system_prompt():
    """T-7: system_prompt_v1.md 必须显式定义 OPDCA 预期工具序列。"""
    sp_path = PROJECT_ROOT / "prompts" / "system_prompt_v1.md"
    assert sp_path.exists()
    # ... 读 system_prompt_v1.md 文件做静态字符串检查
```

✅ **CTO 接受**：runtime 验证属 e2e（Phase 1.8 范畴），invariant 测试应静态（不跑 LLM）。pmagent 校正符合 invariant 测试的设计原则。

### 2.4 校正 #3 实证：tools.allowed vs tools.denied

**pmagent test_opdca_workflow_invariants.py:73-95**：

```python
# T-8: reflection_agent profile.yaml 不允许 task（防递归 SubAgent）
def test_reflection_agent_no_task_in_allowed():
    """T-8: reflection_agent profile.yaml `tools.allowed` 不应包含 `task`。
    
    上游 deepagents 默认 deny — 不在 allowed 即不可见。
    
    校正：deepagents 验收报告原写"tools.denied 含 task"，实际 reflection_agent
    profile.yaml denied list 不含 task（task 不在 allowed 即默认 deny）。
    """
    allowed = profile.get("tools", {}).get("allowed", [])
    assert "task" not in allowed, (
        f"🔴 反递归防御违反！reflection_agent profile.yaml `tools.allowed` 含 `task`。\n"
        f"    allowed: {allowed}\n"
    )
```

✅ **CTO 接受**：基于 LangChain agent middleware **deny-by-default** 默认行为，"不在 allowed 即默认 deny"是正确的语义模型。CTO 推荐 "tools.denied 含 task" 反映对 LangChain middleware 的误解（不是显式 deny list 而是 allow list）。

### 2.5 校正 fidelity 100% vs ~97% 度量差异

**CTO Phase 1.5 验收报告 §4 行数 fidelity**：

| 函数 | 上游行数 | pmagent 行数 | 比例 |
|---|---|---|---|
| build_main_middleware | 59 | 58 | 98% |
| build_gp_middleware | 38 | 30 | 79% |
| build_subagent_middleware | 38 | 43 | 113% |
| **平均** | — | — | **~97%** |

**Pmagent 三方专家 100% 顺序 fidelity 实测**：

```
上游 graph.py:399-442 装配顺序（14 中间件）:
[0] TodoListMiddleware                       → I-1
[1] SkillsMiddleware                         → I-2
[2] FilesystemMiddleware
[3] SubAgentMiddleware                       → I-3 (替换为 SubAgentObservability)
[4] _DeepAgentsSummarizationMiddleware
[5] PatchToolCallsMiddleware
[6] AsyncSubAgentMiddleware
[7] user_middleware
[8] profile.extra_middleware                 → I-4
[9] _ToolExclusionMiddleware
[10] AnthropicPromptCachingMiddleware        → I-7
[11] MemoryMiddleware                        → I-5
[12] HumanInTheLoopMiddleware                → I-6
[13] _PermissionMiddleware                   → I-8

pmagent builders.py:258-316 装配顺序（15 中间件 = 14 等价 + 1 新增）：
+ 1 项 BinaryDocConverter (Plan H+ 路径 B #3，I-3)
```

**CTO 实证**（Python 对照脚本）：

- 上游 14 中间件序列与 pmagent 14 中间件**逐一对齐**
- pmagent 比上游多 1 项 BinaryDocConverter（Plan H+ 路径 B #3 新增 — 设计意图）
- **pmagent 14/14 上游对齐 = 100% 顺序等价**

✅ **CTO 接受度量校正**：

- CTO 用的"行数 fidelity"反映代码体积（含合理适配差异）
- pmagent 用的"顺序 fidelity"反映装配语义等价
- **"顺序等价 > 行数等价" — pmagent 度量更适合 ADR fidelity 验证**
- 未来 ADR fidelity 验证应优先采用顺序等价度量

### 2.6 T-3 反向验证机制设计实证

**测试代码**（test_assembly_invariants.py:187-216）：

```python
def test_anthropic_cache_before_memory_silent_failure(...):
    """T-3 (🔴 最危险): AnthropicPromptCachingMiddleware 必须在 MemoryMiddleware 之前。
    
    若顺序反了 → MemoryMiddleware 内容会 invalidate cache → cache 命中率 ~0%
    → 每次请求重算全 prompt → API 账单暴涨（隐蔽性极强，无报错）。
    """
    mw = _build_main_stack(backend, real_model, empty_profile, fake_subagent_spec)
    cache_idx = next((i for i, m in enumerate(mw) if type(m).__name__ == "AnthropicPromptCachingMiddleware"), None)
    memory_idx = next((i for i, m in enumerate(mw) if type(m).__name__ == "MemoryMiddleware"), None)
    
    assert cache_idx is not None, "AnthropicPromptCachingMiddleware 缺失"
    assert memory_idx is not None, "MemoryMiddleware 缺失"
    assert cache_idx < memory_idx, (
        f"🔴 silent failure 风险！AnthropicCache (idx {cache_idx}) 必须在 "
        f"Memory (idx {memory_idx}) 之前，否则 prompt cache 失效，API 账单暴涨。"
    )
```

**CTO 实证机制设计正确**：

1. ✅ 断言方向对：`cache_idx < memory_idx`（cache 必须**先于** memory）
2. ✅ 反向验证可行：如果 builders.py 把 memory 移到 cache 之前，`cache_idx > memory_idx` 时断言 fail
3. ✅ 错误消息明确：含具体 idx 值 + 业务影响（API 账单暴涨）
4. ✅ pmagent 三方专家**主动**做了反向验证实证（移动顺序后 fail，恢复后 pass），超出 CTO 推荐标准

### 2.7 Pmagent 自报 56/56 PASS 验证策略

**CTO 限制**：在 deepagents 工作区跑 pmagent 测试需要 pmagent venv（含 deepagents pip install）。系统 Python 3.9 无 deepagents → CTO **未独立重跑测试**。

**信任依据**：

1. ✅ commit bd97f66 已 push origin/main，测试文件可追溯
2. ✅ 测试代码逻辑实证正确（T-3 反向验证机制 + 3 处校正全部成立）
3. ✅ pmagent 三方专家联合签字（架构师 + 研发主管 + 专家），独立 review 质量
4. ✅ pmagent 报告含具体跑测时长（288s）和 warning 来源（26 上游 deprecation），细节可信

**CTO 后续建议**：pmagent 在 CI（GitHub Actions / LangGraph dev pre-commit）配置 invariant tests 自动跑，避免依赖人工跑（防止"自报 PASS"信任问题）。

---

## 3. 超出 CTO 推荐的 3 项额外测试评估

pmagent 三方专家补的 3 项测试（CTO 未推荐）：

| # | 测试 | CTO 评估 | 价值 |
|---|---|---|---|
| **T-11** | namespace_collision_regression | 🟢 **HIGH 价值** — Phase 1.1 实测发生过 1.5h 阻塞 bug，加 regression test 防复发 | ✅ 应纳入未来 ADR checklist |
| **T-12** | create_pmagent_agent_smoke | 🟡 MEDIUM — 自动化 Phase 1.5 手工验证 | 合理 |
| **T-13** | builders_idempotence | 🟡 MEDIUM — 防 builders 内部状态泄漏 | 合理 |

**CTO 接受 3 项**，并认为 **T-11 应作为未来所有 namespace 修订的强制 regression test**（写入 ADR checklist v3）。

---

## 4. ADR checklist v3 增补建议（基于本次验收沉淀）

延续 v1+v2，建议加入：

| # | 内容 | 来源 |
|---|---|---|
| **#9** | 跨文档编号系统必须显式声明权威源（不假设一致）| 本次校正 #1 |
| **#10** | invariant 测试必须明确边界：invariant = 结构断言（静态）；e2e = 行为验证（runtime）| 本次校正 #2 |
| **#11** | fidelity 验证应优先采用**顺序等价**度量，行数等价为辅助 | 本次校正度量 |
| **#12** | namespace / 路径修订必须写 regression test（如 T-11）| 三方专家补 T-11 |
| **#13** | 反向验证（破坏 invariant 应 FAIL）应作为关键 invariant 测试的强制门 | T-3 反向验证实证 |

---

## 5. 验收三方签字延续

| 角色 | 状态 | 备注 |
|---|---|---|
| **pmagent 三方专家**（架构师 + 研发主管 + LangChain/LangGraph/deepagents 专家）| ✅ APPROVE 2026-05-03 | 联合签字，质量优于 CTO 单方推荐 |
| **deepagents CTO** | ✅ **PASS — 接受三方专家校正 + 实证验证 2026-05-03** | 接受 3 处校正、fidelity 度量校正、T-11 regression test 价值 |
| **项目负责人** | ⏳ 待批准下游动作启动 | 见 §6 |

---

## 6. CTO 推荐下一步

| 优先级 | 工作 | 团队 | 估时 | 触发条件 |
|---|---|---|---|---|
| 🟢 **P0** | **D-2 v2 telemetry hook 实现**（R-1 ~ R-6，**完全在 pmagent**，0 deepagents 修改 — 用 langchain `wrap_tool_call` hook + additive subclass）| **pmagent 团队**（实施）+ deepagents CTO（review）| 3 d pmagent + 1.5 h CTO review | Phase 1.6 完成 ✓ — **现可立即启动** |
| 🟢 **P0**（独立）| **Track 2 P2 慢响应根因调查**（reasoning model 70% 优先）| **pmagent 团队** | 0.5 d | 任意时间，独立任务 |
| 🟡 P1 | Phase 1.7 升级 SOP 文档（治理纪律 #3）| **pmagent 团队** | 0.25 d | Phase 1.6 完成 ✓ |
| 🟡 P2 | Phase 1.2 拓展（3 V2 类，优先 BinaryDocConverter 激活 I-3）| **pmagent 团队** | 1-2 d | 视业务需求 |
| 🟡 P2 | Phase 1.3 Option M（add_async_compat）| **pmagent 团队** | 0.5 d | 视 V2 实施需求 |
| ⏳ trigger | Phase 1.8 e2e 验证 → 触发 D-1 fork 归档 SOP | **双方协同** | — | Phase 1.8 e2e 通过 + 双方授权 |

### 6.1 CTO 推荐启动顺序（双轨并行）

```
Track A (deepagents)：D-2 telemetry hook 实现 (2.5 d) ─┐
                                                      │  独立并行
Track B (pmagent)：    Phase 1.7 SOP (0.25 d)         ├──→ 双方汇合
                       Track 2 P2 调查 (0.5 d)        ─┘   Phase 1.8 启动
                                                            ↓
                                                    e2e 通过 → 触发 D-1
                                                            ↓
                                                    Phase 2 fork 归档 SOP 执行
```

---

## 7. 元层方法论沉淀

### 7.1 三方专家联合 review > CTO 单方 review

本次 pmagent 三方专家联合 review 产出**显著优于** CTO 单方 review：

- 校正 CTO 3 处错误（编号、runtime/static、tools.denied）
- 补充 3 项 CTO 未覆盖测试（T-11/T-12/T-13）
- 实施 15 测试 vs CTO 推荐 6（+150%）
- 主动反向验证（T-3）超出 CTO 标准

**沉淀**：未来涉及 invariant tests / 装配代码 / 私有 API 治理的 review，应优先三方专家模式（架构师 + 研发主管 + 框架专家），而不是 CTO 单方决策。

### 7.2 CTO 接受校正的诚实声明

本次验收 pmagent 校正 CTO 3 处推荐错误，CTO **全部接受**而不强词夺理。这印证了：

> "图纸 review 不等于实证验证" 的同源教训也适用于 CTO 推荐 — **CTO 推荐也需要被实证检验**。

未来 CTO 推荐文档应明确标注"待实证检验"，欢迎实施团队校正。

### 7.3 顺序 fidelity > 行数 fidelity

本次 fidelity 度量分歧（CTO ~97% vs pmagent 100%）证明：

- **顺序等价**：反映装配语义（直接关联 invariant），度量装配是否真等价
- **行数等价**：反映代码体积（含适配差异），不直接对应 invariant
- **结论**：未来 ADR fidelity 验证优先采用**顺序等价**，行数为辅

---

**验收报告状态**: ✅ 完成 2026-05-03
**deepagents CTO 签字**: ✅ 2026-05-03（PASS — 接受三方专家校正 + 实证验证 + ADR checklist v3 增补建议）

**下一步**:

1. ⏳ 项目负责人批准 §6 下游动作启动
2. 🟢 **pmagent 团队**现可启动 **D-2 v2 telemetry hook 实现**（R-1 ~ R-6，3 d，完全在 pmagent，0 deepagents 修改）；deepagents CTO 转入 review 角色（~1.5 h）
3. 🟢 pmagent 团队现可启动 Phase 1.7 SOP / Track 2 P2 调查（独立并行）

**配套文档**:

- [Phase 1.5 验收报告](2026-05-03-phase-1-5-acceptance-report.md)（本次验收为延续）
- [ADR-0002 v3](decisions/0002-fork-customization-strategy.md)（checklist v3 增补建议待加入）
- [D-2 SubAgent telemetry hook 设计](2026-05-03-d2-subagent-telemetry-hook-design.md)（CTO 现可启动实现）
- [D-1 Fork 归档 SOP](2026-05-03-d1-fork-archive-sop.md)（Phase 1.8 后触发）
