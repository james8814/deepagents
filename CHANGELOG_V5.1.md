# Changelog - V5.1 Upload Adapter

## [5.1.0] - 2026-02-28

### Added
- **Universal Upload Adapter** (`upload_files`)
  - Unified interface for uploading files to any DeepAgents backend
  - Automatic strategy selection based on backend capabilities
  - Support for FilesystemBackend, StateBackend, and CompositeBackend

- **UploadResult Dataclass**
  - Standardized result format with path, success, error fields
  - Overwrite detection (`is_overwrite`, `previous_size`)
  - Strategy tracking and encoding information

- **Factory Function Support**
  - Support for callable backend factories
  - Runtime context injection for stateful backends

- **Binary/Text Content Detection**
  - Automatic detection of binary vs text content
  - Base64 encoding for binary files in StateBackend

### Security
- Secure temporary directory for fallback strategy
  - Uses `tempfile.mkdtemp()` with random suffix
  - Directory permissions `0o700` (owner-only access)
  - File permissions `0o600` (owner read/write only)
  - Automatic cleanup with `try-finally`

- Path traversal protection via FilesystemBackend.virtual_mode
- Symbolic link attack prevention via O_NOFOLLOW

### Performance
- Deferred imports to avoid circular dependencies
- Module-level import caching
- WeakKeyDictionary for lock management (prevents memory leaks)
- Per-runtime fine-grained locking

### Changed
- Updated `deepagents/__init__.py` to export `upload_files` and `UploadResult`
- Updated `CLAUDE.md` with key implementation details

### Technical Details
- **Implementation**: `libs/deepagents/deepagents/upload_adapter.py` (633 lines)
- **Tests**: `libs/deepagents/tests/unit_tests/test_upload_adapter.py` (43 tests)
- **Documentation**: `docs/UPLOAD_ADAPTER_GUIDE.md`

### Performance Benchmarks
- Single file upload: 0.121ms average
- Batch 100 files: <30ms
- Concurrent 20 threads: 500 uploads/sec

### Compatibility
- Backward compatible: Pure additive feature
- Python 3.10+ compatible
- All existing backends supported

---

## Migration Guide

### For SDK Users

**Before:**
```python
# Direct backend usage (limited backend support)
backend.upload_files(files)
```

**After:**
```python
from deepagents import upload_files

# Universal upload (supports all backends)
results = upload_files(backend, files)
```

### For Dependent Projects

Projects depending on DeepAgents SDK can now:
1. Use `upload_files` for universal file upload
2. Support StateBackend uploads (previously not possible)
3. Get consistent UploadResult format across all backends

No breaking changes - existing code continues to work.

---

## Testing

All tests passing:
- Unit tests: 43/43
- Integration tests: 20/20
- Security tests: 5/5
- Performance tests: 4/4

---

## Credits

- Implementation: DeepAgents Core Team
- Security Review: Security Architecture Team
- Performance Testing: Performance Engineering Team
