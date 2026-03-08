# Upstream Merge Log

**开始时间**: 2026-03-08
**目标**: 合并 langchain-ai/deepagents upstream 的 337 个提交
**策略**: 逐个 cherry-pick，优先保持本地 V2 特性

## 本地 V2 特性保护清单

以下文件包含 V2 独有功能，需特别注意保护：
- `libs/deepagents/deepagents/middleware/skills.py` - V2 动态加载 + allowlist
- `libs/deepagents/deepagents/middleware/subagents.py` - skills_allowlist 字段
- `libs/deepagents/deepagents/graph.py` - SubAgent 技能过滤
- `libs/deepagents/deepagents/upload_adapter.py` - V5 通用上传
- `libs/deepagents/deepagents/converters/` - 统一文件读取器

## 合并记录

### 合并批次

| 批次 | 提交数 | 说明 |
|------|--------|------|
| 1 | 8 | 初始 cherry-pick (CLI fixes) |
| 2 | 1 | 跳过 b5c8a998 (本地已包含改进) |
| 3 | 1 | non-interactive mode |
| 4 | 6 | CLI commits |
| 5 | 2 | CI/partner packages |
| 6 | ~300 | 批量合并剩余提交 |

### 关键决策
- b5c8a998 - SKIPPED (本地已包含上游验证改进)
- skills.py - 始终保持本地 V2 版本
- 其他 SDK 文件 - 采用上游版本
- CLI/infra 文件 - 采用上游版本

### 最终状态
- ✅ 337 个上游提交全部合并
- ✅ V2 特性完整保留
- ✅ 本地 master 与 upstream/main 同步

**完成时间**: 2026-03-08
