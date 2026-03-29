# 外部团队 API 使用指南

**版本**: 2.0.0
**日期**: 2026-03-20
**SDK 版本**: 0.5.0 / CLI 版本: 0.0.34
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

### 1.2 名称级 allowlist（按 SubAgent 精准可见）

除了目录级控制（`skills=[...]`），你可以为某个 SubAgent 指定“名称级 allowlist”，让该 SubAgent 仅看到并可加载被列入名单的技能。这样可以保证不同 SubAgent 的能力边界更清晰，系统提示更聚焦。

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4o-mini",
    skills=["/skills/user", "/skills/project"],  # 目录级来源仍然有效
    subagents=[
        {
            "name": "research_agent",
            "description": "Research focused agent",
            "system_prompt": "...",
            "skills": ["/skills/user", "/skills/project"],
            "skills_allowlist": ["web-research", "source-eval", "outline", "note-take"],
        },
        {
            "name": "analysis_agent",
            "description": "Analysis focused agent",
            "system_prompt": "...",
            "skills": ["/skills/user", "/skills/project"],
            "skills_allowlist": ["code-review", "test-plan", "security-audit", "perf-check", "api-trace", "db-inspect"],
        },
    ],
)
```

- allowlist 中的名称需与技能 frontmatter 的 `name` 字段一致（小写连字符）。
- 不设置 `skills_allowlist` 时行为保持兼容：SubAgent 将看到来源目录下全部技能。
- 若需要主 Agent 也做全局收敛，可手动在 `middleware` 中注入自定义的 `SkillsMiddleware(allowed_skills=[...])`。

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

| DeepAgents 版本 | 动态加载支持 | 文档转换支持 | 异步子代理 | 推荐做法 |
|----------------|-------------|-------------|-----------|----------|
| < 0.4.0 | ❌ 不支持 | ❌ 不支持 | ❌ | 升级版本 |
| 0.4.0 - 0.4.3 | ⚠️ 部分支持 | ❌ | ❌ | 使用 `expose_dynamic_tools=True` |
| 0.4.4 - 0.4.10 | ✅ 完全支持 | ❌ | ❌ | 升级到最新版本 |
| 0.4.11 | ✅ 完全支持 | ✅ read_file 自动转换 | ❌ | 安装 `[converters]` 依赖 |
| ≥ 0.5.0 | ✅ 完全支持 | ✅ read_file 自动转换 | ✅ 远程 LangGraph | **当前版本**，见下方变更说明 |

---

## 🆕 二进制文档转换（0.4.11 新增）

### 概述

自 `0.4.11` 起，`read_file` 工具内置了二进制文档自动转换能力。Agent 可以直接读取 PDF、Word、Excel、PowerPoint 等格式，无需手动调用 `execute("pdftotext ...")` 或 `execute("pandoc ...")`。

### ⚠️ 必要操作：安装可选依赖

此功能依赖可选包。**请在升级后执行以下安装命令**：

```bash
# 安装文档转换依赖（必须）
pip install deepagents[converters]

# 或者在 requirements.txt / pyproject.toml 中更新
deepagents[converters]>=0.4.11
```

**包含的依赖**：

| 包 | 版本要求 | 用途 | 体积 |
|----|---------|------|------|
| `pdfplumber` | ≥0.10.0 | PDF 文档解析 | ~2 MB |
| `python-docx` | ≥1.0.0 | Word (.docx) 文档解析 | ~1 MB |
| `openpyxl` | ≥3.1.0 | Excel (.xlsx) 表格解析 | ~4 MB |
| `python-pptx` | ≥0.6.23 | PowerPoint (.pptx) 解析 | ~3 MB |
| `puremagic` | ≥1.20 | MIME 类型检测（magic bytes） | <1 MB |

**总计约 11 MB**，无系统级依赖（不需要 poppler、tesseract 等）。

### 不安装会怎样？

**不会导致任何错误或崩溃。** 未安装时：

- 现有的文本文件、图片读取行为完全不变
- 对 PDF/DOCX/XLSX/PPTX 调用 `read_file` 会返回友好的安装提示：
  ```
  Error: No converter available for '/uploads/report.pdf' (type: .pdf).
  Install optional dependencies: pip install deepagents[converters]
  ```
- Agent 可以根据此提示自行引导用户安装，或 fallback 到 `execute` 工具

### 支持的文件格式

| 格式 | 扩展名 | 输出 | 分页 |
|------|--------|------|------|
| PDF | `.pdf` | Markdown（含表格） | ✅ `offset=N` 读取第 N 页 |
| Word | `.docx` | Markdown | ❌ 全文输出 |
| Excel | `.xlsx` | Markdown 表格 | ❌ 全文输出 |
| PowerPoint | `.pptx` | Markdown（含幻灯片标题） | ✅ `offset=N` 读取第 N 张 |
| 图片 | `.png/.jpg/.gif/.webp` | 多模态 ImageBlock | — |
| 文本/代码 | `.py/.md/.txt/.json/...` | 带行号文本（不变） | 按行分页（不变） |

> **注意**：旧版 Office 格式（`.doc`、`.xls`、`.ppt`）的扩展名虽已注册，但底层库不支持 Office 97-2003 格式，转换会失败并返回错误提示。请引导用户转换为新格式后再上传。

### 使用方式

**对 Agent 用户**：无需任何代码变更。Agent 直接调用 `read_file` 即可：

```
用户：请帮我分析这份 PDF 报告
Agent：我来读取这份报告。
      → read_file("/uploads/report.pdf")
      → 返回 Markdown 格式的报告内容
```

**对开发者（编程方式调用）**：

```python
from deepagents import create_deep_agent

# 无需额外配置，read_file 自动检测格式
agent = create_deep_agent()

result = agent.invoke({
    "messages": [{"role": "user", "content": "读取 /uploads/report.pdf"}]
})
# Agent 将调用 read_file("/uploads/report.pdf") → 返回 Markdown
```

**分页读取大型 PDF**：

```python
# Agent 可以按页读取，避免上下文溢出
# read_file("/uploads/long_report.pdf", offset=1)  → 第 1 页
# read_file("/uploads/long_report.pdf", offset=2)  → 第 2 页
# offset=0 或不传 → 全文
```

### 自定义 Converter（高级）

如需支持额外格式，可注册自定义转换器：

```python
from pathlib import Path
from deepagents.middleware.converters import BaseConverter, ConverterRegistryManager

class EPubConverter(BaseConverter):
    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        import ebooklib
        from ebooklib import epub
        book = epub.read_epub(str(path))
        # ... 提取文本并转为 Markdown
        return markdown_text

manager = ConverterRegistryManager()
manager.register("application/epub+zip", EPubConverter())
```

### 常见问题

#### Q: 安装 `deepagents[converters]` 后需要重启服务吗？

A: 是的。Converter 注册表在首次调用时惰性初始化，安装后需要重启 Python 进程使新包生效。

#### Q: 远程沙箱（Daytona/Modal）中如何安装？

A: 在沙箱的 Dockerfile 或初始化脚本中添加：
```dockerfile
RUN pip install deepagents[converters]
```

#### Q: 转换大文件会不会阻塞事件循环？

A: 不会。async 路径通过 `asyncio.to_thread` 将 CPU 密集型转换卸载到线程池。sync 路径在当前线程执行，如果调用方使用 async API 则自动走 async 路径。

#### Q: 临时文件会不会泄漏？

A: 不会。转换使用 `tempfile.mkstemp()` + `finally: unlink()`，即使转换过程抛出异常也保证清理。

---

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

## v0.5.0 变更说明（2026-03-20）

### Backend 返回类型升级

v0.5.0 将 Backend 方法的返回类型从裸 `list`/`str` 升级为强类型 dataclass：

| 旧方法名 | 新方法名 | 返回类型 |
|----------|---------|----------|
| `ls_info()` | **`ls()`** | `LsResult(error, entries)` |
| `read()` | `read()` (不变) | `ReadResult(error, file_data)` |
| `grep_raw()` | **`grep()`** | `GrepResult(error, matches)` |
| `glob_info()` | **`glob()`** | `GlobResult(error, matches)` |
| `write()` | `write()` (不变) | `WriteResult(error, ...)` |
| `edit()` | `edit()` (不变) | `EditResult(error, ...)` |

**兼容性**：旧方法名（`ls_info`/`grep_raw`/`glob_info`）和旧返回类型仍可工作（deprecation shim），但会打印 `DeprecationWarning`。建议尽早迁移到新方法名。

**迁移示例**：
```python
# 旧代码
items = backend.ls_info("/path")
for item in items:
    print(item["path"])

# 新代码 (方法名 + 返回类型都更新)
from deepagents.backends.protocol import LsResult
result = backend.ls("/path")  # ls_info → ls
if isinstance(result, LsResult):
    for item in result.entries or []:
        print(item["path"])
```

### 图片读取方式变更

v0.5.0 中，图片文件（`.png/.jpg/.gif/.webp`）的读取不再通过 `download_files()` + base64 编码实现，而是通过统一的 `read()` → `ReadResult` → `_handle_read_result` 路径返回 multimodal `ToolMessage`。

**对外部团队的影响**：如果您的代码直接调用 `backend.read()` 读取图片文件，返回值现在是 `ReadResult` 对象（`file_data` 中 `content` 为 base64 编码，`encoding` 字段为 `"base64"`），而非纯文本字符串。

### 异步子代理（新功能）

v0.5.0 新增 `AsyncSubAgentMiddleware`，支持连接远程 LangGraph 服务器的异步子代理。

> **注意**：`async_subagents` 参数已合并到统一的 `subagents` 参数中。通过 `graph_id` 字段自动识别异步子代理。

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    subagents=[
        # 同步子代理
        {"name": "helper", "description": "Helper agent", "system_prompt": "You help."},
        # 异步子代理 (通过 graph_id 识别)
        {
            "name": "researcher",
            "description": "Research agent on remote server",
            "graph_id": "research-agent",
            "url": "http://localhost:8123",
        }
    ],
)
```

提供 5 个工具：`start_async_task`、`check_async_task`、`update_async_task`、`cancel_async_task`、`list_async_tasks`。

> **注意**：工具名已从 `*_async_subagent*` 重命名为 `*_async_task*`。`AsyncSubAgentJob` 已重命名为内部类 `AsyncTask`，不再公共导出。

### 新增公共 API 导出

```python
from deepagents import AsyncSubAgent, AsyncSubAgentMiddleware
```

### Default Model 变更

默认模型从 `claude-sonnet-4-5-20250929` 更新为 `claude-sonnet-4-6`。

### 依赖版本要求变更

| 依赖 | 旧版本要求 | 新版本要求 |
|------|-----------|-----------|
| `langchain-core` | >=1.2.18 | >=1.2.19 |
| `langchain` | >=1.2.11 | >=1.2.12 |
| `langchain-anthropic` | >=1.3.4 | >=1.3.5 |

---

## 相关文档

- [API 参考文档（含 Converter API）](API_REFERENCE.md)
- [动态加载问题定位指南](../integrations/skills/dynamic_loading_guide.md)
- [SkillsMiddleware V2 升级方案](../skillsmiddleware_docs/DeepAgents_SkillsMiddlewareV2升级设计方案.md)
- [统一文件读取器设计文档](../unified_file_reader/UNIFIED_FILE_READER_DESIGN.md)
- [Converter 集成 Changelog](../../CHANGELOG_CONVERTER_INTEGRATION.md)
- [上游合并风险分析](../upstream_merge/2026-03-17_upstream_143_commits_risk_analysis.md)

## 支持与反馈

如果您在集成过程中遇到问题：

1. **检查版本**: 确保使用最新版 DeepAgents (`pip show deepagents`)
2. **检查依赖**: 确认 `[converters]` 已安装 (`pip show pdfplumber python-docx openpyxl python-pptx puremagic`)
3. **查看日志**: 启用调试模式获取详细信息 (`logging.getLogger("deepagents").setLevel("DEBUG")`)
4. **验证配置**: 对照本指南检查参数设置
5. **提交问题**: 在项目仓库创建 Issue，包含错误详情和版本信息

---

## Round 8+9 变更通知 (2026-03-29)

### 向后兼容变更

- **FileData 类型**: `created_at`/`modified_at` 变为 `NotRequired[str]`。构造 `FileData` 时可省略这两个字段。
- **FilesystemMiddleware**: 新增 `human_message_token_limit_before_evict` 参数（默认 50000），超大 HumanMessage 自动驱逐到文件系统。
- **FilesystemBackend.edit()**: 自动规范化 CRLF 行结束符。

### 需要关注的变更

- **`wrap_model_call`/`awrap_model_call` 返回类型**: 从 `ModelResponse[ResponseT]` 扩展为 `ModelResponse[ResponseT] | ExtendedModelResponse`。如果外部团队有自定义 middleware 子类覆写了这些方法，需检查返回类型标注与类型检查结果。
- **依赖版本下限**: `langchain-core` ≥ 1.2.22, `langchain-google-genai` ≥ 4.2.1。源码直连或严格锁定版本的团队需做依赖求解验证。

---

*本指南最后更新：2026-03-29*
