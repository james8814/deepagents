# DeepAgents 通用文件上传适配器实施方案 V1.0

**版本**: V1.0
**日期**: 2026-02-27
**状态**: 初稿 / 待审查

---

## 1. 执行摘要

### 1.1 问题陈述

当前 DeepAgents 框架存在严重的 backend 能力不一致问题：

| Backend | `upload_files` | `read_file` | 适用场景 |
|---------|---------------|-------------|----------|
| `FilesystemBackend` | ✅ 支持 | ✅ 支持 | 本地开发 |
| `StateBackend` | ❌ **不支持** | ✅ 支持 | 默认配置 |
| `StoreBackend` | ✅ 支持 | ✅ 支持 | 生产持久化 |
| `SandboxBackend` | ✅ 支持 | ✅ 支持 | 远程沙箱 |
| `CompositeBackend` | ✅ 支持 | ✅ 支持 | 混合配置 |

**核心问题**: `StateBackend` 默认被使用，但不支持 `upload_files`，导致任何文件上传功能都会失败。

### 1.2 解决方案概述

设计**通用上传适配器（Universal Upload Adapter）**，通过**能力检测（Capability Detection）**自动选择最佳上传策略，无需硬编码 backend 类型。

### 1.3 关键特性

- ✅ **零配置**: 自动检测 backend 能力
- ✅ **向后兼容**: 不破坏现有代码
- ✅ **可扩展**: 支持未来新增 backend 类型
- ✅ **统一接口**: 单一 `upload_files()` 函数

---

## 2. 架构设计

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                     Universal Upload Adapter                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Capability     │  │   Strategy      │  │   Executor      │  │
│  │  Detector       │→ │   Selector      │→ │                 │  │
│  │                 │  │                 │  │                 │  │
│  │ • upload_files  │  │ • Direct        │  │ • Filesystem    │  │
│  │ • state write   │  │ • StateWrite    │  │ • State         │  │
│  │ • sandbox       │  │ • SandboxProxy  │  │ • Sandbox API   │  │
│  │ • direct write  │  │ • Fallback      │  │ • Composite     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 策略模式设计

```python
class UploadStrategy(ABC):
    @abstractmethod
    def upload(self, backend, files, runtime=None) -> list[FileUploadResponse]:
        pass

class DirectUploadStrategy(UploadStrategy):
    """Backend 原生支持 upload_files"""
    pass

class StateWriteStrategy(UploadStrategy):
    """写入 runtime.state['files']"""
    pass

class SandboxProxyStrategy(UploadStrategy):
    """代理到 Sandbox API"""
    pass

class FilesystemFallbackStrategy(UploadStrategy):
    """直接写入本地文件系统"""
    pass
```

---

## 3. 详细设计

### 3.1 能力检测算法

```python
@dataclass
class UploadCapability:
    supports_upload_files: bool      # 是否实现 upload_files
    supports_state_files: bool       # 是否有 runtime.state
    supports_direct_write: bool      # 是否能直接写文件系统
    is_sandbox: bool                 # 是否是远程沙箱
    is_composite: bool               # 是否是组合 backend
```

**检测逻辑**:

```python
def detect_capabilities(backend) -> UploadCapability:
    caps = UploadCapability()

    # 检测 1: 是否支持 upload_files
    try:
        # 通过反射检查方法是否存在且不是抛出 NotImplementedError
        import inspect
        source = inspect.getsource(backend.upload_files)
        caps.supports_upload_files = "NotImplementedError" not in source
    except (OSError, TypeError):
        caps.supports_upload_files = True  # 假设支持，运行时验证

    # 检测 2: 是否支持 state 写入
    caps.supports_state_files = hasattr(backend, "runtime")

    # 检测 3: 是否是 sandbox
    caps.is_sandbox = hasattr(backend, "sandbox_id")

    # 检测 4: 是否是 composite
    caps.is_composite = hasattr(backend, "routes")

    return caps
```

### 3.2 策略选择矩阵

| 条件 | 选择策略 | 说明 |
|------|---------|------|
| `is_sandbox == True` | `SandboxProxyStrategy` | 远程沙箱，使用 API |
| `supports_upload_files == True` | `DirectUploadStrategy` | 原生支持 |
| `supports_state_files == True` | `StateWriteStrategy` | 写入 state |
| 其他 | `FilesystemFallbackStrategy` | 直接写磁盘 |

### 3.3 核心实现

```python
# deepagents/upload_adapter.py

class UploadAdapter:
    """通用上传适配器"""

    _strategies: dict[str, UploadStrategy] = {
        "direct": DirectUploadStrategy(),
        "state": StateWriteStrategy(),
        "sandbox": SandboxProxyStrategy(),
        "fallback": FilesystemFallbackStrategy(),
    }

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[FileUploadResponse]:
        # 1. 检测能力
        caps = self._detect_capabilities(backend)

        # 2. 选择策略
        strategy = self._select_strategy(caps)

        # 3. 执行上传
        return strategy.upload(backend, files, runtime)
```

---

## 4. 集成方案

### 4.1 后端 API 集成

```python
# server/routers/upload.py

from deepagents.upload_adapter import upload_files

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    backend=Depends(get_backend),
    runtime=Depends(get_runtime_optional),  # StateBackend 需要
):
    content = await file.read()
    target_path = f"/uploads/{file.filename}"

    # 通用上传 - 自动适配任意 backend
    results = upload_files(backend, [(target_path, content)], runtime)

    return {"path": target_path, "success": results[0].error is None}
```

### 4.2 CLI 集成

```python
# cli/deepagents_cli/app.py

from deepagents.upload_adapter import upload_files

class DeepAgentsApp:
    async def handle_upload(self, file_path: str):
        content = Path(file_path).read_bytes()
        target_path = f"/uploads/{Path(file_path).name}"

        # 自动适配 backend
        results = upload_files(
            self._backend,
            [(target_path, content)],
            runtime=self._runtime,  # 可选
        )
```

### 4.3 用户代码集成

```python
# 用户代码 - 无需关心 backend 类型

from deepagents import create_deep_agent
from deepagents.upload_adapter import upload_files

# 任意 backend 配置
agent = create_deep_agent(backend=user_config)

# 上传文件
upload_files(agent.backend, [("/uploads/file.pdf", content)])

# Agent 自动读取
agent.invoke({"messages": [{"role": "user", "content": "Read /uploads/file.pdf"}]})
```

---

## 5. 测试策略

### 5.1 单元测试矩阵

| Backend | 策略 | 测试场景 |
|---------|------|----------|
| `FilesystemBackend` | Direct | 正常上传、大文件、权限错误 |
| `StateBackend` | StateWrite | 写入 state、跨调用持久化 |
| `CompositeBackend` | Direct | 路由正确、多 backend 混合 |
| `DaytonaBackend` | SandboxProxy | API 调用、网络错误 |
| `MockBackend` | Fallback | 无 upload_files 方法 |

### 5.2 集成测试

```python
def test_upload_with_all_backends():
    """测试所有 backend 类型"""
    backends = [
        FilesystemBackend(root_dir="/tmp/test"),
        StateBackend(mock_runtime),
        CompositeBackend(...),
    ]

    for backend in backends:
        result = upload_files(backend, [("/uploads/test.txt", b"content")])
        assert result[0].error is None
```

---

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 能力检测不准确 | 中 | 高 | 运行时验证 + 降级策略 |
| StateBackend 性能问题 | 低 | 中 | 大文件检测 + 警告 |
| 并发上传冲突 | 低 | 中 | 文件级锁或原子写入 |
| 路径遍历攻击 | 低 | 高 | 输入验证 + virtual_path 检查 |

---

## 7. 实施计划

### Phase 1: 核心实现 (2 天)
- [ ] 实现 `UploadAdapter` 类
- [ ] 实现 4 种上传策略
- [ ] 实现能力检测算法

### Phase 2: 集成 (1 天)
- [ ] 集成到 CLI `/upload` 命令
- [ ] 集成到后端 API

### Phase 3: 测试 (2 天)
- [ ] 单元测试覆盖所有策略
- [ ] 集成测试所有 backend 类型
- [ ] 性能测试

### Phase 4: 文档 (1 天)
- [ ] API 文档
- [ ] 用户指南
- [ ] 迁移指南

---

## 8. 待审查问题

1. **能力检测准确性**: 反射检查 `upload_files` 源码是否可靠？
2. **StateBackend 大文件**: 写入 state 是否适合大文件（>10MB）？
3. **CompositeBackend 路由**: 是否需要特殊处理前缀剥离？
4. **错误处理**: 如何统一不同策略的错误格式？
5. **并发安全**: 是否需要考虑多线程/多进程并发上传？

---

**下一步**: 专家审查与挑战
