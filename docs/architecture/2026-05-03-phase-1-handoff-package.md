# Phase 1 装配支援包 — deepagents 团队 → pmagent 团队

**起草日期**: 2026-05-03
**起草人**: deepagents CTO + 架构师团队
**目标**: 为 pmagent 团队 Phase 1.0-1.3（仓库准备 + 装配实施 + invariant 测试）提供精确输入，消除 pmagent 从 deepagents 仓库摸索关键信息的盲区
**版本基准**: deepagents master @ 2026-05-03（SDK v0.5.0）+ ADR-0002 v2 ACCEPTED
**对应 pmagent Phase**: 1.0（仓库准备 + invariants.py 起草）+ 1.1（装配代码拷贝）+ 1.2（V2 增强类）+ 1.3（invariant 测试）

**包含内容**：

- **H-1**: 私有 API import 清单（pmagent 装配将依赖的 deepagents 私有 API + 稳定性承诺）
- **H-2**: 5 V2 增强类接口冻结声明（pmagent 拷贝/继承时的接口契约）
- **H-3**: 8 项装配不变量精确化（可执行的测试断言基础）

---

## H-1. 私有 API import 清单

pmagent 装配代码将从 deepagents 直接 import 以下私有 API（带下划线前缀）。本清单是 pmagent `invariants.py` 的直接输入。

### H-1.1 必须 import 的私有 API（11 项）

| # | API | 来源模块 | 用途 | 稳定性承诺 |
|---|---|---|---|---|
| 1 | `_HarnessProfile` | [`deepagents.profiles`](libs/deepagents/deepagents/profiles/__init__.py) | Profile dataclass 定义（init_kwargs / extra_middleware / excluded_tools 等 7 字段）| 🟢 **冻结至 0.6.x**（dataclass 字段 add-only，不删除/重命名）|
| 2 | `_get_harness_profile` | [`deepagents.profiles`](libs/deepagents/deepagents/profiles/__init__.py) | 按 model spec 查找 profile（exact → provider prefix → empty）| 🟢 **冻结至 0.6.x**（签名 `(spec: str) -> _HarnessProfile`）|
| 3 | `_register_harness_profile` | `deepagents.profiles._harness_profiles` | 注册新 profile（pmagent 不需要直接调用，但若添加自定义 provider 时需要）| 🟢 冻结 |
| 4 | `_EXCLUDED_STATE_KEYS` | [`deepagents.middleware.subagents`](libs/deepagents/deepagents/middleware/subagents.py#L310-L320) | SubAgent 状态隔离 key 集合（含 9 个 key）| 🟡 **可能添加新 key（add-only）**，pmagent 应通过 `set.update()` 扩展，不要替换 |
| 5 | `_PermissionMiddleware` | [`deepagents.middleware.permissions`](libs/deepagents/deepagents/middleware/permissions.py#L188) | 文件权限末位 middleware | 🟢 冻结（必须放装配末位）|
| 6 | `_ToolExclusionMiddleware` | [`deepagents.middleware._tool_exclusion`](libs/deepagents/deepagents/middleware/_tool_exclusion.py#L31) | 上游不兼容工具剥离 middleware | 🟢 冻结 |
| 7 | `_resolve_extra_middleware` | `deepagents.graph` | 从 profile 实体化 extra_middleware 序列 | 🟡 **建议复制实现**（仅 ~10 行，pmagent 可独立维护）|
| 8 | `_build_main_agent_middleware` | `deepagents.graph` | 主 agent middleware stack 装配（~60 行）| 🔴 **不直接 import，pmagent 拷贝改写**（这是装配主权所在）|
| 9 | `_build_subagent_middleware_stack` | `deepagents.graph` | Subagent middleware stack 装配（~30 行）| 🔴 **不直接 import，pmagent 拷贝改写** |
| 10 | `_build_final_system_prompt` | `deepagents.graph` | profile prompt 合成 | 🟡 建议复制实现 |
| 11 | `BASE_AGENT_PROMPT` | `deepagents.graph` 或 `deepagents.prompts` | 基础 system prompt 字符串 | 🟢 冻结至 0.6.x |

### H-1.2 import 推荐写法（pmagent `harness/__init__.py`）

```python
# Public API (no underscore)
from deepagents import (
    AsyncSubAgent, AsyncSubAgentMiddleware,
    CompiledSubAgent, SubAgent, SubAgentMiddleware,
    FilesystemMiddleware, FilesystemPermission,
    MemoryMiddleware,
)
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.summarization import create_summarization_middleware
from deepagents.middleware.subagents import _EXCLUDED_STATE_KEYS  # private, see invariants
from deepagents.middleware.permissions import _PermissionMiddleware  # private
from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware  # private
from deepagents.profiles import _HarnessProfile, _get_harness_profile  # private
```

### H-1.3 私有 API 弃用 SOP（4 治理纪律之 #2 落地）

| 行为 | pmagent 团队动作 |
|---|---|
| 上游 minor 升级（0.5.x → 0.6.0）| 运行 invariant 测试 → 检查弃用警告 → 更新 import 路径如有变更 |
| 上游 major 升级（0.6 → 1.0）| 1-2 d 集中升级 SOP，可能需要重写部分私有 API 用法 |
| 私有 API 突然消失 | invariant 测试会立即失败 → pmagent 复制本地实现作为 fallback（参考 #7、#10）|

---

## H-2. 5 V2 增强类接口冻结声明

pmagent 拷贝/继承的 5 V2 增强类接口签名 + 稳定性承诺。这些是 deepagents fork master 的本地优越特性。

### H-2.1 SkillsMiddlewareV2

**导入路径**：`from deepagents.middleware.skills import SkillsMiddleware`

**接口签名**（已冻结）：

```python
class SkillsMiddleware(AgentMiddleware):
    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,                       # 必须
        sources: Sequence[SkillSource],               # 必须；str 或 (path, label) tuple
        max_loaded_skills: int = 10,                  # V2: context budget
        expose_dynamic_tools: bool = False,           # V2: load_skill/unload_skill 工具
        allowed_skills: list[str] | None = None,      # V2: per-subagent 过滤
    ) -> None: ...
```

**State fields**（必须在 `_EXCLUDED_STATE_KEYS` 中）：
- `skills_metadata`、`skills_loaded`、`skill_resources`

**pmagent 使用方式**：直接使用本类，无需子类化。

**稳定性**：🟢 接口冻结至 0.6.x（add-only fields）

---

### H-2.2 SubAgentObservability（_ENABLE_SUBAGENT_LOGGING）

**导入路径**：`from deepagents.middleware.subagents import SubAgentMiddleware`（环境变量驱动）

**激活方式**：

```bash
export _ENABLE_SUBAGENT_LOGGING=1
```

**State fields**（必须在 `_EXCLUDED_STATE_KEYS` 中）：
- `subagent_logs`

**pmagent 使用方式**：环境变量级别开关，无需子类化。

**稳定性**：🟡 环境变量名稳定，但 log schema（`_extract_subagent_logs` 输出）可能小幅调整 → pmagent 不应依赖 schema 内部结构

---

### H-2.3 SummarizationOverwriteGuard

**导入路径**：`from deepagents.middleware.summarization import create_summarization_middleware`

**保护机制**：内置在 `_DeepAgentsSummarizationMiddleware`，处理 `Overwrite` 类型 messages 的 `isinstance(messages, Overwrite)` guard

**State fields**（必须在 `_EXCLUDED_STATE_KEYS` 中）：
- `_summarization_event`

**pmagent 使用方式**：通过 `create_summarization_middleware(model, backend)` 工厂函数，自动启用 guard。

**稳定性**：🟢 工厂签名冻结；guard 行为冻结

---

### H-2.4 BinaryDocConverterMiddleware（converters）

**导入路径**：`deepagents.middleware.converters` 包

**包结构**：

```
deepagents/middleware/converters/
├── base.py              # ConverterProtocol、ConverterRegistry
├── pdf.py               # PDFConverter (pdfplumber)
├── docx.py              # DOCXConverter (python-docx)
├── pptx.py              # PPTXConverter (python-pptx)
├── xlsx.py              # XLSXConverter (openpyxl)
├── csv.py、text.py、image.py
└── registry.py          # 全局注册表
```

**pmagent 使用方式**：自动通过 `FilesystemMiddleware.read_file()` 触发，无需直接调用。需安装 `pip install deepagents[converters]`。

**稳定性**：🟢 ConverterProtocol 冻结；新增格式 add-only

---

### H-2.5 add_async_compat（Memory isawaitable）

**导入路径**：`from deepagents.middleware.memory import MemoryMiddleware`

**机制**：[memory.py:318](libs/deepagents/deepagents/middleware/memory.py#L318) `inspect.isawaitable(maybe_awaitable)` 实现 async/sync 双兼容

**pmagent 使用方式**：直接使用 `MemoryMiddleware`，自动处理 sync/async backends。

**State fields**（必须在 `_EXCLUDED_STATE_KEYS` 中）：
- `memory_contents`

**稳定性**：🟢 行为冻结

---

## H-3. 8 项装配不变量精确化（可执行测试断言基础）

ADR-0002 §6 列出的 8 项装配不变量，本节升级为可执行的测试断言。pmagent `tests/test_assembly_invariants.py` 可直接基于本节断言编写。

### H-3.1 主 agent middleware 期望顺序（基于 [graph.py:384-443](libs/deepagents/deepagents/graph.py#L384-L443)）

```
索引   Middleware                                       条件
─────  ─────────────────────────────────────────────  ────────────────────
[0]    TodoListMiddleware                              无条件（不变量 #1）
[1]    SkillsMiddleware                                if skills is not None and not in user middleware
[2-3]  FilesystemMiddleware                            无条件
       SubAgentMiddleware                              无条件
[+1]   _DeepAgentsSummarizationMiddleware              无条件（create_summarization_middleware）
[+1]   PatchToolCallsMiddleware                        无条件
[+1]   AsyncSubAgentMiddleware                         if async_subagents
[+N]   user middleware（来自调用方）                    extends
[+M]   profile.extra_middleware                        if profile.extra_middleware
[+1]   _ToolExclusionMiddleware                        if profile.excluded_tools
[+1]   AnthropicPromptCachingMiddleware                无条件（不变量 #3）
[+1]   MemoryMiddleware                                if memory is not None（不变量 #4：必须在 AnthropicCache 之后）
[+1]   HumanInTheLoopMiddleware                        if interrupt_on is not None
[-1]   _PermissionMiddleware                           if permissions（不变量 #2：末位）
```

### H-3.2 8 项不变量精确化测试断言

| # | 不变量 | 测试断言（伪代码）| 失败后果 |
|---|---|---|---|
| **1** | `TodoListMiddleware` 必须在索引 0 | `assert isinstance(stack[0], TodoListMiddleware)` | todos 状态被错误初始化 |
| **2** | `_PermissionMiddleware` 必须在最后一位（末位） | `if has_permissions: assert isinstance(stack[-1], _PermissionMiddleware)` | 权限检查被绕过（**安全漏洞**）|
| **3** | `AnthropicPromptCachingMiddleware` 必须无条件添加 | `assert any(isinstance(m, AnthropicPromptCachingMiddleware) for m in stack)` | prompt cache 失效（**性能损失**）|
| **4** | `MemoryMiddleware` 必须在 `AnthropicPromptCachingMiddleware` 之后 | `cache_idx = idx_of(AnthropicPromptCachingMiddleware); mem_idx = idx_of(MemoryMiddleware); assert mem_idx > cache_idx` | cache prefix 失效（**最危险的 silent failure**：性能下降无报错）|
| **5** | `SkillsMiddleware` 主 agent 在 `[1]`（FilesystemMiddleware 之前）；subagent stack 在 `extend(user_middleware)` 之后 | 主：`assert idx_of(Skills) < idx_of(Filesystem)`；subagent：`assert idx_of(Skills) > idx_of(user_mw[-1])` | skills 元数据未注入 system prompt |
| **6** | Subagent profile.extra_middleware 必须独立实体化（不与主 agent 共享实例）| `main_extra = _resolve_extra_middleware(profile); sub_extra = _resolve_extra_middleware(profile); assert main_extra[i] is not sub_extra[i]` | profile factory pattern 失效，状态泄漏 |
| **7** | `interrupt_on` 必须双路径（主 agent + 每个 SubAgent spec 默认继承）| 主：`if interrupt_on: assert HumanInTheLoopMiddleware in main_stack`；subagent：每个 SubAgent spec 默认继承 parent `interrupt_on`，除非显式 `interrupt_on={}` | HITL 配置在 subagent 失效（绕过审批）|
| **8** | 默认 general-purpose subagent 必须自动插入 | `assert "general-purpose" in subagent_graphs` 或 `general_purpose_agent=True` 时存在 | task tool 在无 subagents 时不可用 |

### H-3.2.5 反向测试要求（H3-A1 修订，2026-05-04）

**应用 ADR v5 #22 + #23**：每项不变量测试**必须配反向验证**，仅单向 assertion 是 #22 反例（"用单一条件下的多次重复代替对照"）。

**反向测试设计**：

```text
对每项不变量 T-N（如 T-1 主 stack 顺序）：

正向断言（implementation 符合 invariant 时 PASS）:
  装配代码符合规范 → 测试通过
  ✅ 验证"实施符合 spec"

反向验证（破坏 invariant 时 FAIL）:
  临时修改装配代码（如把 MemoryMiddleware 移到 AnthropicCache 之前）
  → 测试**应该 FAIL**（含明确 error message + idx 数字）
  → 验证"测试真能 catch 违反"，不是 false-pass
  → 恢复代码后测试重新 PASS
  ✅ 验证"测试设计有效"

如不做反向验证：
  风险：测试可能写成"恒为 True"的 false-pass（assert True 类）
  实证反例：pmagent T-1~T-13 中仅 T-3 做反向验证（v1.6 audit MEDIUM #2）
```

**Verification 章节**（应用 ADR v5 #23）：

| 客观判定标准 | 验证方法 | 失败可观察信号 | 责任 |
|---|---|---|---|
| 每项 T-N 配反向验证 | 跑反向测试看是否 FAIL | 反向时测试仍 PASS = false-pass | pmagent 实施 |
| 反向 error message 含具体 idx | 读 assertion message | 仅 "AssertionError" 无具体信号 | pmagent 测试编写 |
| 恢复代码后测试 PASS | 重跑测试套件 | 测试无法恢复 = 测试有副作用 | pmagent 验证 |

**实证模板**（参考 pmagent T-3 反向验证）：

```python
def test_anthropic_cache_before_memory_silent_failure(...):
    """T-3 反向验证示例 — 复制此模式到其他 T-N。"""
    mw = _build_main_stack(...)
    cache_idx = next((i for i, m in enumerate(mw) if type(m).__name__ == "AnthropicPromptCachingMiddleware"), None)
    memory_idx = next((i for i, m in enumerate(mw) if type(m).__name__ == "MemoryMiddleware"), None)
    assert cache_idx < memory_idx, (
        f"🔴 silent failure 风险！AnthropicCache (idx {cache_idx}) 必须在 "
        f"Memory (idx {memory_idx}) 之前，否则 prompt cache 失效，API 账单暴涨。"
    )
    # 反向验证步骤（手工或 fixture）:
    # 1. 临时修改 builders.py 把 MemoryMiddleware 移到 AnthropicCache 之前
    # 2. 重跑此测试，应 FAIL
    # 3. 恢复 builders.py，测试重新 PASS
```

**沉淀根因**：CTO H3-A1 finding（2026-05-04）+ pmagent v1.6 audit MEDIUM #2 catch — 仅 T-3 做反向，其他 12 项可能 false-pass 风险。

### H-3.3 关键参考代码位置（pmagent 拷贝时对照）

| 任务 | deepagents 源 | 行数 |
|---|---|---|
| 主 agent middleware 装配 | [graph.py:384-443](libs/deepagents/deepagents/graph.py#L384-L443) | ~60 行 |
| Subagent middleware 装配 | [graph.py:218-256](libs/deepagents/deepagents/graph.py#L218-L256) | ~38 行 |
| `_resolve_extra_middleware` | `graph.py:116-127` | ~12 行 |
| `_build_final_system_prompt` | `graph.py:446-458` | ~13 行 |
| `_EXCLUDED_STATE_KEYS` 集合 | [subagents.py:310-320](libs/deepagents/deepagents/middleware/subagents.py#L310-L320) | 11 行 |
| `_HarnessProfile` 完整字段 | [profiles/_harness_profiles.py:28-110](libs/deepagents/deepagents/profiles/_harness_profiles.py#L28-L110) | 7 字段 |

**总拷贝量**：~150 行（与 ADR-0002 §10 step 2 reference template 估算的 280-380 行接近，差异在于 pmagent 是否复制 `_resolve_*` 辅助函数）

---

## 4. 升级触发的复检 SOP（4 治理纪律之 #3 落地）

当 deepagents 上游升级（`pip install -U deepagents`）后，pmagent 团队按以下 SOP 复检：

| 步骤 | 动作 | 验证 |
|---|---|---|
| 1 | 运行 invariant 测试套件 | 全部通过 → 装配仍兼容；任何失败 → 进入 step 2 |
| 2 | 对比 deepagents [graph.py](libs/deepagents/deepagents/graph.py) 主 agent middleware 装配代码 | 与 pmagent 本地拷贝 diff，识别变更 |
| 3 | 对比 `_HarnessProfile` 字段 | 新增字段 → pmagent 装配代码 add-only 同步；删除字段 → upstream issue 沟通 |
| 4 | 对比 `_EXCLUDED_STATE_KEYS` | 新增 key → pmagent SubAgentObservability 子类 `set.update()` 同步 |
| 5 | 运行 pmagent 集成测试 | 全部通过 → 升级完成；失败 → 回滚 + 升级 SOP 文档化新问题 |

---

## 5. 交付物清单

本支援包是 pmagent Phase 1 的**直接输入**：

| pmagent Phase | 本支援包章节 |
|---|---|
| 1.0 仓库准备 + `invariants.py` 起草 | **H-1** + **H-3.2** |
| 1.1 装配代码拷贝 | **H-1.2** + **H-3.3** |
| 1.2 V2 增强类移植 | **H-2** |
| 1.3 invariant 测试套件 | **H-3.1** + **H-3.2** |

---

## 6. 后续事项

- **配套文档**：M-1（SubAgent 终止最佳实践 + OPDCA-style workflow 预期行为）单独交付为 [`2026-05-03-subagent-termination-best-practices.md`](2026-05-03-subagent-termination-best-practices.md)
- **可选未来工作**：§5.2 P3 SubAgentMiddleware telemetry hook（pmagent 表态可推迟到 Phase 1 完成后）

---

**支援包状态**：✅ 起草完成 2026-05-03
**deepagents CTO 签字**：✅ 2026-05-03
**等待 pmagent 团队 review 与 acknowledge**
