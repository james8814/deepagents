# DeepAgents v0.4.0 Release Notes

**Release Date**: 2026-02-28
**Version**: v0.4.0
**Status**: Pre-release (Draft)

---

## 🎉 Highlights

This is the first major release since forking, introducing significant enhancements to DeepAgents SDK:

- **Unified File Reader** - Read PDF, Word, Excel, PowerPoint, and more with automatic format conversion
- **Universal Upload Adapter** - Universal file upload support for any backend
- **SkillsMiddleware V2** - Dynamic skill loading with context budget management
- **Multi-Provider Support** - DeepSeek, Qwen, and enhanced provider configuration

---

## ✨ New Features

### 1. Unified File Reader (统一文件读取器) 🆕

A major feature that enables agents to read multiple file formats with automatic conversion to Markdown.

**Supported Formats**:
- **PDF** - Automatic text and table extraction with pagination support
- **Microsoft Word** (.docx, .doc) - Document conversion with table support
- **Microsoft Excel** (.xlsx, .xls) - Spreadsheet to Markdown table conversion
- **Microsoft PowerPoint** (.pptx, .ppt) - Slide extraction with pagination
- **CSV** - Automatic table formatting
- **Images** (.png, .jpg, etc.) - Metadata extraction with placeholder
- **Text files** - Direct reading with syntax highlighting

**Key Capabilities**:
- Automatic MIME type detection (3-layer fallback strategy)
- Async file reading to prevent event loop blocking
- Pagination support for large PDFs and PowerPoints
- Extensible converter architecture via `BaseConverter`
- Lazy loading of optional dependencies

**Usage**:
```python
# Install with file format support
pip install "deepagents[converters]"

# Read any supported file
content = read_file("/uploads/report.pdf")      # PDF
content = read_file("/uploads/document.docx")   # Word
content = read_file("/uploads/data.xlsx")       # Excel
content = read_file("/uploads/slides.pptx")     # PowerPoint

# Pagination for large files
page_5 = read_file("/uploads/large.pdf", page=5)
```

**Implementation**:
- 11 new converter modules
- 132 unit tests
- 8 performance benchmarks
- Complete design documentation

---

### 2. Universal Upload Adapter V5.1 (通用上传适配器) 🆕

Universal file upload support that works with any DeepAgents backend.

**Features**:
- Unified interface for all backends (FilesystemBackend, StateBackend, CompositeBackend)
- Automatic strategy selection based on backend capabilities
- Binary/text content detection with automatic encoding
- Secure temporary directory handling
- Overwrite detection and file size tracking

**Security**:
- Path traversal protection
- Symbolic link attack prevention
- Secure file permissions (0o600/0o700)
- Automatic cleanup

**Usage**:
```python
from deepagents import upload_files

results = upload_files(backend, files)
```

---

### 3. SkillsMiddleware V2 (技能中间件 V2) 🆕

Enhanced skill system with dynamic loading and context management.

**New Features**:
- `load_skill` / `unload_skill` tools for dynamic skill management
- Context budget control (default: 10 simultaneous skills)
- Resource auto-discovery (scripts/, references/, assets/)
- `[Loaded]` marker in system prompt
- Backward compatible with V1

**Benefits**:
- Prevent context overflow
- Fine-grained skill control
- Better resource management

---

### 4. Multi-Provider Support (多提供商支持) 🆕

Enhanced model provider configuration.

**New Providers**:
- **DeepSeek** - Full integration with DeepSeek models
- **Qwen (通义千问)** - Alibaba Cloud Qwen model support
- **Enhanced configuration** - Better provider switching

**Example**:
```bash
export MODEL_PROVIDER="deepseek"
export DEEPSEEK_API_KEY="your-key"
```

---

### 5. Enhanced CLI Features

- **DuckDuckGo Search Fallback** - Automatic fallback when primary search fails
- **Daytona Sandbox Integration** - Improved sandbox lifecycle management
- **Auto-stop Configuration** - Configurable sandbox auto-stop (default: 60 minutes)
- **UI Visibility** - StateSyncBackend for UI visibility of sandbox files

---

## 📚 Documentation

### New Documentation
- `CHANGELOG_V0.4.0.md` - Version changelog
- `docs/SDK_MIGRATION_GUIDE_v0.4.0.md` - Migration guide
- `docs/unified_file_reader/UNIFIED_FILE_READER_DESIGN.md` - Design document
- `docs/UPLOAD_ADAPTER_GUIDE.md` - Upload adapter guide
- `docs/SDK_UPGRADE_GUIDE.md` - SDK upgrade guide

### Updated Documentation
- `README.md` - Added Universal File Reader feature
- `libs/deepagents/README.md` - Enhanced feature list

---

## 🔧 Technical Improvements

### Performance
- Async file operations prevent blocking
- Lazy loading reduces memory footprint
- Pagination for large files
- Optimized MIME type detection

### Security
- Path traversal protection
- File permission management
- Secure temporary directories
- Input validation

### Testing
- 703+ unit tests passing
- 132 converter-specific tests
- 8 performance benchmarks
- Integration tests for all backends

---

## 📦 Installation

### Basic Installation
```bash
pip install deepagents
```

### With File Format Support
```bash
pip install "deepagents[converters]"
```

### Development Installation
```bash
git clone https://github.com/james8814/deepagents.git
cd deepagents/libs/deepagents
pip install -e ".[converters]"
```

---

## 🔄 Migration Guide

### From v0.3.x to v0.4.0

**No Breaking Changes** - All existing code continues to work.

**To use new features**:
1. Upgrade: `pip install --upgrade "deepagents[converters]"`
2. Read various file formats directly
3. Use async APIs for better performance

See [SDK_MIGRATION_GUIDE_v0.4.0.md](docs/SDK_MIGRATION_GUIDE_v0.4.0.md) for details.

---

## 🐛 Known Limitations

1. **Complex PDF Layouts** - Some complex layouts may not convert perfectly
2. **Encrypted Documents** - Password-protected files are not supported
3. **Image OCR** - Text in images is not extracted (use OCR tools)
4. **Parallel Tool Calls** - Current framework doesn't support parallel execution

---

## 📊 Statistics

- **Files Changed**: 21+
- **Lines Added**: 5,860+
- **Test Coverage**: ~85%
- **Documentation Pages**: 10+

---

## 🙏 Credits

- **Core Team**: DeepAgents Development Team
- **Architecture**: Architecture Review Board
- **Testing**: QA Team
- **Documentation**: Technical Writing Team

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/james8814/deepagents/issues)
- **Documentation**: [docs.langchain.com](https://docs.langchain.com/oss/python/deepagents/overview)
- **API Reference**: [reference.langchain.com](https://reference.langchain.com/python/deepagents/)

---

## 🔗 Links

- **Repository**: https://github.com/james8814/deepagents
- **PyPI**: https://pypi.org/project/deepagents/
- **Documentation**: https://docs.langchain.com/oss/python/deepagents/overview

---

**Note**: This is a pre-release version. Please test thoroughly before production use.
