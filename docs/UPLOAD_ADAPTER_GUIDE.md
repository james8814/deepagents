# DeepAgents Upload Adapter 使用指南

**版本**: V5.0
**日期**: 2026-02-27
**状态**: 生产就绪

---

## 快速开始

```python
from deepagents import upload_files, UploadResult
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
        print(f"✓ {result.path}: uploaded ({result.strategy})")
    else:
        print(f"✗ {result.path}: failed - {result.error}")
```

---

## 功能特性

### 自动策略选择

Upload Adapter 自动检测 backend 类型并选择最佳上传策略：

| Backend 类型 | 策略 | 说明 |
|-------------|------|------|
| `FilesystemBackend` | `direct` | 使用 `upload_files()` 直接上传 |
| `CompositeBackend` | `direct` | 路由到适当的 backend |
| `StateBackend` | `state` | 使用 `write()` 写入 state |
| 其他 | `fallback` | 使用临时 FilesystemBackend |

### P0 问题修复

V5.0 修复了以下关键问题：

| 问题 | 修复方案 |
|------|---------|
| **锁内存泄漏** | 使用 `WeakKeyDictionary` 自动释放 |
| **read() 类型错误** | 使用 `download_files()` 检测存在性 |
| **代码未实现** | 提供完整 548 行实现 |

---

## 使用场景

### 场景 1: FilesystemBackend

```python
from deepagents import upload_files
from deepagents.backends import FilesystemBackend

backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)

results = upload_files(backend, [
    ("/data/config.json", b'{"key": "value"}'),
])

# 结果包含覆盖检测
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

## API 参考

### `upload_files()`

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
    """
```

### `UploadResult`

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

## 安全配置

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

---

## 错误处理

```python
from deepagents import upload_files

try:
    results = upload_files(backend, files, runtime=runtime)
    for result in results:
        if not result.success:
            if result.error == "file_not_found":
                print("File not found")
            elif result.error == "permission_denied":
                print("Permission denied")
            elif "too large" in str(result.error):
                print("File too large")
            else:
                print(f"Error: {result.error}")
except RuntimeError as e:
    # 缺少 runtime 参数
    print(f"Runtime error: {e}")
```

---

## 性能优化

### 并发上传

Upload Adapter 使用细粒度锁确保线程安全：

```python
import threading

def upload_worker(files):
    upload_files(backend, files, runtime=runtime)

# 多线程安全上传
threads = [
    threading.Thread(target=upload_worker, args=(file_batch,))
    for file_batch in batches
]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### 内存优化

```python
# WeakKeyDictionary 自动释放锁
# 无需手动清理
```

---

## 与 CLI 集成

```python
# 在 CLI agent 中使用
from deepagents import create_deep_agent
from deepagents.middleware import AttachmentMiddleware

agent = create_deep_agent(
    middleware=[
        AttachmentMiddleware(backend=backend, uploads_dir="/uploads")
    ]
)
```

---

## 迁移指南

### 从直接 backend.upload_files() 迁移

**之前**:
```python
backend.upload_files([
    ("/file.txt", b"content")
])
```

**之后**:
```python
from deepagents import upload_files

upload_files(backend, [
    ("/file.txt", b"content")
])
```

**优势**:
- 自动策略选择
- StateBackend 支持
- 覆盖检测
- 统一错误处理

---

## 测试覆盖

| 测试类别 | 数量 | 状态 |
|---------|------|------|
| 基础功能 | 12 | ✅ 通过 |
| 安全测试 | 8 | ✅ 通过 |
| 并发测试 | 6 | ✅ 通过 |
| 边界测试 | 10 | ✅ 通过 |
| 集成测试 | 8 | ✅ 通过 |
| **总计** | **44** | **✅ 100%** |

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| V1.0 | 2026-02-27 | 初始设计 |
| V2.0 | 2026-02-27 | 修复能力检测 |
| V3.0 | 2026-02-27 | SRP分离，OCP规则 |
| V4.0 | 2026-02-27 | 综合评审版 |
| **V5.0** | **2026-02-27** | **生产就绪版** |

---

## 相关文档

- [UNIVERSAL_UPLOAD_ADAPTER_V5.md](attachment_function_docs/UNIVERSAL_UPLOAD_ADAPTER_V5.md) - 完整实施方案
- [FINAL_DELIVERY_REPORT.md](attachment_function_docs/FINAL_DELIVERY_REPORT.md) - 评审报告
- [SDK_UPGRADE_GUIDE.md](SDK_UPGRADE_GUIDE.md) - SDK 升级指南
