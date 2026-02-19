# DeepAgents SDK 升级说明

**版本**: V2.0
**日期**: 2026-02-18
**适用对象**: 使用 DeepAgents SDK 的外部研发团队

---

## 快速总结

**一句话**: SkillsMiddleware V2 是**向后兼容**的功能增强版，现有代码无需修改即可升级。

**核心变化**:
- ✅ **新增** `load_skill` / `unload_skill` 工具
- ✅ **新增** 上下文预算控制 (默认 10 个技能)
- ✅ **新增** 资源自动发现
- ✅ **保持** 所有现有 API 不变
- ✅ **保持** 现有 SKILL.md 文件兼容

---

## 1. 升级内容详解

### 1.1 新增功能

| 功能 | 说明 | 影响 |
| :--- | :--- | :--- |
| `load_skill` 工具 | 专用工具加载技能完整内容 | Agent 不再需要手动 `read_file` |
| `unload_skill` 工具 | 卸载已加载技能释放上下文 | 防止上下文溢出 |
| `[Loaded]` 标记 | 系统提示显示已加载技能 | Agent 清楚知道哪些技能已激活 |
| 资源发现 | 自动扫描 `scripts/`, `references/`, `assets/` | Agent 知道技能有哪些资源文件 |
| 上下文预算 | 默认最多 10 个同时加载技能 | 防止性能下降 |

### 1.2 与官方 Agent Skills 规范的差异

| 维度 | 官方规范 | DeepAgents V2 | 说明 |
| :--- | :--- | :--- | :--- |
| 技能加载 | 手动 | `load_skill` 工具 | 更灵活 |
| 技能卸载 | ❌ 不支持 | ✅ `unload_skill` | **DeepAgents 特有** |
| 资源发现 | 自动 | 延迟发现 | 性能优化 |
| 上下文预算 | 无限制 | `max_loaded_skills=10` | **DeepAgents 特有** |
| `allowed-tools` | 推荐语义 | 推荐语义 | 与规范一致 |

**重要**: DeepAgents 是基于 Agent Skills 规范的**扩展实现**，不是官方参考实现。

---

## 2. 兼容性保证

### 2.1 向后兼容

```python
# V1 代码无需修改，直接使用
from deepagents.middleware import SkillsMiddleware

middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills/"],
)
```

### 2.2 SKILL.md 文件格式

```yaml
# 现有 SKILL.md 文件无需任何修改
---
name: web-research
description: Structured approach to web research
license: MIT
---
```

### 2.3 状态字段扩展

V2 新增的状态字段（不影响现有代码）:

```python
class SkillsState(AgentState):
    skills_metadata: ...  # V1 已有
    skills_loaded: ...    # V2 新增 - 已加载技能列表
    skill_resources: ...  # V2 新增 - 资源缓存
```

---

## 3. 使用示例

### 3.1 基础使用（与 V1 相同）

```python
from deepagents import create_deep_agent
from deepagents.middleware import SkillsMiddleware
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    skills=["/path/to/skills/"],
    backend=FilesystemBackend(root_dir="/workspace"),
)
```

### 3.2 V2 新功能（可选）

```python
# Agent 现在可以使用专用工具
# load_skill("skill-name") - 加载技能
# unload_skill("skill-name") - 卸载技能

# 自定义上下文预算
middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills/"],
    max_loaded_skills=15,  # 默认 10，可调大/小
)
```

---

## 4. 升级检查清单

如果你的团队使用了 SkillsMiddleware，请确认：

- [ ] **现有代码** - 无需修改，直接兼容
- [ ] **SKILL.md 文件** - 无需修改，直接兼容
- [ ] **测试用例** - 建议运行一次完整测试
- [ ] **文档** - 更新内部文档说明 V2 新功能
- [ ] **监控** - 观察 `max_loaded_skills` 是否合理（默认 10）

---

## 5. 已知限制

| 限制 | 说明 | 缓解策略 |
| :--- | :--- | :--- |
| 并行工具调用 | 当前框架不支持并行 | 未来可添加 reducer |
| `sources` 运行时不可变 | `__init__` 时固定 | 重启 agent 以识别新 `sources` |
| SubAgent 技能隔离 | 状态不共享 | SubAgent 自行 `load_skill` |
| 卸载不删除历史 | 仅移除状态标记 | 预期行为 |

---

## 6. 技术联系

**问题反馈**: 请提交 GitHub Issue
**文档**:
- [SkillsMiddleware V2 设计文档](./DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md)
- [核查报告](./SkillsMiddleware_V2_核查报告.md)
- [Phase3 审查报告](./Phase3_CodeReview_Report.md)

---

## 附录 A: 完整变更列表

### A.1 新增类型

```python
class ResourceMetadata(TypedDict):
    path: str
    type: Literal["script", "reference", "asset", "other"]
    skill_name: str
```

### A.2 新增状态字段

```python
# SkillsState 扩展
skills_loaded: list[str]           # 已加载技能名称
skill_resources: dict[...]         # 资源缓存
```

### A.3 新增工具

```python
# SkillsMiddleware.tools 自动包含
- load_skill(skill_name: str) -> Command | str
- unload_skill(skill_name: str) -> Command | str
```

### A.4 新增参数

```python
def __init__(
    self,
    *,
    backend: BACKEND_TYPES,
    sources: list[str],
    max_loaded_skills: int = 10,  # V2 新增
) -> None:
```

### A.5 新增函数

```python
# 模块级函数
def _discover_resources(...) -> list[ResourceMetadata]
def _adiscover_resources(...) -> list[ResourceMetadata]
def _format_resource_summary(...) -> str
def _format_skill_annotations(...) -> str
```

---

**升级完成日期**: 2026-02-18
**Git Commit**: `178b14e feat(skills): SkillsMiddleware V2 完整实施`
