# 专家审查报告 - 第一轮 (架构师视角)

**审查日期**: 2026-02-27
**审查人**: 系统架构师
**方案版本**: V1.0

---

## 🔴 严重问题 (必须修复)

### 1. 能力检测算法不可靠

**问题描述**:
```python
# V1 方案代码
source = inspect.getsource(backend.upload_files)
caps.supports_upload_files = "NotImplementedError" not in source
```

**问题**:
- `inspect.getsource()` 在多种情况下会失败（pyc 文件、C 扩展、IDE 环境）
- 字符串匹配 "NotImplementedError" 不可靠，可能有多种写法
- 没有真正测试 backend 的行为

**建议**:
使用**行为检测**而非**源码检测**:
```python
def detect_upload_capability(backend) -> bool:
    """通过鸭子类型检测 upload_files 能力"""
    # 检查方法是否存在
    if not hasattr(backend, 'upload_files'):
        return False

    # 尝试上传一个测试文件（空文件或临时文件）
    try:
        test_result = backend.upload_files([("/__test__/detect.txt", b"")])
        # 如果返回列表且不是异常，说明支持
        return isinstance(test_result, list)
    except NotImplementedError:
        return False
    except Exception:
        # 其他错误（权限、路径等）不代表不支持
        return True
```

### 2. StateBackend 策略有严重缺陷

**问题描述**:
```python
# StateWriteStrategy
file_data = create_file_data(
    content=content.decode("utf-8", errors="replace"),
    ...
)
```

**问题**:
- 强制将 bytes 转为 str，会破坏二进制文件（图片、PDF）
- StateBackend 设计用于文本文件，不适合存储二进制内容
- 大文件会占用大量内存

**建议**:
StateWriteStrategy 应该:
1. 检测文件类型，拒绝二进制文件
2. 或者使用 base64 编码存储二进制
3. 添加大小限制，拒绝大文件

### 3. CompositeBackend 处理不正确

**问题描述**:
V1 方案没有针对 CompositeBackend 的特殊处理。

**问题**:
- CompositeBackend 有自己的 `upload_files` 实现
- 它会自动路由到子 backend
- 但如果子 backend 是 StateBackend，子 backend 会失败

**建议**:
```python
# 需要递归检测
if caps.is_composite:
    # 对于 CompositeBackend，让它自己处理
    # 但需要确保子 backend 能够处理
    return DirectUploadStrategy()
```

---

## 🟠 中等问题 (建议修复)

### 4. 缺少运行时 backend 工厂支持

**问题描述**:
```python
# 用户可能使用工厂函数
backend_factory = lambda rt: StateBackend(rt)

# V1 方案不支持
upload_files(backend_factory, ...)  # ❌ 失败
```

**建议**:
支持工厂函数:
```python
def upload_files(backend_or_factory, files, runtime=None):
    backend = backend_or_factory
    if callable(backend) and runtime is not None:
        backend = backend(runtime)
    # ...
```

### 5. 并发安全性未考虑

**问题描述**:
多个请求同时上传文件到 StateBackend:
```python
runtime.state["files"][path] = file_data  # 非原子操作
```

**问题**:
- 可能丢失更新
- StateBackend 使用 dict，不是线程安全的

**建议**:
添加锁或提示用户处理并发

### 6. 错误处理不一致

**问题描述**:
不同策略返回的错误格式不一致:
- `DirectUploadStrategy`: 返回 `FileUploadResponse`
- `StateWriteStrategy`: 返回 `dict`
- `FilesystemFallbackStrategy`: 可能返回 `OSError`

**建议**:
统一错误格式:
```python
@dataclass
class UploadResult:
    path: str
    success: bool
    error: str | None
    strategy: str  # 记录使用的策略
```

---

## 🟡 小问题 (可选优化)

### 7. Fallback 策略路径设计

**问题**:
```python
FilesystemFallbackStrategy(root_dir="/tmp/deepagents_uploads")
```
- 硬编码 `/tmp` 路径
- 没有考虑 Windows 环境
- 没有清理机制

### 8. 缺少监控和日志

**问题**:
没有记录:
- 使用了哪种策略
- 上传耗时
- 失败原因

---

## 📊 审查总结

| 类别 | 数量 | 状态 |
|------|------|------|
| 🔴 严重问题 | 3 | 必须修复 |
| 🟠 中等问题 | 3 | 建议修复 |
| 🟡 小问题 | 2 | 可选修复 |

**总体评价**: V1 方案在概念上是正确的，但在实现细节上有多处需要完善，特别是能力检测和 StateBackend 处理。

**建议**: 修复严重问题后，进行第二轮审查。
