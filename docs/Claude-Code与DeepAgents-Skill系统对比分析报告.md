# Claude Code 与 DeepAgents Skill 系统对比分析报告

> 版本：1.3
> 日期：2026-02-16
> 状态：三轮评审完成

**相关文档**：本报告与 `基于LangGraph与渐进式披露的动态Skill系统实现方案.md` 配套使用。该文档提供整体设计理念和架构规划，本报告提供详细的对比分析、差距识别和具体实现建议。

---

## 目录

1. [执行摘要](#一执行摘要)
2. [系统架构对比](#二系统架构对比)
3. [元数据设计对比](#三元数据设计对比)
4. [目录结构与资源管理对比](#四目录结构与资源管理对比)
5. [调用机制对比](#五调用机制对比)
6. [流程控制设计对比](#六流程控制设计对比)
7. [差距分析](#七差距分析)
8. [优化建议](#八优化建议)
9. [实现路线图](#九实现路线图)
10. [附录](#十附录)

---

## 一、执行摘要

### 1.1 研究背景

本报告旨在深入对比分析 Claude Code 与 DeepAgents 的 Skill 系统设计，识别关键差距，并提出系统性优化建议。研究基于对 Claude Code 官方 skill 实现（superpowers 4.3.0、plugin-dev 等）的深入分析，以及对 DeepAgents 现有 SkillsMiddleware 源码的详细审查。

### 1.2 核心发现

| 维度 | Claude Code | DeepAgents | 差距程度 |
|------|-------------|------------|----------|
| **Skill 定位** | 可执行流程单元 | 被动知识库 | ⚠️ 高 |
| **资源管理** | 完整支持 references/templates/examples/scripts | 仅支持 SKILL.md | ⚠️ 高 |
| **状态感知** | 系统追踪 skill 使用状态 | 无状态追踪 | ⚠️ 高 |
| **流程控制** | Phase/Checklist/Iron Law 机制 | 无结构化流程 | ⚠️ 中 |
| **强制检查** | "1% 可能性必须调用" | 纯 LLM 自主 | ⚠️ 中 |
| **用户控制** | /skill 命令显式调用 | 不支持 | ⚠️ 低 |

### 1.3 建议优先级

- **P0（必须）**: load_skill 工具、skills_loaded 状态、资源目录支持
- **P1（重要）**: Phase/Checklist 机制、强制检查提示、Rationalization Table
- **P2（增强）**: 用户 /skill 调用、Skill 间引用、Red Flags
- **P3（生态）**: Plugin Manifest、Marketplace、MCP 集成

---

## 二、系统架构对比

### 2.1 设计理念对比

| 方面 | Claude Code | DeepAgents |
|------|-------------|------------|
| **核心隐喻** | Skill = 程序（可调用、有状态、可组合） | Skill = 书籍（可查阅、无状态） |
| **执行模型** | TDD 风格（RED-GREEN-REFACTOR 循环） | 线性阅读执行 |
| **触发模式** | 强制检查 + 主动调用 | 纯 LLM 自主决策 |
| **状态管理** | 显式 skills_loaded 状态追踪 | 无状态追踪 |

### 2.2 架构图对比

#### Claude Code 架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Plugin System (容器)                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐               │
│  │ plugin.json│ │ commands/ │ │ agents/   │ │ hooks/    │               │
│  │ manifest  │ │ 用户命令   │ │ 子代理    │ │ 事件钩子   │               │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘               │
├─────────────────────────────────────────────────────────────────────────┤
│                         Skills System (核心)                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  SKILL.md + references/ + templates/ + examples/ + scripts/     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                         Skill Tool (调用入口)                            │
│  • 用户调用: /skill-name                                                │
│  • 自动触发: "有 1% 可能性就必须调用"                                     │
│  • 强制检查: System Reminder 要求                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

#### DeepAgents 架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SkillsMiddleware (单一组件)                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  before_agent: 扫描 sources → 加载 skills_metadata               │   │
│  │  wrap_model_call: 注入技能列表到 system prompt                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                      Agent 自主行为                                      │
│  • Agent 看到: 技能列表 (name + description + path)                     │
│  • Agent 决定: 是否需要使用技能 (LLM 语义推理)                           │
│  • Agent 行动: 调用 read_file 读取完整内容                               │
│  • 系统状态: 不感知技能是否被使用                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 组件对比

| 组件 | Claude Code | DeepAgents | 差距说明 |
|------|-------------|------------|---------|
| Plugin Manifest | ✅ plugin.json | ❌ 无 | 无插件元数据管理 |
| Skill Tool | ✅ 专用工具 | ❌ 复用 read_file | 语义不明确，无状态追踪 |
| Commands | ✅ /command 用户触发 | ❌ 无 | 用户无法主动控制 |
| Agents | ✅ 子代理定义 | ✅ SubAgent（不同机制） | 实现方式不同 |
| Hooks | ✅ 事件钩子系统 | ❌ 无 | 无事件驱动能力 |
| MCP 集成 | ✅ 配置文件 | ❌ 无 | 无协议支持 |

---

## 三、元数据设计对比

### 3.1 YAML Frontmatter 字段对比

| 字段 | Claude Code | DeepAgents | 对比说明 |
|------|-------------|------------|---------|
| `name` | ✅ 必需，字母数字连字符 | ✅ 必需，64 字符限制 | 基本一致 |
| `description` | ✅ 必需，**仅触发条件** | ✅ 必需，1024 字符限制 | **关键差异** |
| `allowed_tools` | ❌ 不支持 | ✅ 支持（仅展示） | DeepAgents 有但未强制 |
| `license` | ❌ 不在 frontmatter | ✅ 支持 | DeepAgents 更完整 |
| `compatibility` | ❌ 不支持 | ✅ 支持 | DeepAgents 更完整 |
| `metadata` | ❌ 不支持 | ✅ 支持 | DeepAgents 更完整 |

### 3.2 Description 设计哲学（关键差异）

**Claude Code 的严格规范：**

> "Description = When to Use, NOT What the Skill Does"

```yaml
# ❌ 错误：总结了工作流程 - Claude 会直接使用这个而不读取完整内容
description: Use when executing plans - dispatches subagent per task with code review

# ✅ 正确：仅包含触发条件，无工作流程
description: Use when executing implementation plans with independent tasks
```

**原因**（来自 Claude Code 官方文档）：
> 如果 description 包含工作流程摘要，Claude 会直接遵循 description 而不读取完整 SKILL.md。这被称为 "CSO (Claude Search Optimization) 陷阱"。

**DeepAgents 问题**：
- 没有明确的设计哲学
- description 可能包含过多信息
- 未定义 description 的最佳实践

### 3.3 建议的增强 SkillMetadata

```python
class SkillResource(TypedDict):
    """技能资源文件"""
    path: str           # 文件路径
    type: str           # "reference" | "template" | "example" | "script" | "rule"
    description: str    # 资源描述

class SkillPhase(TypedDict):
    """技能执行阶段"""
    name: str
    description: str
    checklist: list[str]
    required: bool  # 是否必须按顺序完成

class EnhancedSkillMetadata(TypedDict):
    """增强的技能元数据"""
    # 基础字段
    name: str
    description: str
    path: str               # SKILL.md 路径
    skill_dir: str          # 技能目录路径（新增）

    # 现有字段
    license: str | None
    compatibility: str | None
    metadata: dict[str, str]
    allowed_tools: list[str]

    # 资源管理（新增）
    resources: list[SkillResource]

    # 流程控制（新增）
    phases: list[SkillPhase]
    iron_law: str | None
    rationalizations: dict[str, str]  # excuse -> reality
    red_flags: list[str]

    # 依赖关系（新增）
    depends_on: list[str]   # 依赖的其他 skill
```

---

## 四、目录结构与资源管理对比

### 4.1 目录结构设计

#### Claude Code 目录结构模式

```
skill-name/
├── SKILL.md                    # 核心文件（必需）
├── anthropic-best-practices.md # 参考文档（语义命名）
├── persuasion-principles.md    # 理论背景
├── root-cause-tracing.md       # 子技术参考
├── implementer-prompt.md       # 子代理提示模板
├── find-polluter.sh            # 可执行脚本
├── condition-based-waiting-example.ts  # 代码示例
├── examples/                   # 示例目录
│   └── CLAUDE_MD_TESTING.md
├── rules/                      # 条件规则目录
│   └── install.md
└── references/                 # 或语义命名的参考文件
    ├── advanced.md
    └── patterns.md
```

#### DeepAgents 目录结构模式

```
skill-name/
├── SKILL.md                    # 核心文件（必需）
└── helper.py                   # 可选支持文件（无标准使用方式）
```

### 4.2 资源类型与使用场景

| 资源类型 | 使用场景 | Claude Code | DeepAgents |
|---------|---------|-------------|------------|
| **references/** | 详细 API 文档、语法指南、理论背景（100+ 行内容） | ✅ | ❌ |
| **templates/** | 子代理提示模板、输出模板、风格指南 | ✅ | ❌ |
| **examples/** | 完整工作示例、真实用例演示 | ✅ | ❌ |
| **scripts/** | 可执行工具、渲染实用程序、自动化脚本 | ✅ | ⚠️ helper.py 无标准用法 |
| **rules/** | 条件内容、错误处理程序、平台特定指令 | ✅ | ❌ |

### 4.3 资源引用方式

**Claude Code 引用语法：**

```markdown
# 方式 1：显式文件引用
See `root-cause-tracing.md` in this directory for the complete technique.

# 方式 2：Markdown 链接
**Form filling**: See [FORMS.md](FORMS.md) for complete guide

# 方式 3：条件加载
When adding mocks, read testing-anti-patterns.md to avoid common pitfalls

# 方式 4：用途优先描述
**Psychology note:** See persuasion-principles.md for research foundation

# 禁止方式（强制加载浪费上下文）
❌ @skills/testing/test-driven-development/SKILL.md
```

**DeepAgents：无标准引用语法**

### 4.4 渐进式披露层级对比

| 级别 | 内容 | Claude Code | DeepAgents |
|------|------|-------------|------------|
| Level 0 | name + description（始终可见） | ✅ ~100 词 | ✅ 同上 |
| Level 1 | SKILL.md 主体（触发时加载） | ✅ <5k 词 | ⚠️ 需手动 read_file |
| Level 2 | references/（按需加载） | ✅ | ❌ 无机制 |
| Level 3 | templates/（按需加载） | ✅ | ❌ 无机制 |
| Level 4 | examples/（按需加载） | ✅ | ❌ 无机制 |

### 4.5 资源管理增强实现方案

```python
RESOURCE_DIRS = {
    "references": "reference",
    "templates": "template",
    "examples": "example",
    "scripts": "script",
    "rules": "rule",
}

def _discover_resources(
    backend: BackendProtocol,
    skill_dir: str
) -> list[SkillResource]:
    """发现技能目录下的资源文件"""
    resources: list[SkillResource] = []

    items = backend.ls_info(skill_dir)
    for item in items:
        if not item.get("is_dir"):
            continue

        subdir_name = PurePosixPath(item["path"]).name
        if subdir_name not in RESOURCE_DIRS:
            continue

        resource_type = RESOURCE_DIRS[subdir_name]
        files = backend.ls_info(item["path"])

        for f in files:
            if not f.get("is_dir"):
                resources.append(SkillResource(
                    path=f["path"],
                    type=resource_type,
                    description="",
                ))

    return resources
```

---

## 五、调用机制对比

### 5.1 触发机制对比

| 机制 | Claude Code | DeepAgents | 差距 |
|------|-------------|------------|------|
| **用户显式调用** | ✅ `/skill-name` | ❌ 不支持 | 用户无法主动控制 |
| **LLM 自动判断** | ✅ 语义推理 | ✅ 语义推理 | - |
| **强制检查** | ✅ "有 1% 可能性就必须调用" | ❌ 无 | 可靠性差距 |
| **专用工具** | ✅ `Skill` tool | ❌ 复用 `read_file` | 语义不明确 |
| **状态追踪** | ✅ `skills_loaded` 状态 | ❌ 无 | 无法感知使用状态 |

### 5.2 Claude Code 强制检查机制

**System Reminder 内容：**

```
If you think there is even a 1% chance a skill might apply to what
you are doing, you ABSOLUTELY MUST invoke the skill.

IMPORTANT: Invoke relevant or requested skills BEFORE any response
or action. Even a 1% chance a skill might apply means that you
should invoke the skill to check.
```

**DeepAgents 建议增强：**

```python
SKILL_ENFORCEMENT_PROMPT = """

## CRITICAL: Skill Check Required

Before responding to ANY user request, you MUST check if any
available skill applies.

**Rule**: If there's even a 1% chance a skill might help, you MUST
invoke `load_skill` first.

**Do NOT**:
- Skip skill check because the task "seems simple"
- Assume you know the skill content without loading it
- Respond before checking skill applicability

"""
```

### 5.3 调用流程对比

#### Claude Code 完整流程

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ System Reminder (强制):                                     │
│ "有 1% 可能性就必须调用 skill"                               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
LLM 判断 → 需要 skill?
    │
    ├── 是 → 调用 Skill tool
    │         │
    │         ▼
    │     系统加载 SKILL.md
    │         │
    │         ▼
    │     更新 skills_loaded 状态
    │         │
    │         ▼
    │     Agent 执行 skill 内容
    │         │
    │         ▼
    │     需要详细参考?
    │         │
    │         └──→ read_file("references/xxx.md")
    │
    └── 否 → 直接响应
```

#### DeepAgents 现有流程

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ System Prompt 注入:                                         │
│ "有这些技能: web-research, sql-analysis..."                 │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
LLM 判断 → 需要 skill?（无强制）
    │
    ├── 是 → Agent 自己调用 read_file
    │         │
    │         ▼
    │     系统不知道这是 skill！
    │     无状态追踪
    │     无资源信息
    │
    └── 否 → 直接响应
```

### 5.4 load_skill 工具实现方案

```python
@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> str:
    """加载并激活一个技能

    Args:
        skill_name: 技能名称

    Returns:
        技能完整内容
    """
    # 1. 查找技能
    metadata = runtime.state.get("skills_metadata", [])
    skill = next((s for s in metadata if s["name"] == skill_name), None)

    if not skill:
        return f"Skill '{skill_name}' not found. Available skills: {[s['name'] for s in metadata]}"

    # 2. 更新状态
    current_loaded = list(runtime.state.get("skills_loaded", []))
    if skill_name not in current_loaded:
        current_loaded.append(skill_name)
        # 返回 Command 更新状态
        return Command(update={
            "skills_loaded": current_loaded,
            "messages": [ToolMessage(
                content=skill.get("full_content", ""),
                tool_call_id=runtime.tool_call_id
            )]
        })

    return f"Skill '{skill_name}' already loaded."
```

---

## 六、流程控制设计对比

### 6.1 Phase 设计

**Claude Code 模式：**

```markdown
## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation
1. **Read Error Messages Carefully**
2. **Reproduce Consistently**
3. **Check Recent Changes**
4. **Gather Evidence**
5. **Trace Data Flow**

### Phase 2: Pattern Analysis
...

### Phase 3: Hypothesis and Testing
...

### Phase 4: Implementation
...
```

**DeepAgents：无此设计**

### 6.2 Checklist 机制

**Claude Code 模式：**

```markdown
## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

Can't check all boxes? You skipped TDD. Start over.
```

**DeepAgents：无此设计**

### 6.3 Iron Law 声明

**Claude Code 模式：**

```markdown
## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

**Violating the letter of this process is violating the spirit.**

**No exceptions:**
- Not for "simple additions"
- Not for "just adding a section"
- Not for "documentation updates"
- Don't keep untested changes as "reference"
```

**DeepAgents：无此设计**

### 6.4 Rationalization Table

**Claude Code 模式：**

```markdown
| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Emergency" | Systematic is faster than thrashing. |
| "One more fix attempt" | 3+ failures = architectural problem. |
```

**DeepAgents：无此设计**

### 6.5 Red Flags 警告

**Claude Code 模式：**

```markdown
## Red Flags - STOP

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "One more fix attempt" (when already tried 2+)

**ALL mean: STOP. Return to Phase 1.**
```

**DeepAgents：无此设计**

### 6.6 流程控制增强建议

建议在 SkillMetadata 中支持以下流程控制字段：

```python
class SkillPhase(TypedDict):
    name: str
    description: str
    checklist: list[str]
    required: bool

class FlowControl(TypedDict):
    iron_law: str | None              # 核心规则
    phases: list[SkillPhase]           # 执行阶段
    rationalizations: dict[str, str]   # excuse -> reality 映射
    red_flags: list[str]               # 危险信号列表
```

---

## 七、差距分析

### 7.1 差距总览

| 差距类别 | 子项 | 严重程度 | 影响描述 |
|---------|------|---------|---------|
| **基础能力** | load_skill 工具 | 🔴 高 | 无法追踪 skill 使用状态 |
| | skills_loaded 状态 | 🔴 高 | 无法实现按需内容注入 |
| | 强制检查机制 | 🟡 中 | Agent 可能忽略相关 skill |
| **资源管理** | references/ 支持 | 🔴 高 | 无法组织复杂参考文档 |
| | templates/ 支持 | 🟡 中 | 无法复用提示模板 |
| | examples/ 支持 | 🟡 中 | 无法提供完整示例 |
| | scripts/ 支持 | 🟢 低 | helper.py 已存在但无规范 |
| | 资源路径注入 | 🟡 中 | Agent 不知道可用资源 |
| **流程控制** | Phase 设计 | 🟡 中 | 复杂任务难以追踪进度 |
| | Checklist 机制 | 🟡 中 | 无法确保流程完整性 |
| | Iron Law 声明 | 🟢 低 | 增强规则执行 |
| | Rationalization Table | 🟢 低 | 对抗合理化倾向 |
| **用户体验** | /skill 用户调用 | 🟢 低 | 用户无法主动控制 |
| | Skill 间引用 | 🟢 低 | 无法组合多个 skill |
| **生态系统** | Plugin Manifest | 🔵 未来 | 插件管理能力 |
| | Marketplace | 🔵 未来 | 技能分发能力 |

### 7.2 差距影响分析

#### 高严重程度差距

1. **load_skill 工具缺失**
   - 影响：系统无法感知 skill 是否被使用
   - 后果：无法实现按需内容注入、无法追踪执行状态
   - 解决方案：新增专用工具

2. **skills_loaded 状态缺失**
   - 影响：无法追踪已激活 skill
   - 后果：无法实现渐进式披露的完整闭环
   - 解决方案：扩展 SkillsState

3. **资源目录不支持**
   - 影响：无法组织复杂 skill 的参考文档
   - 后果：SKILL.md 变得臃肿或信息不完整
   - 解决方案：实现资源发现机制

---

## 八、优化建议

### 8.1 P0 优化项（必须）

#### 8.1.1 添加 skills_loaded 状态

```python
# 现有
class SkillsState(AgentState):
    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]

# 建议增强
class EnhancedSkillsState(AgentState):
    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]
    skills_loaded: NotRequired[Annotated[list[str], PrivateStateAttr]]  # 新增
```

#### 8.1.2 实现 load_skill 工具

```python
@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> str | Command:
    """加载并激活一个技能"""
    # 实现见 5.4 节
```

#### 8.1.3 实现按需内容注入

```python
def wrap_model_call(self, request, handler):
    # 基础注入
    prompt = inject_skill_list(request)

    # 按需注入已加载技能的完整内容
    loaded = request.state.get("skills_loaded", [])
    for skill_name in loaded:
        skill = get_skill(skill_name)
        prompt += f"\n\n## Active Skill: {skill_name}\n{skill.full_content}"

    return handler(request.override(system_message=prompt))
```

#### 8.1.4 实现资源发现

```python
def _discover_resources(backend: BackendProtocol, skill_dir: str) -> list[SkillResource]:
    # 实现见 4.5 节
```

#### 8.1.5 实现 load_skill_resource 工具

```python
@tool
def load_skill_resource(
    skill_name: str,
    resource_path: str,
    runtime: ToolRuntime,
) -> str:
    """加载技能的资源文件

    Args:
        skill_name: 技能名称
        resource_path: 资源文件路径（相对路径）

    Returns:
        资源文件内容
    """
    metadata = runtime.state.get("skills_metadata", [])
    skill = next((s for s in metadata if s["name"] == skill_name), None)

    if not skill:
        return f"Skill '{skill_name}' not found."

    # 检查资源是否存在
    resources = skill.get("resources", [])
    resource = next((r for r in resources if r["path"].endswith(resource_path)), None)

    if not resource:
        available = [r["path"] for r in resources]
        return f"Resource '{resource_path}' not found. Available: {available}"

    # 通过 backend 读取
    backend = get_backend(runtime)
    response = backend.download_files([resource["path"]])[0]
    if response.content:
        return response.content.decode("utf-8")

    return f"Failed to load resource '{resource_path}'."
```

#### 8.1.6 实现 allowed_tools 强制执行

现有 DeepAgents 已解析 `allowed_tools` 字段但未强制执行。建议在 `wrap_tool_call` 钩子中实现：

```python
def wrap_tool_call(self, request: ToolCallRequest, handler: ToolCallHandler) -> ToolMessage:
    """在工具调用前检查 allowed_tools 权限"""
    tool_name = request.tool.name

    # 获取已加载技能的 allowed_tools
    skills_loaded = request.state.get("skills_loaded", [])
    skills_metadata = request.state.get("skills_metadata", [])

    # 收集所有已加载技能的 allowed_tools
    all_allowed: set[str] = set()
    for skill in skills_metadata:
        if skill["name"] in skills_loaded:
            all_allowed.update(skill.get("allowed_tools", []))

    # 如果有 allowed_tools 限制且当前工具不在列表中
    if all_allowed and tool_name not in all_allowed:
        return ToolMessage(
            content=f"Tool '{tool_name}' is not allowed in current skill context. "
                    f"Allowed tools: {sorted(all_allowed)}",
            tool_call_id=request.tool_call.id,
        )

    return handler(request)
```

### 8.2 P1 优化项（重要）

#### 8.2.1 添加强制检查提示

```python
SKILL_ENFORCEMENT_PROMPT = """

## CRITICAL: Skill Check Required

Before responding to ANY user request, you MUST check if any
available skill applies.

**Rule**: If there's even a 1% chance a skill might help, you MUST
read the skill file first.

"""
```

#### 8.2.2 支持 Phase 定义

在 SKILL.md 中支持结构化的阶段定义：

```markdown
---
name: systematic-debugging
description: Use when encountering any bug
phases:
  - name: Root Cause Investigation
    required: true
  - name: Pattern Analysis
    required: true
  - name: Hypothesis and Testing
    required: true
  - name: Implementation
    required: true
---
```

#### 8.2.3 支持 Rationalization Table

```markdown
---
name: test-driven-development
rationalizations:
  "Too simple to test": "Simple code breaks. Test takes 30 seconds."
  "I'll test after": "Tests passing immediately prove nothing."
---
```

### 8.3 P2 优化项（增强）

#### 8.3.1 支持用户 /skill 调用

```python
# 在消息处理中识别 /skill 语法
if message.startswith("/"):
    skill_name = message[1:].strip()
    return Command(goto="load_skill", args={"skill_name": skill_name})
```

#### 8.3.2 支持 Skill 间引用

```python
class EnhancedSkillMetadata(TypedDict):
    # ...
    depends_on: list[str]  # 依赖的其他 skill
```

### 8.4 P3 优化项（生态）

#### 8.4.1 Plugin Manifest

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "skills": ["./skills/skill1", "./skills/skill2"],
  "commands": ["./commands/cmd1"],
  "agents": ["./agents/agent1"]
}
```

---

## 九、实现路线图

### 9.1 Phase 1：基础能力（P0）

**目标**：建立 skill 状态追踪和专用加载机制

| 任务 | 描述 | 依赖 |
|------|------|------|
| 1.1 | 扩展 SkillsState 添加 skills_loaded 字段 | 无 |
| 1.2 | 实现 load_skill 工具 | 1.1 |
| 1.3 | 增强 wrap_model_call 实现按需内容注入 | 1.1, 1.2 |
| 1.4 | 实现 _discover_resources() 资源发现 | 无 |
| 1.5 | 扩展 SkillMetadata 添加 resources 字段 | 1.4 |
| 1.6 | 增强资源路径注入到 system prompt | 1.4, 1.5 |
| 1.7 | 实现 load_skill_resource 工具 | 1.4, 1.5 |
| 1.8 | 实现 allowed_tools 强制执行 | 1.1 |

**交付物**：
- 增强的 SkillsMiddleware（含 skills_loaded 状态）
- load_skill 工具
- load_skill_resource 工具
- 资源发现机制
- allowed_tools 权限控制

### 9.2 Phase 2：流程控制（P1）

**目标**：支持结构化流程控制机制

| 任务 | 描述 | 依赖 |
|------|------|------|
| 2.1 | 支持 phases 定义和解析 | Phase 1 |
| 2.2 | 支持 checklist 定义 | 2.1 |
| 2.3 | 支持 iron_law 声明 | 无 |
| 2.4 | 支持 rationalizations 表 | 无 |
| 2.5 | 支持 red_flags 列表 | 无 |
| 2.6 | 添加强制检查提示 | 无 |

**交付物**：
- 流程控制元数据支持
- 强制检查机制

### 9.3 Phase 3：用户体验（P2）

**目标**：增强用户控制和 skill 组合能力

| 任务 | 描述 | 依赖 |
|------|------|------|
| 3.1 | 支持 /skill 用户调用 | Phase 1 |
| 3.2 | 支持 Skill 间引用语法 | Phase 1 |
| 3.3 | 支持 depends_on 依赖声明 | 3.2 |

**交付物**：
- 用户调用接口
- Skill 组合能力

### 9.4 Phase 4：生态系统（P3）

**目标**：建立完整的插件生态系统

| 任务 | 描述 | 依赖 |
|------|------|------|
| 4.1 | Plugin Manifest 规范 | Phase 3 |
| 4.2 | Marketplace 集成 | 4.1 |
| 4.3 | MCP 协议支持 | Phase 1 |

**交付物**：
- 插件管理系统
- 技能分发能力

---

## 十、附录

### A. 参考文件路径

| 资源类型 | Claude Code 路径示例 |
|---------|---------------------|
| Skill 主文件 | `superpowers/4.3.0/skills/systematic-debugging/SKILL.md` |
| 参考文档 | `superpowers/4.3.0/skills/systematic-debugging/root-cause-tracing.md` |
| 代码示例 | `superpowers/4.3.0/skills/systematic-debugging/condition-based-waiting-example.ts` |
| 工具脚本 | `superpowers/4.3.0/skills/systematic-debugging/find-polluter.sh` |
| 理论参考 | `superpowers/4.3.0/skills/writing-skills/persuasion-principles.md` |
| 提示模板 | `superpowers/4.3.0/skills/subagent-driven-development/implementer-prompt.md` |

### B. DeepAgents 相关文件

| 文件 | 路径 |
|------|------|
| SkillsMiddleware | `libs/deepagents/deepagents/middleware/skills.py` |
| Backend Protocol | `libs/deepagents/deepagents/backends/protocol.py` |
| 现有设计文档 | `docs/基于LangGraph与渐进式披露的动态Skill系统实现方案.md` |

### C. 关键设计原则

1. **渐进式披露**：SKILL.md 作为目录，详细资源按需加载
2. **最小侵害性**：通过中间件扩展，不修改核心代码
3. **状态驱动**：使用 LangGraph State 追踪 skill 生命周期
4. **语义化组织**：按 references/templates/examples/scripts 分类
5. **Description 即触发器**：仅包含触发条件，不包含流程

### D. 术语表

| 术语 | 定义 |
|------|------|
| Progressive Disclosure | 渐进式披露，按需加载详细内容 |
| Iron Law | 核心规则，不可违反的约束 |
| Rationalization Table | 合理化对抗表，excuse -> reality 映射 |
| Red Flags | 危险信号，需要停止和重新评估的情况 |
| CSO | Claude Search Optimization，优化 skill 可发现性 |

---

## 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0 | 2026-02-16 | 初始版本 |
| 1.1 | 2026-02-16 | 第一轮修订：添加文档关系说明、load_skill_resource 工具、allowed_tools 强制执行实现 |
| 1.2 | 2026-02-16 | 第二轮修订：修正日期、统一 superpowers 版本号至 4.3.0、完善变更历史 |
| 1.3 | 2026-02-16 | 第三轮评审：最终格式检查和润色，确认报告完整性 |

---

*本报告基于 Claude Code superpowers 4.3.0 和 DeepAgents 当前实现进行对比分析。*
