# Round 13 上游合并进度

**日期**: 2026-04-12
**分支**: `upstream-sync-round13`
**范围**: `39b43cf8..a9e6e4f7` (114 upstream commits)

## 总结

| 指标 | 值 |
|------|-----|
| 上游 commits 总数 | 114 |
| 已合并 | 104 |
| 跳过 (release) | 10 |
| 冲突解决 | 8 文件 |
| 本地修复 commits | 2 |
| 新增测试 | +170 (SDK 1081→1251) |

## 执行顺序

### Segment 1: 低风险 (97 commits) ✅

Cherry-pick 了 CLI、Evals、CI、deps、docs 等低风险 commits。

**关键变更**:
- `deepagents deploy` 新命令 (CLI)
- `/notifications` 命令 (CLI)
- LLM-powered failure analysis (Evals)
- LangSmith sandbox environment (Evals)
- `artifacts_root` for CompositeBackend (SDK)
- `BASE_AGENT_PROMPT` tweaks (SDK)
- cryptography 46.0.6→46.0.7, langchain-core 1.2.27→1.2.28

**冲突解决**:
- `app.py`: help string 合并 (保留 `/upload`，添加 `/notifications`)
- `test_agent.py`: 残留冲突标记清理
- `categories.json`: 更新为新的 eval 标签方案 (conversation, unit_test 替代旧分类)
- `pyproject.toml`: 恢复 puremagic 依赖 + CLI 版本 0.0.34
- 多个 `uv.lock`: 接受上游版本

**测试**: SDK 1081p / CLI 2959p / Evals 239p

### Gate A: Namespace improvements (`66c57e1e`) ✅

StoreBackend namespace factory 从 BackendContext 改为直接接收 Runtime。
`_NamespaceRuntimeCompat` 提供向后兼容。

**冲突**: 无
**测试**: SDK 1088p (+7)

### Gate B: Harness profiles (`d6fa568e` + `a83f1bcf`) ✅

`HarnessProfile` 注册表 + `_ToolExclusionMiddleware` + `_openrouter.py`。
`graph.py` 356 行 diff — 3 个冲突区域手动解决。

**冲突解决** (graph.py):
1. 函数定义前: 接受上游 helper 函数 (`_resolve_extra_middleware`, `_harness_profile_for_model`, `_tool_name`, `_apply_tool_description_overrides`)
2. GP subagent middleware 尾部: 保留 SkillsMiddleware + 添加上游 `_ToolExclusionMiddleware`
3. SubAgent middleware: 保留 skills_allowlist + skip-duplicate-SkillsMiddleware + 添加上游 profile middleware

**本地优越特性 8/8 验证通过**:
- ✅ skills_allowlist (6 tests)
- ✅ subagent_logging (20 tests)
- ✅ stream_writer (8 tests)
- ✅ summarization_factory (3 tests)
- ✅ Converters (23 tests)
- ✅ state_schema (symbol)
- ✅ skills_expose_dynamic_tools (symbol)
- ✅ Overwrite guard (symbol)

**测试**: SDK 1165p (+77)

### Gate C: Permissions system (`41dc7597` + `6dd61223` + `723d27dc`) ✅

新增 `permissions.py` (348 行) + `_PermissionMiddleware`。
`graph.py` 新增 `permissions` 参数。

**冲突解决**:
- `graph.py`: 添加 `_PermissionMiddleware` 到 GP subagent middleware
- `filesystem.py` (2处): 保留本地 Converter 二进制文档转换逻辑
- `subagents.py`: SubAgent TypedDict 保留 `skills_allowlist` + 添加 `permissions`

**测试**: SDK 1249p (+84)

### Benefit D: StateBackend upload_files (`57983451`) ✅

上游实现了 `StateBackend.upload_files()`。

**结果**: 3 xpassed (之前 xfailed 现在通过), 8 仍 xfailed (需 graph context)
**测试**: SDK 1251p (+2)

## 最终测试结果

| 包 | 通过 | 跳过 | xfailed | xpassed | 失败 |
|----|------|------|---------|---------|------|
| SDK | 1251 | 73 | 12 | 3 | 0 |
| CLI | 2959 | 1 | 0 | 0 | 0 |
| Evals | 239 | 0 | 0 | 0 | 0 |
| ACP | 76 | 0 | 0 | 0 | 0 |
| REPL | 59 | 0 | 0 | 0 | 0 |
| **总计** | **4584** | **74** | **12** | **3** | **0** |

**Lint**: 全部通过 (SDK, CLI, Evals — 仅 EXE002 外部卷文件系统权限问题)

## 版本状态

| 包 | 本地版本 | 上游版本 | 说明 |
|----|---------|---------|------|
| deepagents | 0.5.0 | 0.5.2 | 保留本地，含所有上游功能 |
| deepagents-cli | 0.0.34 | 0.0.37 | 保留本地 |

## Checkpoints

```
checkpoint-round13-segment1-done  # Segment 1 完成
checkpoint-round13-gate-a         # Gate A 通过
checkpoint-round13-gate-b         # Gate B 通过
checkpoint-round13-gate-c         # Gate C 通过
checkpoint-round13-segment2-done  # 全部 Gate + Benefit D 完成
```

## 新增上游特性总结

1. **Permissions system**: `FilesystemPermission` rules, `_PermissionMiddleware`, first-match-wins 策略
2. **Harness profiles**: `HarnessProfile` 注册表, `_ToolExclusionMiddleware`, provider-specific 配置
3. **Namespace improvements**: `StoreBackend` namespace factory 重构, `_NamespaceRuntimeCompat`
4. **StateBackend.upload_files()**: 原生上传支持
5. **`deepagents deploy`**: CLI 部署命令 + 配置解析 + bundler
6. **`/notifications`**: CLI 通知设置命令
7. **LangSmith sandbox**: Evals 沙箱环境
8. **LLM failure analysis**: Evals CI 失败分析
9. **`artifacts_root`**: CompositeBackend 工件路径
10. **OpenRouter attribution**: Profile-based OpenRouter headers
