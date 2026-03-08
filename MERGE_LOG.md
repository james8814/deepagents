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

