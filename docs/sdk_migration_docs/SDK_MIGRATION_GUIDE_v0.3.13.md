# DeepAgents SDK v0.3.13 迁移指南

**发布日期**: 2026-02-28
**版本号**: v0.3.13 (Feature Release)
**影响范围**: SDK 用户（CLI 用户无影响）

---

## 📋 执行摘要

本版本新增 **Universal Upload Adapter**，为所有 DeepAgents 后端提供统一的文件上传接口。

### 变更统计
- ✅ **新功能**: `upload_files()` 函数
- ✅ **新数据类**: `UploadResult`
- ✅ **后端支持**: FilesystemBackend, StateBackend, CompositeBackend
- ✅ **测试覆盖**: 新增 44 个单元测试
- ✅ **向后兼容**: 100% 兼容，无破坏性变更

---

## ✨ 新功能

### 1. upload_files() 函数

**统一的文件上传接口**，自动检测后端类型并选择最佳上传策略。

**导入方式**:
```python
from deepagents import upload_files, UploadResult
```

**基本用法**:
```python
from deepagents import upload_files
from deepagents.backends import FilesystemBackend

# 创建 backend
backend = FilesystemBackend(root_dir="/workspace")

# 上传文件
results = upload_files(backend, [
    ("/uploads/file1.txt", b"Hello, World!"),
    ("/uploads/file2.txt", b"Second file content"),
])

# 检查结果
for result in results:
    if result.success:
        print(f"✓ {result.path}: uploaded via {result.strategy}")
    else:
        print(f"✗ {result.path}: failed - {result.error}")
```

### 2. UploadResult 数据类

**标准化的上传结果格式**:

```python
@dataclass
class UploadResult:
    path: str                    # 虚拟路径
    success: bool               # 是否成功
    error: str | None           # 错误信息
    strategy: str               # 使用的策略 (direct/state/fallback)
    encoding: str | None        # 编码 (utf-8/base64)
    physical_path: str | None   # 物理路径 (仅 fallback 策略)
    is_overwrite: bool          # 是否覆盖已存在的文件
    previous_size: int | None   # 原文件大小（如果覆盖）
```

### 3. 自动策略选择

| Backend 类型 | 策略 | 说明 |
|-------------|------|------|
| `FilesystemBackend` | `direct` | 使用 `upload_files()` 直接上传 |
| `CompositeBackend` | `direct` | 路由到适当的 backend |
| `StateBackend` | `state` | 使用 `write()` 写入 state |
| 其他 | `fallback` | 使用安全临时 FilesystemBackend |

---

## 📖 使用场景

### 场景 1: FilesystemBackend

```python
from deepagents import upload_files
from deepagents.backends import FilesystemBackend

backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)

results = upload_files(backend, [
    ("/data/config.json", b'{"key": "value"}'),
])

# 覆盖检测
if results[0].is_overwrite:
    print(f"Overwrote file (previous size: {results[0].previous_size} bytes)")
```

### 场景 2: StateBackend

```python
from deepagents import upload_files
from deepagents.backends import StateBackend

# StateBackend 需要 runtime
runtime = {"state": {"files": {}}}
backend = StateBackend(runtime)

results = upload_files(backend, [
    ("/state/data.txt", b"State stored content"),
], runtime=runtime)

# 二进制文件自动 Base64 编码
results = upload_files(backend, [
    ("/state/image.png", binary_data),
], runtime=runtime)
```

### 场景 3: 工厂函数

```python
from deepagents import upload_files
from deepagents.backends import StateBackend

# 使用工厂函数
def backend_factory(runtime):
    return StateBackend(runtime)

runtime = {"state": {"files": {}}}

results = upload_files(backend_factory, [
    ("/factory/data.txt", b"Factory created"),
], runtime=runtime)
```

### 场景 4: CompositeBackend

```python
from deepagents import upload_files
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

fs = FilesystemBackend(root_dir="/workspace")
state_runtime = {"state": {"files": {}}}
state = StateBackend(state_runtime)

composite = CompositeBackend(
    default=fs,
    routes={
        "/state/": state,
    }
)

# 路由到不同 backend
results = upload_files(composite, [
    ("/data/file.txt", b"Goes to FilesystemBackend"),
    ("/state/config.txt", b"Goes to StateBackend"),
])
```

---

## 🔒 安全特性

### 文件大小限制

```python
import os

# 设置 5MB 限制 (默认 1MB)
os.environ["DEEPAGENTS_UPLOAD_MAX_SIZE"] = str(5 * 1024 * 1024)
```

### 路径安全

```python
from deepagents.backends import FilesystemBackend

# virtual_mode=True 启用路径遍历防护
backend = FilesystemBackend(
    root_dir="/workspace",
    virtual_mode=True  # 防止 .. 和 ~ 攻击
)
```

### 安全临时目录（fallback 策略）

- 使用 `tempfile.mkdtemp()` 创建安全临时目录
- 目录权限 `0o700` (仅所有者可访问)
- 文件权限 `0o600` (仅所有者可读写)
- 自动清理（try-finally）
- 随机后缀防止路径预测攻击

---

## 🔄 迁移指南

### 对于现有用户

**无需修改** - 这是纯增量更新，完全向后兼容。

### 推荐使用方式

**之前** (直接使用 backend.upload_files):
```python
# 仅支持 FilesystemBackend
backend.upload_files([
    ("/file.txt", b"content")
])
```

**之后** (使用统一接口):
```python
from deepagents import upload_files

# 支持 FilesystemBackend, StateBackend, CompositeBackend
upload_files(backend, [
    ("/file.txt", b"content")
])
```

**优势**:
- 自动策略选择
- StateBackend 支持
- 覆盖检测
- 统一错误处理
- 工厂函数支持

---

## 🧪 测试覆盖

| 测试类别 | 数量 | 状态 |
|---------|------|------|
| StateUploadLock | 3 | ✅ 通过 |
| ResolveBackend | 3 | ✅ 通过 |
| SelectStrategy | 5 | ✅ 通过 |
| IsTextContent | 6 | ✅ 通过 |
| UploadDirect | 3 | ✅ 通过 |
| UploadToState | 7 | ✅ 通过 |
| UploadFallback | 3 | ✅ 通过 |
| Integration | 4 | ✅ 通过 |
| Boundary | 4 | ✅ 通过 |
| Security | 6 | ✅ 通过 |
| ErrorHandling | 4 | ✅ 通过 |
| **总计** | **44** | **✅ 100%** |

**运行测试**:
```bash
cd libs/deepagents
make test TEST_FILE=tests/unit_tests/test_upload_adapter.py
```

---

## 📦 依赖变更

**无新依赖** - 所有功能使用 Python 标准库实现：
- `threading` - 并发锁
- `weakref` - 内存泄漏防护
- `tempfile` - 安全临时目录
- `secrets` - 随机 token
- `base64` - 二进制编码

**版本要求**:
- Python >=3.11 (保持不变)

---

## 📋 API 参考

### upload_files()

```python
def upload_files(
    backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Upload files to any backend with automatic strategy selection.

    Args:
        backend_or_factory: Backend instance or factory function.
        files: List of (virtual_path, content) tuples.
        runtime: Optional runtime context (required for StateBackend).

    Returns:
        List of UploadResult objects.

    Raises:
        RuntimeError: If StateBackend used without runtime parameter.
    """
```

### UploadResult

```python
@dataclass
class UploadResult:
    path: str                    # 虚拟路径
    success: bool               # 是否成功
    error: FileOperationError | str | None  # 错误信息
    strategy: str               # 使用的策略 (direct/state/fallback)
    encoding: str | None        # 编码 (utf-8/base64)
    physical_path: str | None   # 物理路径 (fallback)
    is_overwrite: bool          # 是否覆盖
    previous_size: int | None   # 原文件大小
```

---

## 📋 检查清单

升级后请确认：

- [ ] 更新 `deepagents` 包到 v0.3.13
- [ ] 如需使用新功能，导入 `upload_files` 和 `UploadResult`
- [ ] 运行测试确保功能正常
- [ ] 查看 `docs/UPLOAD_ADAPTER_GUIDE.md` 了解详细用法

---

## 🔗 相关文档

- **用户指南**: `docs/UPLOAD_ADAPTER_GUIDE.md`
- **变更日志**: `CHANGELOG_V5.1.md`
- **测试文件**: `libs/deepagents/tests/unit_tests/test_upload_adapter.py`
- **实现文件**: `libs/deepagents/deepagents/upload_adapter.py`

---

## 📞 技术支持

如有问题，请联系：
- GitHub Issues: https://github.com/james8814/deepagents/issues
- 文档: https://docs.langchain.com/oss/python/deepagents/overview

---

**迁移难度**: ⭐ (极低) - 纯增量更新，无需修改现有代码

**建议升级时间**: 10 分钟（安装 + 验证）

**兼容性**: ✅ 100% 向后兼容