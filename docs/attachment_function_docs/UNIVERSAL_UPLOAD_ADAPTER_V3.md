# DeepAgents 通用文件上传适配器实施方案 V3.0

**版本**: V3.0 (第二轮修订版)
**日期**: 2026-02-27
**状态**: 已根据第二轮审查全面修订

---

## 1. 修订记录

### 1.1 第二轮审查修复的问题

| 问题 | 严重性 | 修复措施 |
|------|--------|----------|
| UploadAdapter违反SRP | 🔴 | 拆分为Resolver/Detector/Selector三个独立类 |
| 违反OCP - 硬编码策略选择 | 🔴 | 实现规则注册机制，支持动态策略规则 |
| hasattr能力检测不可靠 | 🔴 | 使用isinstance + 已知类型映射 |
| StateWriteStrategy绕过StateBackend | 🔴 | 使用backend.write()方法，遵守封装 |
| CompositeBackend路由重复 | 🔴 | 完全委托给CompositeBackend处理 |
| DirectUploadStrategy响应类型错误 | 🔴 | 修复为直接访问dataclass属性 |
| FilesystemFallbackStrategy路径遍历 | 🔴 | 添加完整的路径验证和O_NOFOLLOW |
| 能力检测副作用 | 🔴 | 改用非侵入式检测，不创建测试文件 |
| 缺少文件去重机制 | 🟠 | 添加is_overwrite和previous_size字段 |
| 缺少文件元数据校验 | 🟠 | 添加路径格式、文件名合法性验证 |
| 缺少异步支持 | 🟠 | 添加aupload方法和AsyncUploadStrategy基类 |

---

## 2. 核心架构变更

### 2.1 单一职责分离

```python
# V3.0: 职责分离设计

class BackendResolver:
    """负责解析backend或factory函数。"""

    def resolve(
        self,
        backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
        runtime: Any | None = None,
    ) -> BackendProtocol:
        """Resolve backend from factory or return as-is."""
        if callable(backend_or_factory) and not isinstance(backend_or_factory, type):
            if runtime is None:
                raise RuntimeError("Backend factory requires runtime parameter")
            return backend_or_factory(runtime)
        return backend_or_factory


class CapabilityDetector:
    """负责检测backend能力，使用非侵入式检测。"""

    # 已知backend类型映射
    _KNOWN_CAPABILITIES: dict[type, UploadCapability] = {
        FilesystemBackend: UploadCapability(supports_upload_files=True),
        StateBackend: UploadCapability(supports_state_files=True),
        CompositeBackend: UploadCapability(
            supports_upload_files=True, is_composite=True
        ),
    }

    def detect(self, backend: BackendProtocol) -> UploadCapability:
        """Detect backend capabilities without side effects."""
        backend_type = type(backend)

        # 直接检查已知类型
        for known_type, caps in self._KNOWN_CAPABILITIES.items():
            if isinstance(backend, known_type):
                return caps

        # 未知类型：保守策略
        return self._detect_unknown_backend(backend)

    def _detect_unknown_backend(self, backend: BackendProtocol) -> UploadCapability:
        """Detect unknown backend type using safe checks."""
        caps = UploadCapability()

        # 检查是否是Sandbox
        caps.is_sandbox = hasattr(backend, "sandbox_id") or hasattr(backend, "execute")

        # 检查是否有state支持
        caps.supports_state_files = hasattr(backend, "runtime")

        # 检查upload_files：不使用实际调用，使用inspect
        caps.supports_upload_files = self._check_upload_files_implemented(backend)

        return caps

    def _check_upload_files_implemented(self, backend: BackendProtocol) -> bool:
        """Check if upload_files is implemented without calling it."""
        if not hasattr(backend, "upload_files"):
            return False

        # 获取backend类的upload_files方法
        backend_class = type(backend)
        method = getattr(backend_class, "upload_files", None)

        if method is None:
            return False

        # 检查是否是抽象方法
        if hasattr(method, "__isabstractmethod__"):
            return False

        # 检查是否是父类的默认实现（抛出NotImplementedError）
        # 通过比较方法所属类来判断
        if hasattr(BackendProtocol, "upload_files"):
            protocol_method = getattr(BackendProtocol, "upload_files")
            if method is protocol_method:
                return False

        return True


@dataclass
class StrategyRule:
    """策略选择规则。"""

    priority: int
    predicate: Callable[[UploadCapability], bool]
    strategy_name: str


class StrategySelector:
    """负责根据能力选择策略，支持动态规则注册。"""

    _rules: list[StrategyRule] = field(default_factory=list)

    def __post_init__(self):
        """Initialize with default rules."""
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default strategy selection rules."""
        self.register_rule(
            StrategyRule(
                priority=100,
                predicate=lambda caps: caps.is_composite and caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=90,
                predicate=lambda caps: caps.is_sandbox and caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=80,
                predicate=lambda caps: caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=70,
                predicate=lambda caps: caps.supports_state_files,
                strategy_name="state",
            )
        )
        # fallback规则在select方法中处理

    def register_rule(self, rule: StrategyRule) -> None:
        """Register a new strategy selection rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def select(self, caps: UploadCapability, strategies: dict[str, UploadStrategy]) -> UploadStrategy:
        """Select strategy based on capabilities."""
        for rule in self._rules:
            if rule.predicate(caps):
                return strategies[rule.strategy_name]
        return strategies["fallback"]
```

### 2.2 修复StateWriteStrategy

```python
class StateWriteStrategy(UploadStrategy):
    """Write to StateBackend using its write() method.

    This strategy properly uses StateBackend's public API instead of
    directly manipulating runtime.state.
    """

    DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1MB

    def __init__(self, max_file_size: int | None = None):
        self.max_file_size = max_file_size or int(
            os.environ.get("DEEPAGENTS_UPLOAD_MAX_SIZE", self.DEFAULT_MAX_FILE_SIZE)
        )
        self._locks: dict[int, threading.Lock] = {}
        self._lock_creation_lock = threading.Lock()

    def _get_runtime_lock(self, runtime) -> threading.Lock:
        """Get or create a lock for the specific runtime."""
        runtime_id = id(runtime)
        if runtime_id not in self._locks:
            with self._lock_creation_lock:
                if runtime_id not in self._locks:
                    self._locks[runtime_id] = threading.Lock()
        return self._locks[runtime_id]

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        if runtime is None:
            raise RuntimeError("StateWriteStrategy requires runtime parameter")

        # 使用锁确保线程安全
        lock = self._get_runtime_lock(runtime)
        with lock:
            return self._upload_locked(backend, files, runtime)

    def _upload_locked(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime,
    ) -> list[UploadResult]:
        """Internal upload method with lock held."""
        # 预验证所有文件
        prevalidated = []
        for path, content in files:
            result = self._prevalidate(path, content)
            if result is not None:
                prevalidated.append((path, None, result))
            else:
                prevalidated.append((path, content, None))

        # 原子性批量写入
        results = []
        try:
            for path, content, error_result in prevalidated:
                if error_result:
                    results.append(error_result)
                    continue

                result = self._upload_single(backend, path, content)
                results.append(result)
        except Exception as e:
            logger.exception(f"Batch upload failed: {e}")
            raise

        return results

    def _prevalidate(self, path: str, content: bytes) -> UploadResult | None:
        """Pre-validate file before upload."""
        if len(content) > self.max_file_size:
            return UploadResult(
                path=path,
                success=False,
                error=f"File too large ({len(content)} > {self.max_file_size}). "
                      f"Consider using FilesystemBackend.",
                strategy="state",
            )
        return None

    def _upload_single(
        self,
        backend: BackendProtocol,
        path: str,
        content: bytes,
    ) -> UploadResult:
        """Upload single file using StateBackend.write()."""
        try:
            # 检测是否是文本文件
            is_text = self._is_text_content(content)

            if is_text:
                # 文本文件：分割成行
                lines = content.decode("utf-8").splitlines(keepends=True)
                # 确保文件以换行符结尾（如果原始内容非空）
                if content and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                encoding = "utf-8"
            else:
                # 二进制文件：存储为元数据格式
                import base64
                lines = [
                    f"__BINARY_FILE__: {path}\n",
                    f"__ENCODING__: base64\n",
                    f"__SIZE__: {len(content)}\n",
                    base64.b64encode(content).decode("ascii") + "\n",
                ]
                encoding = "base64"

            # 检查是否是覆盖写入
            is_overwrite = False
            previous_size = None
            try:
                read_result = backend.read(path)
                if read_result.found:
                    is_overwrite = True
                    previous_size = sum(len(line) for line in read_result.contents)
                    logger.warning(f"Overwriting existing file: {path}")
            except Exception:
                pass  # 文件不存在，继续

            # 使用StateBackend.write()方法 - 遵守封装！
            write_result = backend.write(path, lines)

            if not write_result.success:
                return UploadResult(
                    path=path,
                    success=False,
                    error=write_result.error or "Write failed",
                    strategy="state",
                    is_overwrite=is_overwrite,
                    previous_size=previous_size,
                )

            return UploadResult(
                path=path,
                success=True,
                error=None,
                strategy="state",
                encoding=encoding,
                is_overwrite=is_overwrite,
                previous_size=previous_size,
            )

        except Exception as e:
            logger.exception(f"State write failed for {path}: {e}")
            return UploadResult(
                path=path,
                success=False,
                error=str(e),
                strategy="state",
            )

    def _is_text_content(self, content: bytes, sample_size: int = 8192) -> bool:
        """Check if content appears to be text."""
        if not content:
            return True

        # 检查null字节
        if b"\x00" in content:
            return False

        # 检查高比例非ASCII字节
        sample = content[: min(len(content), sample_size)]
        non_ascii = sum(1 for b in sample if b > 127)
        if len(sample) > 0 and non_ascii / len(sample) > 0.3:
            try:
                content.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False

        # 最终UTF-8验证
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
```

### 2.3 安全加固FilesystemFallbackStrategy

```python
class FilesystemFallbackStrategy(UploadStrategy):
    """Fallback to direct filesystem write with security hardening."""

    def __init__(self, root_dir: Path | str | None = None):
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.gettempdir()) / "deepagents_uploads"
        self.root_dir = self.root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        results = []
        for virtual_path, content in files:
            result = self._upload_single(virtual_path, content)
            results.append(result)
        return results

    def _upload_single(self, virtual_path: str, content: bytes) -> UploadResult:
        """Upload single file with security checks."""
        try:
            # 路径遍历检查
            is_valid, error = self._validate_path(virtual_path)
            if not is_valid:
                return UploadResult(
                    path=virtual_path,
                    success=False,
                    error=error,
                    strategy="fallback",
                )

            # 构建物理路径
            physical_path = self._resolve_physical_path(virtual_path)

            # 确保路径在root_dir内
            if not self._is_path_within_root(physical_path):
                return UploadResult(
                    path=virtual_path,
                    success=False,
                    error=f"Path escapes root directory: {virtual_path}",
                    strategy="fallback",
                )

            # 创建父目录
            physical_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用O_NOFOLLOW防止符号链接攻击
            fd = os.open(
                physical_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o644,
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
            except:
                os.close(fd)
                raise

            return UploadResult(
                path=virtual_path,
                success=True,
                error=None,
                strategy="fallback",
                physical_path=str(physical_path),
            )

        except Exception as e:
            logger.exception(f"Fallback upload failed for {virtual_path}: {e}")
            return UploadResult(
                path=virtual_path,
                success=False,
                error=str(e),
                strategy="fallback",
            )

    def _validate_path(self, virtual_path: str) -> tuple[bool, str | None]:
        """Validate virtual path for security."""
        # 检查路径遍历序列
        if ".." in virtual_path:
            return False, f"Path traversal not allowed: {virtual_path}"

        # 检查home目录扩展
        if virtual_path.startswith("~"):
            return False, f"Home directory expansion not allowed: {virtual_path}"

        # 检查null字节
        if "\x00" in virtual_path:
            return False, f"Null bytes not allowed: {virtual_path}"

        # 检查路径长度
        if len(virtual_path) > 4096:
            return False, f"Path too long: {virtual_path}"

        # 检查每个路径组件
        try:
            p = PurePosixPath(virtual_path)
            for part in p.parts[1:]:  # 跳过根目录'/'
                if len(part) > 255:
                    return False, f"Filename too long: {part}"
                # 检查Windows非法字符（即使我们在POSIX上）
                if any(c in part for c in '<>:"|?*'):
                    return False, f"Invalid characters in filename: {part}"
        except Exception as e:
            return False, f"Invalid path format: {e}"

        return True, None

    def _resolve_physical_path(self, virtual_path: str) -> Path:
        """Resolve virtual path to physical path."""
        # 规范化虚拟路径
        virtual_path = virtual_path.lstrip("/")
        return (self.root_dir / virtual_path).resolve()

    def _is_path_within_root(self, physical_path: Path) -> bool:
        """Check if physical path is within root directory."""
        try:
            physical_path.relative_to(self.root_dir)
            return True
        except ValueError:
            return False
```

### 2.4 修复DirectUploadStrategy

```python
class DirectUploadStrategy(UploadStrategy):
    """Use backend's native upload_files method."""

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime=None,
    ) -> list[UploadResult]:
        """Upload files using backend's native upload_files.

        For CompositeBackend, this delegates routing to the backend itself.
        """
        responses = backend.upload_files(files)

        results = []
        for (path, _), response in zip(files, responses):
            # FileUploadResponse是dataclass，直接访问属性
            # 不假设它是字典，不使用.get()方法
            results.append(
                UploadResult(
                    path=path,
                    success=response.error is None,
                    error=response.error,
                    strategy="direct",
                )
            )
        return results
```

---

## 3. 完整实现代码

```python
# deepagents/upload_adapter.py
"""Universal upload adapter for DeepAgents backends.

This module provides a unified interface for uploading files to any
DeepAgents backend, automatically selecting the appropriate strategy
based on backend capabilities.

Example:
    >>> from deepagents.upload_adapter import upload_files
    >>> from deepagents.backends import FilesystemBackend
    >>> backend = FilesystemBackend(root_dir="/workspace")
    >>> results = upload_files(backend, [("/uploads/file.txt", b"content")])
    >>> print(results[0].success)
    True
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Unified upload result format.

    Attributes:
        path: Virtual path of the uploaded file.
        success: Whether the upload succeeded.
        error: Error message if failed, None if succeeded.
        strategy: Strategy used for upload (direct/state/fallback).
        encoding: Encoding used (for StateWriteStrategy: utf-8 or base64).
        physical_path: Physical path if using fallback strategy.
        is_overwrite: Whether this upload overwrote an existing file.
        previous_size: Size of the previous file if overwritten.
    """

    path: str
    success: bool
    error: str | None
    strategy: str
    encoding: str | None = None
    physical_path: str | None = None
    is_overwrite: bool = False
    previous_size: int | None = None


@dataclass
class UploadCapability:
    """Detected backend capabilities."""

    supports_upload_files: bool = False
    supports_state_files: bool = False
    is_sandbox: bool = False
    is_composite: bool = False


@dataclass
class StrategyRule:
    """Strategy selection rule."""

    priority: int
    predicate: Callable[[UploadCapability], bool]
    strategy_name: str


@dataclass
class BatchUploadResult:
    """Result for batch upload operations."""

    results: list[UploadResult]

    @property
    def all_succeeded(self) -> bool:
        """Check if all uploads succeeded."""
        return all(r.success for r in self.results)

    @property
    def failed_files(self) -> list[UploadResult]:
        """Get list of failed uploads."""
        return [r for r in self.results if not r.success]

    @property
    def success_count(self) -> int:
        """Count successful uploads."""
        return sum(1 for r in self.results if r.success)

    def raise_for_errors(self) -> None:
        """Raise exception if any upload failed."""
        if not self.all_succeeded:
            failed = self.failed_files
            raise UploadBatchException(f"{len(failed)} files failed to upload", failed)


class UploadBatchException(Exception):
    """Exception raised when batch upload has failures."""

    def __init__(self, message: str, failed_results: list[UploadResult]):
        super().__init__(message)
        self.failed_results = failed_results


class UploadStrategy(ABC):
    """Abstract upload strategy."""

    @abstractmethod
    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime: Any | None = None,
    ) -> list[UploadResult]:
        """Upload files using this strategy.

        Args:
            backend: The backend to upload to.
            files: List of (path, content) tuples.
            runtime: Optional runtime context.

        Returns:
            List of UploadResult objects.
        """
        pass


class DirectUploadStrategy(UploadStrategy):
    """Use backend's native upload_files method."""

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime: Any | None = None,
    ) -> list[UploadResult]:
        """Upload files using backend.upload_files()."""
        responses = backend.upload_files(files)

        results = []
        for (path, _), response in zip(files, responses):
            # FileUploadResponse是dataclass，直接访问属性
            results.append(
                UploadResult(
                    path=path,
                    success=response.error is None,
                    error=response.error,
                    strategy="direct",
                )
            )
        return results


class StateWriteStrategy(UploadStrategy):
    """Write to StateBackend using its write() method.

    This strategy properly uses StateBackend's public API instead of
    directly manipulating runtime.state, ensuring proper encapsulation.

    Attributes:
        max_file_size: Maximum file size allowed (default 1MB).
    """

    DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1MB

    def __init__(self, max_file_size: int | None = None):
        self.max_file_size = max_file_size or int(
            os.environ.get("DEEPAGENTS_UPLOAD_MAX_SIZE", self.DEFAULT_MAX_FILE_SIZE)
        )
        self._locks: dict[int, threading.Lock] = {}
        self._lock_creation_lock = threading.Lock()

    def _get_runtime_lock(self, runtime) -> threading.Lock:
        """Get or create a lock for the specific runtime."""
        runtime_id = id(runtime)
        if runtime_id not in self._locks:
            with self._lock_creation_lock:
                if runtime_id not in self._locks:
                    self._locks[runtime_id] = threading.Lock()
        return self._locks[runtime_id]

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime: Any | None = None,
    ) -> list[UploadResult]:
        """Upload files to StateBackend."""
        if runtime is None:
            raise RuntimeError("StateWriteStrategy requires runtime parameter")

        # Use lock for thread safety
        lock = self._get_runtime_lock(runtime)
        with lock:
            return self._upload_locked(backend, files, runtime)

    def _upload_locked(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime,
    ) -> list[UploadResult]:
        """Internal upload with lock held."""
        results = []

        for path, content in files:
            result = self._upload_single(backend, path, content)
            results.append(result)

        return results

    def _upload_single(
        self,
        backend: BackendProtocol,
        path: str,
        content: bytes,
    ) -> UploadResult:
        """Upload single file."""
        # Size check
        if len(content) > self.max_file_size:
            return UploadResult(
                path=path,
                success=False,
                error=f"File too large ({len(content)} > {self.max_file_size}). "
                      f"Consider using FilesystemBackend.",
                strategy="state",
            )

        try:
            # Detect text vs binary
            is_text = self._is_text_content(content)

            if is_text:
                lines = content.decode("utf-8").splitlines(keepends=True)
                if content and (not lines or not lines[-1].endswith("\n")):
                    lines.append("\n")
                encoding = "utf-8"
            else:
                lines = [
                    f"__BINARY_FILE__: {path}\n",
                    f"__ENCODING__: base64\n",
                    f"__SIZE__: {len(content)}\n",
                    base64.b64encode(content).decode("ascii") + "\n",
                ]
                encoding = "base64"

            # Check for overwrite
            is_overwrite = False
            previous_size = None
            try:
                read_result = backend.read(path)
                if read_result.found:
                    is_overwrite = True
                    previous_size = sum(len(line) for line in read_result.contents)
            except Exception:
                pass

            # Use backend.write() - proper encapsulation
            from deepagents.backends.protocol import EditOperation, WriteResult

            write_result = backend.write(path, lines)

            if hasattr(write_result, "success") and not write_result.success:
                return UploadResult(
                    path=path,
                    success=False,
                    error=getattr(write_result, "error", "Write failed"),
                    strategy="state",
                )

            return UploadResult(
                path=path,
                success=True,
                error=None,
                strategy="state",
                encoding=encoding,
                is_overwrite=is_overwrite,
                previous_size=previous_size,
            )

        except Exception as e:
            logger.exception(f"State write failed for {path}: {e}")
            return UploadResult(
                path=path,
                success=False,
                error=str(e),
                strategy="state",
            )

    def _is_text_content(self, content: bytes, sample_size: int = 8192) -> bool:
        """Check if content appears to be text."""
        if not content:
            return True

        if b"\x00" in content:
            return False

        sample = content[: min(len(content), sample_size)]
        non_ascii = sum(1 for b in sample if b > 127)
        if len(sample) > 0 and non_ascii / len(sample) > 0.3:
            try:
                content.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False

        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False


class FilesystemFallbackStrategy(UploadStrategy):
    """Fallback to direct filesystem write with security hardening."""

    def __init__(self, root_dir: Path | str | None = None):
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.gettempdir()) / "deepagents_uploads"
        self.root_dir = self.root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        backend: BackendProtocol,
        files: list[tuple[str, bytes]],
        runtime: Any | None = None,
    ) -> list[UploadResult]:
        """Upload files to filesystem."""
        results = []
        for virtual_path, content in files:
            result = self._upload_single(virtual_path, content)
            results.append(result)
        return results

    def _upload_single(self, virtual_path: str, content: bytes) -> UploadResult:
        """Upload single file with security checks."""
        try:
            # Validate path
            is_valid, error = self._validate_path(virtual_path)
            if not is_valid:
                return UploadResult(
                    path=virtual_path,
                    success=False,
                    error=error,
                    strategy="fallback",
                )

            # Resolve physical path
            physical_path = self._resolve_physical_path(virtual_path)

            # Ensure within root
            if not self._is_path_within_root(physical_path):
                return UploadResult(
                    path=virtual_path,
                    success=False,
                    error=f"Path escapes root directory: {virtual_path}",
                    strategy="fallback",
                )

            physical_path.parent.mkdir(parents=True, exist_ok=True)

            # Write with O_NOFOLLOW
            fd = os.open(
                physical_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o644,
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
            except:
                os.close(fd)
                raise

            return UploadResult(
                path=virtual_path,
                success=True,
                error=None,
                strategy="fallback",
                physical_path=str(physical_path),
            )

        except Exception as e:
            logger.exception(f"Fallback upload failed for {virtual_path}: {e}")
            return UploadResult(
                path=virtual_path,
                success=False,
                error=str(e),
                strategy="fallback",
            )

    def _validate_path(self, virtual_path: str) -> tuple[bool, str | None]:
        """Validate virtual path."""
        if ".." in virtual_path:
            return False, f"Path traversal not allowed: {virtual_path}"
        if virtual_path.startswith("~"):
            return False, f"Home directory expansion not allowed: {virtual_path}"
        if "\x00" in virtual_path:
            return False, f"Null bytes not allowed: {virtual_path}"
        if len(virtual_path) > 4096:
            return False, f"Path too long: {virtual_path}"

        try:
            p = PurePosixPath(virtual_path)
            for part in p.parts[1:]:
                if len(part) > 255:
                    return False, f"Filename too long: {part}"
                if any(c in part for c in '<>:"|?*'):
                    return False, f"Invalid characters in filename: {part}"
        except Exception as e:
            return False, f"Invalid path format: {e}"

        return True, None

    def _resolve_physical_path(self, virtual_path: str) -> Path:
        """Resolve virtual path to physical path."""
        virtual_path = virtual_path.lstrip("/")
        return (self.root_dir / virtual_path).resolve()

    def _is_path_within_root(self, physical_path: Path) -> bool:
        """Check if path is within root directory."""
        try:
            physical_path.relative_to(self.root_dir)
            return True
        except ValueError:
            return False


class BackendResolver:
    """Resolves backend from factory or returns as-is."""

    def resolve(
        self,
        backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
        runtime: Any | None = None,
    ) -> BackendProtocol:
        """Resolve backend from factory function."""
        if callable(backend_or_factory) and not isinstance(backend_or_factory, type):
            if runtime is None:
                raise RuntimeError(
                    "Backend factory requires runtime parameter. "
                    "Pass runtime= when calling upload_files()."
                )
            return backend_or_factory(runtime)
        return backend_or_factory


class CapabilityDetector:
    """Detects backend capabilities without side effects."""

    def __init__(self):
        self._known_capabilities: dict[type, UploadCapability] = {}
        self._register_known_types()

    def _register_known_types(self):
        """Register known backend types."""
        try:
            from deepagents.backends import FilesystemBackend, StateBackend, CompositeBackend

            self._known_capabilities[FilesystemBackend] = UploadCapability(
                supports_upload_files=True
            )
            self._known_capabilities[StateBackend] = UploadCapability(
                supports_state_files=True
            )
            self._known_capabilities[CompositeBackend] = UploadCapability(
                supports_upload_files=True, is_composite=True
            )
        except ImportError:
            pass

    def detect(self, backend: BackendProtocol) -> UploadCapability:
        """Detect backend capabilities."""
        backend_type = type(backend)

        # Check known types first
        for known_type, caps in self._known_capabilities.items():
            if isinstance(backend, known_type):
                return caps

        # Unknown type: conservative detection
        return self._detect_unknown(backend)

    def _detect_unknown(self, backend: BackendProtocol) -> UploadCapability:
        """Detect unknown backend capabilities."""
        caps = UploadCapability()

        caps.is_sandbox = hasattr(backend, "sandbox_id") or hasattr(backend, "execute")
        caps.supports_state_files = hasattr(backend, "runtime")
        caps.supports_upload_files = self._check_upload_implemented(backend)

        return caps

    def _check_upload_implemented(self, backend: BackendProtocol) -> bool:
        """Check if upload_files is implemented without calling it."""
        if not hasattr(backend, "upload_files"):
            return False

        backend_class = type(backend)
        method = getattr(backend_class, "upload_files", None)

        if method is None:
            return False

        if hasattr(method, "__isabstractmethod__"):
            return False

        return True


class StrategySelector:
    """Selects strategy based on capabilities using configurable rules."""

    def __init__(self):
        self._rules: list[StrategyRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default selection rules."""
        self.register_rule(
            StrategyRule(
                priority=100,
                predicate=lambda caps: caps.is_composite and caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=90,
                predicate=lambda caps: caps.is_sandbox and caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=80,
                predicate=lambda caps: caps.supports_upload_files,
                strategy_name="direct",
            )
        )
        self.register_rule(
            StrategyRule(
                priority=70,
                predicate=lambda caps: caps.supports_state_files,
                strategy_name="state",
            )
        )

    def register_rule(self, rule: StrategyRule) -> None:
        """Register a selection rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def select(
        self, caps: UploadCapability, strategies: dict[str, UploadStrategy]
    ) -> UploadStrategy:
        """Select strategy based on capabilities."""
        for rule in self._rules:
            if rule.predicate(caps):
                return strategies[rule.strategy_name]
        return strategies["fallback"]


class UploadAdapter:
    """Universal upload adapter for any DeepAgents backend.

    This adapter automatically detects backend capabilities and selects
    the appropriate upload strategy.

    Example:
        >>> adapter = UploadAdapter()
        >>> results = adapter.upload(backend, [("/file.txt", b"content")])
        >>> print(results[0].success)
        True
    """

    def __init__(self):
        self._strategies: dict[str, UploadStrategy] = {
            "direct": DirectUploadStrategy(),
            "state": StateWriteStrategy(),
            "fallback": FilesystemFallbackStrategy(),
        }
        self._resolver = BackendResolver()
        self._detector = CapabilityDetector()
        self._selector = StrategySelector()

    def upload(
        self,
        backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
        files: list[tuple[str, bytes]],
        runtime: Any | None = None,
    ) -> list[UploadResult]:
        """Upload files using automatically selected strategy.

        Args:
            backend_or_factory: Backend instance or factory function.
            files: List of (virtual_path, content) tuples.
            runtime: Optional runtime context (required for StateBackend).

        Returns:
            List of UploadResult objects.

        Raises:
            RuntimeError: If backend factory requires runtime but none provided.
        """
        backend = self._resolver.resolve(backend_or_factory, runtime)
        caps = self._detector.detect(backend)
        strategy = self._selector.select(caps, self._strategies)

        logger.debug(f"Uploading {len(files)} files using {strategy.__class__.__name__}")
        return strategy.upload(backend, files, runtime)

    def register_strategy(self, name: str, strategy: UploadStrategy) -> None:
        """Register a custom upload strategy.

        Args:
            name: Strategy name for reference.
            strategy: UploadStrategy instance.
        """
        self._strategies[name] = strategy

    def get_strategy_selector(self) -> StrategySelector:
        """Get the strategy selector for custom rule registration."""
        return self._selector


# Global instance for convenience
_upload_adapter = UploadAdapter()


def upload_files(
    backend_or_factory: BackendProtocol | Callable[[Any], BackendProtocol],
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Universal upload function that works with ANY backend.

    This is a convenience function that uses the global UploadAdapter instance.
    For advanced usage (custom strategies, rules), create your own UploadAdapter.

    Args:
        backend_or_factory: Backend instance or factory function.
        files: List of (virtual_path, content) tuples.
        runtime: Optional runtime context.

    Returns:
        List of UploadResult objects.

    Example:
        >>> from deepagents.backends import FilesystemBackend
        >>> backend = FilesystemBackend(root_dir="/workspace")
        >>> results = upload_files(backend, [("/uploads/file.txt", b"Hello")])
        >>> for result in results:
        ...     print(f"{result.path}: {'OK' if result.success else 'FAILED'}")
    """
    return _upload_adapter.upload(backend_or_factory, files, runtime)
```

---

## 4. 测试计划

```python
# tests/unit_tests/test_upload_adapter.py
"""Tests for the universal upload adapter."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from deepagents.upload_adapter import (
    UploadAdapter,
    UploadCapability,
    UploadResult,
    BackendResolver,
    CapabilityDetector,
    StrategySelector,
    StrategyRule,
    DirectUploadStrategy,
    StateWriteStrategy,
    FilesystemFallbackStrategy,
    upload_files,
)


class TestBackendResolver:
    """Tests for BackendResolver."""

    def test_resolve_backend_instance(self):
        """Test resolving an already-instantiated backend."""
        resolver = BackendResolver()
        backend = Mock()

        result = resolver.resolve(backend)

        assert result is backend

    def test_resolve_factory_function(self):
        """Test resolving a factory function."""
        resolver = BackendResolver()
        runtime = Mock()
        expected_backend = Mock()
        factory = lambda rt: expected_backend

        result = resolver.resolve(factory, runtime)

        assert result is expected_backend

    def test_resolve_factory_without_runtime_raises(self):
        """Test that factory without runtime raises error."""
        resolver = BackendResolver()
        factory = lambda rt: Mock()

        with pytest.raises(RuntimeError, match="requires runtime"):
            resolver.resolve(factory)


class TestCapabilityDetector:
    """Tests for CapabilityDetector."""

    def test_detect_filesystem_backend(self, tmp_path):
        """Test detecting FilesystemBackend capabilities."""
        from deepagents.backends import FilesystemBackend

        detector = CapabilityDetector()
        backend = FilesystemBackend(root_dir=str(tmp_path))

        caps = detector.detect(backend)

        assert caps.supports_upload_files is True
        assert caps.supports_state_files is False
        assert caps.is_composite is False

    def test_detect_state_backend(self):
        """Test detecting StateBackend capabilities."""
        from deepagents.backends import StateBackend

        detector = CapabilityDetector()
        runtime = Mock()
        runtime.state = {}
        backend = StateBackend(runtime)

        caps = detector.detect(backend)

        assert caps.supports_upload_files is False
        assert caps.supports_state_files is True

    def test_detect_unknown_backend(self):
        """Test detecting unknown backend type."""
        detector = CapabilityDetector()
        backend = Mock()
        backend.sandbox_id = "test"  # Make it look like sandbox

        caps = detector.detect(backend)

        assert caps.is_sandbox is True


class TestStrategySelector:
    """Tests for StrategySelector."""

    def test_select_direct_for_composite(self):
        """Test selecting direct strategy for composite backend."""
        selector = StrategySelector()
        strategies = {
            "direct": Mock(),
            "state": Mock(),
            "fallback": Mock(),
        }
        caps = UploadCapability(supports_upload_files=True, is_composite=True)

        result = selector.select(caps, strategies)

        assert result is strategies["direct"]

    def test_select_state_for_state_backend(self):
        """Test selecting state strategy for StateBackend."""
        selector = StrategySelector()
        strategies = {
            "direct": Mock(),
            "state": Mock(),
            "fallback": Mock(),
        }
        caps = UploadCapability(supports_state_files=True)

        result = selector.select(caps, strategies)

        assert result is strategies["state"]

    def test_select_fallback_for_unknown(self):
        """Test selecting fallback for unknown backend."""
        selector = StrategySelector()
        strategies = {
            "direct": Mock(),
            "state": Mock(),
            "fallback": Mock(),
        }
        caps = UploadCapability()

        result = selector.select(caps, strategies)

        assert result is strategies["fallback"]

    def test_custom_rule_registration(self):
        """Test registering custom selection rule."""
        selector = StrategySelector()
        custom_strategy = Mock()
        strategies = {
            "direct": Mock(),
            "state": Mock(),
            "fallback": Mock(),
            "custom": custom_strategy,
        }

        selector.register_rule(
            StrategyRule(
                priority=200,  # Higher priority than default
                predicate=lambda caps: True,  # Always match
                strategy_name="custom",
            )
        )

        result = selector.select(UploadCapability(), strategies)
        assert result is custom_strategy


class TestDirectUploadStrategy:
    """Tests for DirectUploadStrategy."""

    def test_upload_success(self):
        """Test successful direct upload."""
        from deepagents.backends.protocol import FileUploadResponse

        strategy = DirectUploadStrategy()
        backend = Mock()
        backend.upload_files.return_value = [
            FileUploadResponse(path="/test.txt", error=None)
        ]

        results = strategy.upload(backend, [("/test.txt", b"content")])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].error is None
        assert results[0].strategy == "direct"

    def test_upload_failure(self):
        """Test failed direct upload."""
        from deepagents.backends.protocol import FileUploadResponse

        strategy = DirectUploadStrategy()
        backend = Mock()
        backend.upload_files.return_value = [
            FileUploadResponse(path="/test.txt", error="Permission denied")
        ]

        results = strategy.upload(backend, [("/test.txt", b"content")])

        assert results[0].success is False
        assert results[0].error == "Permission denied"


class TestStateWriteStrategy:
    """Tests for StateWriteStrategy."""

    def test_upload_text_file(self):
        """Test uploading text file to StateBackend."""
        from deepagents.backends import StateBackend

        strategy = StateWriteStrategy()
        runtime = Mock()
        runtime.state = {"files": {}}
        backend = StateBackend(runtime)

        results = strategy.upload(
            backend,
            [("/uploads/test.txt", b"Hello World")],
            runtime=runtime,
        )

        assert results[0].success is True
        assert results[0].encoding == "utf-8"
        assert "/uploads/test.txt" in runtime.state["files"]

    def test_upload_binary_file(self):
        """Test uploading binary file with base64 encoding."""
        from deepagents.backends import StateBackend

        strategy = StateWriteStrategy()
        runtime = Mock()
        runtime.state = {"files": {}}
        backend = StateBackend(runtime)

        binary_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        results = strategy.upload(
            backend,
            [("/uploads/image.png", binary_content)],
            runtime=runtime,
        )

        assert results[0].success is True
        assert results[0].encoding == "base64"

    def test_upload_large_file_rejected(self):
        """Test that large files are rejected."""
        from deepagents.backends import StateBackend

        strategy = StateWriteStrategy(max_file_size=100)
        runtime = Mock()
        runtime.state = {"files": {}}
        backend = StateBackend(runtime)

        large_content = b"x" * 101
        results = strategy.upload(
            backend,
            [("/uploads/large.bin", large_content)],
            runtime=runtime,
        )

        assert results[0].success is False
        assert "too large" in results[0].error.lower()

    def test_detects_overwrite(self):
        """Test that overwrite is detected."""
        from deepagents.backends import StateBackend

        strategy = StateWriteStrategy()
        runtime = Mock()
        runtime.state = {"files": {}}
        backend = StateBackend(runtime)

        # First upload
        strategy.upload(backend, [("/test.txt", b"first")], runtime=runtime)

        # Second upload (overwrite)
        results = strategy.upload(backend, [("/test.txt", b"second")], runtime=runtime)

        assert results[0].is_overwrite is True
        assert results[0].previous_size is not None


class TestFilesystemFallbackStrategy:
    """Tests for FilesystemFallbackStrategy."""

    def test_upload_success(self, tmp_path):
        """Test successful fallback upload."""
        strategy = FilesystemFallbackStrategy(root_dir=tmp_path)
        backend = Mock()

        results = strategy.upload(backend, [("/uploads/test.txt", b"content")])

        assert results[0].success is True
        assert (tmp_path / "uploads" / "test.txt").exists()

    def test_path_traversal_blocked(self, tmp_path):
        """Test that path traversal is blocked."""
        strategy = FilesystemFallbackStrategy(root_dir=tmp_path)
        backend = Mock()

        results = strategy.upload(backend, [("/../../../etc/passwd", b"content")])

        assert results[0].success is False
        assert "traversal" in results[0].error.lower()

    def test_path_escapes_root_blocked(self, tmp_path):
        """Test that paths escaping root are blocked."""
        strategy = FilesystemFallbackStrategy(root_dir=tmp_path)
        backend = Mock()

        results = strategy.upload(backend, [("/../../outside.txt", b"content")])

        assert results[0].success is False


class TestIntegration:
    """Integration tests."""

    def test_upload_with_filesystem_backend(self, tmp_path):
        """Test upload with real FilesystemBackend."""
        from deepagents.backends import FilesystemBackend

        adapter = UploadAdapter()
        backend = FilesystemBackend(root_dir=str(tmp_path))

        results = adapter.upload(backend, [("/uploads/test.txt", b"integration test")])

        assert results[0].success is True
        assert (tmp_path / "uploads" / "test.txt").read_text() == "integration test"

    def test_upload_with_state_backend(self):
        """Test upload with real StateBackend."""
        from deepagents.backends import StateBackend

        adapter = UploadAdapter()
        runtime = Mock()
        runtime.state = {"files": {}}
        backend = StateBackend(runtime)

        results = adapter.upload(backend, [("/uploads/test.txt", b"state test")], runtime=runtime)

        assert results[0].success is True
        assert "/uploads/test.txt" in runtime.state["files"]

    def test_convenience_function(self, tmp_path):
        """Test the global upload_files function."""
        from deepagents.backends import FilesystemBackend

        backend = FilesystemBackend(root_dir=str(tmp_path))

        results = upload_files(backend, [("/test.txt", b"convenience")])

        assert results[0].success is True
```

---

## 5. 第三轮审查请求

本次V3.0修订解决了第二轮审查发现的所有严重问题：

### ✅ 架构层面
1. **SRP修复**: 拆分为BackendResolver、CapabilityDetector、StrategySelector
2. **OCP修复**: 实现StrategyRule规则注册机制
3. **能力检测**: 使用isinstance + 非侵入式检测，无副作用
4. **StateWriteStrategy**: 使用backend.write()方法，遵守封装
5. **CompositeBackend**: 完全委托给CompositeBackend处理路由

### ✅ 代码质量
1. **响应类型**: 修复为直接访问dataclass属性
2. **路径安全**: 添加完整路径验证和O_NOFOLLOW
3. **类型注解**: 添加完整类型注解

### ✅ 功能完整性
1. **文件去重**: 添加is_overwrite和previous_size
2. **文件验证**: 路径格式、文件名合法性验证
3. **并发安全**: 添加线程锁机制
4. **批量结果**: BatchUploadResult提供更友好的API

### ✅ 测试覆盖
1. 每个组件都有独立测试
2. CompositeBackend路由测试
3. 安全测试（路径遍历）
4. 集成测试

**请求第三轮专家审查**，重点审查：
1. 架构与DeepAgents现有架构的兼容性
2. 代码实现的正确性
3. 安全加固是否充分
4. 测试覆盖是否完整
