# DeepAgents SDK 升级说明 — Round 14

**日期**: 2026-04-17
**适用对象**: 使用 DeepAgents SDK 的外部研发团队
**SDK 版本**: 0.5.0（版本号不变）
**涵盖变更**: Round 14 (2026-04-17)

---

## 快速总结

本次升级包含 **1 项新增能力**、**1 项废弃预告**、**1 项 CLI 部署增强** 和依赖升级。无架构级重构，中间件栈 14 层不变。

**新增能力**:

1. **SubAgent 结构化输出** — `SubAgent.response_format` 字段，支持 `ToolStrategy`/`ProviderStrategy`/`AutoStrategy`

**必须关注**:

1. `model=None` 废弃预告 — `create_deep_agent(model=None)` 将发出 `DeprecationWarning`
2. 如果使用 SkillsMiddleware V2（`expose_dynamic_tools=True`）— 本轮修正了 V1/V2 提示指令的一致性

**不影响你的代码（如果你没有做以下事情）**:

- 使用 `model=None` 调用 `create_deep_agent`
- 自定义 SubAgent 的结构化输出

---

## 1. SubAgent 结构化输出（新增）

### 1.1 概述

`SubAgent` TypedDict 新增 `response_format` 字段。当指定时，子代理将产出符合 schema 的 `structured_response`，并以 JSON 序列化后作为 `ToolMessage` 内容返回给父代理。

### 1.2 使用方式

```python
from pydantic import BaseModel

class Findings(BaseModel):
    findings: str
    confidence: float

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[
        {
            "name": "analyzer",
            "description": "Analyzes data and returns structured findings",
            "system_prompt": "Analyze the data and return your findings.",
            "model": "openai:gpt-4o",
            "tools": [],
            "response_format": Findings,  # NEW
        },
    ],
)
```

### 1.3 支持的策略

| 策略 | 用法 | 说明 |
| --- | --- | --- |
| `ToolStrategy(schema)` | 使用工具调用提取结构化输出 | 最广泛兼容 |
| `ProviderStrategy(schema)` | 使用 provider 原生结构化输出模式 | 依赖 provider 支持 |
| `AutoStrategy(schema)` | 自动选择最佳策略 | 推荐 |
| 裸 Python 类型 | `BaseModel` 子类 / `dataclass` / `TypedDict` | 等价于 `AutoStrategy(schema)` |
| `dict[str, Any]` | JSON Schema 字典 | 手动 schema 定义 |

### 1.4 JSON 序列化行为

返回给父代理的 `ToolMessage.content` 为 JSON 字符串：

- Pydantic `BaseModel` → `model.model_dump_json()`
- `dataclass` → `json.dumps(dataclasses.asdict(result))`
- 其他 → `json.dumps(result)`

### 1.5 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 未使用 `response_format` | **无影响** | 字段为 `NotRequired`，默认行为不变 |
| 想要子代理返回结构化数据 | **新功能** | 在 SubAgent spec 中添加 `response_format` |
| 已有 `skills_allowlist` 或 `permissions` | **无影响** | 三个字段互不干扰 |

---

## 2. `model=None` 废弃预告

### 2.1 变更内容

`create_deep_agent(model=None)` 现在会发出 `DeprecationWarning`。

```python
# 会触发 DeprecationWarning:
agent = create_deep_agent()  # model defaults to None
agent = create_deep_agent(model=None)

# 不会触发:
agent = create_deep_agent(model="anthropic:claude-sonnet-4-6")
agent = create_deep_agent(model=my_chat_model)
```

### 2.2 迁移

```python
# 之前:
agent = create_deep_agent()

# 之后:
agent = create_deep_agent(model="anthropic:claude-sonnet-4-6")
```

### 2.3 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 显式传入 `model` 参数 | **无影响** | — |
| 依赖默认 `model=None` | **需迁移** | 显式指定 model |
| 测试中大量使用默认 model | **低风险** | `pyproject.toml` 已配置 `filterwarnings` 抑制 |

---

## 3. CLI 部署增强: User Scoped Memory

### 3.1 概述

`deepagents deploy` 现在支持 per-user 可写 memory。每个用户获得独立的 `AGENTS.md`，可跨会话持久化偏好和上下文。

### 3.2 启用方式（Opt-in）

在项目目录中创建 `user/` 目录即可启用。不创建则 user memory 完全禁用。

```text
my-agent/
├── deepagents.toml
├── AGENTS.md          # 共享指令 (只读)
└── user/
    └── AGENTS.md      # per-user memory 模板 (运行时可写)
```

### 3.3 技术细节

- 路径: `/memories/user/AGENTS.md`
- 命名空间: `(assistant_id, user_id)` — 完全隔离
- `user_id` 来源: `runtime.user.identity`（自定义认证）
- 无 `user_id` 时: 静默跳过（不报错）

### 3.4 与 FilesystemPermission 的交互

如果你同时使用 `permissions` 和 user memory：

- `FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="deny")` **会阻止** user memory 写入
- 建议: 不要对 `/memories/user/**` 配置 deny write 规则，或使用更精确的 deny 路径（如 `/memories/AGENTS.md` 仅保护共享指令的只读性）

---

## 4. Skill Prompt 行为变更

### 4.1 变更内容

本轮修正了 SkillsMiddleware 的 prompt 指令一致性：

- **V1 模式** (`expose_dynamic_tools=False`, 默认): prompt 引导使用 `read_file(path, limit=1000)`
- **V2 模式** (`expose_dynamic_tools=True`): prompt 引导使用 `load_skill("skill-name")`

### 4.2 影响判断

| 场景 | 影响 | 操作 |
| --- | --- | --- |
| 使用默认 `expose_dynamic_tools=False` | **行为改善** | 模型现在被一致引导使用 `read_file + limit=1000`（不再出现不可用的 `load_skill` 提示） |
| 使用 `expose_dynamic_tools=True` | **行为改善** | 模型被一致引导使用 `load_skill`（不再出现 `read_file` 与 `load_skill` 的指令冲突） |

---

## 5. 依赖更新

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| `langsmith` | 0.7.31 | 功能更新（跨 11 个子包） |
| `pytest` | 9.0.3 | 测试框架更新 |
| `pillow` | 12.2.0 | 图像处理更新 |
| `python-multipart` | 0.0.26 | MIME 解析更新 |

---

## 6. 升级检查清单

### 必须检查

- [ ] 如果 `create_deep_agent()` 未显式传入 `model`: 添加显式 model 参数
- [ ] 运行完整测试套件，确认无回归

### 建议检查

- [ ] 如果需要子代理结构化输出: 评估引入 `response_format`
- [ ] 如果使用 `deepagents deploy` + user memory: 确认 permissions 不阻止 `/memories/user/**` 写入
- [ ] 更新内部文档说明 model=None 废弃

### 无需操作

- [ ] 中间件栈 14 层不变
- [ ] `SubAgent.response_format` 为 `NotRequired`，不影响现有 spec
- [ ] `permissions`、`skills_allowlist` 字段不受影响

---

## 7. 技术联系

**问题反馈**: 请提交 GitHub Issue

**文档**:

- [Round 14 合并进度](../../docs/upstream_merge/ROUND14_PROGRESS.md)
- [Round 14 风险评估](../../docs/upstream_merge/ROUND14_RISK_ASSESSMENT.md)
- [Round 13 升级说明](./SDK_UPGRADE_NOTICE_ROUND13.md)
