# DeepAgents SDK v0.4.0 迁移指南

**版本**: v0.4.0  
**日期**: 2026-02-28  
**适用对象**: 使用 DeepAgents SDK v0.3.x 的开发者  

---

## 快速总结

**一句话**: v0.4.0 新增统一文件读取器功能，完全向后兼容，现有代码无需修改。

**核心变化**:
- ✅ **新增** 统一文件读取器（Unified File Reader）
- ✅ **新增** 支持 PDF、DOCX、XLSX、PPTX、CSV 等格式
- ✅ **新增** 异步文件读取接口
- ✅ **新增** 分页读取大文件功能
- ✅ **新增** `[converters]` 可选依赖组
- ✅ **保持** 所有现有 API 不变
- ✅ **保持** 完全向后兼容

---

## 1. 升级内容详解

### 1.1 新增功能

| 功能 | 说明 | 影响 |
| :--- | :--- | :--- |
| 统一文件读取器 | 单一接口读取所有文件格式 | Agent 可以读取更多文件类型 |
| 自动格式转换 | PDF/Word/Excel 自动转 Markdown | 无需手动转换 |
| 异步读取 | `async_read_file` 非阻塞接口 | 提升大文件性能 |
| 分页读取 | `page` 参数支持分页 | 处理大文件避免上下文溢出 |
| 可选依赖 | `[converters]` 依赖组 | 按需安装，保持轻量 |

### 1.2 支持的文件格式

| 格式 | 扩展名 | 转换器 | 分页支持 |
| :--- | :--- | :--- | :--- |
| PDF | .pdf | PDFConverter | ✅ |
| Word | .docx, .doc | DOCXConverter | ❌ |
| Excel | .xlsx, .xls | XLSXConverter | ❌ |
| PowerPoint | .pptx, .ppt | PPTXConverter | ✅ |
| CSV | .csv | CSVConverter | ❌ |
| 文本 | .txt, .md, .json, etc. | TextConverter | ❌ |
| 图像 | .png, .jpg, etc. | ImageConverter | ❌ |

---

## 2. 兼容性保证

### 2.1 向后兼容

```python
# v0.3.x 代码无需修改，直接使用
from deepagents import create_deep_agent

agent = create_deep_agent()
# 所有现有功能完全兼容
```

### 2.2 接口兼容

| 接口 | v0.3.x | v0.4.0 | 兼容性 |
| :--- | :--- | :--- | :--- |
| `read_file` | ✅ | ✅ + 增强 | 完全兼容 |
| `write_file` | ✅ | ✅ | 完全兼容 |
| `edit_file` | ✅ | ✅ | 完全兼容 |
| `ls` | ✅ | ✅ | 完全兼容 |
| `glob` | ✅ | ✅ | 完全兼容 |
| `grep` | ✅ | ✅ | 完全兼容 |
| `execute` | ✅ | ✅ | 完全兼容 |

### 2.3 状态字段

v0.4.0 新增的状态字段（不影响现有代码）:

```python
# FilesystemState 扩展（内部使用）
# 新增转换器相关字段，对现有代码透明
```

---

## 3. 升级步骤

### 3.1 基础升级（推荐）

```bash
# 升级 SDK
pip install --upgrade deepagents

# 验证安装
python -c "import deepagents; print(deepagents.__version__)"
```

### 3.2 完整升级（使用文件格式支持）

```bash
# 升级 SDK 并安装文件格式支持
pip install --upgrade "deepagents[converters]"

# 验证转换器安装
python -c "from deepagents.middleware.converters import get_default_registry; print(len(get_default_registry()), 'converters available')"
```

### 3.3 开发环境升级

```bash
# 克隆最新代码
git clone https://github.com/langchain-ai/deepagents.git
cd deepagents/libs/deepagents

# 安装开发依赖
pip install -e ".[converters]"

# 运行测试
make test
```

---

## 4. 新功能使用指南

### 4.1 读取不同格式文件

```python
from deepagents import create_deep_agent

agent = create_deep_agent()

# 读取 PDF（自动转换）
content = agent.tools["read_file"].invoke({
    "file_path": "/uploads/report.pdf"
})

# 读取 Word 文档
content = agent.tools["read_file"].invoke({
    "file_path": "/uploads/document.docx"
})

# 读取 Excel 表格
content = agent.tools["read_file"].invoke({
    "file_path": "/uploads/data.xlsx"
})
```

### 4.2 分页读取大文件

```python
# 读取 PDF 第 5 页
page_5 = agent.tools["read_file"].invoke({
    "file_path": "/uploads/large.pdf",
    "page": 5
})

# 读取文本文件的特定范围
section = agent.tools["read_file"].invoke({
    "file_path": "/uploads/large.txt",
    "offset": 100,
    "limit": 50
})
```

### 4.3 异步读取

```python
import asyncio

async def read_files_async():
    # 并发读取多个文件
    tasks = [
        agent.tools["read_file"].acall({"file_path": "/uploads/file1.pdf"}),
        agent.tools["read_file"].acall({"file_path": "/uploads/file2.docx"}),
        agent.tools["read_file"].acall({"file_path": "/uploads/file3.xlsx"}),
    ]
    results = await asyncio.gather(*tasks)
    return results

# 运行异步任务
results = asyncio.run(read_files_async())
```

### 4.4 自定义转换器

```python
from pathlib import Path
from deepagents.middleware.converters import BaseConverter, ConverterRegistryManager

class XMLConverter(BaseConverter):
    """自定义 XML 转换器示例"""
    
    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        # 读取 XML 内容
        if raw_content is None:
            content = path.read_text()
        else:
            content = raw_content
        
        # 简单的 XML 到 Markdown 转换
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        
        # 转换为 Markdown 格式
        lines = [f"# {root.tag}", ""]
        for child in root:
            lines.append(f"## {child.tag}")
            lines.append(child.text or "")
            lines.append("")
        
        return "\n".join(lines)

# 注册自定义转换器
manager = ConverterRegistryManager()
manager.register("application/xml", XMLConverter())
```

---

## 5. 依赖管理

### 5.1 依赖组说明

```toml
[project.optional-dependencies]
converters = [
    "pdfplumber>=0.10.0,<1.0.0",  # PDF 支持
    "openpyxl>=3.1.0,<4.0.0",     # Excel 支持
    "python-docx>=1.1.0,<2.0.0",  # Word 支持
    "python-pptx>=0.6.21,<1.0.0", # PowerPoint 支持
    "puremagic>=1.20.0,<2.0.0",   # MIME 检测
    "Pillow>=10.0.0,<12.0.0",     # 图像支持
]
```

### 5.2 按需安装

```bash
# 只安装 PDF 支持
pip install deepagents pdfplumber

# 只安装 Office 文档支持
pip install deepagents python-docx openpyxl python-pptx

# 安装所有转换器支持
pip install "deepagents[converters]"
```

---

## 6. 升级检查清单

如果你的项目使用了 DeepAgents SDK，请确认：

- [ ] **现有代码** - 无需修改，直接兼容
- [ ] **依赖更新** - 升级到 v0.4.0
- [ ] **可选依赖** - 根据需要安装 `[converters]`
- [ ] **测试用例** - 建议运行一次完整测试
- [ ] **文档** - 更新内部文档说明新功能
- [ ] **监控** - 观察文件读取性能

---

## 7. 故障排查

### 7.1 转换器未找到

**问题**: `No converter found for application/pdf`

**解决**:
```bash
pip install pdfplumber
```

### 7.2 中文乱码

**问题**: PDF/Word 中的中文显示乱码

**解决**:
```bash
# 安装中文字体（Ubuntu/Debian）
sudo apt-get install fonts-wqy-zenhei

# 或（macOS）
brew install font-wqy-zenhei
```

### 7.3 大文件内存不足

**问题**: 读取大文件时内存溢出

**解决**:
```python
# 使用分页读取
content = read_file("/uploads/large.pdf", page=1)

# 或使用偏移量
content = read_file("/uploads/large.txt", offset=0, limit=100)
```

---

## 8. 已知限制

| 限制 | 说明 | 缓解策略 |
| :--- | :--- | :--- |
| 复杂 PDF 布局 | 某些复杂布局可能转换不完美 | 使用 `execute` 工具调用专业工具 |
| 加密文档 | 不支持密码保护的文档 | 先解密再读取 |
| 图像内容 | 图像中的文字无法提取 | 使用 OCR 工具 |
| 超大文件 | >100MB 文件可能性能下降 | 使用分页读取 |

---

## 9. 技术支持

**问题反馈**: 请提交 GitHub Issue  
**文档**:
- [统一文件读取器设计文档](./unified_file_reader/UNIFIED_FILE_READER_DESIGN.md)
- [API 参考](https://reference.langchain.com/python/deepagents/)
- [用户指南](https://docs.langchain.com/oss/python/deepagents/overview)

---

## 附录 A: 版本对比

### A.1 功能对比

| 功能 | v0.3.x | v0.4.0 | 说明 |
| :--- | :--- | :--- | :--- |
| 文本文件 | ✅ | ✅ | 完全兼容 |
| PDF 文件 | ❌ | ✅ | 新增 |
| Word 文件 | ❌ | ✅ | 新增 |
| Excel 文件 | ❌ | ✅ | 新增 |
| PowerPoint | ❌ | ✅ | 新增 |
| 异步读取 | ❌ | ✅ | 新增 |
| 分页读取 | ❌ | ✅ | 新增 |
| 自定义转换器 | ❌ | ✅ | 新增 |

### A.2 性能对比

| 场景 | v0.3.x | v0.4.0 | 提升 |
| :--- | :--- | :--- | :--- |
| 小文件读取 | 1x | 1x | 持平 |
| 大文件读取 | 阻塞 | 非阻塞 | 显著提升 |
| 并发读取 | 串行 | 并行 | 10x+ |
| 格式支持 | 5 种 | 30+ 种 | 6x+ |

---

## 附录 B: 完整变更列表

### B.1 新增模块

```
deepagents/middleware/converters/
├── __init__.py
├── base.py          # BaseConverter 基类
├── registry.py      # ConverterRegistry
├── utils.py         # MIME 类型检测
├── pdf.py           # PDFConverter
├── docx.py          # DOCXConverter
├── xlsx.py          # XLSXConverter
├── pptx.py          # PPTXConverter
├── csv.py           # CSVConverter
├── text.py          # TextConverter
└── image.py         # ImageConverter
```

### B.2 新增测试

```
tests/unit_tests/middleware/converters/
├── test_base.py     # 17 个测试
tests/performance_tests/
└── test_converter_performance.py  # 8 个测试
```

### B.3 新增文档

```
docs/
├── unified_file_reader/
│   └── UNIFIED_FILE_READER_DESIGN.md
├── SDK_MIGRATION_GUIDE_v0.4.0.md
└── CHANGELOG_V0.4.0.md
```

---

**迁移完成！** 您的项目现在可以使用 DeepAgents v0.4.0 的强大文件读取功能了。
