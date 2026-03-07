# 外部团队 API 使用指南

**版本**: 1.0.0
**日期**: 2026-03-07
**目标读者**: 使用 DeepAgents 作为依赖的外部项目团队

---

## 概述

本指南专为外部项目团队设计，帮助您集成 DeepAgents 的动态技能加载功能。如果您在测试中遇到 `SkillsMiddleware` 相关错误，或者需要使用运行时技能管理功能，请阅读本文档。

## 快速开始

### 1. 基础集成

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware

# 创建支持动态技能加载的代理
agent = create_deep_agent(
    model="openai:gpt-4o-mini",  # 或其他模型
    middleware=[
        SkillsMiddleware(
            backend=FilesystemBackend(root_dir="/srv/app"),
            sources=["/skills/user", "/skills/project"],
            expose_dynamic_tools=True,   # 🔥 关键：开启动态工具
            max_loaded_skills=10,      # 可调上限（生产推荐 ≤4）
        ),
    ],
)

# 使用代理
result = agent.invoke({
    "messages": [{"role": "user", "content": "加载数据分析技能"}]
})
```

### 1.1 推荐：统一控制主 Agent + 所有 SubAgents

当你只需要在一个地方启用动态技能加载，推荐直接通过 `create_deep_agent` 的参数统一控制，这样主 Agent 与所有 SubAgents 会同时生效：

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4o-mini",
    skills=["/skills/user", "/skills/project"],
    skills_expose_dynamic_tools=True,  # 主 Agent + 所有 SubAgents 同时启用动态工具
)
```

如果某个 SubAgent 需要独立控制，可在该 SubAgent 的 `middleware` 中自行注入 `SkillsMiddleware`，框架将自动跳过默认注入，避免重复。

### 2. 关键参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expose_dynamic_tools` | bool | False | 是否暴露动态技能管理工具 |
| `max_loaded_skills` | int | 10 | 最大同时加载技能数（生产环境建议 ≤4） |
| `sources` | List[str] | [] | 技能源路径列表 |
| `backend` | BackendProtocol | 必需 | 后端存储实例 |

## 动态技能管理

### 可用工具

当 `expose_dynamic_tools=True` 时，代理将获得以下工具：

#### load_skill - 加载技能

```python
# 用户可以通过自然语言触发
"请加载 web_search 技能"

# 或者在代码中直接调用
result = agent.invoke({
    "messages": [{"role": "user", "content": "load_skill('web_search')"}]
})
```

**功能**: 将指定技能标记为"已加载"状态，在系统提示中显示 `[Loaded]` 标记。

**返回值**:
- 成功: `"Loaded skill 'web_search'"`
- 失败: `"Skill 'web_search' not found"` 或 `"Max loaded skills (4) reached"`

#### unload_skill - 卸载技能

```python
# 用户可以通过自然语言触发
"请卸载 web_search 技能"

# 或者在代码中直接调用
result = agent.invoke({
    "messages": [{"role": "user", "content": "unload_skill('web_search')"}]
})
```

**功能**: 取消技能的"已加载"状态。

**返回值**:
- 成功: `"Unloaded skill 'web_search'"`
- 失败: `"Skill 'web_search' is not loaded"`

## 常见问题解决

### ❌ 测试失败：缺少 `_create_load_skill_tool` 方法

**错误表现**:
```
AttributeError: 'SkillsMiddleware' object has no attribute '_create_load_skill_tool'
```

**解决方案**:
1. 确保使用最新版 DeepAgents (≥0.4.4)
2. 在 `SkillsMiddleware` 构造函数中设置 `expose_dynamic_tools=True`
3. 使用工具名 `load_skill` 而不是内部方法名

```python
# ✅ 正确做法
middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills"],
    expose_dynamic_tools=True,  # 开启动态工具
)

# ❌ 错误做法（不要直接调用内部方法）
# middleware._create_load_skill_tool()  # 不要这样做
```

### ❌ 测试失败：缺少 `max_loaded_skills` 参数

**错误表现**:
```
TypeError: SkillsMiddleware.__init__() got an unexpected keyword argument 'max_loaded_skills'
```

**解决方案**:
1. 升级 DeepAgents 到最新版本
2. `max_loaded_skills` 参数已添加到构造函数

```python
# ✅ 正确做法（新版本支持）
middleware = SkillsMiddleware(
    backend=backend,
    sources=["/skills"],
    expose_dynamic_tools=True,
    max_loaded_skills=4,  # 设置最大加载数
)
```

### ❌ 技能加载失败

**错误表现**:
```
"Skill 'my_skill' not found"
```

**解决方案**:
1. 检查技能文件是否存在：`/skills/my_skill/SKILL.md`
2. 确认 `sources` 路径配置正确
3. 验证技能文件格式是否符合规范

## 最佳实践

### 1. 生产环境配置

```python
# 生产环境推荐配置
middleware = SkillsMiddleware(
    backend=FilesystemBackend(root_dir="/app"),
    sources=["/app/skills/core", "/app/skills/team"],
    expose_dynamic_tools=True,
    max_loaded_skills=4,  # 限制数量，避免上下文过度膨胀
)
```

### 2. 测试环境适配

对于前瞻性测试，建议添加特性探测：

```python
import pytest
from deepagents.middleware.skills import SkillsMiddleware

def test_dynamic_loading():
    # 特性探测
    try:
        middleware = SkillsMiddleware(
            backend=backend,
            sources=["/skills"],
            expose_dynamic_tools=True,
            max_loaded_skills=4,
        )
    except TypeError:
        pytest.skip("当前 DeepAgents 版本不支持动态加载功能")

    # 测试逻辑...
```

### 3. 错误处理

```python
def safe_load_skill(agent, skill_name):
    """安全加载技能，包含错误处理"""
    try:
        result = agent.invoke({
            "messages": [{
                "role": "user",
                "content": f"load_skill('{skill_name}')"
            }]
        })

        # 检查结果
        if f"Loaded skill '{skill_name}'" in str(result):
            return True, "加载成功"
        elif "not found" in str(result):
            return False, f"技能 '{skill_name}' 不存在"
        elif "Max loaded skills" in str(result):
            return False, "已达到最大加载数量限制"
        else:
            return False, f"未知错误: {result}"

    except Exception as e:
        return False, f"异常: {str(e)}"
```

## 版本兼容性

| DeepAgents 版本 | 动态加载支持 | 推荐做法 |
|----------------|-------------|----------|
| < 0.4.0 | ❌ 不支持 | 升级版本或跳过相关测试 |
| 0.4.0 - 0.4.3 | ⚠️ 部分支持 | 使用 `expose_dynamic_tools=True` |
| ≥ 0.4.4 | ✅ 完全支持 | 使用本指南的所有功能 |

## 迁移指南

### 从旧版本迁移

如果您的项目之前依赖内部API，请按以下步骤迁移：

1. **移除内部方法调用**
   ```python
   # ❌ 旧代码
   middleware._create_load_skill_tool()
   middleware._create_unload_skill_tool()

   # ✅ 新代码
   # 不需要直接调用，通过 expose_dynamic_tools=True 自动启用
   ```

2. **更新构造函数参数**
   ```python
   # ❌ 旧代码
   middleware = SkillsMiddleware(backend=backend, sources=["/skills"])

   # ✅ 新代码
   middleware = SkillsMiddleware(
       backend=backend,
       sources=["/skills"],
       expose_dynamic_tools=True,
       max_loaded_skills=4,
   )
   ```

3. **更新测试用例**
   ```python
   # ❌ 旧测试
   def test_old_api():
       tool = middleware._create_load_skill_tool()
       result = tool(skill_name="test")

   # ✅ 新测试
   def test_new_api():
       result = agent.invoke({
           "messages": [{"role": "user", "content": "load_skill('test')"}]
       })
   ```

## 相关文档

- [动态加载问题定位指南](../integrations/skills/dynamic_loading_guide.md)
- [SkillsMiddleware V2 升级方案](../skillsmiddleware_docs/DeepAgents_SkillsMiddlewareV2升级设计方案.md)
- [API 参考文档](API_REFERENCE.md)

## 支持与反馈

如果您在集成过程中遇到问题：

1. **检查版本**: 确保使用最新版 DeepAgents
2. **查看日志**: 启用调试模式获取详细信息
3. **验证配置**: 对照本指南检查参数设置
4. **提交问题**: 在项目仓库创建 Issue，包含错误详情

---

*本指南最后更新：2026-03-07*
