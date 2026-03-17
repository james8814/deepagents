# 上游 143 个提交合并风险分析报告

**分析日期**: 2026-03-17
**本地版本**: SDK 0.4.10 / CLI 0.0.27 (master, HEAD: 65ca8985)
**上游版本**: SDK 0.5.0 / CLI 0.0.34 (upstream/main, HEAD: 626fb6fb)
**提交数量**: 143 个新提交待合并

---

## 一、版本跳跃概览

| 项目 | 本地 master | 上游 main | 差距 |
|------|------------|-----------|------|
| SDK | 0.4.10 | 0.5.0（main 分支预发布，PyPI 最新为 0.4.11） | 主版本跳跃 |
| CLI | 0.0.27 | 0.0.34 | 跨 7 个 minor 版本 |
| langchain-core | >=1.2.18 | >=1.2.19 | 小版本 |
| langchain | >=1.2.11 | >=1.2.12 | 小版本 |
| langchain-anthropic | >=1.3.4 | >=1.3.5 | 小版本 |

---

## 二、破坏性 API 变更（影响外部调用者）

### 2.1 `create_deep_agent()` 签名变化 — 高风险

| 参数 | 本地 | 上游 0.5 | 影响 |
|------|------|----------|------|
| `skills_expose_dynamic_tools: bool = False` | 存在 | **已移除** | 调用者传此参数会 TypeError |
| `state_schema: type[Any] \| None = None` | 存在（本地刚添加） | **已移除** | 同上 |
| `async_subagents: list[AsyncSubAgent] \| None = None` | 不存在 | **新增** | 非破坏性，新功能 |

**影响范围**: 所有直接调用 `create_deep_agent()` 并传递 `skills_expose_dynamic_tools` 或 `state_schema` 的外部项目。

### 2.2 Backend 返回类型体系重构 — 极高风险

上游引入全新结构化返回类型，替代原来的裸 `list` 和 `str`：

| 方法 | 本地返回类型 | 上游返回类型 | 兼容层 |
|------|------------|------------|--------|
| `ls_info()` | `list[FileInfo]` | `LsResult` | 有（deprecation warning） |
| `read()` | `str` | `ReadResult` | 有（deprecation warning） |
| `grep_raw()` | `list[GrepMatch] \| str` | `GrepResult` | 有 |
| `glob_info()` | `list[FileInfo]` | `GlobResult` | 有 |

**新增数据类型**:

```python
@dataclass
class LsResult:
    error: str | None = None
    entries: list[FileInfo] | None = None

@dataclass
class ReadResult:
    error: str | None = None
    file_data: FileData | None = None

@dataclass
class GrepResult:
    error: str | None = None
    matches: list[GrepMatch] | None = None

@dataclass
class GlobResult:
    error: str | None = None
    matches: list[FileInfo] | None = None
```

### 2.3 FileData 格式变更 — 高风险

| 字段 | 本地 FileData | 上游 FileData |
|------|-------------|-------------|
| `content` | `list[str]`（按行分割） | `str`（单字符串，UTF-8 或 base64） |
| `encoding` | **不存在** | `"utf-8" \| "base64"` **新增** |

上游引入 `FileFormat` 版本控制：
- `"v1"`: 旧格式（`content: list[str]`，无 `encoding`）— 对应本地当前格式
- `"v2"`: 新格式（`content: str`，含 `encoding`）

本地 `StateBackend.ls_info()` 执行 `len("\n".join(fd.get("content", [])))` — 依赖 `content` 是 `list[str]`，合并后与上游 v2 格式不兼容。

### 2.4 公共 API 导出变化 — 中等风险

| 导出名 | 本地 | 上游 | 影响 |
|--------|------|------|------|
| `upload_files` | 存在 | **已移除** | `from deepagents import upload_files` 会 ImportError |
| `UploadResult` | 存在 | **已移除** | 同上 |
| `AsyncSubAgent` | 不存在 | **新增** | 非破坏性 |
| `AsyncSubAgentMiddleware` | 不存在 | **新增** | 非破坏性 |

---

## 三、本地优越特性冲突风险

### 3.1 冲突文件矩阵

| 文件 | 本地行数 | 上游估计 | 冲突风险 | 原因 |
|------|---------|---------|---------|------|
| `middleware/skills.py` | 1190 行 | ~834 行 | **极高** | V2 完全不在上游，`__init__` 参数不兼容 |
| `graph.py` | ~345 行 | ~320 行 | **高** | 参数移除 + middleware 顺序变化 |
| `middleware/filesystem.py` | 大文件 | 重写 | **高** | FileData 格式变更，Converter 系统冲突 |
| `backends/protocol.py` | ~519 行 | 更多 | **高** | 新增 LsResult/ReadResult 等全部方法签名变化 |
| `backends/state.py` | ~200 行 | 变化 | **中** | ls_info 返回旧类型，需适配新类型 |
| `__init__.py` | ~21 行 | 不同 | **中** | upload_files/UploadResult 被移除 |
| `middleware/subagents.py` | ~807 行 | 类似 | **低-中** | 本地 subagent_logs 特性，上游变化不大 |
| `middleware/memory.py` | 大文件 | 类似 | **中** | isawaitable 修复已被上游覆盖过两次 |
| `middleware/summarization.py` | 大文件 | 类似 | **低** | create_summarization_middleware 上游也存在 |

### 3.2 本地独有特性清单（合并时必须保留）

1. **SkillsMiddleware V2**（`middleware/skills.py`，1190 行）
   - `load_skill` / `unload_skill` 动态工具
   - `expose_dynamic_tools` 参数
   - `allowed_skills` 过滤
   - `max_loaded_skills=10` 上限
   - Per-SubAgent 技能过滤（`skills_allowlist` 字段）

2. **Converter 系统**（`middleware/converters/`）
   - PDF/DOCX/XLSX/PPTX 自动转 Markdown
   - 上游不存在该目录

3. **upload_adapter.py**（V5.0）
   - `upload_files()` 工具
   - `UploadResult` 类型
   - 上游已将其从公共 API 移除

4. **Memory 异步/同步兼容**（`middleware/memory.py`）
   - `inspect.isawaitable()` 模式
   - 已被上游覆盖过两次，合并时需特别注意

5. **SubAgent 日志功能**（`middleware/subagents.py`）
   - `_ENABLE_SUBAGENT_LOGGING` 环境变量门控
   - `_extract_subagent_logs` / `_redact_sensitive_fields` / `_truncate_text`

6. **state_schema 参数**（`graph.py`）
   - `create_deep_agent()` 接受自定义状态模式
   - 上游已移除此参数

---

## 四、对外部依赖项目的具体影响

### 4.1 使用 `create_deep_agent()` 的项目

| 调用方式 | 合并后影响 |
|---------|-----------|
| `create_deep_agent(skills_expose_dynamic_tools=True)` | **TypeError — 立即报错** |
| `create_deep_agent(state_schema=MyState)` | **TypeError — 立即报错** |
| `create_deep_agent(model="openai:gpt-4")` | 正常 |
| `create_deep_agent(tools=[...], subagents=[...])` | 正常 |

### 4.2 实现了自定义 Backend 的项目

- `ls_info()` / `read()` / `grep_raw()` / `glob_info()` 返回类型需要从裸类型迁移到 `LsResult`/`ReadResult` 等
- 短期有兼容层（deprecation warning），**不会立即崩溃**
- `FileData.content` 从 `list[str]` 变为 `str` — 直接访问 `content[0]` 或 `"\n".join(content)` 的代码**会崩溃**
- 受影响的 Backend 实现：CLIShellBackend、DaytonaSandbox、ModalBackend、RunloopBackend

### 4.3 使用 `from deepagents import upload_files` 的项目

- **ImportError**
- 需要改用其他上传方式或从 `deepagents.upload_adapter` 直接导入

### 4.4 CLI 用户

- Textual 8.x 迁移（Rich Text -> Content API），渲染层全面重写
- 新增外部编辑器（`ctrl+x` / `/editor`）、客户端-服务器架构
- SDK 版本锁定 `deepagents==0.4.11`，与 SDK 0.5 存在版本不匹配

---

## 五、新增功能分析

### 5.1 AsyncSubAgentMiddleware（新模块）

位置：`libs/deepagents/deepagents/middleware/async_subagents.py`（本地不存在）

用于连接远程 LangGraph 服务器上运行的 Agent。提供 5 个工具：
- `launch_async_subagent` — 创建远程 thread + run，立即返回 job_id
- `check_async_subagent` — 查询 job 状态和结果
- `update_async_subagent` — 发送后续指令
- `cancel_async_subagent` — 终止运行中的 job
- `list_async_subagent_jobs` — 列出所有 job 及状态

新增状态字段：`async_subagent_jobs`，持久化到 agent state。

### 5.2 quickjs Partner 包

位置：`libs/partners/quickjs/`（独立包 `langchain-quickjs`）

提供 QuickJS JavaScript 运行时集成，包含 REPL 工具、ToolRuntime 支持、异步支持。完全独立，不影响 SDK 核心。

### 5.3 CLI 重大新功能

- **外部编辑器支持**（`ctrl+x` / `/editor`）— 在系统编辑器中编辑长消息
- **客户端-服务器架构**（`langgraph dev`）— CLI 作为客户端连接服务器
- **Content API 迁移**（Rich Text -> Textual Content）— 渲染层全面重写
- **HITL 延迟审批**（用户输入时推迟审批菜单显示）
- **性能优化**：stream layout、Rust layout primitives、异步路径优化

---

## 六、综合风险评估

| 风险等级 | 变更内容 | 影响范围 | 建议 |
|---------|---------|---------|------|
| **极高** | Backend 返回类型重构 | 所有自定义 Backend 实现者 | 分阶段迁移，先建兼容层 |
| **极高** | SkillsMiddleware V2 冲突 | 使用 load_skill/allowed_skills 的用户 | 必须保留本地版本 |
| **高** | FileData 格式 v1 -> v2 | 本地 Converter 系统、StateBackend | 需要格式转换层 |
| **高** | create_deep_agent 参数移除 | 传递 state_schema/skills_expose_dynamic_tools 的调用者 | 需添加 deprecation 桥接 |
| **高** | CLI Textual 8.x 迁移 | CLI 用户 | CLI widget 全面适配 |
| **中** | upload_adapter 公共 API 移除 | `from deepagents import upload_files` | 保留本地导出 |
| **低** | AsyncSubAgentMiddleware 新增 | 无破坏性 | 直接采纳 |
| **低** | quickjs partner 包 | 独立包 | 直接采纳 |

---

## 七、合并策略（最终方案）

### 核心原则

1. **不一次性合并全部 143 个提交** — 风险过高
2. **按时间线 + 模块分批，而非按风险等级分批** — 避免依赖链断裂导致的额外冲突
3. **兼容层在需要时再建** — 不提前建脚手架，避免返工
4. **工作树隔离** — 每批次在独立 worktree 中操作，失败可弃，不污染主线

### 为什么是两批而非三批

架构师初版建议按风险等级分三批。经研发评审后调整为两批，理由如下：

1. **依赖链问题**：按风险分批时，提交之间存在依赖链（如 CLI release 依赖前序功能提交，Backend hotfix 依赖类型重构提交），跨批次 cherry-pick 会产生大量额外冲突
2. **时间线连续性**：按上游时间线分批，每批内部提交连续，cherry-pick 冲突最小
3. **第三批独立性不强**：原第三批（签名变更、async_subagents）与第二批的类型重构紧密耦合，分开处理反而增加复杂度
4. **AsyncSubAgent 无需等待**：`async_subagents.py` 是新文件零冲突，不应放到最后一批
5. **无外部调用者需要观察期**：我们是 fork 仓库，upload_files、state_schema 等 API 只有我们自己在用，不需要"两周兼容观察期"

### 第一批：SDK 0.4.11 之前的连续提交（约 90 个）

**分界点**：上游 SDK 0.4.11 release commit (`b5636f36`) 及之前的所有提交。

**内容**：
- CLI 改进（外部编辑器、HITL 延迟、性能优化、Content API 迁移、客户端-服务器架构）
- CLI 0.0.32 / 0.0.33 / 0.0.34 release
- 依赖 bump（orjson、multipart、github-actions、tornado）
- CI/infra 改进（release workflow、PR labeling、pre-commit hooks）
- quickjs 新 partner 包（全部提交）
- AsyncSubAgentMiddleware 新模块（新文件，零冲突）
- Summarization test fixture
- Evals 改进（memory evals、tool usage relational）
- examples 更新
- 文档更新
- SDK 0.4.11 release

**风险**：低-中。这些提交与本地 0.4.10 兼容性最好。AsyncSubAgent 是新文件不会冲突。CLI 文件可能有少量冲突但不涉及核心逻辑。

**预估冲突**：
- CLI `app.py`、`main.py`（少量，手动解决）
- `graph.py`（添加 `async_subagents` 参数，同时保留本地 `state_schema` 和 `skills_expose_dynamic_tools`）
- `pyproject.toml`（版本号 0.4.10 → 0.4.11）

**不在此批次建兼容层** — 这些提交尚未触及类型重构，提前建兼容层无必要且可能因后续实现差异而返工。

**验证**：
- `make lint` + `make test`（SDK 全量单元测试）
- CLI 单元测试
- Daytona 测试
- 本地优越特性完整性检查（4 项）

### 第二批：SDK 0.5.0 的类型重构 + 签名变更（约 50 个）

**分界点**：SDK 0.4.11 之后到 upstream/main HEAD 的所有提交。

**内容**：
- Backend 返回类型重构（`LsResult`/`ReadResult`/`GrepResult`/`GlobResult`）
- FileData 格式 v1 → v2 迁移
- `BackendProtocol` 方法签名全面更新
- SDK 版本号跳到 0.5.0
- Harbor backend 适配
- `langchain-anthropic` / `langchain-google-genai` 显式依赖
- CLI 剩余提交（Textual speedups、editable install path 等）
- 剩余 CI/infra 提交

**风险**：高。这是真正需要兼容层和手动适配的批次。

**此批次需要建立的兼容层**：

1. **FileData v1/v2 双栈**：在 `format_read_response` / `format_content_with_line_numbers` 处检测 `content` 类型（`list[str]` vs `str`），做统一处理
2. **Backend 返回类型适配**：本地 Converter 系统、StateBackend 适配新的 `LsResult`/`ReadResult` 等
3. **SkillsMiddleware V2 保留策略**：
   - 保持目录与全部能力（1190 行）
   - `expose_dynamic_tools` 改为通过 middleware 配置项控制（不依赖被上游移除的顶层签名参数）
   - `allowed_skills` 保持在 middleware 层
4. **create_deep_agent 签名**：
   - 保留 `state_schema` 参数（标注 `experimental`）
   - `skills_expose_dynamic_tools` 改为通过 `SkillsMiddleware` 构造参数传入
   - 添加 `async_subagents` 参数（来自上游）
5. **公共导出**：保留 `upload_files` / `UploadResult` 在 `__init__.py`，标注 deprecation

**预估冲突**（多文件结构性冲突）：
- `backends/protocol.py` — 新增类型定义
- `backends/state.py` — 返回类型适配
- `middleware/filesystem.py` — FileData 格式 + Converter 系统挂接
- `middleware/skills.py` — V2 保留（1190 行 vs 上游 834 行，最大冲突）
- `middleware/memory.py` — isawaitable 修复（第三次保护）
- `__init__.py` — 导出列表
- `graph.py` — 签名最终收敛
- `pyproject.toml` — 版本号（0.4.11 → 0.5.0 或自定义版本）

**验证**：
- SDK 全量单元测试 + Backends 类型迁移用例
- Converters 测试（23 个）
- Filesystem 工具测试（行号/分页/截断）
- CLI 全量测试 + Textual 快照
- Daytona 测试
- 端到端测试
- 本地优越特性完整性检查（全部 6 项）

### 每批合并流程

```
1. git worktree add /tmp/deepagents-batch-N -b upstream-sync-batch-N
2. 在 worktree 中逐个 cherry-pick 该批次的提交
3. 解决冲突，保留本地优越特性
4. 建立兼容层（仅第二批需要）
5. 运行完整测试套件（SDK + CLI + Daytona）
6. 代码审查（独立审查员）
7. 验证通过后合并到 master
8. 清理 worktree
```

### 回滚方案

- 每批次在独立 worktree 中操作，主线不受污染
- 若验证门失败，直接弃用该 worktree，不影响 master
- 若第一批合并后第二批失败，可 `git revert` 第一批的 merge commit 回到原始状态

### 批次概览

| 批次 | 提交数 | 分界点 | 冲突预估 | 复杂度 | 是否需要兼容层 |
|------|-------|--------|---------|--------|--------------|
| 第一批 | ~90 | SDK 0.4.11 release 及之前 | 少量（CLI + graph.py） | 低-中 | 否 |
| 第二批 | ~50 | SDK 0.4.11 → 0.5.0 | 多文件结构性冲突 | 高 | 是 |

### 本地特性保留方案

| 特性 | 保留策略 |
|------|---------|
| **SkillsMiddleware V2** | 保持目录与能力，`expose_dynamic_tools` 改为 middleware 配置项 |
| **Converters** | 保留目录，在 filesystem 读取路径上触发，适配 FileData v2 输出 |
| **upload_adapter** | 保留 `__init__.py` 导出，标注 deprecation |
| **Memory isawaitable** | 合并时检查并保留 `inspect.isawaitable()` 模式 |
| **SubAgent 日志** | 继续环境变量门控，不与 AsyncSubAgentMiddleware 冲突 |
| **state_schema** | 保留在 graph 层入口，docstring 标注 `experimental` |

### 校验门（每批次必跑）

```
make lint                    # ruff check
make test                    # SDK 全量单元测试
CLI 单元测试                  # 排除已知 flaky 测试
Daytona 测试                 # 5 个单元测试
本地优越特性检查               # 6 项自动化验证脚本
```

---

## 八、关键文件清单

合并时需要特别关注的文件：

| 文件路径 | 关注点 |
|---------|--------|
| `libs/deepagents/deepagents/__init__.py` | 公共 API 导出（保留 upload_files） |
| `libs/deepagents/deepagents/graph.py` | create_deep_agent 签名（保留本地参数 + 添加 async_subagents） |
| `libs/deepagents/deepagents/backends/protocol.py` | 新增 LsResult/ReadResult 等类型 |
| `libs/deepagents/deepagents/backends/state.py` | ls_info/read 返回类型适配 |
| `libs/deepagents/deepagents/middleware/skills.py` | V2 保留（1190 行 vs 上游 834 行） |
| `libs/deepagents/deepagents/middleware/filesystem.py` | FileData 格式 + Converter 系统 |
| `libs/deepagents/deepagents/middleware/memory.py` | isawaitable 修复（第三次保护） |
| `libs/deepagents/deepagents/middleware/subagents.py` | SubAgent 日志功能保留 |
| `libs/deepagents/deepagents/middleware/summarization.py` | 工厂函数保留 |
| `libs/deepagents/pyproject.toml` | 版本号决策（保持 0.4.x 还是跟进 0.5） |

---

## 附录：143 个提交分类统计

| 类别 | 数量 | 典型提交 |
|------|------|---------|
| CLI 功能/修复 | ~45 | 外部编辑器、Content API 迁移、HITL 延迟、性能优化 |
| SDK 功能/修复 | ~25 | Backend 类型重构、AsyncSubAgent、evals、FileData v2 |
| 依赖 bump | ~20 | orjson、multipart、github-actions、tornado |
| CI/infra | ~15 | release workflow、PR labeling、pre-commit hooks |
| 发布/版本 | ~10 | SDK 0.4.11、CLI 0.0.32/33/34、SDK 0.5.0 |
| 文档/示例 | ~10 | NVIDIA example、contributing guidelines |
| quickjs 新包 | ~8 | REPL、async 支持、ToolRuntime |
| 测试 | ~10 | evals、memory bench、summarization fixture |
