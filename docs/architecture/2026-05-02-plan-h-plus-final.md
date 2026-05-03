# Plan H+ — Fork 定制策略最终设计（消除 fork + pmagent 全主权 + 私有 API 治理）

**日期**: 2026-05-02（v3 命名修订 2026-05-03）
**作者**: deepagents 项目技术总监 + 架构师团队 + pmagent 技术总监（联合）
**状态**: Plan H+ 推荐设计 v3（命名修订版），配套 ADR-0002 v3（ACCEPTED）
**前序方案**: v1 → v2 → v3 → v4-rev2 → Plan E++ → Plan H → **Plan H+**（8 次方向探索后收敛）
**目标读者**: pmagent 团队（实施方）、deepagents 上游观察者

**v2 → v3 namespace 修订（2026-05-03）**: 所有 `src/agent/` → `src/agent_assembly/`（9 处），原因是 Python import 系统不允许 module + package 同名共存（与现有 `src/agent.py` 业务入口冲突）。架构决策不变，仅命名修订。详见 ADR-0002 v3 changelog。

---

## 0. 摘要

### 0.1 Plan H+ 一句话定义

**消除 fork 仓库**，pmagent 通过 pip 直接依赖上游 deepagents，**自己拥有完整装配代码 + V2 增强类 + 私有 API 治理**。

### 0.2 核心架构对比

| 方案 | 仓库结构 | pmagent 主权 | Monkey-patch | 私有 API 暴露 |
| --- | --- | --- | --- | --- |
| v3 Plan D | upstream + fork（深度修改）+ pmagent | 业务层 | 无（直接修改）| 中 |
| v4-rev2 / Plan E++ | upstream + fork（含 enhanced + extras）+ pmagent（thin wrapper）| 业务层 | 🔴 enhanced 内 | 🟢 fork 吸收 |
| Plan H | upstream + fork（仅 extras）+ pmagent（装配）| harness 层 | 0 | 🟡 部分 fork buffer |
| **Plan H+（终局）**| **upstream + pmagent（装配 + V2 + 治理，全部）**| **完全主权** | **0** | **🟡 pmagent 治理** |

### 0.3 决策依据

1. **L8（harness 层能力建设）确认**：用户明确表示 6-12 月将构建异步优化、多 agent 并行、agent 团队协作、自我学习等 harness 能力 → 需要装配主权
2. **风险厌恶偏好**：用户明确"不喜欢风险" → upfront 投资换确定性
3. **Q4 关键洞察**："Plan H 是拷贝不是写新代码" → 真实成本被之前系统性高估
4. **fork 无独立组织价值**：fork 仓库实际是 pmagent 的延伸（james8814/deepagents 个人仓库，唯一 consumer），Plan H+ 把它正式回收

---

## 1. 仓库布局（Plan H+ 终局架构）

```text
（fork 不再存在！）

pmagent/                                        # 唯一项目仓库
├── pyproject.toml                              # deepagents ~= 0.5.0 (PEP 440 兼容范围：允许 0.5.x patch，禁止 0.6.x minor)
├── src/
│   ├── agent.py                                # 业务入口（调 create_pmagent_agent）
│   └── agent/                                   # 装配 + 增强 + 治理
│       ├── __init__.py
│       ├── assembly.py                         # create_pmagent_agent 主入口
│       ├── builders.py                          # _build_gp_middleware / _build_subagent_middleware / _build_main_middleware
│       ├── _private_api_imports.py             # 🔴 集中管理 + 文档化所有私有 API import
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── skills_v2.py                    # SkillsMiddlewareV2 子类
│       │   ├── subagent_observability.py       # SubAgentObservability 子类（含 _EXCLUDED_STATE_KEYS extension in __init__）
│       │   ├── summarization_overwrite_guard.py # augment + super 子类
│       │   └── binary_doc_converter.py         # 独立 post-processing middleware（awrap_tool_call 模式）
│       ├── backends/
│       │   ├── __init__.py
│       │   └── async_compat.py                  # add_async_compat() in-place 方法 patch
│       ├── patches.py                           # _EXCLUDED_STATE_KEYS mutate-in-place patch（如不在 SubAgentObservability.__init__ 内）
│       └── invariants.py                        # 装配 invariant 测试入口 + 8 个不变量文档
├── tools/
│   ├── check_private_api.py                    # 私有 API 兼容性检查工具
│   └── check_increments.py                      # V2 子类 vs 上游修改对比工具
├── docs/
│   ├── decision-records/
│   │   └── 0002-fork-customization-strategy-acceptance.md  # pmagent 接受 ADR-0002 的副本
│   └── operations/
│       └── deepagents-upgrade-sop.md           # 升级 deepagents 版本的 SOP
└── tests/
    ├── test_assembly_invariants.py              # invariant 测试套件
    ├── test_v2_middlewares.py                   # V2 子类测试
    ├── test_private_api_compatibility.py        # 私有 API 兼容性测试
    └── test_subagent_logs_contract.py           # 9 个 subagent_logs 契约测试

upstream deepagents (PyPI, ~=0.5.0)              # pmagent 直接依赖，无 fork 中间层
```

---

## 2. 装配代码核心设计

### 2.1 核心入口：`create_pmagent_agent`

> **Import path 说明（v2 RC-7 修订）**：以下示例 import 使用 `src.agent.xxx` 路径。
> 实际 import path 取决于 pmagent 包配置（`pyproject.toml` 的 `packages = [...]` 设置）。
> pmagent 团队按实际仓库布局调整。如 pmagent 改用 `pmagent/` 顶层 package 布局，import 改为 `pmagent.agent.xxx`。

```python
# pmagent/src/agent_assembly/assembly.py
"""pmagent 完整 agent 装配。

替代 deepagents.create_deep_agent，提供 pmagent 完整 harness 主权 +
路径 B 5 项 V2 增强 + Option M backend 兼容。

设计原则：
- 拷贝自上游 deepagents.graph.create_deep_agent（~80% 拷贝）
- V2 类替换（5 项增强）
- pmagent 业务适配（PMAgentState, multi-model, 6+ subagents, HIL, 双 backend）
- 0 monkey-patch
- 私有 API 集中管理（见 _private_api_imports.py）

**升级注意**：deepagents 升级前必须跑 tools/check_private_api.py 验证兼容性。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

# Public API imports from upstream
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.permissions import FilesystemPermission
from deepagents.middleware.subagents import (
    GENERAL_PURPOSE_SUBAGENT,
    CompiledSubAgent,
    SubAgent,
)
from deepagents.middleware.summarization import create_summarization_middleware
from deepagents.middleware.todo_list import TodoListMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.anthropic_prompt_caching import AnthropicPromptCachingMiddleware
from deepagents.middleware.human_in_the_loop import HumanInTheLoopMiddleware

# Private API imports — 集中在专用模块管理（治理纪律 2）
from src.agent._private_api_imports import (
    resolve_model,
    BASE_AGENT_PROMPT,
    _resolve_extra_middleware,
    _apply_tool_description_overrides,
    _HarnessProfile,
    _get_harness_profile,
    _ToolExclusionMiddleware,
    _PermissionMiddleware,
)

# pmagent V2 增强类（住 pmagent，不依赖 fork）
from src.agent.middleware.skills_v2 import SkillsMiddlewareV2
from src.agent.middleware.subagent_observability import SubAgentObservability
from src.agent.middleware.summarization_overwrite_guard import SummarizationOverwriteGuard
from src.agent.middleware.binary_doc_converter import BinaryDocConverterMiddleware
from src.agent.backends.async_compat import add_async_compat

# pmagent 业务（PMAgentState、multi-model 解析、harness profile 等）
from pmagent.src.state import PMAgentState
from pmagent.src.models import resolve_pmagent_model  # 多 model provider 路由
from pmagent.src.context import ContextMiddleware


def create_pmagent_agent(
    *,
    # 标准 deepagents 参数（透传给 langchain create_agent）
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict] | None = None,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | None = None,
    interrupt_on: dict[str, Any] | None = None,
    response_format: Any = None,
    context_schema: Any = None,
    checkpointer: Any = None,
    store: Any = None,
    debug: bool = False,
    name: str | None = None,
    cache: Any = None,
    # pmagent 增强参数
    skills_expose_dynamic_tools: bool = True,
    skills_allowlist: list[str] | None = None,
    pmagent_skills_backend: BackendProtocol | None = None,  # 双 backend 系统
    state_schema: type = PMAgentState,
    **kwargs: Any,
):
    """pmagent 完整 agent 装配（Plan H+ 实现）。

    与上游 create_deep_agent 功能等价 + 5 项路径 B V2 增强 + Option M。

    业务代码调用此函数替代 `from deepagents import create_deep_agent`。
    """
    # ==========================================================================
    # 1. Backend 处理（Option M in-place 方法 patch）
    # ==========================================================================
    if backend is None:
        backend = StateBackend()
    add_async_compat(backend)  # in-place patch（不变 class，不破坏 isinstance）

    # ==========================================================================
    # 2. 模型解析 + profile 查找
    # ==========================================================================
    if model is None:
        model = resolve_pmagent_model()  # pmagent 业务：multi-model provider 路由
    elif isinstance(model, str):
        model = resolve_pmagent_model(model)
    profile = _get_harness_profile(model_spec=None, model=model)

    # ==========================================================================
    # 3. tools 处理
    # ==========================================================================
    _tools = _apply_tool_description_overrides(
        list(tools) if tools else [],
        profile.tool_description_overrides,
    )

    # ==========================================================================
    # 4. subagents 拆分 + Alt E pattern 注入预构建 V2
    # ==========================================================================
    inline_subagents_raw, async_subagents = _split_subagents(subagents or [])

    # 处理用户 inline_subagents（含 pmagent 双 backend Alt E pattern）
    processed_inline_subagents: list[SubAgent] = []
    for spec in inline_subagents_raw:
        if "graph" in spec or hasattr(spec, "ainvoke"):
            processed_inline_subagents.append(spec)
            continue

        # SubAgent: 解析 model + 装配 middleware
        subagent_model_spec = spec.get("model", model)
        subagent_model = (
            resolve_pmagent_model(subagent_model_spec)
            if isinstance(subagent_model_spec, str)
            else subagent_model_spec
        )

        subagent_middleware, spec_updates = _build_subagent_middleware(
            spec=spec,
            backend=backend,
            pmagent_skills_backend=pmagent_skills_backend,  # 双 backend 系统
            parent_permissions=permissions,
            parent_interrupt_on=interrupt_on,
            subagent_model=subagent_model,
        )
        processed_spec: SubAgent = {**spec, **spec_updates}
        processed_inline_subagents.append(processed_spec)

    # ==========================================================================
    # 5. Default GP subagent 注入 + 装配 gp_middleware
    # ==========================================================================
    gp_middleware = _build_gp_middleware(
        backend=backend,
        pmagent_skills_backend=pmagent_skills_backend,
        profile=profile,
        skills=skills,
        permissions=permissions,
        skills_expose_dynamic_tools=skills_expose_dynamic_tools,
        skills_allowlist=skills_allowlist,
    )
    gp_spec: SubAgent = {
        **GENERAL_PURPOSE_SUBAGENT,
        "model": model,
        "tools": _tools,
        "middleware": gp_middleware,
    }
    if interrupt_on is not None:
        gp_spec["interrupt_on"] = interrupt_on

    final_inline_subagents = _ensure_general_purpose(processed_inline_subagents, gp_spec=gp_spec)

    # ==========================================================================
    # 6. 主 agent middleware 装配（含路径 B #3 BinaryDocConverter prepend）
    # ==========================================================================
    main_middleware = _build_main_middleware(
        backend=backend,
        pmagent_skills_backend=pmagent_skills_backend,
        profile=profile,
        model=model,
        skills=skills,
        memory=memory,
        permissions=permissions,
        interrupt_on=interrupt_on,
        inline_subagents=final_inline_subagents,
        async_subagents=async_subagents,
        user_middleware=middleware,
        skills_expose_dynamic_tools=skills_expose_dynamic_tools,
        skills_allowlist=skills_allowlist,
    )

    # ==========================================================================
    # 7. System prompt 组装
    # ==========================================================================
    final_system_prompt = _build_system_prompt(
        user_system_prompt=system_prompt,
        profile=profile,
    )

    # ==========================================================================
    # 8. 调 langchain create_agent + with_config
    # ==========================================================================
    return create_agent(
        model,
        system_prompt=final_system_prompt,
        tools=_tools,
        middleware=main_middleware,
        response_format=response_format,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        debug=debug,
        name=name,
        cache=cache,
        state_schema=state_schema,
    ).with_config({
        "recursion_limit": 9_999,
        "metadata": {
            "ls_integration": "pmagent",
            "versions": {"pmagent": "TODO[pmagent: read from version file]"},
            "lc_agent_name": name,
        },
    })
```

### 2.2 builders.py 三大装配函数

参见 `docs/architecture/spike/2026-05-02-planh-step2-reference-template.py`，pmagent 拷贝 + 适配。

详细 builder 实现：
- `_build_gp_middleware` — 9 层装配（拷贝自上游 graph.py:443-475）
- `_build_subagent_middleware` — 10 层装配（拷贝自上游 graph.py:482-543）+ pmagent 双 backend Alt E
- `_build_main_middleware` — 14 层装配（拷贝自上游 graph.py:551-606）+ BinaryDocConverter prepend

---

## 3. V2 增强类设计（5 项）

### 3.1 SkillsMiddlewareV2

```python
# pmagent/src/agent_assembly/middleware/skills_v2.py
"""SkillsMiddleware V2 — load_skill / unload_skill / expose_dynamic_tools / allowed_skills。

# LocalFeatures: [expose_dynamic_tools, allowed_skills, load_skill_tool, unload_skill_tool, V1V2_prompt_mutex]
# ShadowRisk: 中（覆盖 V1 多个方法；上游对应方法变更需手工同步）
# UpstreamCompat: 检查 SkillsMiddleware.__init__ 签名 + 关键方法签名（升级时跑 tests/test_skills_middleware_signature_compat）
"""
from deepagents.middleware.skills import SkillsMiddleware
# ... V2 实现
```

### 3.2 SubAgentObservability

```python
# pmagent/src/agent_assembly/middleware/subagent_observability.py
"""SubAgent stream_writer + logging + 敏感字段脱敏 + _EXCLUDED_STATE_KEYS 扩展。

# LocalFeatures: [stream_writer, subagent_logs, redact_sensitive, excluded_state_keys_extension]
# ShadowRisk: 高（依赖上游 5+ 模块级 helper：_extract_subagent_logs, _stream_subagent_sync 等）
# UpstreamCompat: 升级时强制跑 9 个 subagent_logs contract 测试
"""
import deepagents.middleware.subagents as _subagents
from deepagents.middleware.subagents import SubAgentMiddleware


class SubAgentObservability(SubAgentMiddleware):
    """V2 SubAgent middleware with observability + state isolation extension."""

    _FORK_EXTRA_EXCLUDED = frozenset({
        "subagent_logs", "skills_loaded", "skill_resources", "_summarization_event"
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # _EXCLUDED_STATE_KEYS mutate-in-place 扩展（实例 init 时一次性执行，幂等）
        if not self._FORK_EXTRA_EXCLUDED.issubset(_subagents._EXCLUDED_STATE_KEYS):
            _subagents._EXCLUDED_STATE_KEYS.update(self._FORK_EXTRA_EXCLUDED)

    # ... stream_writer + logging + redact 实现
```

### 3.3 SummarizationOverwriteGuard

```python
# pmagent/src/agent_assembly/middleware/summarization_overwrite_guard.py
"""augment + super 模式 — 在 SummarizationMiddleware._get_effective_messages 前 unwrap Overwrite。

# LocalFeatures: [overwrite_unwrap]
# ShadowRisk: 0（augment + super，不重新实现方法体）
"""
from langgraph.types import Overwrite
from deepagents.middleware.summarization import SummarizationMiddleware


class SummarizationOverwriteGuard(SummarizationMiddleware):
    def _get_effective_messages(self, messages, event):
        if isinstance(messages, Overwrite):
            messages = messages.value
        return super()._get_effective_messages(messages, event)
```

### 3.4 BinaryDocConverterMiddleware

```python
# pmagent/src/agent_assembly/middleware/binary_doc_converter.py
"""拷贝自 spike 步骤 1+2 设计：post-processing wrap_tool_call 拦截 read_file。

# LocalFeatures: [pdf_to_md, docx_to_md, xlsx_to_md, pptx_to_md, page_offset]
# ShadowRisk: 0（独立 middleware，不 subclass FilesystemMiddleware）
# UpstreamCompat: 依赖 langchain awrap_tool_call API（公开稳定）
"""
# ... 完整实现见 spike 步骤 2 reference template §6.3
```

### 3.5 add_async_compat (Option M)

```python
# pmagent/src/agent_assembly/backends/async_compat.py
"""in-place backend 实例方法 patch — 保留 isinstance 兼容（Option M）。

# LocalFeatures: [async_compat_adownload]
# ShadowRisk: 0
"""
import functools
import inspect


def add_async_compat(backend):
    """Add async tolerance to backend.adownload_files — in-place, idempotent."""
    if backend is None:
        return backend
    fn = getattr(backend, "adownload_files", None)
    if fn is None or inspect.iscoroutinefunction(fn):
        return backend
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

---

## 4. 私有 API 治理（核心纪律）

### 4.1 集中管理：`_private_api_imports.py`

```python
# pmagent/src/agent_assembly/_private_api_imports.py
"""集中管理 deepagents 私有 API import + 升级 review rationale。

⚠️ 任何 _ 前缀 import 必须在此模块声明 + 文档化。
任何升级 deepagents 版本前必须跑 tools/check_private_api.py。

格式：
    from <module> import <_api>
    \"\"\"rationale: <为什么使用>
       alternative: <是否有公开 API 替代>
       upgrade_review: <升级时检查什么>\"\"\"
"""

# 1. resolve_model
from deepagents._models import resolve_model
"""rationale: 模型字符串 → BaseChatModel 解析。
   alternative: 无公开 API 替代（langchain init_chat_model 不含 deepagents 特定 profile）。
   upgrade_review: 检查 resolve_model(spec: str) -> BaseChatModel 签名不变。"""

# 2. BASE_AGENT_PROMPT
from deepagents.graph import BASE_AGENT_PROMPT
"""rationale: 上游基础 system prompt 模板，pmagent 装配复用。
   alternative: pmagent 自管基础 prompt（需冗余维护）。
   upgrade_review: 半公开常量；如重命名直接改本 import。"""

# 3. _resolve_extra_middleware
from deepagents.graph import _resolve_extra_middleware
"""rationale: profile 系统的 middleware 注入点。
   alternative: 重新实现 profile 加载（需 ~50 行 + 与上游同步）。
   upgrade_review: 检查 _resolve_extra_middleware(profile) -> list[Middleware] 接口契约。"""

# 4. _apply_tool_description_overrides
from deepagents.graph import _apply_tool_description_overrides
"""rationale: profile 决定的 tool 描述重写。
   alternative: 重新实现（少量代码）。
   upgrade_review: 检查 (tools, overrides) -> tools 签名不变。"""

# 5. _HarnessProfile
from deepagents.profiles import _HarnessProfile
"""rationale: profile 类型注解 + extra_middleware/tool_description_overrides/excluded_tools 字段访问。
   alternative: 自定义 Protocol 类（duck typing）。
   upgrade_review: 检查 _HarnessProfile 字段不变（base_system_prompt, tool_description_overrides, excluded_tools, extra_middleware, system_prompt_suffix）。"""

# 6. _get_harness_profile
from deepagents.profiles import _get_harness_profile
"""rationale: profile 查找入口（按 model spec 路由到具体 profile）。
   alternative: 自管 profile registry（需同步 OpenAI/OpenRouter/Anthropic 等）。
   upgrade_review: 检查 _get_harness_profile(spec, model) 签名 + profile 数据结构。"""

# 7. _ToolExclusionMiddleware
from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware
"""rationale: profile.excluded_tools 实现需要此 middleware。
   alternative: 自定义 ToolExclusion middleware（需重新实现 hooks）。
   upgrade_review: 检查 _ToolExclusionMiddleware(excluded=frozenset[str]) 签名。"""

# 8. _PermissionMiddleware
from deepagents.middleware.permissions import _PermissionMiddleware
"""rationale: pmagent 使用 permissions 参数时需要此 middleware（FilesystemPermission 公开但 _PermissionMiddleware 私有）。
   alternative: 直接传 FilesystemPermission 列表给 deepagents（v4-rev2 接口）— 已不适用 Plan H+。
   upgrade_review: 检查 _PermissionMiddleware(rules, backend) 签名。"""

# 9. _EXCLUDED_STATE_KEYS
import deepagents.middleware.subagents as _subagents
"""rationale: pmagent 扩展 4 个键（subagent_logs / skills_loaded / skill_resources / _summarization_event）。
   alternative: 完全自定义状态隔离（需重写 SubAgentMiddleware 状态过滤逻辑）。
   upgrade_review: 检查 _EXCLUDED_STATE_KEYS 是 set 类型（mutable），仍存在。
   特殊：使用 set.update() mutate-in-place（防御未来引用捕获）。"""

# 10. GENERAL_PURPOSE_SUBAGENT
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
"""rationale: default general-purpose subagent spec（name 等关键字段）。
   alternative: 自管 GP spec（需同步上游 default 行为）。
   upgrade_review: 检查 GENERAL_PURPOSE_SUBAGENT['name'] 不变（pmagent 装配靠此判断是否需要注入 default GP）。"""
```

### 4.2 私有 API 兼容性检查工具

```python
# pmagent/tools/check_private_api.py
"""升级 deepagents 版本前必跑：验证 10 项私有 API 仍存在 + 签名兼容。

退出码：
- 0: 全部 API 兼容，可以升级
- 1: 有 API 失效或签名变化，不升级
"""
import sys
import inspect


def main():
    failures = []

    # Check 1-10: import + 签名
    try:
        from deepagents._models import resolve_model
        sig = inspect.signature(resolve_model)
        if "spec" not in sig.parameters and "model" not in sig.parameters:
            failures.append("resolve_model 签名变化")
    except ImportError as e:
        failures.append(f"resolve_model 失效: {e}")

    # ... 其余 9 项类似检查

    if failures:
        print("❌ 私有 API 兼容性检查失败:")
        for f in failures:
            print(f"  - {f}")
        print("\n不要升级 deepagents 版本，先排查上述问题。")
        sys.exit(1)

    print("✅ 10 项私有 API 全部兼容，可以升级。")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 4.3 升级 SOP

参见 `pmagent/docs/operations/deepagents-upgrade-sop.md`，强制 7 步检查（详见 ADR-0002 §6.2 纪律 3）。

---

## 5. 实施计划（7-10 d 总日历）

### Phase A: 异步问题诊断（与 Phase 1 并行，0.5-1 d）

| 工作 | 责任 | 输出 |
| --- | --- | --- |
| 诊断 pmagent "异步执行严重问题"具体根因 | pmagent | 诊断报告（pmagent 业务代码 / LangGraph dispatch / SubAgent 调度 / 其他）|

### Phase 1: pmagent 装配实施（**7-10 d**，v2 修订 RC-4）

| 步骤 | 工作 | 估时 |
| --- | --- | --- |
| 1.1 | 拷贝 spike 步骤 2 reference template 到 `pmagent/src/agent_assembly/assembly.py` + `builders.py` | 0.5 d |
| 1.2 | 实现 5 个 V2 类到 `pmagent/src/agent_assembly/middleware/` | 1.5-2 d |
| 1.3 | 实现 `add_async_compat()` 到 `backends/async_compat.py` | 0.25 d |
| 1.4 | 创建 `_private_api_imports.py` 集中管理 + 文档化 10 项私有 API | 0.5 d |
| 1.5 | pmagent 业务适配（PMAgentState、harness profiles、multi-model、6+ subagents、HIL、双 backend、Alt E pattern） | 2-3 d |
| 1.6 | invariant 测试（5 个 test cases）+ 9 个 subagent_logs contract 测试 | 0.5 d |
| 1.7 | 升级 SOP 文档 + `tools/check_private_api.py` 工具 | 0.5 d |
| 1.8 | e2e + langgraph dev 烟测 | 0.5 d |

### Phase 2: Migration 收尾（1 d）

| 步骤 | 工作 | 估时 |
| --- | --- | --- |
| 2.1 | 修改 `pmagent/pyproject.toml`：deepagents 直接依赖 `~=0.5.0`（PEP 440 兼容范围）| 0.25 d |
| 2.2 | 删除/归档 fork 仓库（保留作为历史档案）| 0.25 d |
| 2.3 | pmagent 业务代码 import 替换（`create_deep_agent` → `create_pmagent_agent`）| 0.25 d |
| 2.4 | 全量回归测试 + 文档定稿 + ADR-0002 转 Accepted（三方签字后）| 0.25 d |

### 总日历

**9-12 d**（v2 修订）：含 Phase A 诊断 + Phase 1 装配（7-10 d，含 buffer）+ Phase 2 收尾，全部 pmagent 团队执行。Phase A 与 Phase 1.0-1.4 可并行；Phase A 必须先于 Phase 1.5（pmagent 业务适配）启动。

---

## 6. 测试策略

### 6.1 装配 invariant 测试（5 项）

参见 ADR-0002 §6 纪律 4：

1. `test_private_apis_still_exist` — 10 项私有 API 持续可用
2. `test_v2_classes_correctly_assembled` — V2 子类装配生效
3. `test_skills_middleware_signature_compat` — V2 父类签名兼容
4. `test_excluded_state_keys_extended` — fork 扩展 4 键生效
5. `test_binary_doc_converter_assembled` — BinaryDocConverter prepend 顺序正确

### 6.2 9 个 subagent_logs 契约测试（保留自 v3）

| 测试 | 类型 |
| --- | --- |
| `test_subagent_logs_acceptance.py` | 验收 |
| `test_pmagent_ui_comprehensive.py` | UI 综合 |
| `test_pmagent_comprehensive.py` | 综合 |
| `test_state_schema.py` | 状态字段 |
| `tests/manual/test_subagent_logging.py` | 手动 |
| `tests/manual/verify_subagent_logging_env.py` | 手动 |
| `tests/manual/verify_subagent_logs_display.py` | 显示验证 |
| `tests/manual/test_subagent_sdk.py` | SDK |
| `tests/integration/test_hil_interrupt_mock.py` | 集成 |

### 6.3 e2e 烟测

- `langgraph dev` 启动 + 真实 SubAgent 调用
- pmagent 6+ subagents 各跑 1 次 task
- 双 backend 系统验证（pmagent_skills_backend FilesystemBackend + 主 backend StateBackend/Factory）

---

## 7. 实证基础（22 个 PoC + spike 三步走）

参见 ADR-0002 §5 实证支撑表。Plan H+ 复用：

- ✅ Option M PoC（5/5）：`add_async_compat()` 设计验证
- ✅ Summarization factory（3/3）：augment + super 模式验证
- ✅ RC-5 mutate-in-place（3/3）：`_EXCLUDED_STATE_KEYS` 扩展验证
- ✅ Spike 步骤 1+2：上游装配分支文档 + reference template
- ✅ Spike 步骤 3：pmagent 适配实测（309 行 + 32 分支量化）

---

## 8. 风险与缓解

参见 ADR-0002 §10 表格。核心风险：

1. **私有 API 依赖**（10 项 `_` 前缀 import）— 4 项治理纪律缓解
2. **8 个不变量心智负担** — pmagent 团队培养 SDK 装配工程能力 + invariants.py 文档化
3. **装配代码 long-lived 维护** — 80% 是上游拷贝，主动同步频率低
4. **跨大版本升级（0.7+）** — SOP 强制 7 步检查

---

## 9. 与 ADR-0002 的关系

本文档是 Plan H+ 的**完整技术设计**。ADR-0002 是**决策档案**（含决策理由、否决方案、签发流程）。

| 内容 | 位于 |
| --- | --- |
| 决策推荐 / 否决理由 / 翻盘条件 / 签字流程 | ADR-0002 |
| 完整技术设计 / 代码示例 / 实施细节 | 本文档 |
| 实证 PoC / spike 数据 | `docs/architecture/spike/` |

---

## 10. 历史方案归档

被 Plan H+ 取代的历史方案：

| 方案 | 文档 | 状态 |
| --- | --- | --- |
| Plan B（v1）| `2026-04-29-fork-customization-downsink-plan.md` | HISTORICAL |
| Plan D 提出（v2）| `2026-05-01-fork-customization-downsink-plan-v2.md` | HISTORICAL |
| Plan D 三轮加强（v3）| `2026-05-01-fork-customization-downsink-plan-v3.md` | HISTORICAL |
| Plan E++（v4-rev2）| `2026-05-02-fork-enhancement-package-plan-v4.md` | SUPERSEDED |
| **Plan H+（本文档）** | `2026-05-02-plan-h-plus-final.md` | **CURRENT** |

---

**文档状态**：CURRENT（与 ADR-0002 Draft 配套）
**等待**：ADR-0002 三方签字 → Phase A + Phase 1 启动
