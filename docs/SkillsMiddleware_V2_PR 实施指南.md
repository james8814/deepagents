# SkillsMiddleware V2 PR 实施指南

**日期**: 2026-02-18
**版本**: 1.0

---

## 概述

由于 V2 改动较大，建议分三个 PR 逐步实施：

| PR | 内容 | 改动行数 | 风险 |
| :--- | :--- | :--- | :---: |
| **PR 1** | 类型定义 | ~60 行 | 低 |
| **PR 2** | 资源发现函数 | ~120 行 | 低 |
| **PR 3** | V2 工具方法 | ~250 行 | 中 |

---

## PR 1: 类型定义

### 改动内容

1. **导入扩展**
   - 添加 `Literal` 到 typing 导入
   - 添加 `BaseTool` 导入
   - 添加 `Command` 导入
   - 添加 `ToolMessage` 导入

2. **新增常量**
   ```python
   RESOURCE_TYPE_MAP: dict[str, Literal["script", "reference", "asset"]] = {
       "scripts": "script",
       "references": "reference",
       "assets": "asset",
   }
   ```

3. **新增类型**
   ```python
   class ResourceMetadata(TypedDict):
       path: str
       type: Literal["script", "reference", "asset", "other"]
       skill_name: str
   ```

4. **扩展 SkillsState**
   ```python
   class SkillsState(AgentState):
       skills_metadata: ...  # 现有
       skills_loaded: NotRequired[Annotated[list[str], PrivateStateAttr]]  # 新增
       skill_resources: NotRequired[Annotated[dict[str, list[ResourceMetadata]], PrivateStateAttr]]  # 新增
   ```

5. **扩展 SkillsStateUpdate**
   ```python
   class SkillsStateUpdate(TypedDict):
       skills_metadata: list[SkillMetadata]  # 现有
       skills_loaded: list[str]  # 新增
       skill_resources: dict[str, list[ResourceMetadata]]  # 新增
   ```

6. **更新 __all__**
   ```python
   __all__ = ["SkillMetadata", "SkillsMiddleware", "ResourceMetadata"]
   ```

### 应用补丁

```bash
cd /Volumes/0-/jameswu projects/deepagents/libs/deepagents
patch -p1 < ../../docs/PR1_types.patch
```

### 验证

```bash
python3 -m py_compile deepagents/middleware/skills.py
python3 -c "from deepagents.middleware.skills import ResourceMetadata, SkillsState, SkillsStateUpdate; print('OK')"
```

---

## PR 2: 资源发现函数

### 改动内容

在 `SkillMetadata` 类定义之后、`SkillsState` 类定义之前添加以下函数：

1. **`_discover_resources`** - 同步资源发现
2. **`_adiscover_resources`** - 异步资源发现
3. **`_format_resource_summary`** - 资源摘要格式化
4. **`_format_skill_annotations`** - 技能注解格式化

### 应用补丁

```bash
cd /Volumes/0-/jameswu projects/deepagents/libs/deepagents
patch -p1 < ../../docs/PR2_resource_discovery.patch
```

### 验证

```bash
python3 -m py_compile deepagents/middleware/skills.py
python3 -c "from deepagents.middleware.skills import _discover_resources, _format_resource_summary; print('OK')"
```

---

## PR 3: V2 工具方法

### 改动内容

在 `SkillsMiddleware` 类中添加以下方法：

1. **`_get_backend_from_runtime`** - 从 runtime 解析 backend
2. **`_create_load_skill_tool`** - 创建 load_skill 工具
3. **`_execute_load_skill`** - load_skill 同步核心逻辑
4. **`_aexecute_load_skill`** - load_skill 异步核心逻辑
5. **`_create_unload_skill_tool`** - 创建 unload_skill 工具
6. **`_execute_unload_skill`** - unload_skill 核心逻辑

### 修改 __init__

```python
def __init__(
    self,
    *,
    backend: BACKEND_TYPES,
    sources: list[str],
    max_loaded_skills: int = 10,  # 新增参数
) -> None:
    self._backend = backend
    self.sources = sources
    self.system_prompt_template = SKILLS_SYSTEM_PROMPT
    self._max_loaded_skills = max_loaded_skills  # 新增
    self.tools = [  # 新增
        self._create_load_skill_tool(),
        self._create_unload_skill_tool(),
    ]
```

### 应用补丁

```bash
# 使用预生成的完整文件
cp libs/deepagents/deepagents/middleware/skills_v2_full.py libs/deepagents/deepagents/middleware/skills.py
```

或手动编辑：
1. 在 `__init__` 中添加 `max_loaded_skills` 参数和 `tools` 初始化
2. 在类末尾添加 V2 方法（见 `skills_v2_full.py` 第 500-750 行）

### 验证

```bash
python3 -m py_compile deepagents/middleware/skills.py
python3 -c "
from deepagents.middleware.skills import SkillsMiddleware
print('_execute_load_skill:', hasattr(SkillsMiddleware, '_execute_load_skill'))
print('_execute_unload_skill:', hasattr(SkillsMiddleware, '_execute_unload_skill'))
"
```

---

## 完整测试

三个 PR 都应用后，运行完整测试：

```bash
cd libs/deepagents
source .venv/bin/activate
pytest tests/unit_tests/middleware/test_skills_middleware.py -xvs
```

---

## 回滚方案

如果某个 PR 出现问题，可以回滚：

```bash
# 回滚到原始版本
git checkout libs/deepagents/deepagents/middleware/skills.py
```

---

## 文件清单

| 文件 | 说明 |
| :--- | :--- |
| `docs/PR1_types.patch` | PR1 补丁文件 |
| `docs/PR2_resource_discovery.patch` | PR2 补丁文件 |
| `libs/deepagents/deepagents/middleware/skills_v2_full.py` | PR3 完整文件 |
| `libs/deepagents/deepagents/middleware/skills.py.bak` | 原始备份 |

---

**实施完成后，删除临时文件**：
```bash
rm libs/deepagents/deepagents/middleware/skills_v2_full.py
rm libs/deepagents/deepagents/middleware/skills.py.bak
rm docs/PR*.patch
```
