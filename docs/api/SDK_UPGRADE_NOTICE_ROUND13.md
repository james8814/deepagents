# DeepAgents SDK 升级说明 — Round 13

**日期**: 2026-04-12
**适用对象**: 使用 DeepAgents SDK 的外部研发团队
**SDK 版本**: 0.5.0
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

## 0. 外部团队适配指南（建议顺序）

这一节面向“怎么做升级适配”，尽量把信息组织成可执行步骤。后续第 1-5 节是变更细节，第 6-9 节是废弃项与 API 清单。

### 0.1 影响自检（先判断你是否需要改代码）

| 你现在的用法 | 影响级别 | 你需要做什么 |
| --- | --- | --- |
| 仅使用 `create_deep_agent(...)` + 默认 backend，未自定义 `StoreBackend(namespace=...)` | 无影响 | 升级依赖后跑测试即可 |
| 使用 OpenRouter（`model="openrouter:..."`） | 需确认 | 确保 `langchain-openrouter>=0.2.0`，否则 `resolve_model(...)` 会在运行时报错 |
| 自定义 `StoreBackend(namespace=...)` | 需迁移 | 把 `lambda ctx: ...` 改为 `lambda rt: ...`，并通过预发/灰度观察 `DeprecationWarning` 是否消失 |
| 自定义 middleware 且依赖“谁在最后/谁先执行”的栈顺序 | 需确认 | 对照第 2.4 节（11→14 层）检查你的逻辑是否依赖旧顺序；重点关注工具过滤与权限层新增 |
| 想要新增文件访问控制 | 新能力 | 按第 1 节引入 `permissions=[FilesystemPermission(...)]`，并按 0.3 的验收点做灰度观察 |
| 使用 `deepagents init/dev/deploy` | 新能力 | 按第 5 节准备项目布局与配置，优先用 `--dry-run` 验证产物 |

### 0.2 升级步骤（从可回滚到可发布）

1. 升级 DeepAgents SDK 到 0.5.0，并保持依赖锁可回滚（requirements/uv lock 等）
2. 运行单测与静态检查（见第 8.4 节），确保升级后“功能不退化”
3. 扫描并清理 `DeprecationWarning`（见第 6 节）：
   - 优先处理 `StoreBackend(namespace=...)` 的签名迁移（第 3 节）
   - 若你实现了自定义 backend：把 `ls_info/glob_info/grep_raw` 迁移到 `ls/glob/grep`（第 6 节）
4. 若你使用 OpenRouter：先验证版本要求（第 2.6 节），再在预发环境运行一次包含模型调用的用例
5. 若你引入 `permissions`：从最小 deny 规则开始灰度（例如先 deny `/secrets/**` 的写入或读取），观察工具失败率与“静默过滤”是否符合预期（第 1.3 / 8.5）
6. 若你使用 deploy：先 `deepagents deploy --dry-run` 生成 bundle 并检查产物，再走平台发布流程（第 5 节）

### 0.3 验收标准（研发主管/负责人可直接用）

- 单测全绿：升级前后用例结果一致（除非你引入了新的 deny 权限规则）
- 无新增错误告警：允许出现预期的 `DeprecationWarning`（迁移完成后应消失）
- 工具行为一致：`ls/glob/grep` 返回的路径集合在“无权限 deny”时与升级前一致；启用 deny 后仅表现为被过滤/被拒绝
- 回滚可行：能在不改业务代码的情况下切回旧依赖锁（必要时先将 `permissions` 置空/关闭）

### 0.4 常见报错/现象速查（外部团队排障）

| 现象/报错 | 典型原因 | 处理建议 |
| --- | --- | --- |
| `deepagents requires langchain-openrouter>=0.2.0, but ... is installed` | OpenRouter 版本过低 | `pip install 'langchain-openrouter>=0.2.0'`（见 2.6） |
| `Windows absolute paths are not supported: C:\\...` | 工具参数传入了 Windows 盘符路径 | 统一改为虚拟绝对路径（以 `/` 开头），例如 `/workspace/file.txt`（见 1.6.2） |
| `Path traversal not allowed: ~...` / `../...` | 工具参数含 `~` 或 `..` | 传入 `/...` 的虚拟绝对路径，不使用 home/相对路径（见 1.6.2） |
| `DeprecationWarning: Passing a callable (factory) as backend is deprecated` | 给 `FilesystemMiddleware(backend=...)` 传了 factory callable | 直接传 `BackendProtocol` 实例（如 `StateBackend()`）（见第 6 节） |

### 0.5 术语对照（快速扫一遍，降低沟通成本）

| 术语 | 含义 | 在本文出现位置 |
| --- | --- | --- |
| backend | 文件/状态存储后端（State/Filesystem/Store/Composite 等），为工具提供 `ls/read/write/...` 能力 | 第 1/3/4 节 |
| Runtime | LangGraph 的运行时上下文对象，提供服务端与用户标识等信息 | 第 3 节 |
| CompositeBackend route | 以路由前缀（如 `/workspace/`）把不同路径分发到不同 backend | 第 1.4 节 |
| 虚拟路径 | 统一使用以 `/` 开头的路径语义（与真实 OS 路径解耦），工具会先做 `validate_path()` 规范化 | 第 1.6 节 |
| Harness Profile | provider 级配置注册表（默认参数/extra middleware/工具过滤） | 第 2 节 |

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

本轮涉及两类“路径”校验：一类发生在 **权限规则构造时**（校验 `FilesystemPermission.paths`），另一类发生在 **工具调用运行时**（校验工具参数里的 `file_path` / `path`）。

#### 1.6.1 权限规则构造时（`FilesystemPermission.__post_init__`）

对每条规则的 `paths` 做轻量校验（不做规范化）：

- 必须以 `/` 开头，否则抛出 `ValueError`
- 路径组件中出现 `..`，抛出 `ValueError`
- 路径中出现名为 `~` 的路径组件（例如 `/~`、`/~/...`），抛出 `NotImplementedError`（权限规则不支持 `~` 语义）

注意：这里 **不检查** Windows 盘符路径（如 `C:\\...` / `D:/...`），因为权限规则 `paths` 的语义是“虚拟路径的 glob pattern”，推荐始终使用 POSIX 风格的绝对虚拟路径（例如 `/workspace/**`）。

#### 1.6.2 工具运行时（`validate_path()`）

权限匹配前会对工具参数路径做 `validate_path()` 规范化与安全校验（虚拟路径语义）：

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

### 1.8 适配建议（外部团队落地）

- 从最小 deny 开始：优先 deny 明确敏感目录（例如 `/secrets/**`、`/credentials/**`），避免一上来全盘 deny 导致大量工具失败。
- 把“工作区”显式 allow：如果你的业务约定只允许在 `/workspace/**` 写入，建议同时加一条 write allow 规则，让意图更清晰（并避免未来默认策略变化时出现意外）。
- 正确理解“静默过滤”：当 `ls/glob/grep` 命中 deny 路径时，结果会被过滤，而不是返回错误；这是为了不泄露路径存在性。排障时可先临时移除 deny 规则，确认行为差异是否来自权限过滤。

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

### 2.7 适配建议（外部团队落地）

- 统一 `provider:model`：这会触发 provider profile（默认参数、extra middleware、工具过滤等）。对多 provider 混用的服务，建议强制规范化（例如配置层统一补全前缀）。
- 不要依赖“工具一定存在”：provider profile 可能通过 `_ToolExclusionMiddleware` 过滤某些工具，让它们不出现在模型可见的工具列表中。若你的业务逻辑假设某个工具必然可用，应在调用前做能力检测/降级策略。

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

#### 3.2.1 如何定位你是否受影响（建议先做这一步）

- 全仓搜索 `StoreBackend(` 并检查是否有 `namespace=` 参数
- 如果你能看到类似 `lambda ctx:`、`ctx.runtime`、`ctx.state`，说明你在使用旧签名（需要迁移）

迁移时的原则：

- 旧代码里如果只用到了 `ctx.runtime`，通常可以直接把 `ctx.runtime.<...>` 改为 `rt.<...>`
- 若你依赖了 `ctx.state`（旧 wrapper 暴露的便捷字段），请显式改为从 `rt` 获取你需要的信息；不要继续依赖 compat wrapper 的“鸭子类型”行为（它会在 v0.7 移除）

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

### 4.3 示例（外部团队最常见两种用法）

```python
from deepagents.backends import StateBackend

backend = StateBackend()

# 用法 A：在图/运行时上下文内（工具调用、middleware、graph node 等）可以直接用 upload_files()
# backend.upload_files([...])  # 具体参数以你的调用点为准
```

```python
# 用法 B：在运行时上下文外（例如你想在启动阶段/独立脚本里上传）
# 仍应使用 upload_adapter 并显式提供 runtime
from deepagents.upload_adapter import upload_files

# upload_files(..., runtime=rt)  # runtime 必填；没有 runtime 就无法定位 state 写入位置
```

---

## 5. CLI 新功能

### 5.1 `deepagents deploy` 命令

从 `deepagents.toml` 配置文件生成 LangGraph 服务部署包。

注意：`deepagents init` / `deepagents dev` / `deepagents deploy` 均为 beta 能力，配置格式与行为可能在后续版本中调整。

```bash
# 初始化（生成 deepagents.toml / AGENTS.md / .env / mcp.json / skills/）
deepagents init

# 本地运行 langgraph dev（用于联调）
deepagents dev --port 2024

# 部署到 LangGraph Platform（支持 --dry-run 只生成不部署）
deepagents deploy --dry-run
```

常用参数:

- `deepagents init <name> --force`：覆盖已存在的同名目录/文件
- `deepagents dev --config /path/to/deepagents.toml`：显式指定配置路径（否则默认在当前目录查找 `deepagents.toml`；不会向上遍历父目录）
- `deepagents deploy --config /path/to/deepagents.toml`：显式指定配置路径（否则默认在当前目录查找 `deepagents.toml`；不会向上遍历父目录）

关键约束（对外部团队最常踩坑的点）:

- `AGENTS.md` 是必需项：既是 system prompt，也是 deploy bundler 的 memory seed 来源；部署生成的 graph 会将其注入到只读 memory 路由（写入/编辑会被拦截）。
- `mcp.json` 是可选项：仅支持 `http`/`sse` 类型的 MCP server；`stdio` 在部署上下文不支持。`deepagents init` 会生成一个空的 `mcp.json`，不用的话可以删除。
- `.env` 是可选项：用于本地 dev/deploy 时注入环境变量；打包时会单独复制到产物目录，不会写入 `_seed.json`（避免把密钥混进 seed）。

产物对照（便于 code review / 安全审计）：

| 输入（项目目录） | 产物（bundle 目录） | 说明 |
| --- | --- | --- |
| `AGENTS.md` | `_seed.json` | 作为 memory seed 注入（只读路由） |
| `skills/` | `_seed.json` | 作为 skills seed 注入（只读路由） |
| `mcp.json`（可选） | `_mcp.json` | 被重命名后随 bundle 携带；仅 http/sse |
| `.env`（可选） | `.env` | 会复制到产物目录，但不会写进 `_seed.json` |
| `deepagents.toml` | `deploy_graph.py` / `langgraph.json` / `pyproject.toml` | 作为生成图与部署描述的输入 |

配置文件示例:

```toml
# deepagents.toml
[agent]
name = "my-agent"
model = "anthropic:claude-sonnet-4-6"
```

如果你需要 sandbox（例如代码执行或特定运行环境），再添加 `[sandbox]` 段；不写时等价于 `provider="none"`，会退化为进程内 `StateBackend`（`execute` 工具不可用/为 no-op）：

```toml
[sandbox]
provider = "none"            # none | langsmith | daytona | modal | runloop
scope = "thread"             # thread | assistant
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
| 6 | `FilesystemMiddleware(backend=callable)`（backend factory callable） | 直接传 `BackendProtocol` 实例（例如 `StateBackend()`） | Round 10 |

---

## 7. 依赖更新

以下版本为 DeepAgents 官方依赖锁定（以本仓库 `libs/deepagents/uv.lock` 为准）。外部团队的当前版本可能不同，建议以“是否使用对应能力”为准进行升级。

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| `cryptography` | 46.0.7 | 安全修复 |
| `langchain-core` | 1.2.28 | 功能更新 |
| `langchain-openrouter` | >=0.2.0 | 仅 OpenRouter 用户需要；版本过低会在 `resolve_model("openrouter:...")` 时报错 |

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
