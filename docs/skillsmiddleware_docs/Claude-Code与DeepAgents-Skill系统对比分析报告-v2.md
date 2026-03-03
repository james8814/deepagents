# Claude Code 与 DeepAgents Skill 系统对比分析报告（修订版）

> 版本：2.1 (最终版)
> 日期：2026-02-16
> 状态：最终评审通过，生产就绪

**声明**：本报告是在专家评审意见基础上重新撰写的修正版本。原报告存在关键性错误——将第三方插件 `superpowers` 的设计模式错误归因于 Claude Code 原生系统。本报告已彻底纠正此问题，并按照正确的层次框架重新组织分析。

---

## 目录

1. [概念层次框架](#一概念层次框架)
2. [Agent Skills 开放规范解读](#二agent-skills-开放规范解读)
3. [Claude Code 原生 Skill 系统分析](#三claude-code-原生-skill-系统分析)
4. [superpowers 第三方插件分析](#四superpowers-第三方插件分析)
5. [DeepAgents 现有实现分析](#五deepagents-现有实现分析)
6. [系统性对比](#六系统性对比)
7. [差距分析与优化建议](#七差距分析与优化建议)
8. [实现路线图](#八实现路线图)
9. [附录](#九附录)

---

## 一、概念层次框架

### 1.1 Skill 生态的三个层次

本报告严格区分以下三个层次：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    第一层：Agent Skills 开放规范                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  • 跨平台标准 (https://agentskills.io/specification)            │   │
│  │  • 定义 SKILL.md 格式、元数据字段、目录结构                       │   │
│  │  • 所有实现应遵循的基础规范                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                    第二层：Claude Code 原生系统                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  • Anthropic 官方实现，遵循并扩展 Agent Skills 规范              │   │
│  │  • 原生特性：context:fork, hooks, disable-model-invocation 等   │   │
│  │  • 四级存储结构：Enterprise > Personal > Project > Plugin        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                    第三层：superpowers 第三方插件                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  • 社区插件 (https://github.com/obra/superpowers)               │   │
│  │  • 内容级设计模式：Iron Law, Phase, Checklist, Red Flags        │   │
│  │  • 提示工程技巧："1% 可能性必须调用"                              │   │
│  │  • 非官方特性，不属 Claude Code 原生系统                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 层次归属速查表

| 特性/概念 | 归属层次 | 说明 |
|----------|---------|------|
| `name`, `description` 字段 | Agent Skills 规范 | 标准字段 |
| `allowed-tools` 字段 | Agent Skills 规范 | 规范定义，各实现支持程度不同 |
| `scripts/`, `references/`, `assets/` 目录 | Agent Skills 规范 | 标准目录结构 |
| 渐进式披露 | Agent Skills 规范 | 规范推荐的设计模式 |
| `disable-model-invocation` | Claude Code 原生 | 非规范字段 |
| `context: fork` | Claude Code 原生 | 子代理执行机制 |
| `hooks` 字段 | Claude Code 原生 | 事件驱动钩子系统（14+事件） |
| `model` 字段 | Claude Code 原生 | 模型切换 |
| 四级存储结构 | Claude Code 原生 | 分层优先级管理 |
| `!`command`` 语法 | Claude Code 原生 | 动态上下文注入 |
| Iron Law | superpowers 插件 | 内容级设计模式 |
| Phase/Checklist | superpowers 插件 | 内容级设计模式 |
| "1% 可能性必须调用" | superpowers 插件 | 提示工程技巧 |
| Rationalization Table | superpowers 插件 | 内容级设计模式 |
| CSO (description 仅触发条件) | superpowers 插件 | 插件的最佳实践 |

---

## 二、Agent Skills 开放规范解读

### 2.1 规范来源

**官方文档**：https://agentskills.io/specification

Agent Skills 是一个跨平台的开放规范，定义了技能的标准格式，使技能可以在不同的 AI 工具间共享。

### 2.2 目录结构

**Agent Skills 规范定义：**
```
skill-name/
├── SKILL.md          # 必需：YAML frontmatter + Markdown 内容
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：参考文档
└── assets/           # 可选：静态资源
```

**Claude Code 实际使用差异**：
- 官方文档示例常使用 `template.md`（单文件模板）
- 常见 `examples/` 目录（示例目录）
- 支持任意命名的参考文件（如 `implementer-prompt.md`）

这表明 Claude Code 实现比规范更灵活，不严格限定目录名称。

### 2.3 Frontmatter 字段

| 字段 | 必需 | 约束 | 说明 |
|------|------|------|------|
| `name` | 是 | 1-64字符，小写字母数字连字符 | 技能标识符 |
| `description` | 是 | 1-1024字符 | **描述做什么和何时使用** |
| `license` | 否 | - | 许可证名称或引用 |
| `compatibility` | 否 | 1-500字符 | 环境要求 |
| `metadata` | 否 | 键值映射 | 附加元数据 |
| `allowed-tools` | 否 | 空格分隔列表 | 预批准工具列表（实验性） |

### 2.4 description 字段规范（关键）

**规范原文**：
> Should describe both what the skill does and when to use it

**正确示例**（来自规范）：
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

**重要澄清**：
- superpowers 插件主张 description 仅包含触发条件（CSO 技巧）
- 这是插件的最佳实践，**不是** Agent Skills 规范要求
- 规范明确要求 description 包含"做什么"和"何时使用"

### 2.5 渐进式披露

规范推荐的上下文使用层级：

1. **元数据层** (~100 tokens)：name + description，启动时加载所有技能
2. **指令层** (<5000 tokens)：SKILL.md 主体，技能激活时加载
3. **资源层**（按需）：scripts/、references/、assets/ 中的文件

---

## 三、Claude Code 原生 Skill 系统分析

### 3.1 系统定位

Claude Code 遵循 Agent Skills 开放规范，并在此基础上提供了多项扩展特性。

**官方文档**：https://code.claude.com/docs/en/skills

### 3.2 扩展的 Frontmatter 字段

| 字段 | 规范 | Claude Code | 说明 |
|------|------|-------------|------|
| `name` | ✅ 必需 | ⚠️ 可选 | **差异**：Claude Code 省略时使用目录名 |
| `description` | ✅ | ✅ | 相同 |
| `license` | ✅ | ✅ | 相同 |
| `compatibility` | ✅ | ✅ | 相同 |
| `metadata` | ✅ | ✅ | 相同 |
| `allowed-tools` | ✅ | ✅ | 相同，支持限制+预批准 |
| `argument-hint` | ❌ | ✅ | **原生扩展**：参数提示 |
| `disable-model-invocation` | ❌ | ✅ | **原生扩展**：禁止模型自动调用 |
| `user-invocable` | ❌ | ✅ | **原生扩展**：用户可调用性 |
| `model` | ❌ | ✅ | **原生扩展**：模型切换 |
| `context` | ❌ | ✅ | **原生扩展**：设为 `fork` 启用子代理 |
| `agent` | ❌ | ✅ | **原生扩展**：子代理类型 |
| `hooks` | ❌ | ✅ | **原生扩展**：事件驱动钩子（见 3.3.3） |

### 3.3 关键原生特性详解

#### 3.3.1 `disable-model-invocation`

```yaml
---
name: deploy
description: Deploy the application to production
disable-model-invocation: true
---
```

- **功能**：防止 Claude 自动加载此技能
- **用途**：适用于有副作用的操作（部署、提交等），仅允许用户手动触发
- **行为**：description 不会被注入上下文

#### 3.3.2 `context: fork` + `agent`

```yaml
---
name: deep-research
description: Research a topic thoroughly
context: fork
agent: Explore
---
```

- **功能**：在隔离的子代理环境中执行技能
- **用途**：需要隔离执行、无访问主会话历史的任务
- **行为**：技能内容成为子代理的 prompt

#### 3.3.3 `hooks`

Claude Code 的 hooks 是一个**事件驱动系统**，而非简单的生命周期回调。它通过 `hooks.json` 配置文件定义，包含事件类型、匹配器和处理器。

**正确的事件类型（部分列表）：**

| 事件 | 触发时机 | 可否阻止操作 |
|------|---------|-------------|
| `PreToolUse` | 工具执行前 | ✅ 可以阻止 |
| `PostToolUse` | 工具执行后 | ❌ 只能观察 |
| `SessionStart` | 会话开始时 | ❌ 只能注入上下文 |
| `SessionEnd` | 会话结束时 | ❌ 只能观察 |
| `Stop` | 会话停止时 | ✅ 可以阻止 |
| `UserPromptSubmit` | 用户提交消息时 | ✅ 可以阻止 |

**正确的 hooks.json 格式：**

```json
{
  "description": "Security reminder hook",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/security_check.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**关键组件：**
- **matcher**：工具名称匹配模式，支持正则表达式（如 `"Bash"` 或 `"Edit|Write"`）
- **hooks**：处理器数组，每个处理器包含 `type`（command/prompt）和 `command`（执行的脚本）
- **timeout**：超时时间（秒）

**处理器输出格式：**
```json
// 警告（不阻止）
{ "systemMessage": "⚠️ Security warning detected" }

// 阻止操作（仅 PreToolUse）
{ "decision": "block", "reason": "Dangerous operation blocked" }
```

#### 3.3.4 `allowed-tools`

```yaml
---
name: safe-reader
description: Read files without making changes
allowed-tools: Read, Grep, Glob
---
```

- **功能**：限制技能激活时可用的工具
- **行为**：Claude 可以使用这些工具而无需逐次批准

### 3.4 四级存储结构

| 级别 | 路径 | 适用范围 | 优先级 |
|------|------|---------|--------|
| Enterprise | 托管设置 | 组织内所有用户 | 最高 |
| Personal | `~/.claude/skills/` | 用户所有项目 | 高 |
| Project | `.claude/skills/` | 当前项目 | 中 |
| Plugin | `<plugin>/skills/` | 插件启用范围 | 使用命名空间 |

**优先级规则**：同名技能按 Enterprise > Personal > Project 优先级覆盖。Plugin 使用 `plugin-name:skill-name` 命名空间，不与其他级别冲突。

### 3.5 动态上下文注入

```yaml
---
name: pr-summary
description: Summarize changes in a pull request
---

## Pull request context
- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
```

- **功能**：`` !`command` `` 语法在技能发送给 Claude 前执行 shell 命令
- **行为**：命令输出替换占位符，Claude 接收实际数据

### 3.6 字符串替换

| 变量 | 说明 |
|------|------|
| `$ARGUMENTS` | 传递给技能的所有参数 |
| `$ARGUMENTS[N]` | 第 N 个参数（0-based） |
| `$N` | `$ARGUMENTS[N]` 的简写 |
| `${CLAUDE_SESSION_ID}` | 当前会话 ID |

### 3.7 其他重要原生特性

#### 3.7.1 技能访问限制

通过 `managed settings` 可以限制 Claude 可访问的技能：

```
# 允许特定技能
Skill(commit)
Skill(review-pr *)

# 禁止特定技能
Skill(deploy *)

# 禁止所有技能
Skill
```

#### 3.7.2 实时变更检测

通过 `--add-dir` 添加的技能目录支持实时编辑和重载，无需重启会话即可看到更改。

#### 3.7.3 Monorepo 支持

当处理子目录中的文件时，Claude Code 会自动发现嵌套的 `.claude/skills/` 目录：

```
packages/frontend/
└── .claude/skills/     # 编辑 packages/frontend/ 中的文件时自动发现
```

#### 3.7.4 内容类型区分

**Reference content**：添加知识的参考内容（约定、模式、风格指南）
**Task content**：执行特定操作的步骤指令（通常设置 `disable-model-invocation: true`）

---

## 四、superpowers 第三方插件分析

### 4.1 插件定位

**仓库**：https://github.com/obra/superpowers

**重要声明**：superpowers 是由 obra 开发的**第三方社区插件**，不是 Claude Code 的官方或原生特性。以下内容是插件的设计模式，不应与 Claude Code 原生系统混淆。

### 4.2 内容级设计模式

这些模式通过 Markdown 内容实现，任何能阅读 Markdown 的 Agent 都能理解和遵循，**无需系统层面的特殊支持**。

#### 4.2.1 Iron Law

```markdown
## The Iron Law

NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST

**Violating the letter of this process is violating the spirit.**

**No exceptions:**
- Not for "simple additions"
- Not for "just adding a section"
- Don't keep untested changes as "reference"
```

**性质**：Markdown 内容，内容级约束

#### 4.2.2 Phase/Checklist

```markdown
## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation
1. Read Error Messages Carefully
2. Reproduce Consistently
3. Check Recent Changes

### Phase 2: Pattern Analysis
...

### Phase 3: Hypothesis and Testing
...

### Phase 4: Implementation
...
```

**性质**：Markdown 内容，内容级流程控制

#### 4.2.3 Rationalization Table

```markdown
| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Emergency" | Systematic is faster than thrashing. |
```

**性质**：Markdown 表格，内容级反模式

#### 4.2.4 Red Flags

```markdown
## Red Flags - STOP

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "One more fix attempt" (when already tried 2+)

**ALL mean: STOP. Return to Phase 1.**
```

**性质**：Markdown 内容，内容级警告

### 4.3 提示工程技巧

#### 4.3.1 "1% 可能性必须调用"规则

**来源**：`skills/using-superpowers/SKILL.md`

```markdown
<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what
you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE.
YOU MUST USE IT.
</EXTREMELY-IMPORTANT>
```

**性质**：提示工程技巧，通过强调语气增强 Agent 的技能使用意识

#### 4.3.2 CSO (Claude Search Optimization)

**来源**：`skills/writing-skills/SKILL.md`

**核心观点**：description 仅包含触发条件，不包含工作流程摘要

```yaml
# ❌ 错误（superpowers 观点）：总结了工作流程
description: Use when executing plans - dispatches subagent per task with code review

# ✅ 正确（superpowers 观点）：仅包含触发条件
description: Use when executing implementation plans with independent tasks
```

**重要澄清**：
- 这是 superpowers 插件的最佳实践
- **不是** Agent Skills 规范要求
- 规范明确要求 description 描述"做什么"和"何时使用"

### 4.4 superpowers 模式实现建议

**关键洞察**：这些模式是**内容级**的，不需要系统级支持。

**推荐实现方式**：
1. 在 SKILL.md 中直接使用这些 Markdown 模式
2. 任何 Agent 只要能阅读 Markdown 就能理解和遵循
3. 无需在 `SkillMetadata` 中添加 `phases`、`iron_law` 等字段

**不建议**：
```python
# ❌ 过度工程化
class SkillMetadata(TypedDict):
    phases: list[SkillPhase]      # 不需要系统级支持
    iron_law: str | None          # 不需要系统级支持
    rationalizations: dict        # 不需要系统级支持
```

**推荐**：
```markdown
# ✅ 在 SKILL.md 中使用 Markdown
## The Iron Law
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

---

## 五、DeepAgents 现有实现分析

### 5.1 实现概述

**文件位置**：`libs/deepagents/deepagents/middleware/skills.py`

DeepAgents 的 SkillsMiddleware 实现了 Agent Skills 规范的核心功能，采用渐进式披露模式。

### 5.2 已实现功能

#### 5.2.1 元数据解析

```python
class SkillMetadata(TypedDict):
    name: str
    description: str
    path: str
    license: str | None
    compatibility: str | None
    metadata: dict[str, str]
    allowed_tools: list[str]
```

**符合规范**：完整支持 Agent Skills 规范的所有字段

#### 5.2.2 渐进式披露

```python
SKILLS_SYSTEM_PROMPT = """
## Skills System
**Available Skills:**
{skills_list}

**How to Use Skills (Progressive Disclosure):**
1. Recognize when a skill applies
2. Read the skill's full instructions
3. Follow the skill's instructions
4. Access supporting files
"""
```

**实现方式**：
- `before_agent`: 扫描 sources，加载 skills_metadata
- `wrap_model_call`: 注入技能列表到 system prompt
- Agent 自主决定何时读取完整内容

#### 5.2.3 Source 优先级覆盖

```python
def before_agent(self, state, runtime, config):
    all_skills: dict[str, SkillMetadata] = {}
    for source_path in self.sources:
        source_skills = _list_skills(backend, source_path)
        for skill in source_skills:
            all_skills[skill["name"]] = skill  # 后者覆盖前者
    return SkillsStateUpdate(skills_metadata=list(all_skills.values()))
```

#### 5.2.4 BackendProtocol 抽象

```python
def __init__(self, *, backend: BACKEND_TYPES, sources: list[str]):
    self._backend = backend
    self.sources = sources
```

**支持后端**：StateBackend（内存）、FilesystemBackend（磁盘）、StoreBackend（LangGraph Store）

#### 5.2.5 完整异步支持

```python
async def abefore_agent(...)
async def awrap_model_call(...)
```

#### 5.2.6 安全限制

```python
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10MB
```

#### 5.2.7 加载优化

```python
def before_agent(self, state, runtime, config):
    # 优化：避免重复加载
    if "skills_metadata" in state:
        return None  # 已存在则跳过
    ...
```

此优化逻辑避免了每次 agent 迭代时重新扫描技能目录。

#### 5.2.8 子代理技能隔离

主代理与自定义子代理的技能状态完全隔离，子代理不会继承主代理的 `skills_loaded` 状态。

### 5.3 未实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| `load_skill` 工具 | ❌ 缺失 | Agent 需使用通用 read_file |
| `skills_loaded` 状态 | ❌ 缺失 | 无法追踪已激活技能 |
| `allowed_tools` 强制执行 | ❌ 仅显示 | 已解析但不强制 |
| 资源目录发现 | ❌ 缺失 | 不支持 scripts/references/assets |
| `/skill` 用户调用 | ❌ 缺失 | 无用户主动触发机制 |
| `context: fork` | ❌ 缺失 | 无子代理执行支持 |
| `hooks` 机制 | ❌ 缺失 | 无生命周期钩子 |

### 5.4 与规范对比

| Agent Skills 规范要求 | DeepAgents 实现 |
|----------------------|-----------------|
| SKILL.md 格式 | ✅ 完整支持 |
| name 字段 | ✅ 支持（64字符限制） |
| description 字段 | ✅ 支持（1024字符限制） |
| license 字段 | ✅ 支持 |
| compatibility 字段 | ✅ 支持 |
| metadata 字段 | ✅ 支持 |
| allowed-tools 字段 | ⚠️ 解析但不强制 |
| scripts/ 目录 | ❌ 不支持发现 |
| references/ 目录 | ❌ 不支持发现 |
| assets/ 目录 | ❌ 不支持发现 |
| 渐进式披露 | ⚠️ 部分实现（无状态追踪） |

---

## 六、系统性对比

### 6.1 三方系统特性对比

| 特性 | Agent Skills 规范 | Claude Code 原生 | DeepAgents | superpowers |
|------|------------------|-----------------|------------|-------------|
| **规范遵循** | - | ✅ 扩展 | ✅ 核心遵循 | ✅ 遵循 |
| **基础元数据** | ✅ 定义 | ✅ 支持 | ✅ 支持 | ✅ 支持 |
| **allowed-tools** | ✅ 定义 | ✅ 强制执行 | ⚠️ 仅显示 | ✅ 使用 |
| **资源目录** | ✅ 定义 | ✅ 支持 | ❌ 不支持 | ✅ 使用 |
| **渐进式披露** | ✅ 推荐 | ✅ 完整实现 | ⚠️ 部分实现 | ✅ 使用 |
| **disable-model-invocation** | ❌ | ✅ 原生扩展 | ❌ | ❌ |
| **context: fork** | ❌ | ✅ 原生扩展 | ❌ | ❌ |
| **hooks** | ❌ | ✅ 原生扩展 | ❌ | ❌ |
| **四级存储** | ❌ | ✅ 原生特性 | ⚠️ Source 优先级 | ❌ |
| **Iron Law** | ❌ | ❌ | ❌ | ✅ 内容模式 |
| **Phase/Checklist** | ❌ | ❌ | ❌ | ✅ 内容模式 |
| **"1% 可能性"规则** | ❌ | ❌ | ❌ | ✅ 提示技巧 |
| **CSO 技巧** | ❌ | ❌ | ❌ | ✅ 最佳实践 |

### 6.2 差距性质分析

| 差距类型 | 说明 | 优先级 |
|---------|------|--------|
| **规范对齐** | 与 Agent Skills 规范的差异 | 高 |
| **原生特性借鉴** | Claude Code 原生扩展特性 | 中 |
| **社区实践参考** | superpowers 的内容级模式 | 低（内容层面） |

---

## 七、差距分析与优化建议

### 7.1 规范对齐差距（优先级：高）

#### 7.1.1 资源目录支持

**现状**：DeepAgents 不支持 scripts/、references/、assets/ 目录的发现

**规范要求**：
```
skill-name/
├── SKILL.md
├── scripts/       # 可执行脚本
├── references/    # 参考文档
└── assets/        # 静态资源
```

**建议实现**：

```python
RESOURCE_DIRS = {
    "scripts": "script",
    "references": "reference",
    "assets": "asset",
}

def _discover_resources(
    backend: BackendProtocol,
    skill_dir: str
) -> list[dict]:
    """发现技能目录下的资源文件"""
    resources = []
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
                resources.append({
                    "path": f["path"],
                    "type": resource_type,
                })

    return resources
```

#### 7.1.2 skills_loaded 状态追踪

**现状**：无状态追踪，无法实现完整的渐进式披露闭环

**建议**：

```python
class SkillsState(AgentState):
    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]
    skills_loaded: NotRequired[Annotated[list[str], PrivateStateAttr]]  # 新增
```

#### 7.1.3 load_skill 工具

**现状**：Agent 需使用通用 read_file，无专用工具

**建议**：

```python
@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> str | Command:
    """加载并激活一个技能

    Args:
        skill_name: 技能名称

    Returns:
        技能完整内容
    """
    metadata = runtime.state.get("skills_metadata", [])
    skill = next((s for s in metadata if s["name"] == skill_name), None)

    if not skill:
        return f"Skill '{skill_name}' not found."

    # 更新 skills_loaded 状态
    current_loaded = list(runtime.state.get("skills_loaded", []))
    if skill_name not in current_loaded:
        current_loaded.append(skill_name)
        return Command(update={
            "skills_loaded": current_loaded,
            "messages": [ToolMessage(
                content=_read_skill_content(skill["path"]),
                tool_call_id=runtime.tool_call_id
            )]
        })

    return f"Skill '{skill_name}' already loaded."
```

#### 7.1.4 allowed_tools 强制执行

**现状**：已解析 allowed_tools 但不强制执行

**建议**：

```python
def wrap_tool_call(self, request, handler):
    """在工具调用前检查 allowed_tools 权限"""
    tool_name = request.tool.name

    skills_loaded = request.state.get("skills_loaded", [])
    skills_metadata = request.state.get("skills_metadata", [])

    all_allowed: set[str] = set()
    for skill in skills_metadata:
        if skill["name"] in skills_loaded:
            all_allowed.update(skill.get("allowed_tools", []))

    if all_allowed and tool_name not in all_allowed:
        return ToolMessage(
            content=f"Tool '{tool_name}' not allowed. Allowed: {sorted(all_allowed)}",
            tool_call_id=request.tool_call.id,
        )

    return handler(request)
```

> **可行性说明**：需验证与 LangChain `AgentMiddleware` 的 `wrap_tool_call` 接口兼容性。当前 DeepAgents 使用的中间件基类可能不支持此钩子，需扩展或使用替代方案。

### 7.2 原生特性借鉴（优先级：中）

#### 7.2.1 disable-model-invocation 支持

**价值**：允许定义仅用户可触发的技能

**建议**：

```python
class SkillMetadata(TypedDict):
    # ... 现有字段
    disable_model_invocation: bool  # 新增
```

在 `wrap_model_call` 中过滤：
```python
def _format_skills_list(self, skills):
    # 过滤掉 disable_model_invocation 为 True 的技能
    visible_skills = [s for s in skills if not s.get("disable_model_invocation")]
    ...
```

#### 7.2.2 /skill 用户调用支持

**价值**：赋予用户直接控制权

**建议**：

```python
def process_message(self, message: str, state, runtime, config):
    """在消息处理中识别 /skill 语法"""
    if message.startswith("/"):
        skill_name = message[1:].strip().split()[0]
        # 检查技能是否存在
        metadata = state.get("skills_metadata", [])
        if any(s["name"] == skill_name for s in metadata):
            return Command(
                update={"messages": [...]}
            )
    return None
```

> **可行性说明**：此功能需要在消息预处理阶段实现，可能需要扩展 DeepAgents 的消息处理流程。建议与 CLI 层（`libs/cli`）协调实现，或在 `SkillsMiddleware` 中添加消息拦截逻辑。

### 7.3 社区实践参考（优先级：低）

#### 7.3.1 强制检查提示

**来源**：superpowers 的提示工程技巧

**建议**：作为可选的系统提示增强

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

#### 7.3.2 Iron Law 等内容模式

**建议**：**不需要系统级实现**

这些模式应在 SKILL.md 的 Markdown 内容中实现，而非作为 SkillMetadata 的字段。任何 Agent 只要能阅读 Markdown 就能理解和遵循。

---

## 八、实现路线图

### 8.1 Phase 1：对齐规范与基础建设

**目标**：完整实现 Agent Skills 规范核心功能

| 任务 | 描述 | 依赖 |
|------|------|------|
| 1.1 | 扩展 SkillsState 添加 skills_loaded 字段 | 无 |
| 1.2 | 实现 load_skill 专用工具 | 1.1 |
| 1.3 | 实现 _discover_resources() 资源发现 | 无 |
| 1.4 | 扩展 SkillMetadata 添加 resources 字段 | 1.3 |
| 1.5 | 实现 load_skill_resource 工具 | 1.3, 1.4 |
| 1.6 | 实现 allowed_tools 强制执行 | 1.1 |
| 1.7 | 增强 wrap_model_call 实现按需内容注入 | 1.1, 1.2 |

**交付物**：
- 完整对齐 Agent Skills 规范的 SkillsMiddleware
- load_skill 和 load_skill_resource 工具
- allowed_tools 权限控制

### 8.2 Phase 2：强化流程控制与用户体验

**目标**：引入轻量级流程控制，提升用户主动性

| 任务 | 描述 | 依赖 |
|------|------|------|
| 2.1 | 注入可选的强制检查提示 | 无 |
| 2.2 | 支持 /skill 用户调用 | Phase 1 |
| 2.3 | 支持 disable-model-invocation 字段 | 无 |

**交付物**：
- 用户主动触发技能的能力
- 可配置的强制检查机制

### 8.3 Phase 3：引入高级原生特性

**目标**：借鉴 Claude Code 原生系统的高价值特性

| 任务 | 描述 | 依赖 |
|------|------|------|
| 3.1 | 研究 context: fork 与 SubAgentMiddleware 集成方案 | Phase 1 |
| 3.2 | 设计并实现与 Claude Code 兼容的事件驱动 hooks 系统，优先支持 `PreToolUse` 和 `PostToolUse` 事件 | Phase 1 |
| 3.3 | 支持动态上下文注入 `` !`command` `` 语法 | 无 |

**交付物**：
- 子代理执行能力
- 事件驱动钩子系统（支持 `PreToolUse`, `PostToolUse`, `SessionStart` 等事件）

### 8.4 Phase 4：构建生态系统

**目标**：建立技能分发和管理机制

| 任务 | 描述 | 依赖 |
|------|------|------|
| 4.1 | 设计插件清单规范 | Phase 3 |
| 4.2 | 实现插件加载器 | 4.1 |
| 4.3 | 探索 MCP 协议集成 | Phase 1 |

**交付物**：
- 插件管理系统
- 技能分发能力

---

## 九、附录

### A. 参考资源

| 资源 | URL |
|------|-----|
| Agent Skills 规范 | https://agentskills.io/specification |
| Claude Code 技能文档 | https://code.claude.com/docs/en/skills |
| superpowers 仓库 | https://github.com/obra/superpowers |
| DeepAgents SkillsMiddleware | libs/deepagents/deepagents/middleware/skills.py |

### B. 术语表

| 术语 | 定义 | 归属 |
|------|------|------|
| Progressive Disclosure | 渐进式披露：按需加载详细内容 | Agent Skills 规范 |
| allowed-tools | 预批准工具列表 | Agent Skills 规范 |
| disable-model-invocation | 禁止模型自动加载技能 | Claude Code 原生 |
| context: fork | 在隔离子代理中执行技能 | Claude Code 原生 |
| hooks | 事件驱动钩子系统（PreToolUse、PostToolUse 等） | Claude Code 原生 |
| Iron Law | 不可违反的核心规则（内容模式） | superpowers 插件 |
| CSO | Claude Search Optimization | superpowers 插件 |

### C. 修订说明

**v2.0 修正（基于首次专家评审）：**
1. **层次混淆修正**：明确区分 Agent Skills 规范、Claude Code 原生系统、superpowers 第三方插件
2. **事实错误修正**：
   - "1% 可能性必须调用" 是 superpowers 插件的提示技巧，非 Claude Code 原生
   - Iron Law、Phase、Checklist 是内容级模式，非系统级特性
   - description 仅包含触发条件是 superpowers 的 CSO 最佳实践，非规范要求
3. **分析框架重构**：按照"规范对齐 → 原生借鉴 → 社区参考"的优先级组织
4. **实现建议修正**：避免将内容级模式过度工程化为系统级特性

**v2.1 修正（基于二次专家评审）：**
1. **hooks 系统完全重写**：
   - 修正错误的生命周期阶段描述（`on_load` 等 → 事件驱动系统）
   - 提供正确的 JSON 配置格式
   - 列出实际事件类型（`PreToolUse`, `PostToolUse`, `SessionStart` 等）
2. **规范与实现差异标注**：
   - `name` 字段：规范必需，Claude Code 可选
   - 资源目录：规范定义 vs Claude Code 实际使用差异
3. **补充遗漏原生特性**：managed settings 限制、实时变更检测、monorepo 支持、内容类型区分
4. **补充 DeepAgents 实现细节**：加载优化逻辑、子代理技能隔离
5. **可行性分析增强**：为关键建议添加与 `AgentMiddleware` 接口兼容性说明

---

## 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0 | 2026-02-16 | 初始版本（已废弃，存在层次混淆错误） |
| 2.0 | 2026-02-16 | 基于首次专家评审完全重写：修正层次混淆、事实错误，重构分析框架 |
| 2.1 | 2026-02-16 | 基于二次专家评审修正：①修正 hooks 系统描述（事件驱动，14+事件）；②标注 name 字段在 Claude Code 中可选；③补充资源目录差异；④补充遗漏原生特性（managed settings、实时变更检测、monorepo 支持）；⑤补充 DeepAgents 加载优化逻辑；⑥添加可行性分析注释 |

---

*本报告严格区分 Agent Skills 开放规范、Claude Code 原生 Skill 系统、以及 superpowers 第三方插件。所有事实陈述均基于官方文档和源代码验证。*
