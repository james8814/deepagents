# Round 4 上游合并 — 全面测试验收报告

**日期**: 2026-03-20
**SDK 版本**: 0.5.0
**CLI 版本**: 0.0.34
**合并提交**: 89 个上游 + 2 个本地适配
**测试执行人**: 架构师 + 质量团队

---

## 一、单元测试矩阵

### 1.1 SDK 全量测试

```
命令: pytest --disable-socket --allow-unix-socket tests/unit_tests/ -q
结果: 979 passed, 73 skipped, 14 deselected, 3 xfailed
耗时: 27.55s
```

### 1.2 SDK 分模块测试

| 模块 | 测试文件 | 通过 | 失败 | 跳过 |
|------|---------|------|------|------|
| 端到端 | test_end_to_end.py | 41 | 0 | 0 |
| Middleware 同步 | test_middleware.py | 65 | 0 | 0 |
| Middleware 异步 | test_middleware_async.py | 69 | 0 | 0 |
| Filesystem 工具 | test_file_system_tools.py | 13 | 0 | 0 |
| Converters | converters/test_converter_integration.py | 23 | 0 | 0 |
| Skills V2 | test_skills_middleware.py + test_skills_dynamic_tools.py | 68 | 0 | 0 |
| Backends 类型 | backends/* | 374 | 0 | 0 |
| Summarization | test_summarization_middleware.py | 52 | 0 | 0 |
| AsyncSubAgent | test_async_subagents.py | 39 | 0 | 0 |
| SubAgent | test_subagents.py | 21 | 0 | 0 |
| Memory | test_memory_middleware.py + test_memory.py | 30 | 0 | 0 |
| Graph Skills Wiring | test_graph_skills_flag_wiring.py | 6 | 0 | 0 |
| Models | test_models.py | 17 | 0 | 0 |
| Local Shell | test_local_shell.py | 11 | 0 | 0 |
| Upload Adapter | test_upload_adapter.py | 44 | 0 | 0 |
| Sandbox 操作 | test_local_sandbox_operations.py | 0 | 0 | 73 |

### 1.3 CLI 全量测试

```
命令: pytest tests/unit_tests/ --disable-socket --allow-unix-socket -q
结果: 2507 passed, 1 skipped
耗时: 96.65s
```

### 1.4 Daytona 测试

```
命令: pytest tests/unit_tests/ -v
结果: 5 passed
耗时: 3.92s
```

### 1.5 测试总计

| 套件 | 通过 | 失败 | 跳过 |
|------|------|------|------|
| SDK | 979 | 0 | 73 |
| CLI | 2507 | 0 | 1 |
| Daytona | 5 | 0 | 0 |
| **总计** | **3491** | **0** | **74** |

---

## 二、端到端场景测试

使用真实 `create_deep_agent()` 编译和 `invoke()` 执行，覆盖 15 个场景。

### 2.1 编译场景 (场景 1-9)

| # | 场景 | 参数 | 结果 |
|---|------|------|------|
| 1 | 默认配置 | 无参数 | PASS |
| 2 | 自定义模型+工具 | `model=fake, tools=[my_tool]` | PASS (工具已注册) |
| 3 | 同步 subagent | `subagents=[{name, description, system_prompt}]` | PASS |
| 4 | 混合同步+异步 subagent | `subagents=[sync_spec, async_spec_with_graph_id]` | PASS |
| 5 | 自定义 state_schema | `state_schema=MyState(extra field)` | PASS (extra 在 channels) |
| 6 | Skills V2 动态工具 | `skills=['/skills/'], skills_expose_dynamic_tools=True` | PASS |
| 7 | FilesystemBackend | `backend=FilesystemBackend(virtual_mode=True)` | PASS |
| 8 | Memory | `memory=['/memory/AGENTS.md']` | PASS |
| 9 | response_format | `response_format=Output(Pydantic)` | PASS |

### 2.2 运行场景 (场景 10-15)

| # | 场景 | 工具调用 | 验证点 | 结果 |
|---|------|---------|--------|------|
| 10 | read_file | `/test.txt` | 内容包含 "Hello World" | PASS |
| 11 | write_file | `/out.txt` | 文件存在于 state | PASS |
| 12 | ls | `/` | 列出 a.txt | PASS |
| 13 | 图片读取 | `/img.png` | 返回 multimodal ToolMessage (type=image, mime=image/png) | PASS |
| 14 | grep | pattern="hello" | 匹配 f.txt | PASS |
| 15 | write_todos | `[{id: 1, content: "Test task"}]` | Tool 响应成功 | PASS |

---

## 三、LangChain/LangGraph 框架验证

| # | 验证项 | 结果 |
|---|--------|------|
| 1 | `create_deep_agent()` 签名包含 `subagents: Sequence[SubAgent\|CompiledSubAgent\|AsyncSubAgent]` | PASS |
| 2 | `async_subagents` 不在签名中（已合并到 subagents） | PASS |
| 3 | `skills_expose_dynamic_tools` 参数保留 | PASS |
| 4 | `state_schema` 参数保留 | PASS |
| 5 | Backend 新方法 ls/als/grep/agrep/glob/aglob 全部可用 | PASS |
| 6 | Backend 旧方法 ls_info/als_info/grep_raw/agrep_raw/glob_info/aglob_info 作为 deprecation shim 可用 | PASS |
| 7 | LsResult/ReadResult/GrepResult/GlobResult/WriteResult/EditResult 类型完整 | PASS |
| 8 | 公共 API 导出 12 个符号完整 | PASS |
| 9 | LangSmithSandbox 可导入 | PASS |
| 10 | 默认 agent 可编译 (节点: model, tools, TodoList, PatchToolCalls) | PASS |
| 11 | SDK 版本 0.5.0 | PASS |

---

## 四、Middleware 顺序验证

```
Main Agent 实际顺序:
1. TodoListMiddleware
2. SkillsMiddleware (可选)
3. FilesystemMiddleware
4. SubAgentMiddleware
5. SummarizationMiddleware
6. PatchToolCallsMiddleware
7. AsyncSubAgentMiddleware (可选)
8. User middleware
9. AnthropicPromptCachingMiddleware  ← 在用户 middleware 之后
10. MemoryMiddleware (可选)           ← 在 cache 之后
11. HumanInTheLoopMiddleware (可选)

验证: AnthropicCache 在 user middleware 之后: PASS
验证: Memory 在 AnthropicCache 之后: PASS
```

---

## 五、SubAgent 路由逻辑验证

```python
# 路由规则 (graph.py):
for spec in subagents or []:
    if "graph_id" in spec:   → AsyncSubAgent → AsyncSubAgentMiddleware
    elif "runnable" in spec: → CompiledSubAgent → SubAgentMiddleware
    else:                    → SubAgent (填充默认值) → SubAgentMiddleware

验证: 混合同步+异步 subagent 编译成功: PASS
验证: graph_id 路由到 AsyncSubAgent: PASS
```

---

## 六、CLI 集成验证

```
CLI version: 0.0.34
SDK version: 0.5.0
create_cli_agent 可导入: True
注册命令数: 18
ALL_CLASSIFIED 数: 21
/upload 在 ALL_CLASSIFIED: True
命令列表: /changelog, /clear, /docs, /editor, /feedback, /help, /mcp,
          /model, /offload, /quit, /reload, /remember, /threads, /tokens,
          /trace, /update, /upload, /version
```

---

## 七、本地特性保留确认

| 特性 | 验证方法 | 状态 |
|------|---------|------|
| SkillsMiddleware V2 (1197 行) | 68 个专项测试 + 编译验证 | 保留 |
| Converters (PDF/DOCX/XLSX/PPTX) | 23 个专项测试 | 保留 |
| upload_adapter V5 | 44 个测试 + 导出验证 | 保留 |
| Memory isawaitable | 代码检查 | 保留 |
| SubAgent 日志 | 代码检查 | 保留 |
| state_schema 参数 | 运行时场景 5 验证 | 保留 |
| skills_expose_dynamic_tools | 运行时场景 6 验证 | 保留 |
| Overwrite 防御性处理 | 代码检查 | 保留 |

---

## 八、代码审查结论

独立代码审查 agent 验证了以下 11 项，全部通过：

1. subagents 参数统一 + async_subagents 移除
2. 本地特性 skills_expose_dynamic_tools / state_schema 保留
3. Subagent 路由逻辑正确
4. skills.py 所有 backend 调用已更新为新方法名
5. V2 Skills 功能完整
6. protocol.py 新方法名 + deprecation shim 双向设计正确
7. filesystem.py 全部调用使用新方法名
8. Converter 系统完整保留
9. __init__.py 所有导出完整
10. LangSmithSandbox 正确实现
11. /upload 命令已注册

发现并修复的问题：
- CLAUDE.md middleware 顺序未同步 → 已修复
- /upload 未在 help body 中列出 → 已修复

---

## 九、结论

**验收通过。** 3491 个测试全绿，15 个端到端场景全部通过，11 项框架验证全部通过，所有本地特性完整保留。
