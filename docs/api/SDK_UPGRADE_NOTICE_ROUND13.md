# DeepAgents SDK 升级说明 — Round 13

**日期**: 2026-04-12
**适用对象**: 使用 DeepAgents SDK 的外部研发团队
**SDK 版本**: 0.5.0（版本号不变）
**涵盖变更**: Round 13 (2026-04-12)

---

## 快速总结

本次升级包含 **3 项新增子系统**、**2 项本轮新增废弃预告 + 4 项历史遗留废弃项汇总**（均计划 v0.7 移除）和多项向后兼容增强。

**新增子系统**:

1. **Permissions 文件系统访问控制** — 声明式 `FilesystemPermission` 规则
2. **Harness Profiles 提供商配置体系** — `_HarnessProfile` 注册表取代硬编码分支
3. **CLI Deploy 命令** — `deepagents deploy` 一键部署到 LangGraph Platform

**必须关注**:

1. `resolve_model()` 行为变更 — 现在通过 Profile 注册表驱动，不再是 if-else 分支
2. `StoreBackend` namespace factory 签名变更 — 旧签名仍可用但发出 DeprecationWarning
3. 中间件栈新增 3 层 — 如果你有依赖栈顺序的自定义中间件，需确认兼容性
4. `model` 建议统一使用 `provider:model`（如 `anthropic:claude-sonnet-4-6`）以启用 provider 级 profile（extra middleware / 默认参数等）

**不影响你的代码（如果你没有做以下事情）**:

- 依赖 `resolve_model()` 的内部实现细节（例如假设某些 provider 的默认 kwargs 来自 if-else 分支）
- 自定义 `StoreBackend` namespace factory
- 依赖中间件栈的精确位置关系

---

## 1. Permissions 文件系统访问控制（新增）

### 1.1 概述

新增 `FilesystemPermission` 数据类和 `_PermissionMiddleware`，提供声明式文件系统访问控制。

### 1.2 使用方式

```python
from deepagents import create_deep_agent, FilesystemPermission

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    permissions=[
        # 禁止读取 /secrets/ 下的所有文件
        FilesystemPermission(operations=["read"], paths=["/secrets/**"], mode="deny"),
        # 允许写入 /workspace/ 下的所有文件
        FilesystemPermission(operations=["write"], paths=["/workspace/**"], mode="allow"),
        # 禁止写入配置文件
        FilesystemPermission(operations=["write"], paths=["/config/*.yaml"], mode="deny"),
    ],
)
```

### 1.3 核心语义

| 特性 | 说明 |
| --- | --- |
| 评估顺序 | **First-match-wins** — 规则按声明顺序评估，第一条匹配的规则生效 |
| 默认策略 | **Permissive** — 无匹配规则时允许操作 |
| 操作类型 | `read`（ls, read_file, glob, grep）/ `write`（write_file, edit_file） |
| 路径匹配 | 使用 `wcmatch.glob`，支持 `*`、`**`、`?` 通配符 |
| Pre-check | write/edit/read 违规 → 返回 error ToolMessage |
| Post-filter | ls/glob/grep 结果中 deny 路径被静默过滤（不泄露路径存在性） |

### 1.4 CompositeBackend 路由感知

```python
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend

composite = CompositeBackend(
    default=StateBackend(),
    routes={"/workspace/": FilesystemBackend(root_dir="/workspace")},
)

agent = create_deep_agent(
    backend=composite,
    permissions=[
        # 规则 scoped 到 /workspace/ 路由
        FilesystemPermission(operations=["read"], paths=["/workspace/secrets/**"], mode="deny"),
    ],
)
```

如果你的 backend 具备命令执行能力（实现 `SandboxBackendProtocol`，即 `execute` 工具可用），权限系统 **目前不支持** 对 `execute` 做工具级权限控制：

- 对普通可执行 backend：传入 `permissions` 会抛出 `NotImplementedError`
- **例外**：当使用 `CompositeBackend` 且 default backend 可执行时，只要你配置的所有 permission `paths` 都严格 scoped 在某个 `routes` 前缀下（权限只作用在路由 backend 上），则允许启用权限系统

### 1.5 SubAgent 权限继承

```python
# SubAgent 默认继承父代理的 permissions
# 可以覆盖：
agent = create_deep_agent(
    permissions=[...],  # 父代理规则
    subagents=[
        {
            "name": "restricted-agent",
            "description": "...",
            "system_prompt": "...",
            "permissions": [  # 覆盖父代理规则
                FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
            ],
        },
    ],
)
```

### 1.6 路径校验

权限匹配前会对路径做 `validate_path()` 规范化与安全校验（虚拟路径语义）：

- 规范化：自动补全前导 `/`、折叠重复分隔符、移除 `.` 等冗余片段（例如 `foo//bar` → `/foo/bar`）
- 禁止穿越：路径组件中出现 `..` 会抛出 `ValueError`
- 禁止 home 语义：路径以 `~` 开头会抛出 `ValueError`
- 禁止 Windows 盘符路径：如 `C:\\...` / `D:/...` 会抛出 `ValueError`

注意：工具层仍要求传入绝对虚拟路径（以 `/` 开头）。虽然规范化会补全前导 `/`，但外部团队仍应避免传相对路径，以免与不同工具/后端的校验规则产生差异。

### 1.7 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 未使用 `permissions` 参数 | **无影响** | 无需操作 |
| 想要限制 agent 文件访问 | **新功能** | 传入 `permissions` 参数 |
| 自定义 `FilesystemMiddleware` | **低风险** | `_PermissionMiddleware` 在栈末尾，不影响上游工具 |

---

## 2. Harness Profiles 提供商配置体系（新增，内部 API）

### 2.1 概述

新增 `_HarnessProfile` 注册表，替代 `_models.py` 和 `graph.py` 中散布的 `if model.startswith(...)` 硬编码分支。

> **注意**: 这是 **内部 API**（下划线前缀），不面向外部使用。但其行为变更可能间接影响你的代码。

### 2.2 行为变更

**之前** (`resolve_model`):

```python
# 内部硬编码:
if model.startswith("openai:"):
    base_url = _openai_base_url()
    use_responses_api = True if not custom_base else False
    return init_chat_model(model, use_responses_api=use_responses_api)
if model.startswith("openrouter:"):
    check_openrouter_version()
    return init_chat_model(model, **_openrouter_attribution_kwargs())
return init_chat_model(model)
```

**之后** (`resolve_model`):

```python
# Profile 驱动:
profile = _get_harness_profile(model)
if profile.pre_init is not None:
    profile.pre_init(model)  # e.g. check_openrouter_version
kwargs = {**profile.init_kwargs}
if profile.init_kwargs_factory is not None:
    kwargs.update(profile.init_kwargs_factory())
return init_chat_model(model, **kwargs)
```

### 2.3 新增中间件层

| 中间件 | 位置 | 作用 |
| --- | --- | --- |
| Profile `extra_middleware` | User middleware 之后 | Provider-specific 中间件注入 |
| `_ToolExclusionMiddleware` | extra_middleware 之后 | 按 profile 配置过滤工具（provider 不支持的工具不发给模型） |

### 2.4 中间件栈变更（11 → 14 层）

```text
Round 12 (11 层):              Round 13 (14 层):
1. TodoList                    1. TodoList
2. Skills                      2. Skills
3. Filesystem                  3. Filesystem
4. SubAgent                    4. SubAgent
5. Summarization               5. Summarization
6. PatchToolCalls              6. PatchToolCalls
7. AsyncSubAgent               7. AsyncSubAgent
8. User middleware              8. User middleware
                               9. Profile extra_middleware  ← NEW
                              10. _ToolExclusionMiddleware  ← NEW
9. AnthropicCache             11. AnthropicCache
10. Memory                    12. Memory
11. HITL                      13. HITL
                              14. _PermissionMiddleware     ← NEW (must be last)
```

### 2.5 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 使用不带 provider 的字符串 model（如 `"claude-sonnet-4-6"`） | **需确认** | 建议改为 `anthropic:claude-sonnet-4-6` 以启用 provider profile（extra middleware / 默认参数）；是否可继续裸名称取决于 `langchain.init_chat_model` 的自动识别能力 |
| 传入 `BaseChatModel` 实例 | **无影响** | Profile 通过 `model_dump` 回查 |
| 自定义 middleware 依赖栈位置 | **低风险** | 你的 middleware 在 [8]，新增层在 [9-10]，Cache/Memory/HITL 位置不变 |
| 直接调用 `resolve_model()` | **行为一致** | 函数签名不变，内部实现改为 profile 驱动 |
| 使用 OpenRouter provider | **需确认** | `langchain-openrouter>=0.2.0` 是新的硬性要求 |

### 2.6 OpenRouter 版本要求

```text
langchain-openrouter >= 0.2.0  (之前无硬性版本要求)
```

如果使用 OpenRouter 且安装了旧版，`resolve_model("openrouter:...")` 会抛出 `ImportError`。
如果未安装 `langchain-openrouter`，版本检查会跳过；后续由 `init_chat_model` 抛出缺失依赖相关错误。

**修复**: `pip install 'langchain-openrouter>=0.2.0'`

---

## 3. Namespace Factory 重构（废弃预告）

### 3.1 变更内容

`StoreBackend` 的 namespace factory 签名从接收 `BackendContext` 改为直接接收 `Runtime`。

### 3.2 迁移

```python
# 旧签名 (deprecated, v0.7 移除):
StoreBackend(
    namespace=lambda ctx: (ctx.runtime.context.user_id, "fs"),
)

# 新签名:
StoreBackend(
    namespace=lambda rt: (rt.server_info.user.identity, "fs"),
)
```

### 3.3 兼容层

`_NamespaceRuntimeCompat` 类同时 duck-type 为 `Runtime` 和 `BackendContext`。旧签名访问 `.runtime` 或 `.state` 时发出 `DeprecationWarning`。

### 3.4 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 使用 `StateBackend`（默认） | **无影响** | 不涉及 namespace |
| 使用 `FilesystemBackend` | **无影响** | 不涉及 namespace |
| 使用 `StoreBackend` 无自定义 namespace | **无影响** | 默认 namespace 自动迁移 |
| 使用 `StoreBackend` + 自定义 namespace factory | **需迁移** | 更新 lambda 签名 |

---

## 4. StateBackend.upload_files()（新增）

### 4.1 变更内容

`StateBackend` 现在原生支持 `upload_files()` 方法。之前必须通过 `upload_adapter` 间接路由。

### 4.2 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 在图执行上下文中使用 `StateBackend.upload_files()`（例如通过 `create_deep_agent` 运行时） | **新能力** | 可直接调用 `backend.upload_files()` |
| 在图执行上下文之外上传到 `StateBackend` | **仍需迁移/注意** | 使用 `deepagents.upload_adapter.upload_files(..., runtime=...)`，`runtime` 是必需参数 |
| 使用 `upload_adapter` | **无影响** | adapter 仍然可用；对 `StateBackend` 仍然要求提供 `runtime` |

---

## 5. CLI 新功能

### 5.1 `deepagents deploy` 命令

从 `deepagents.toml` 配置文件生成 LangGraph 服务部署包。

```bash
# 初始化（生成 deepagents.toml / AGENTS.md / .env / mcp.json / skills/）
deepagents init

# 本地运行 langgraph dev（用于联调）
deepagents dev --port 2024

# 部署到 LangGraph Platform（支持 --dry-run 只生成不部署）
deepagents deploy --dry-run
```

配置文件示例:

```toml
# deepagents.toml
[agent]
name = "my-agent"
model = "anthropic:claude-sonnet-4-6"

[sandbox]
provider = "none"
scope = "thread"
template = "deepagents-deploy"
image = "python:3"
```

### 5.2 `/notifications` 命令

CLI 内置通知设置 UI，配置工具调用时的通知偏好。

### 5.3 Provider 凭证快速失败

缺少 provider API key 时立即报错，不再静默进入无法调用模型的状态。

### 5.4 `AGENTS.md` 去重修复

修复了 `AGENTS.md` 内容被注入系统提示两次的 bug。

---

## 6. 废弃预告汇总（v0.7 移除）

| # | 废弃项 | 替代方案 | 来源 |
| --- | --- | --- | --- |
| 1 | `BackendContext` wrapper | 直接使用 `Runtime` | Round 13 |
| 2 | `StoreBackend` 旧 namespace factory 签名 | `lambda rt: ...` | Round 13 |
| 3 | `WriteResult.files_update` | 内部处理 | Round 10 |
| 4 | `ls_info()` / `glob_info()` / `grep_raw()` | `ls()` / `glob()` / `grep()` | Round 10 |
| 5 | `SubAgentMiddleware(default_model=...)` | `subagents=[...]` | Round 11 |
| 6 | `StateBackend(runtime)` factory callable | `StateBackend()` | Round 10 |

---

## 7. 依赖更新

| 依赖 | 旧版本 | 新版本 | 类型 |
| --- | --- | --- | --- |
| `cryptography` | 46.0.6 | 46.0.7 | 安全修复 |
| `langchain-core` | 1.2.27 | 1.2.28 | 功能更新 |
| `langchain-openrouter` | (无硬性要求) | >=0.2.0 | **新增硬性要求**（仅 OpenRouter 用户） |

---

## 8. 升级检查清单

### 8.1 必须检查

- [ ] 如果使用 OpenRouter：确认 `langchain-openrouter>=0.2.0`
- [ ] 如果自定义 `StoreBackend` namespace factory：迁移为新签名
- [ ] 如果自定义 middleware 依赖栈位置：确认新增 3 层不影响逻辑

### 8.2 建议检查

- [ ] 运行完整测试套件，确认无回归
- [ ] 如果需要文件访问控制：评估引入 `permissions` 参数
- [ ] 如果多 provider 混用：确认 harness profiles 自动匹配正确
- [ ] 更新内部文档说明中间件栈变更（11→14 层）
- [ ] 灰度升级：先在 CI + 预发/小流量环境验证，观察 `DeprecationWarning` 与工具调用行为，再全量推广
- [ ] 回滚预案：保留可快速切回旧 SDK 的依赖锁定（requirements/uv lock），并确保新引入的 `permissions` 可通过配置关闭

### 8.3 无需操作

- [ ] `create_deep_agent()` 签名向后兼容（新参数均有默认值）
- [ ] `resolve_model()` 函数签名不变
- [ ] `SubAgent` TypedDict 新增 `permissions` 字段为 `NotRequired`
- [ ] `FilesystemPermission` 是新类型，不影响现有代码

### 8.4 推荐验证步骤（研发主管）

```bash
# 1) 跑单测（避免网络依赖）
make test

# 2) 跑静态检查（如你的仓库启用）
make lint
```

### 8.5 推荐发布策略（研发主管）

- Phase 0：锁定升级范围与责任人：哪些服务/仓库升级、哪些不升级；哪些路径启用 `permissions`，哪些保持默认 permissive
- Phase 1：CI 验证：单测 + lint 全绿，并确保无新增 `DeprecationWarning` 以外的告警
- Phase 2：预发/灰度：小流量环境观察工具调用失败率、文件工具结果是否被权限过滤（ls/glob/grep 的“静默过滤”属于预期行为）
- Phase 3：全量：通过配置开关逐步扩大 `permissions` 覆盖面；优先以 deny 保护敏感目录（如 `/secrets/**`）而不是一开始全盘 deny
- 回滚：保持依赖锁文件可快速切回；将 `permissions` 配置化（可置空/关闭）以快速解除策略误配带来的阻断

---

## 9. 完整 API 变更清单

### 9.1 新增类型

```python
from dataclasses import dataclass
from typing import Literal

from deepagents import FilesystemPermission

# FilesystemPermission 数据类
@dataclass
class FilesystemPermission:
    operations: list[Literal["read", "write"]]  # 可多选；规则仅在 operation 匹配时参与评估
    paths: list[str]  # Glob 路径模式列表 (e.g. ["/secrets/**"])
    mode: Literal["allow", "deny"] = "allow"
```

### 9.2 `create_deep_agent()` 新增参数

```python
def create_deep_agent(
    ...,
    permissions: list[FilesystemPermission] | None = None,  # NEW — 文件系统访问控制规则
    ...,
) -> CompiledStateGraph:
```

### 9.3 `SubAgent` TypedDict 新增字段

```python
class SubAgent(TypedDict):
    ...,
    permissions: NotRequired[list[FilesystemPermission]]  # NEW — 子代理权限规则（覆盖父代理）
```

### 9.4 `StoreBackend` namespace factory 签名变更

```python
# 旧 (deprecated):
StoreBackend(namespace=lambda ctx: (ctx.runtime.context.user_id, "fs"))
# 新:
StoreBackend(namespace=lambda rt: (rt.server_info.user.identity, "fs"))
```

### 9.5 新增内部模块（不面向外部使用）

| 模块 | 用途 |
| --- | --- |
| `deepagents.profiles._harness_profiles` | Profile 注册表 |
| `deepagents.profiles._openrouter` | OpenRouter 配置 |
| `deepagents.profiles._openai` | OpenAI 配置 |
| `deepagents.middleware._tool_exclusion` | 工具过滤中间件 |
| `deepagents.middleware.permissions` | 权限中间件 |

---

## 10. 技术联系

**问题反馈**: 请提交 GitHub Issue

**文档**:

- [Round 13 合并进度](../../docs/upstream_merge/ROUND13_PROGRESS.md)
- [Round 13 风险评估](../../docs/upstream_merge/ROUND13_RISK_ASSESSMENT.md)
- [Round 10+11 升级说明](./SDK_UPGRADE_NOTICE_ROUND10_11.md)
- [SkillsMiddleware V2 升级说明](./SDK_UPGRADE_GUIDE.md)
