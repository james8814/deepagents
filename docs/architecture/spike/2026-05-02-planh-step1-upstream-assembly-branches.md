> ✅ **PLAN H+ 复用 2026-05-02** — 本文档原为 Plan H spike 步骤 1 输出。
>
> 8 次方向探索后最终方案演进为 **Plan H+（消除 fork + pmagent 全主权）**。本文档的上游装配分支分析**完全适用于 Plan H+** —— pmagent 装配代码以本文档的分支映射为参考，拷贝上游 graph.py 装配逻辑 + V2 替换 + pmagent 适配。
>
> **当前权威方案**：[`../2026-05-02-plan-h-plus-final.md`](../2026-05-02-plan-h-plus-final.md)
> **决策档案**：[`../decisions/0002-fork-customization-strategy.md`](../decisions/0002-fork-customization-strategy.md)
>
> ---

# Plan H+ Spike — 步骤 1：上游 `create_deep_agent` 装配分支文档（Plan H+ 实施 reference）

**日期**: 2026-05-02
**作者**: deepagents 团队
**消费者**: pmagent 团队（Plan H spike 步骤 3 输入）
**用途**: 让 pmagent 团队完整理解"如果走 Plan H，需要复制哪些装配逻辑"

**实测代码版本**: upstream/main（最新），`libs/deepagents/deepagents/graph.py` 共 643 行

---

## 1. `create_deep_agent` 函数级总览

```text
create_deep_agent (line 218)
├── 输入解析 (line 418-441)
│   ├── 模型解析（resolve_model + harness profile 查找）
│   ├── tools 处理（_apply_tool_description_overrides）
│   ├── backend 默认值（StateBackend 兜底）
│   └── extra_kwargs profile-specific（如 init_kwargs_factory）
├── 三个独立的 middleware 栈装配
│   ├── 1. gp_middleware（general-purpose subagent，line 443-475）
│   ├── 2. subagent_middleware × N（用户自定义 subagent，line 482-543）
│   └── 3. deepagent_middleware（主 agent，line 551-606）
├── inline_subagents 列表组装 + 默认 general-purpose 注入 (line 481-549)
├── system_prompt 组装（profile-aware，line 608-619）
└── return create_agent(...)（langchain 公开 API，line 622-631）
       └── .with_config({recursion_limit, metadata}) (line 632-639)
```

---

## 2. 三个 middleware 栈的装配顺序对比

### 2.1 gp_middleware（默认 general-purpose subagent）

| # | 中间件 | 条件 | 备注 |
| --- | --- | --- | --- |
| 1 | `TodoListMiddleware()` | 无条件 | 总是首位 |
| 2 | `FilesystemMiddleware(backend, custom_tool_descriptions=...)` | 无条件 | profile 注入 tool 描述覆盖 |
| 3 | `create_summarization_middleware(model, backend)` | 无条件 | factory 返回 `_DeepAgentsSummarizationMiddleware` |
| 4 | `PatchToolCallsMiddleware()` | 无条件 | |
| 5 | `SkillsMiddleware(backend, sources=skills)` | `if skills is not None` | skills 是 `create_deep_agent` 的入参 |
| 6 | `*_resolve_extra_middleware(_profile)` | profile 提供 | OpenRouter / OpenAI 等 profile-specific |
| 7 | `_ToolExclusionMiddleware(excluded=...)` | `if _profile.excluded_tools` | profile 决定哪些工具被剥离 |
| 8 | `AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")` | 无条件 | 非 Anthropic 模型自动 ignore |
| 9 | `_PermissionMiddleware(rules=permissions, backend=backend)` | `if permissions:` | **必须最后**，看到所有前面注入的工具 |

**关键观察**：gp_middleware 不含 SubAgentMiddleware（递归会无限）也不含 MemoryMiddleware（subagent 不维护独立 memory）。

### 2.2 subagent_middleware（用户自定义 inline subagent，逐个装配）

| # | 中间件 | 条件 | 与 gp 的差异 |
| --- | --- | --- | --- |
| 1 | `TodoListMiddleware()` | 无条件 | 同 gp |
| 2 | `FilesystemMiddleware(backend, custom_tool_descriptions=_subagent_profile.tool_description_overrides)` | 无条件 | profile 是 **subagent 自己的** `_subagent_profile`（基于 subagent's own model）|
| 3 | `create_summarization_middleware(subagent_model, backend)` | 无条件 | model 是 subagent 自己的 model |
| 4 | `PatchToolCallsMiddleware()` | 无条件 | 同 gp |
| 5 | `SkillsMiddleware(backend, sources=subagent_skills)` | `if subagent_skills:` | spec.get("skills") |
| 6 | `*spec.get("middleware", [])` | spec 提供 | **subagent 用户自定义 middleware** |
| 7 | `*_resolve_extra_middleware(_subagent_profile)` | profile 提供 | 用 subagent 自己的 profile |
| 8 | `_ToolExclusionMiddleware(excluded=...)` | `if _subagent_profile.excluded_tools` | 同上 |
| 9 | `AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")` | 无条件 | 同 gp |
| 10 | `_PermissionMiddleware(rules=subagent_permissions, backend=backend)` | `if subagent_permissions:` | `subagent_permissions = spec.get("permissions", permissions)`（继承父或子覆盖）|

**关键观察**：subagent 装配顺序 = gp 顺序 + 第 6 行用户自定义 middleware 插入。

### 2.3 deepagent_middleware（主 agent）

| # | 中间件 | 条件 | 与 gp 的关键差异 |
| --- | --- | --- | --- |
| 1 | `TodoListMiddleware()` | 无条件 | 同 gp |
| 2 | `SkillsMiddleware(backend, sources=skills)` | `if skills is not None` | **位置提前到 #2**（gp 中 SkillsMiddleware 在 #5）|
| 3 | `FilesystemMiddleware(backend, custom_tool_descriptions=...)` | 无条件 | |
| 4 | `SubAgentMiddleware(backend, subagents=inline_subagents, task_description=...)` | 无条件（gp 中没有！） | 主 agent 专属；inline_subagents 已含 default GP + 用户自定义 |
| 5 | `create_summarization_middleware(model, backend)` | 无条件 | |
| 6 | `PatchToolCallsMiddleware()` | 无条件 | |
| 7 | `AsyncSubAgentMiddleware(async_subagents=async_subagents)` | `if async_subagents:` | async subagents 走另一通道 |
| 8 | `*middleware`（用户传入的 middleware 列表） | `if middleware:` | **用户中间件位置**（路径 B #3 BinaryDocConverter 应在此）|
| 9 | `*_resolve_extra_middleware(_profile)` | profile 提供 | 在用户 middleware 之后，memory 之前——保护 prompt cache 前缀 |
| 10 | `_ToolExclusionMiddleware(excluded=...)` | `if _profile.excluded_tools` | |
| 11 | `AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")` | 无条件 | |
| 12 | `MemoryMiddleware(backend, sources=memory, add_cache_control=True)` | `if memory is not None` | 最后注入 system prompt——不影响前面 cache |
| 13 | `HumanInTheLoopMiddleware(interrupt_on=interrupt_on)` | `if interrupt_on is not None` | HITL 接近末尾 |
| 14 | `_PermissionMiddleware(rules=permissions, backend=backend)` | `if permissions:` | **必须最绝对最后** |

**关键观察**：
- 主 agent 的 SkillsMiddleware 位置（#2）比 gp（#5）靠前
- 主 agent 独有 `SubAgentMiddleware`、`AsyncSubAgentMiddleware`、`MemoryMiddleware`、`HumanInTheLoopMiddleware`
- 装配顺序对 prompt cache 工作至关重要（注释解释了 user middleware → extra → memory 顺序）

---

## 3. 完整条件分支清单（Plan H 复制清单）

| 输入参数 | 影响装配 |
| --- | --- |
| `model: str \| BaseChatModel \| None` | resolve → BaseChatModel；驱动 `_harness_profile_for_model` |
| `tools: Sequence \| None` | `_apply_tool_description_overrides` 重写描述 |
| `system_prompt: str \| SystemMessage \| None` | 与 profile.base_system_prompt + suffix 拼接 |
| `middleware: Sequence` | 插入主 agent stack 第 8 位（用户 middleware 位置）|
| `subagents: Sequence` | 拆分为 inline_subagents 和 async_subagents |
| `skills: list[str] \| None` | gp.append(SkillsMiddleware) + main.append(SkillsMiddleware) |
| `memory: list[str] \| None` | main.append(MemoryMiddleware) |
| `permissions: list[FilesystemPermission] \| None` | gp/subagent/main 各自末尾 _PermissionMiddleware |
| `backend: BackendProtocol \| None` | None → StateBackend()；用于所有 middleware |
| `interrupt_on: dict \| None` | gp/subagent.spec[interrupt_on] + main.append(HITL) |
| `response_format` / `context_schema` / `checkpointer` / `store` / `debug` / `name` / `cache` | 全部透传给 `create_agent` |

---

## 4. profile-specific 影响点（HarnessProfile）

`_get_harness_profile(model_spec, model)` 返回 profile。profile 影响：

1. **`tool_description_overrides: dict[str, str]`** — 工具描述被重写（OpenRouter 等 profile 用）
2. **`extra_middleware: callable | list`** — 额外注入的 middleware（OpenAI Responses API、OpenRouter Attribution 等）
3. **`excluded_tools: set[str]`** — 被剥离的工具集合（→ `_ToolExclusionMiddleware`）
4. **`base_system_prompt: str | None`** — 替代 `BASE_AGENT_PROMPT`
5. **`system_prompt_suffix: str | None`** — 追加到 base prompt 后

**对 Plan H 的影响**：pmagent 装配代码必须正确处理 profile 解析 + 装配点注入。subagent 装配时需要根据 subagent 的 model 重新查 profile（`_subagent_profile`）。

---

## 5. inline_subagents 默认 general-purpose 注入逻辑

```python
# upstream graph.py:546-549
if not any(spec["name"] == GENERAL_PURPOSE_SUBAGENT["name"] for spec in inline_subagents):
    inline_subagents.insert(0, general_purpose_spec)
```

**含义**：如果用户传入的 subagents 中没有名字叫"general-purpose"的，自动在列表首位插入 default GP subagent。

**对 Plan H 的影响**：pmagent 需要复制这个 default insertion 逻辑（除非 pmagent 永远显式指定自己的 GP subagent，但这又增加 pmagent 工作）。

---

## 6. final create_agent 调用 + with_config

```python
return create_agent(
    model,
    system_prompt=final_system_prompt,
    tools=_tools,
    middleware=deepagent_middleware,
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
        "ls_integration": "deepagents",
        "versions": {"deepagents": __version__},
        "lc_agent_name": name,
        # ...
    },
})
```

**关键点**：
- recursion_limit 9_999 是 deepagents 特有
- LangSmith metadata 注入（`ls_integration`、versions 等）
- pmagent 走 Plan H 时必须复制这些配置

---

## 7. Plan H 复制工作量预估（步骤 3 输入）

按上述实测：

| 工作 | 估时（pmagent 步骤 3） |
| --- | --- |
| 复制 gp_middleware 装配（9 步骤 + 条件分支）| 30 min |
| 复制 subagent_middleware 装配（10 步骤 + 6 个 subagent 适配）| 60 min |
| 复制 deepagent_middleware 装配（14 步骤 + 条件分支）| 45 min |
| profile 解析 + extra_middleware 处理 | 15 min |
| inline_subagents 默认 GP 注入 + async 拆分 | 15 min |
| system_prompt 组装 + final create_agent + with_config | 15 min |
| 集成 V2 子类（5 个：SkillsV2、SubAgentObs、SummarizationGuard、BinaryDocConverter、Option M）| 30 min |
| pmagent 实际配置适配（PMAgentState、6 个 subagents、harness profiles）| 30 min |
| **合计** | **~4 小时**（pmagent 步骤 3 实测验证目标 2 小时是否够）|

**重要**：如果实际接近 4 小时，**Plan H 的"装配负担"是真的**——这就是决策矩阵该用 v4-rev3 的信号。

---

## 8. 已知陷阱（pmagent 步骤 3 必读）

1. **subagent 的 profile 不是父 profile** — subagent 用自己的 model 查自己的 profile（`_subagent_profile`），不要错用 `_profile`
2. **`_PermissionMiddleware` 必须每个栈最后一位** — 不能用 list.extend 插中间
3. **AnthropicPromptCachingMiddleware 无条件加** — 即使非 Anthropic 模型；它内部判断
4. **MemoryMiddleware 必须在 user middleware + extra_middleware 之后** — 否则破坏 prompt cache 前缀（注释明示）
5. **SkillsMiddleware 在 gp 是 #5，在 main 是 #2** — 位置不对称，不要用同一函数装配
6. **TodoListMiddleware 总是首位** — 没条件
7. **interrupt_on 在 subagent 走 spec["interrupt_on"]，在 main agent 走 HITL middleware** — 两条不同路径
8. **inline_subagents 第一位是 default GP**（如果用户没显式定义同名）—— 不是 append

---

## 9. 步骤 1 交付完成

下一步：步骤 2（写 Plan H 参考模板）→ 同目录下 `2026-05-02-planh-step2-reference-template.py`
