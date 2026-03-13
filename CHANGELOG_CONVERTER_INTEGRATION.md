# Changelog - Converter Integration into read_file

## [0.4.11] - 2026-03-13

### Summary

将内置 Converter 系统集成到 `read_file` 工具中，使 agent 能够直接读取 PDF、Word、Excel、PowerPoint 等二进制文档格式，无需手动调用命令行工具转换。

### Added

- **Binary Document Conversion in read_file** — `read_file` 工具新增二进制文档自动转换能力
  - 支持 `.pdf`、`.docx`、`.xlsx`、`.pptx` 四种核心格式（及旧格式扩展名 `.doc`、`.xls`、`.ppt`）
  - 自动检测文件类型 → 下载原始字节 → 写入临时文件 → Converter 转换 → 返回 Markdown 文本
  - 支持 sync (`_convert_document_sync`) 和 async (`_convert_document_async`) 双路径
  - async 路径使用 `asyncio.to_thread` 将 CPU 密集型转换卸载到线程池
  - async 路径使用 `inspect.isawaitable()` 兼容非标准 backend 的 `adownload_files` 返回值

- **Pagination Support for Binary Documents** — 二进制文档分页读取
  - `read_file(path, offset=N)` 中 `offset` 参数映射为页码（1-indexed）
  - `offset=0`：全文转换
  - `offset=N` (N>0)：调用 `converter.convert_page(path, page=N)` 返回第 N 页
  - 支持分页的格式：PDF、PPTX
  - 自动检测页码越界并返回友好错误信息
  - `get_total_pages()` 返回 `None` 时安全降级为全文转换

- **StateBackend Binary Detection** — StateBackend 二进制文件防御性检测
  - 检测 `__BINARY_FILE__:` 前缀（upload_adapter.py 的 base64 包装格式）
  - 返回明确的错误提示，引导用户使用 FilesystemBackend 或沙箱 backend

- **Optional Dependencies Group** — `pyproject.toml` 新增 `[converters]` 可选依赖组
  ```
  pip install deepagents[converters]
  ```
  包含：`pdfplumber>=0.10.0`、`python-docx>=1.0.0`、`openpyxl>=3.1.0`、`python-pptx>=0.6.23`、`puremagic>=1.20`

- **Comprehensive Test Suite** — 23 个单元测试覆盖完整测试矩阵
  - `TestNormalConversion`：4 种格式的全文转换
  - `TestPagination`：6 种分页场景（正常、边界、越界、None、非分页）
  - `TestErrorHandling`：6 种错误路径（ImportError、未知格式、StateBackend、文件不存在、旧格式、异常传播）
  - `TestTempFileCleanup`：成功和异常路径的临时文件清理验证
  - `TestAsyncPath`：4 种 async 场景（non-awaitable、awaitable、分页、StateBackend）
  - `TestTokenTruncation`：大文档输出截断

### Fixed

- **Registry Bug** — 移除 `registry.py` 中无效的 `DEFAULT_CONVERTER_REGISTRY = property(lambda self: get_default_registry())`
  - 模块级 `property()` 不会触发 getter，直接返回 property 对象本身
  - 同步移除 `__init__.py` 中对应的不可用导出

- **Stale Comment** — 移除 `registry.py` 中过时的 "For backwards compatibility and direct access" 注释

### Changed

- **filesystem.py** — `_create_read_file_tool()` 中新增 `BINARY_DOC_EXTENSIONS` 分支
  - sync_read_file 和 async_read_file 中插入二进制文档检测，位于图片检测之后、文本读取之前
  - 复用现有的 token 截断逻辑处理大文档输出

### Architecture

```
read_file(file_path, offset, limit)
    │
    ├── 图片 (.png/.jpg/.gif/.webp)
    │   └── [不变] download → base64 → ImageBlock (多模态)
    │
    ├── 二进制文档 (.pdf/.docx/.xlsx/.pptx)    ← 新增
    │   └── _convert_document_sync/async
    │       ├── backend.download_files() → raw bytes
    │       ├── StateBackend 检测 (__BINARY_FILE__ 前缀)
    │       ├── detect_mime_type() → MIME 类型
    │       ├── get_default_registry().get(mime) → Converter
    │       ├── tempfile.mkstemp() → 写入临时文件
    │       ├── offset > 0 ? convert_page() : convert()
    │       ├── token 截断（复用现有逻辑）
    │       └── finally: unlink 临时文件
    │
    ├── 文本文件 (.py/.md/.txt/.json/...)
    │   └── [不变] backend.read() → 带行号文本
    │
    └── 其他未知格式
        └── [不变] backend.read() → UTF-8 尝试
```

### Files Modified

| 文件 | 变更 |
|------|------|
| `deepagents/middleware/filesystem.py` | +2 辅助函数, +read_file 分支, +imports, +常量 |
| `deepagents/middleware/converters/registry.py` | 移除无效 property + 过时注释 |
| `deepagents/middleware/converters/__init__.py` | 移除不可用导出 |
| `pyproject.toml` | +`[project.optional-dependencies] converters` |
| `tests/.../test_converter_integration.py` | 完整重写 (4 → 23 测试) |

### Quality Metrics

| 指标 | 结果 |
|------|------|
| Converter 集成测试 | 23/23 passed |
| 全部 middleware 测试 | 268 passed |
| 全部 SDK 单元测试 | 829 passed, 0 failures |
| Lint (ruff) | All checks passed |

### Breaking Changes

无。此更新仅新增功能，不改变现有文本文件和图片的读取行为。

### Migration

无需迁移。如需使用二进制文档转换功能，安装可选依赖：

```bash
pip install deepagents[converters]
```

未安装时，`read_file` 对二进制文档返回清晰的安装提示错误，不影响其他功能。
