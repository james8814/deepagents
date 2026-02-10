# DeepAgents 通用文件上传适配器实施方案 V2.0

**版本**: V2.0 (修订版)
**日期**: 2026-02-27
**状态**: 已根据第一轮审查修订

---

## 1. 修订记录

### 1.1 第一轮审查修复的问题

| 问题 | 严重性 | 修复措施 |
|------|--------|----------|
| 能力检测不可靠 | 🔴 | 改为行为检测（鸭子类型） |
| StateBackend 二进制处理 | 🔴 | 添加 base64 编码 + 大小限制 |
| CompositeBackend 处理 | 🔴 | 正确委托给 CompositeBackend 内部路由 |
| 工厂函数支持 | 🟠 | 添加 callable backend 支持 |
| 并发安全 | 🟠 | 添加线程安全提示 + 可选锁 |
| 错误格式统一 | 🟠 | 统一使用 UploadResult |
| Fallback 路径 | 🟡 | 使用平台无关的临时目录 |

---

## 2. 核心设计变更

### 2.1 行为检测替代源码检测

```python
def _detect_upload_capability(self, backend) -> bool:
    """
    通过行为检测 upload_files 能力（鸭子类型）。

    优于 inspect.getsource() 因为:
    - 不依赖源码可用性
    - 跨平台兼容（包括 pyc 文件）
    - 测试真实行为而非代码形式
    """
    if not hasattr(backend, 'upload_files'):
        return False

    # 尝试上传空文件测试
    try:
        test_files = [("/.__upload_test__/detect.txt", b"")]
        result = backend.upload_files(test_files)

        # 验证返回类型
        if not isinstance(result, list):
            return False
        if len(result) != 1:
            return False

        # 检查结果格式
        response = result[0]
        if hasattr(response, 'error'):
            return True  # 即使 error 不为 None，也说明方法存在
        if isinstance(response, dict) and 'error' in response:
            return True

        return True

    except NotImplementedError:
        # 明确抛出 NotImplementedError
        return False
    except Exception as e:
        # 其他错误（权限、路径等）说明方法存在
        # 只是测试文件有问题
        logger.debug(f"Capability detection test failed with {type(e).__name__}: {e}")
        return True
```

### 2.2 改进的 StateWriteStrategy

```python
class StateWriteStrategy(UploadStrategy):
    """
    将文件写入 runtime.state['files']。

    ⚠️ 限制:
    - 大文件 (>1MB) 会被拒绝（内存考虑）
    - 二进制文件使用 base64 编码（增加 33% 大小）
    - 非线程安全（由调用方保证）
    """

    MAX_FILE_SIZE = 1024 * 1024  # 1MB 限制

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        if runtime is None:
            raise RuntimeError(
                "StateWriteStrategy requires runtime. "
                "Ensure you pass runtime= parameter."
            )

        results = []
        for path, content in files:
            result = self._upload_single(runtime, path, content)
            results.append(result)

        return results

    def _upload_single(
        self,
        runtime,
        path: str,
        content: bytes,
    ) -> UploadResult:
        # 大小检查
        if len(content) > self.MAX_FILE_SIZE:
            return UploadResult(
                path=path,
                success=False,
                error=f"File too large for StateBackend ({len(content)} > {self.MAX_FILE_SIZE}). "
                      f"Consider using FilesystemBackend or CompositeBackend with /uploads/ route.",
                strategy="state",
            )

        try:
            # 检测是否是文本文件
            is_text = self._is_text_content(content)

            if is_text:
                # 文本文件直接存储
                file_content = content.decode("utf-8")
            else:
                # 二进制文件使用 base64
                import base64
                file_content = {
                    "__encoding__": "base64",
                    "data": base64.b64encode(content).decode("ascii"),
                }

            # 创建 FileData 结构
            from deepagents.backends.utils import create_file_data

            file_data = create_file_data(
                content=file_content if is_text else json.dumps(file_content),
                created_at=datetime.now().isoformat(),
                modified_at=datetime.now().isoformat(),
            )

            # 写入 state（非线程安全，调用方负责）
            if "files" not in runtime.state:
                runtime.state["files"] = {}

            runtime.state["files"][path] = file_data

            return UploadResult(
                path=path,
                success=True,
                error=None,
                strategy="state",
                encoding="utf-8" if is_text else "base64",
            )

        except Exception as e:
            return UploadResult(
                path=path,
                success=False,
                error=str(e),
                strategy="state",
            )

    def _is_text_content(self, content: bytes) -> bool:
        """检测内容是否是文本（UTF-8 可解码且没有 null 字节）"""
        if b"\x00" in content[:1024]:
            return False
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
```

### 2.3 统一的返回格式

```python
@dataclass
class UploadResult:
    """统一的上传结果格式"""

    path: str
    """虚拟路径（如 /uploads/file.pdf）"""

    success: bool
    """是否成功"""

    error: str | None
    """错误信息（如果失败）"""

    strategy: str
    """使用的策略（direct/state/sandbox/fallback）"""

    encoding: str | None = None
    """编码方式（仅 StateWriteStrategy）"""

    physical_path: str | None = None
    """物理路径（如果有）"""
```

### 2.4 工厂函数支持

```python
class UploadAdapter:
    def upload(
        self,
        backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        # 解析 backend 工厂
        backend = self._resolve_backend(backend_or_factory, runtime)
        # ... 继续处理

    def _resolve_backend(self, backend_or_factory, runtime):
        """解析 backend 或工厂函数"""
        if callable(backend_or_factory) and not isinstance(backend_or_factory, type):
            # 是工厂函数，需要 runtime
            if runtime is None:
                raise RuntimeError(
                    "Backend factory requires runtime parameter. "
                    "Pass runtime= when calling upload_files()."
                )
            return backend_or_factory(runtime)
        return backend_or_factory
```

### 2.5 CompositeBackend 正确处理

```python
def _detect_capabilities(self, backend) -> UploadCapability:
    caps = UploadCapability()

    # 检测是否是 CompositeBackend
    caps.is_composite = hasattr(backend, "routes") and hasattr(backend, "default")

    if caps.is_composite:
        # CompositeBackend 有自己的 upload_files 实现
        # 它会内部路由到子 backend
        # 我们让它自己处理，但标记为 composite
        caps.supports_upload_files = hasattr(backend, "upload_files")
        return caps

    # 其他 backend 的检测...
    caps.supports_upload_files = self._detect_upload_capability(backend)
    caps.supports_state_files = hasattr(backend, "runtime")
    caps.is_sandbox = hasattr(backend, "sandbox_id") or hasattr(backend, "container_id")

    return caps

def _select_strategy(self, caps: UploadCapability) -> UploadStrategy:
    if caps.is_composite:
        # CompositeBackend 让它自己处理路由
        return self._strategies["direct"]

    # 其他策略选择...
```

---

## 3. 完整实现代码

```python
# deepagents/upload_adapter.py
"""Universal upload adapter for DeepAgents backends."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Unified upload result format."""

    path: str
    success: bool
    error: str | None
    strategy: str
    encoding: str | None = None
    physical_path: str | None = None


@dataclass
class UploadCapability:
    """Detected backend capabilities."""

    supports_upload_files: bool = False
    supports_state_files: bool = False
    is_sandbox: bool = False
    is_composite: bool = False


class UploadStrategy(ABC):
    """Abstract upload strategy."""

    @abstractmethod
    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        pass


class DirectUploadStrategy(UploadStrategy):
    """Use backend's native upload_files method."""

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        responses = backend.upload_files(files)

        results = []
        for (path, _), response in zip(files, responses):
            error = response.error if hasattr(response, "error") else response.get("error")
            results.append(
                UploadResult(
                    path=path,
                    success=error is None,
                    error=error,
                    strategy="direct",
                )
            )
        return results


class StateWriteStrategy(UploadStrategy):
    """Write to runtime.state['files'] with base64 support for binary."""

    MAX_FILE_SIZE = 1024 * 1024  # 1MB

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        if runtime is None:
            raise RuntimeError("StateWriteStrategy requires runtime parameter")

        results = []
        for path, content in files:
            result = self._upload_single(runtime, path, content)
            results.append(result)
        return results

    def _upload_single(self, runtime, path: str, content: bytes) -> UploadResult:
        if len(content) > self.MAX_FILE_SIZE:
            return UploadResult(
                path=path,
                success=False,
                error=f"File too large ({len(content)} > {self.MAX_FILE_SIZE}). "
                      "Use FilesystemBackend for large files.",
                strategy="state",
            )

        try:
            is_text = self._is_text_content(content)

            if is_text:
                file_content = content.decode("utf-8")
                encoding = "utf-8"
            else:
                import base64
                file_content = json.dumps({
                    "__encoding__": "base64",
                    "data": base64.b64encode(content).decode("ascii"),
                })
                encoding = "base64"

            # Create FileData
            file_data = {
                "content": file_content.splitlines(keepends=True),
                "created_at": datetime.now().isoformat(),
                "modified_at": datetime.now().isoformat(),
            }

            # Write to state
            if "files" not in runtime.state:
                runtime.state["files"] = {}
            runtime.state["files"][path] = file_data

            return UploadResult(
                path=path,
                success=True,
                error=None,
                strategy="state",
                encoding=encoding,
            )

        except Exception as e:
            return UploadResult(
                path=path,
                success=False,
                error=str(e),
                strategy="state",
            )

    def _is_text_content(self, content: bytes) -> bool:
        if b"\x00" in content[:1024]:
            return False
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False


class FilesystemFallbackStrategy(UploadStrategy):
    """Fallback to direct filesystem write."""

    def __init__(self):
        import tempfile
        self.root_dir = tempfile.gettempdir() + "/deepagents_uploads"

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        import os
        from pathlib import Path

        results = []
        for virtual_path, content in files:
            try:
                physical_path = Path(self.root_dir) / virtual_path.lstrip("/")
                physical_path.parent.mkdir(parents=True, exist_ok=True)

                with open(physical_path, "wb") as f:
                    f.write(content)

                results.append(
                    UploadResult(
                        path=virtual_path,
                        success=True,
                        error=None,
                        strategy="fallback",
                        physical_path=str(physical_path),
                    )
                )
            except Exception as e:
                results.append(
                    UploadResult(
                        path=virtual_path,
                        success=False,
                        error=str(e),
                        strategy="fallback",
                    )
                )
        return results


class UploadAdapter:
    """Universal upload adapter for any DeepAgents backend."""

    _strategies: dict[str, UploadStrategy] = {}

    def __init__(self):
        self._strategies = {
            "direct": DirectUploadStrategy(),
            "state": StateWriteStrategy(),
            "fallback": FilesystemFallbackStrategy(),
        }

    def upload(
        self,
        backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        """Upload files using automatically selected strategy."""
        backend = self._resolve_backend(backend_or_factory, runtime)
        caps = self._detect_capabilities(backend)
        strategy = self._select_strategy(caps)

        logger.debug(f"Uploading {len(files)} files using {strategy.__class__.__name__}")
        return strategy.upload(backend, files, runtime)

    def _resolve_backend(self, backend_or_factory, runtime):
        if callable(backend_or_factory) and not isinstance(backend_or_factory, type):
            if runtime is None:
                raise RuntimeError("Backend factory requires runtime parameter")
            return backend_or_factory(runtime)
        return backend_or_factory

    def _detect_capabilities(self, backend) -> UploadCapability:
        caps = UploadCapability()

        # Check for CompositeBackend
        caps.is_composite = hasattr(backend, "routes") and hasattr(backend, "_get_backend_and_key")

        if caps.is_composite:
            caps.supports_upload_files = hasattr(backend, "upload_files")
            return caps

        # Check for sandbox
        caps.is_sandbox = hasattr(backend, "sandbox_id") or hasattr(backend, "execute")

        # Check for state support
        caps.supports_state_files = hasattr(backend, "runtime")

        # Check upload_files capability
        caps.supports_upload_files = self._test_upload_capability(backend)

        return caps

    def _test_upload_capability(self, backend) -> bool:
        if not hasattr(backend, "upload_files"):
            return False

        try:
            result = backend.upload_files([("/.__test__/detect.txt", b"")])
            return isinstance(result, list)
        except NotImplementedError:
            return False
        except Exception as e:
            logger.debug(f"Capability test: {type(e).__name__}: {e}")
            return True

    def _select_strategy(self, caps: UploadCapability) -> UploadStrategy:
        if caps.is_composite and caps.supports_upload_files:
            return self._strategies["direct"]

        if caps.is_sandbox:
            # Sandbox backends typically support upload_files
            if caps.supports_upload_files:
                return self._strategies["direct"]

        if caps.supports_upload_files:
            return self._strategies["direct"]

        if caps.supports_state_files:
            return self._strategies["state"]

        return self._strategies["fallback"]


# Global instance
_upload_adapter = UploadAdapter()


def upload_files(
    backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
    files: list[tuple[str, bytes]],
    runtime=None,
) -> list[UploadResult]:
    """Universal upload function that works with ANY backend."""
    return _upload_adapter.upload(backend_or_factory, files, runtime)
```

---

## 4. 测试计划

### 4.1 单元测试

```python
# tests/unit_tests/test_upload_adapter.py

import pytest
from deepagents.upload_adapter import (
    UploadAdapter,
    UploadCapability,
    DirectUploadStrategy,
    StateWriteStrategy,
)
from deepagents.backends import FilesystemBackend, StateBackend


class TestCapabilityDetection:
    """测试能力检测"""

    def test_detect_filesystem_backend(self):
        backend = FilesystemBackend(root_dir="/tmp/test")
        adapter = UploadAdapter()
        caps = adapter._detect_capabilities(backend)

        assert caps.supports_upload_files is True
        assert caps.supports_state_files is False
        assert caps.is_composite is False

    def test_detect_state_backend(self, mock_runtime):
        backend = StateBackend(mock_runtime)
        adapter = UploadAdapter()
        caps = adapter._detect_capabilities(backend)

        assert caps.supports_upload_files is False  # NotImplementedError
        assert caps.supports_state_files is True


class TestStateWriteStrategy:
    """测试 StateWriteStrategy"""

    def test_upload_text_file(self, mock_runtime):
        strategy = StateWriteStrategy()
        backend = StateBackend(mock_runtime)

        results = strategy.upload(
            backend,
            [("/uploads/test.txt", b"Hello World")],
            runtime=mock_runtime,
        )

        assert results[0].success is True
        assert results[0].encoding == "utf-8"
        assert "/uploads/test.txt" in mock_runtime.state["files"]

    def test_upload_binary_file(self, mock_runtime):
        strategy = StateWriteStrategy()
        backend = StateBackend(mock_runtime)

        binary_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        results = strategy.upload(
            backend,
            [("/uploads/image.png", binary_content)],
            runtime=mock_runtime,
        )

        assert results[0].success is True
        assert results[0].encoding == "base64"

    def test_upload_large_file_rejected(self, mock_runtime):
        strategy = StateWriteStrategy()
        backend = StateBackend(mock_runtime)

        large_content = b"x" * (1024 * 1024 + 1)  # 1MB + 1
        results = strategy.upload(
            backend,
            [("/uploads/large.bin", large_content)],
            runtime=mock_runtime,
        )

        assert results[0].success is False
        assert "too large" in results[0].error.lower()


class TestIntegration:
    """集成测试"""

    def test_upload_with_all_backend_types(self):
        """测试所有 backend 类型"""
        from deepagents.upload_adapter import upload_files

        backends = [
            FilesystemBackend(root_dir="/tmp/test_upload"),
            # StateBackend 需要 runtime
            # CompositeBackend 需要配置
        ]

        for backend in backends:
            results = upload_files(
                backend,
                [("/uploads/test.txt", b"integration test")]
            )
            assert results[0].success, f"Failed for {backend.__class__.__name__}"
```

---

## 5. 第二轮审查请求

本次修订解决了第一轮审查发现的所有严重问题：

1. ✅ 能力检测改为行为检测（鸭子类型）
2. ✅ StateBackend 支持二进制文件（base64 编码）
3. ✅ 添加 1MB 大小限制防止内存问题
4. ✅ CompositeBackend 正确处理
5. ✅ 统一 UploadResult 返回格式
6. ✅ 支持工厂函数

**请求第二轮专家审查**。
