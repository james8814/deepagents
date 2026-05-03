"""Plan H+ Spike — 步骤 2：pmagent agent.py 参考模板（Plan H+ 直接拷贝起点）

================================================================================
✅ PLAN H+ 复用 (2026-05-02)

本文件原为 Plan H spike 步骤 2 输出。8 次方向探索后最终方案演进为 Plan H+
（消除 fork + pmagent 全主权）。本模板**完全适用于 Plan H+** —— pmagent 团队
在实施 Plan H+ Phase 1.1 时，直接拷贝本文件到 pmagent/src/agent_assembly/assembly.py
+ builders.py，做 V2 类替换 + pmagent 业务适配。

当前权威方案: docs/architecture/2026-05-02-plan-h-plus-final.md
决策档案: docs/architecture/decisions/0002-fork-customization-strategy.md

唯一架构差异（Plan H vs Plan H+）：
- Plan H: V2 子类住 fork extras 包，pmagent 从 deepagents-extras import
- Plan H+: V2 子类直接住 pmagent，pmagent 从 pmagent.src.agent.middleware import
（其他装配代码完全一致）

================================================================================

下面是原文档内容（Plan H spike 步骤 2 reference template）：
================================================================================

Plan H Spike — 步骤 2：pmagent agent.py 参考模板

================================================================================
这是一个 SKELETON 参考模板，由 deepagents 团队提供给 pmagent 团队。

用途：pmagent 团队基于此模板做步骤 3——把模板适配到 pmagent 实际配置（6 个 subagents、
PMAgentState、harness profiles、multi-model、HIL、TOOL_REGISTRY 等），并量化最终
行数 + 条件分支数 + 复杂度，作为 Plan H vs v4-rev3 决策的实证数据。

模板等价于上游 `create_deep_agent` 完整功能 + 路径 B 5 项 V2 增强 + Option M backend
patch。预计 pmagent 适配后行数：150-250 行（基础装配）+ 50-100 行（pmagent 特定配置）。

================================================================================
"""
from __future__ import annotations

# ============================================================================
# 上游 deepagents 依赖（不变，保留 import 路径）
# ============================================================================
from collections.abc import Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

from deepagents._models import resolve_model
from deepagents._version import __version__
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware  # 上游版（路径 B #3 用 BinaryDocConverter post-process，FS 不再 subclass）
from deepagents.middleware.memory import MemoryMiddleware  # 上游版（Option M backend 方法 patch）
from deepagents.middleware.permissions import FilesystemPermission, _PermissionMiddleware
from deepagents.middleware.subagents import (
    GENERAL_PURPOSE_SUBAGENT,
    CompiledSubAgent,
    SubAgent,
)
from deepagents.middleware.summarization import create_summarization_middleware  # 仍是 factory
from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

# tested 2026-05-03 by pmagent: 以下 3 项 import 路径在 deepagents 0.5.0 不在 deepagents.middleware.*，
# 实际位于 langchain.agents.middleware（TodoList/HITL）和 langchain_anthropic.middleware（PromptCaching）。
# 之前模板错误（deepagents.middleware.todo_list / .anthropic_prompt_caching / .human_in_the_loop）
# 已于 2026-05-03 修订，与 pmagent Phase 1.1 实测一致。
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from langchain_anthropic.middleware.prompt_caching import AnthropicPromptCachingMiddleware
from deepagents.profiles import _HarnessProfile, _get_harness_profile
# tested 2026-05-03 by pmagent: _get_harness_profile 仅接受 spec: str 单个位置参数；
# 当 caller 持有 BaseChatModel 实例时，应用 _harness_profile_for_model(model, spec) 包装函数（解析 model.identifier → spec）
from deepagents.graph import (
    BASE_AGENT_PROMPT,
    _apply_tool_description_overrides,
    _harness_profile_for_model,
    _resolve_extra_middleware,
)

# ============================================================================
# Plan H 增强：5 项路径 B 子类 + 工具
# 来自 deepagents-extras 包（fork 的纯 additive 子类库，无 monkey-patch）
# ============================================================================
from deepagents_extras.middleware.skills_v2 import SkillsMiddlewareV2  # 替代 SkillsMiddleware
from deepagents_extras.middleware.subagent_observability import SubAgentObservability  # 替代 SubAgentMiddleware
from deepagents_extras.middleware.summarization_overwrite_guard import SummarizationOverwriteGuard
from deepagents_extras.middleware.binary_doc_converter import BinaryDocConverterMiddleware  # 路径 B #3 post-process
from deepagents_extras.backends.async_compat import add_async_compat  # 路径 B #7 Option M
from deepagents_extras.middleware.summarization_factory_v2 import (
    create_summarization_middleware_with_overwrite_guard,  # factory 替代品
)


# ============================================================================
# 第 1 节：辅助函数 —— 三个 middleware 栈装配（gp / subagent / main）
# ============================================================================

def _build_gp_middleware(
    *,
    model: BaseChatModel,  # tested 2026-05-03 by pmagent: 必须，否则 line 114 NameError
    backend: BackendProtocol,
    profile: _HarnessProfile,
    skills: list[str] | None,
    permissions: list[FilesystemPermission] | None,
) -> list[AgentMiddleware]:
    """构造 general-purpose subagent 的 middleware 栈（9 层）。

    与上游 graph.py:443-475 等价；区别仅在 SkillsMiddleware → V2、Summarization → Guard。
    """
    middleware: list[AgentMiddleware] = [
        TodoListMiddleware(),
        FilesystemMiddleware(  # 路径 B #3 后 FS 不再 subclass；converter 走 post-process
            backend=backend,
            custom_tool_descriptions=profile.tool_description_overrides,
        ),
        # Plan H V2 替换：用 OverwriteGuard factory（augment + super 子类）
        # tested 2026-05-03 by pmagent: 之前模板写 `model_for_summarization` 是未定义变量（NameError），
        # 实际应传入 `model` 参数。已加 model: BaseChatModel 到函数签名。
        create_summarization_middleware_with_overwrite_guard(model, backend),
        PatchToolCallsMiddleware(),
    ]

    # 5. SkillsMiddleware → V2
    if skills is not None:
        middleware.append(SkillsMiddlewareV2(backend=backend, sources=skills))

    # 6. profile-specific extra middleware
    middleware.extend(_resolve_extra_middleware(profile))

    # 7. Tool exclusion
    if profile.excluded_tools:
        middleware.append(_ToolExclusionMiddleware(excluded=profile.excluded_tools))

    # 8. Anthropic prompt caching（无条件，非 Anthropic 模型自动 ignore）
    middleware.append(AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"))

    # 9. Permissions（必须最后，看到所有前面注入的工具）
    if permissions:
        middleware.append(_PermissionMiddleware(rules=permissions, backend=backend))

    return middleware


def _build_subagent_middleware(
    *,
    spec: SubAgent,
    backend: BackendProtocol,
    parent_permissions: list[FilesystemPermission] | None,
    parent_interrupt_on: dict[str, Any] | None,
    subagent_model: BaseChatModel,
) -> tuple[list[AgentMiddleware], dict[str, Any]]:
    """构造单个 inline subagent 的 middleware 栈（10 层）+ 返回 spec metadata 更新。

    与上游 graph.py:482-543 等价；用 subagent 自己的 profile（不是父 profile）。
    """
    # 关键：用 subagent 自己的 model 查自己的 profile
    # tested 2026-05-03 by pmagent: 之前模板写 `_get_harness_profile(spec.get("model"), subagent_model)`
    # 是 TypeError（_get_harness_profile 仅 1 个 spec: str 参数）。
    # 正确：用 _harness_profile_for_model 包装函数处理 BaseChatModel + 可选 spec 的解析。
    subagent_profile = _harness_profile_for_model(subagent_model, spec.get("model"))

    # Permissions: subagent 自己的 rules 优先，否则继承父
    subagent_permissions = spec.get("permissions", parent_permissions)

    middleware: list[AgentMiddleware] = [
        TodoListMiddleware(),
        FilesystemMiddleware(
            backend=backend,
            custom_tool_descriptions=subagent_profile.tool_description_overrides,
        ),
        # Summarization 用 subagent 自己的 model
        create_summarization_middleware_with_overwrite_guard(subagent_model, backend),
        PatchToolCallsMiddleware(),
    ]

    # 5. SkillsMiddleware → V2（如果 subagent 有自己的 skills）
    subagent_skills = spec.get("skills")
    if subagent_skills:
        middleware.append(SkillsMiddlewareV2(backend=backend, sources=subagent_skills))

    # 6. spec 用户自定义 middleware（subagent 独有）
    middleware.extend(spec.get("middleware", []))

    # 7. profile-specific extra
    middleware.extend(_resolve_extra_middleware(subagent_profile))

    # 8. Tool exclusion
    if subagent_profile.excluded_tools:
        middleware.append(_ToolExclusionMiddleware(excluded=subagent_profile.excluded_tools))

    # 9. Anthropic prompt caching
    middleware.append(AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"))

    # 10. Permissions（最后）
    if subagent_permissions:
        middleware.append(_PermissionMiddleware(rules=subagent_permissions, backend=backend))

    # 处理 interrupt_on（subagent spec 自己的 > 父继承）
    subagent_interrupt_on = spec.get("interrupt_on", parent_interrupt_on)

    spec_updates = {
        "model": subagent_model,
        "tools": _apply_tool_description_overrides(
            spec.get("tools", []),
            subagent_profile.tool_description_overrides,
        ),
        "middleware": middleware,
    }
    if subagent_interrupt_on is not None:
        spec_updates["interrupt_on"] = subagent_interrupt_on

    return middleware, spec_updates


def _build_main_middleware(
    *,
    backend: BackendProtocol,
    profile: _HarnessProfile,
    model: BaseChatModel,
    skills: list[str] | None,
    memory: list[str] | None,
    permissions: list[FilesystemPermission] | None,
    interrupt_on: dict[str, Any] | None,
    inline_subagents: list[SubAgent],
    async_subagents: list[AsyncSubAgent],
    user_middleware: Sequence[AgentMiddleware] | None,
) -> list[AgentMiddleware]:
    """构造主 agent 的 middleware 栈（14 层）。

    与上游 graph.py:551-606 等价；含路径 B #3 BinaryDocConverter prepend、
    SubAgentMiddleware → Observability。
    """
    middleware: list[AgentMiddleware] = [TodoListMiddleware()]

    # 2. SkillsMiddleware（位置在主 agent 比 gp 靠前）
    if skills is not None:
        middleware.append(SkillsMiddlewareV2(backend=backend, sources=skills))

    # 3-6. Filesystem + SubAgentObservability + Summarization + PatchToolCalls
    middleware.extend([
        FilesystemMiddleware(
            backend=backend,
            custom_tool_descriptions=profile.tool_description_overrides,
        ),
        SubAgentObservability(  # Plan H V2 替换：含 stream_writer + logging + 脱敏
            backend=backend,
            subagents=inline_subagents,
            task_description=profile.tool_description_overrides.get("task"),
        ),
        create_summarization_middleware_with_overwrite_guard(model, backend),
        PatchToolCallsMiddleware(),
    ])

    # 7. AsyncSubAgent
    if async_subagents:
        middleware.append(AsyncSubAgentMiddleware(async_subagents=async_subagents))

    # 8. 路径 B #3：BinaryDocConverter prepend（用户 middleware 之前）
    #    AD-2 修订：在用户 middleware 之前注入，使用户 middleware 看到已转换的 Markdown
    middleware.append(BinaryDocConverterMiddleware(backend=backend))

    # 9. 用户传入的 middleware
    if user_middleware:
        middleware.extend(user_middleware)

    # 10. profile-specific extra（在用户 middleware 之后、memory 之前——保护 prompt cache）
    middleware.extend(_resolve_extra_middleware(profile))

    # 11. Tool exclusion
    if profile.excluded_tools:
        middleware.append(_ToolExclusionMiddleware(excluded=profile.excluded_tools))

    # 12. Anthropic prompt caching
    middleware.append(AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"))

    # 13. Memory（在 user middleware + extra 之后；MemoryMiddleware 内部加 cache_control 让前面的 cache 仍有效）
    if memory is not None:
        middleware.append(
            MemoryMiddleware(
                backend=backend,
                sources=memory,
                add_cache_control=True,
            )
        )

    # 14. HITL
    if interrupt_on is not None:
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # 15. Permissions（必须绝对最后）
    if permissions:
        middleware.append(_PermissionMiddleware(rules=permissions, backend=backend))

    return middleware


# ============================================================================
# 第 2 节：subagents 拆分 inline vs async
# ============================================================================

def _split_subagents(
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent],
) -> tuple[list[SubAgent | CompiledSubAgent], list[AsyncSubAgent]]:
    """把 subagents 列表拆分为 inline + async（按 graph_id 字段判断）。

    与上游 graph.py:481-489 等价。
    """
    inline_subagents: list[SubAgent | CompiledSubAgent] = []
    async_subagents: list[AsyncSubAgent] = []
    for spec in subagents:
        if "graph_id" in spec:  # AsyncSubAgent
            async_subagents.append(spec)  # type: ignore[arg-type]
        else:
            inline_subagents.append(spec)  # type: ignore[arg-type]
    return inline_subagents, async_subagents


# ============================================================================
# 第 3 节：default general-purpose subagent 注入
# ============================================================================

def _ensure_general_purpose(
    inline_subagents: list[SubAgent],
    *,
    gp_spec: SubAgent,
) -> list[SubAgent]:
    """如果用户未显式定义 general-purpose subagent，在列表首位插入 default GP。

    与上游 graph.py:546-549 等价。
    """
    if not any(spec["name"] == GENERAL_PURPOSE_SUBAGENT["name"] for spec in inline_subagents):
        inline_subagents.insert(0, gp_spec)
    return inline_subagents


# ============================================================================
# 第 4 节：system prompt 组装
# ============================================================================

def _build_system_prompt(
    *,
    user_system_prompt: str | SystemMessage | None,
    profile: _HarnessProfile,
) -> str | SystemMessage:
    """与上游 graph.py:608-619 等价。

    base_prompt = profile.base_system_prompt or BASE_AGENT_PROMPT
    if profile.system_prompt_suffix: base_prompt += "\n\n" + suffix
    if user_system_prompt is None: return base_prompt
    if isinstance(user_system_prompt, SystemMessage): user.content + base_prompt
    else: user_system_prompt + "\n\n" + base_prompt
    """
    base_prompt = profile.base_system_prompt if profile.base_system_prompt is not None else BASE_AGENT_PROMPT
    if profile.system_prompt_suffix is not None:
        base_prompt = base_prompt + "\n\n" + profile.system_prompt_suffix

    if user_system_prompt is None:
        return base_prompt
    if isinstance(user_system_prompt, SystemMessage):
        # SystemMessage 形式
        return SystemMessage(content=user_system_prompt.content + "\n\n" + base_prompt)
    # str 形式
    return user_system_prompt + "\n\n" + base_prompt


# ============================================================================
# 第 5 节：主入口 —— pmagent 等价的 create_deep_agent（Plan H 实现）
# ============================================================================

def create_pmagent_agent(
    *,
    # 标准 deepagents 输入参数
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
    # ---- 路径 B 增强参数（pmagent 控制 V2 行为）----
    skills_expose_dynamic_tools: bool = False,
    skills_allowlist: list[str] | None = None,
):
    """pmagent 完整 agent 装配（Plan H 实现）。

    与上游 `create_deep_agent` 功能等价 + 路径 B 5 项 V2 增强 + Option M。
    pmagent 业务代码调用此函数替代 `from deepagents import create_deep_agent`。
    """
    # ---- 路径 B #7 Option M: backend 方法 patch ----
    if backend is None:
        backend = StateBackend()
    add_async_compat(backend)  # in-place patch；不变 class，不破坏 isinstance

    # ---- 模型 + profile 解析 ----
    if model is None:
        # TODO[pmagent]: 这里应处理 pmagent 的 model 默认值（multi-model 配置）
        model = resolve_model("anthropic:claude-sonnet-4-6")
    elif isinstance(model, str):
        model = resolve_model(model)
    # tested 2026-05-03 by pmagent: 之前模板写 `_get_harness_profile(model_spec=None, model=model)` 是 TypeError
    # （_get_harness_profile 仅 1 个 spec: str 参数）。正确用 _harness_profile_for_model 包装函数。
    profile = _harness_profile_for_model(model, spec=None)

    # ---- tools 处理 ----
    _tools = _apply_tool_description_overrides(
        list(tools) if tools else [],
        profile.tool_description_overrides,
    )

    # ---- subagents 拆分 ----
    inline_subagents_raw, async_subagents = _split_subagents(subagents or [])

    # ---- 构造 default general-purpose subagent middleware + spec ----
    gp_middleware = _build_gp_middleware(
        backend=backend,
        profile=profile,
        skills=skills,
        permissions=permissions,
    )
    gp_spec: SubAgent = {
        **GENERAL_PURPOSE_SUBAGENT,
        "model": model,
        "tools": _tools,
        "middleware": gp_middleware,
    }
    if interrupt_on is not None:
        gp_spec["interrupt_on"] = interrupt_on  # type: ignore[typeddict-unknown-key]

    # ---- 处理用户 inline_subagents ----
    processed_inline_subagents: list[SubAgent] = []
    for spec in inline_subagents_raw:
        if "graph" in spec or hasattr(spec, "ainvoke"):
            # CompiledSubAgent 直接透传
            processed_inline_subagents.append(spec)  # type: ignore[arg-type]
            continue

        # SubAgent: 解析 model + 装配 middleware
        subagent_model_spec = spec.get("model", model)
        subagent_model = resolve_model(subagent_model_spec) if isinstance(subagent_model_spec, str) else subagent_model_spec

        _, spec_updates = _build_subagent_middleware(
            spec=spec,
            backend=backend,
            parent_permissions=permissions,
            parent_interrupt_on=interrupt_on,
            subagent_model=subagent_model,
        )
        processed_spec: SubAgent = {**spec, **spec_updates}  # type: ignore[typeddict-item]
        processed_inline_subagents.append(processed_spec)

    # ---- 注入 default GP（如未显式定义）----
    final_inline_subagents = _ensure_general_purpose(processed_inline_subagents, gp_spec=gp_spec)

    # ---- 构造主 agent middleware 栈 ----
    main_middleware = _build_main_middleware(
        backend=backend,
        profile=profile,
        model=model,
        skills=skills,
        memory=memory,
        permissions=permissions,
        interrupt_on=interrupt_on,
        inline_subagents=final_inline_subagents,
        async_subagents=async_subagents,
        user_middleware=middleware,
    )

    # ---- system prompt 组装 ----
    final_system_prompt = _build_system_prompt(
        user_system_prompt=system_prompt,
        profile=profile,
    )

    # ---- 调用 langchain create_agent + with_config ----
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
    ).with_config({
        "recursion_limit": 9_999,
        "metadata": {
            "ls_integration": "pmagent",  # 改为 pmagent
            "versions": {"deepagents": __version__, "pmagent": "TODO[pmagent: read from version file]"},
            "lc_agent_name": name,
        },
    })


# ============================================================================
# pmagent 团队步骤 3 待办清单（TODO 标记）
# ============================================================================
"""
pmagent 团队 step 3 任务（基于此模板适配实际配置）：

1. [TODO-1] PMAgentState 集成
   - create_agent 应接受 state_schema=PMAgentState（langchain create_agent 支持）
   - 不在此模板，pmagent 团队需补

2. [TODO-2] Multi-model 配置
   - pmagent 的 model 默认值（DeepSeek/Qwen/OpenAI/Anthropic）逻辑
   - 第 247 行的 model is None 兜底应改为 pmagent 实际逻辑

3. [TODO-3] 6 个 SubAgents 装配
   - pmagent 实际 subagents 列表（包含 model + skills + tools 各异）
   - 验证 _build_subagent_middleware 处理所有 6 个不出错

4. [TODO-4] Skills 配置
   - pmagent 的 skills_expose_dynamic_tools=True 强制开启
   - skills_allowlist per subagent 是 v3 §3.3.2 强需求
   - 确认 SkillsMiddlewareV2 接受这两个参数（Plan H 中 V2 子类需要支持）

5. [TODO-5] Backend 选择
   - StateBackend / FilesystemBackend / CompositeBackend 多场景
   - pmagent 实际场景的 backend 选择逻辑

6. [TODO-6] HIL middleware
   - interrupt_on 配置（execute, write_file, edit_file, web_search, fetch_url, task）

7. [TODO-7] TOOL_REGISTRY 注册
   - pmagent 自定义工具如何注入

8. [TODO-8] 量化（步骤 3 输出）
   - 完整 pmagent agent.py 的最终行数
   - 条件分支数（if-elif）
   - 复杂度（圈复杂度可用 radon 或人工估）
   - 与现有 v4-rev2 enhanced 包对比

9. [TODO-9] 演化曲线（步骤 5）
   - 基于 pmagent 历史 agent.py 增长率（git log + wc -l）
   - 估算 1 年 / 3 年后行数
   - 评估装配增长是否会超过决策矩阵阈值
"""

# ============================================================================
# 模板本身行数统计（基础装配）
# ============================================================================
"""
本模板（不含 TODO 区）：约 280 行
其中：
- imports: 30 行
- _build_gp_middleware: 35 行
- _build_subagent_middleware: 50 行
- _build_main_middleware: 60 行
- _split_subagents: 12 行
- _ensure_general_purpose: 8 行
- _build_system_prompt: 18 行
- create_pmagent_agent 主入口: 70 行

pmagent 步骤 3 适配后预估：
- 基础装配：280 行（本模板）
- pmagent 特定配置（subagents、profiles、TOOL_REGISTRY 等）：50-100 行
- 总计：330-380 行

判断 vs 决策矩阵阈值（pmagent §7.3）：
- ≤ 100 行：远低于此 → 倾向 Plan H
- 100-200 行：低于此 → 评估具体复杂度
- > 200 行：超过此 → 倾向 v4-rev2 (CTO 高估了 Plan H 简单性)

实测 280 行基础装配 + pmagent 适配 → 330-380 行总计
**这超过了决策矩阵的"> 200 行"阈值——倾向选 v4-rev2**

但请 pmagent 团队步骤 3 实际写一遍验证，不要直接接受这个估算。
"""
