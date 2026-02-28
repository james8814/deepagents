# DeepAgents SDK v0.4.0 迁移指南

**发布日期**: 2026-02-27
**版本号**: v0.4.0 (Breaking Changes)
**影响范围**: CLI 和 SDK 用户

---

## 📋 执行摘要

本版本包含重大架构变更：**AttachmentMiddleware 已移除**，文件上传功能已重新设计。所有文件操作现由 `FilesystemMiddleware` 统一处理。

### 变更统计
- 🔴 **Breaking Changes**: 1 项（AttachmentMiddleware 移除）
- ✅ **新功能**: 增强的文件上传 `/upload` 命令
- ✅ **安全增强**: 文件类型验证和大小限制
- ✅ **测试覆盖**: 新增 22 个单元测试

---

## ⚠️ Breaking Changes

### 1. AttachmentMiddleware 已移除

**影响**: 如果您直接使用了 `AttachmentMiddleware`，需要更新代码。

**变更前**:
```python
from deepagents.middleware import AttachmentMiddleware

middleware = [
    AttachmentMiddleware(backend=backend, uploads_dir="/uploads"),
    # ...
]
```

**变更后**:
```python
# AttachmentMiddleware 已移除，无需替换
# 文件上传功能由 CLI /upload 命令和 FilesystemMiddleware 共同处理

middleware = [
    # FilesystemMiddleware 自动处理文件操作
    FilesystemMiddleware(backend=backend),
    # ...
]
```

**理由**:
- 简化架构，避免功能重复
- FilesystemMiddleware 已提供完整的文件操作能力
- 大文件处理逻辑优化

---

## ✨ 新功能

### 1. 增强的文件上传命令

**CLI 新增 `/upload <path>` 命令**:
- 支持文件类型自动检测（使用 magic bytes）
- 100MB 文件大小限制
- 上传后显示类型特定的使用指导

**支持的文件类型**:
| 类型 | MIME 类型 | 使用指导 |
|------|-----------|----------|
| 文本/代码 | text/* | `read_file` 直接读取 |
| JSON | application/json | `read_file` 直接读取 |
| PDF | application/pdf | `execute` + `pdftotext` |
| 图片 | image/* | `execute` + 外部工具 |
| 压缩包 | application/zip, gzip | `execute` + `unzip`/`tar` |
| Office 文档 | application/msword, etc. | `execute` + `pandoc` |

**使用示例**:
```bash
# 在 CLI 中
> /upload /path/to/myfile.txt
✓ myfile.txt uploaded (1.5KB)
   File available at /uploads/myfile.txt. Use `ls /uploads` and `read_file` to access.

> /upload /path/to/document.pdf
✓ document.pdf uploaded (2.3MB)
   File available at /uploads/document.pdf. Note: PDFs cannot be read directly. Use `execute` with `pdftotext` or similar tools.
```

### 2. 安全增强

**新增文件验证** (`libs/cli/deepagents_cli/utils/security.py`):
- 基于 magic bytes 的文件类型检测（`puremagic` 库）
- 未授权文件类型自动拒绝
- 100MB 大小限制
- 文本文件回退检测（UTF-8 编码检查）

**错误处理**:
```python
class SecurityError(Exception):  # 文件类型未授权
    pass

class ValidationError(Exception):  # 文件不存在或过大
    pass
```

---

## 🔄 迁移步骤

### 对于 CLI 用户

**无需修改**，CLI 自动处理文件上传。只需注意：
1. 上传的文件现在存储在 `/uploads/<filename>`
2. 根据文件类型，系统会提示不同的访问方法

### 对于 SDK 用户

**情况 1: 使用了 AttachmentMiddleware**
```python
# 移除以下代码
from deepagents.middleware import AttachmentMiddleware

# 删除 middleware 列表中的 AttachmentMiddleware
```

**情况 2: 需要访问上传的文件**
```python
# 上传的文件可通过 FilesystemMiddleware 访问
# 路径格式: /uploads/<filename>

# Agent 会自动使用 ls /uploads 和 read_file 工具访问
```

**情况 3: 自定义上传目录**
```python
# 之前通过 AttachmentMiddleware(uploads_dir="/custom")
# 现在直接通过 backend 配置
backend = FilesystemBackend(root_dir="/workspace")
```

---

## 🧪 测试覆盖

新增测试确保功能稳定性：

| 测试文件 | 测试数量 | 覆盖范围 |
|----------|----------|----------|
| `test_security.py` | 9 | 文件类型验证、安全边界 |
| `test_upload_command.py` | 13 | 上传流程、错误处理、路径解析 |

**运行测试**:
```bash
cd libs/cli
uv run --group test pytest tests/unit_tests/test_upload_command.py tests/unit_tests/test_security.py -v
```

---

## 📦 依赖变更

**新增依赖**:
- `puremagic>=1.20,<2.0.0` - 文件类型检测

**移除依赖**:
- 无

**版本要求**:
- Python >=3.11 (保持不变)

---

## 📋 检查清单

升级前请确认：

- [ ] 检查是否直接使用了 `AttachmentMiddleware`
- [ ] 检查是否依赖了 `/uploads/` 路径结构
- [ ] 运行测试确保功能正常
- [ ] 更新内部文档

---

## 🔗 相关链接

- **PR**: (待创建)
- **文档**: `docs/SDK_UPGRADE_GUIDE.md`
- **测试**: `libs/cli/tests/unit_tests/`

---

## 📞 技术支持

如有迁移问题，请联系：
- GitHub Issues: https://github.com/james8814/deepagents/issues
- 文档: https://docs.langchain.com/oss/python/deepagents/overview

---

**迁移难度**: ⭐⭐ (低) - 大多数用户无需修改代码

**建议升级时间**: 1-2 小时（包含测试验证）
