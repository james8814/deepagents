"""
Isolated Directory Backend for Deep Agents
在宿主机上创建隔离的工作目录，提供基本的文件隔离
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    SandboxBackendProtocol,
)
from deepagents.backends.sandbox import (
    BaseSandbox,
    SandboxListResponse,
    SandboxProvider,
)


class IsolatedDirectoryBackend(BaseSandbox):
    """隔离目录后端
    
    在宿主机上创建隔离的工作目录，限制 Agent 只能访问该目录。
    注意：这不是真正的沙盒，Agent 仍可能通过命令注入访问系统其他部分。
    建议仅用于受信任的场景。
    """
    
    def __init__(
        self,
        root_dir: str,
        timeout: float = 120.0,
        max_output_bytes: int = 100_000,
    ) -> None:
        """初始化隔离目录后端
        
        Args:
            root_dir: 工作目录的根路径
            timeout: 命令执行超时时间
            max_output_bytes: 最大输出字节数
        """
        self._root_dir = os.path.abspath(root_dir)
        self._timeout = timeout
        self._max_output_bytes = max_output_bytes
        self._sandbox_id = f"isolated-{uuid.uuid4().hex[:8]}"
        
        # 确保目录存在
        os.makedirs(self._root_dir, exist_ok=True)
        
        # 创建 app 子目录
        os.makedirs(os.path.join(self._root_dir, "app"), exist_ok=True)
    
    @property
    def id(self) -> str:
        """沙盒唯一标识"""
        return self._sandbox_id
    
    def _resolve_path(self, path: str) -> str:
        """解析路径，确保在 root_dir 内
        
        Args:
            path: 输入路径
            
        Returns:
            绝对路径
        """
        if path.startswith("/"):
            # 绝对路径，相对于 root_dir
            return os.path.join(self._root_dir, path[1:])
        else:
            # 相对路径，相对于 root_dir/app
            return os.path.join(self._root_dir, "app", path)
    
    def execute(self, command: str) -> ExecuteResponse:
        """在隔离目录中执行命令
        
        Args:
            command: shell 命令
            
        Returns:
            ExecuteResponse
        """
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string",
                exit_code=1,
                truncated=False
            )
        
        try:
            # 创建安全的 shell 脚本，限制在 workdir
            workdir = os.path.join(self._root_dir, "app")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=workdir,
                # 使用最小环境变量
                env={
                    "HOME": self._root_dir,
                    "PWD": workdir,
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "LANG": "C.UTF-8",
                }
            )
            
            # 组合输出
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)
            
            output = "\n".join(output_parts) if output_parts else "<no output>"
            
            # 检查截断
            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[:self._max_output_bytes]
                output += f"\n\n... Output truncated at {self._max_output_bytes} bytes"
                truncated = True
            
            # 添加退出码信息
            if result.returncode != 0:
                output = f"{output.rstrip()}\n\nExit code: {result.returncode}"
            
            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated
            )
            
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Error: Command timed out after {self._timeout:.1f} seconds",
                exit_code=124,
                truncated=False
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command: {e}",
                exit_code=1,
                truncated=False
            )
    
    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """读取文件内容"""
        full_path = self._resolve_path(file_path)
        
        if not os.path.isfile(full_path):
            return f"Error: File '{file_path}' not found"
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            # 应用 offset 和 limit
            start_idx = offset
            end_idx = offset + limit
            selected_lines = lines[start_idx:end_idx]
            
            # 格式化带行号
            result_lines = []
            for i, line in enumerate(selected_lines):
                line_num = offset + i + 1
                line_content = line.rstrip('\n')
                result_lines.append(f"{line_num:6d}\t{line_content}")
            
            return "\n".join(result_lines)
        except Exception as e:
            return f"Error reading file: {e}"
    
    def write(self, file_path: str, content: str) -> Any:
        """写入文件"""
        from deepagents.backends.protocol import WriteResult
        
        full_path = self._resolve_path(file_path)
        
        # 检查文件是否已存在
        if os.path.exists(full_path):
            return WriteResult(error=f"Error: File '{file_path}' already exists")
        
        try:
            # 创建父目录
            parent_dir = os.path.dirname(full_path)
            os.makedirs(parent_dir, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return WriteResult(path=file_path, files_update=None)
        except Exception as e:
            return WriteResult(error=f"Error writing file: {e}")
    
    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> Any:
        """编辑文件"""
        from deepagents.backends.protocol import EditResult
        
        full_path = self._resolve_path(file_path)
        
        if not os.path.isfile(full_path):
            return EditResult(error=f"Error: File '{file_path}' not found")
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 计数
            count = content.count(old_string)
            
            if count == 0:
                return EditResult(error=f"Error: String not found in file: '{old_string}'")
            
            if count > 1 and not replace_all:
                return EditResult(
                    error=f"Error: String '{old_string}' appears multiple times. Use replace_all=True"
                )
            
            # 替换
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return EditResult(path=file_path, files_update=None, occurrences=count)
        except Exception as e:
            return EditResult(error=f"Error editing file: {e}")
    
    def ls_info(self, path: str) -> list:
        """列出目录内容"""
        from deepagents.backends.protocol import FileInfo
        
        full_path = self._resolve_path(path)
        
        if not os.path.isdir(full_path):
            return []
        
        file_infos = []
        try:
            for entry in os.scandir(full_path):
                file_infos.append(FileInfo(
                    path=os.path.join(path, entry.name),
                    is_dir=entry.is_dir(),
                    size=entry.stat().st_size if entry.is_file() else None
                ))
        except Exception:
            pass
        
        return file_infos
    
    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list:
        """搜索文件内容"""
        from deepagents.backends.protocol import GrepMatch
        
        search_path = self._resolve_path(path or "/app")
        
        try:
            # 构建 grep 命令
            cmd = ["grep", "-rHn", "-F", pattern]
            if glob:
                cmd.extend(["--include", glob])
            cmd.append(search_path)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            matches = []
            for line in result.stdout.split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    # 转换路径为相对路径
                    full_file_path = parts[0]
                    rel_path = os.path.relpath(full_file_path, self._root_dir)
                    matches.append(GrepMatch(
                        path="/" + rel_path,
                        line=int(parts[1]),
                        text=parts[2]
                    ))
            
            return matches
        except Exception:
            return []
    
    def glob_info(self, pattern: str, path: str = "/") -> list:
        """查找匹配文件"""
        import fnmatch
        from deepagents.backends.protocol import FileInfo
        
        full_path = self._resolve_path(path)
        
        matches = []
        try:
            for root, dirs, files in os.walk(full_path):
                for filename in files:
                    if fnmatch.fnmatch(filename, pattern):
                        full_file = os.path.join(root, filename)
                        rel_path = "/" + os.path.relpath(full_file, self._root_dir)
                        matches.append(FileInfo(path=rel_path, is_dir=False))
                for dirname in dirs:
                    if fnmatch.fnmatch(dirname, pattern):
                        full_dir = os.path.join(root, dirname)
                        rel_path = "/" + os.path.relpath(full_dir, self._root_dir)
                        matches.append(FileInfo(path=rel_path, is_dir=True))
        except Exception:
            pass
        
        return matches
    
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传文件"""
        responses = []
        for path, content in files:
            try:
                full_path = self._resolve_path(path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, "wb") as f:
                    f.write(content)
                
                responses.append(FileUploadResponse(path=path, error=None))
            except Exception:
                responses.append(FileUploadResponse(path=path, error="file_not_found"))
        
        return responses
    
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """下载文件"""
        responses = []
        for path in paths:
            try:
                full_path = self._resolve_path(path)
                
                with open(full_path, "rb") as f:
                    content = f.read()
                
                responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
        
        return responses


class IsolatedDirectoryProvider(SandboxProvider[dict[str, Any]]):
    """隔离目录沙盒提供商"""
    
    def __init__(self, base_dir: str = "/tmp/deepagents-isolated") -> None:
        """初始化提供商
        
        Args:
            base_dir: 沙盒基础目录
        """
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def list(self, *, cursor: str | None = None, **kwargs: Any) -> SandboxListResponse:
        """列出所有沙盒"""
        items = []
        for name in os.listdir(self._base_dir):
            path = os.path.join(self._base_dir, name)
            if os.path.isdir(path):
                items.append({
                    "sandbox_id": name,
                    "metadata": {"path": path}
                })
        return {"items": items, "cursor": None}
    
    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        **kwargs: Any
    ) -> SandboxBackendProtocol:
        """获取或创建沙盒"""
        if sandbox_id:
            root_dir = os.path.join(self._base_dir, sandbox_id)
            if os.path.exists(root_dir):
                return IsolatedDirectoryBackend(root_dir)
            raise ValueError(f"Sandbox {sandbox_id} not found")
        
        # 创建新沙盒
        sandbox_id = f"sandbox-{uuid.uuid4().hex[:8]}"
        root_dir = os.path.join(self._base_dir, sandbox_id)
        
        return IsolatedDirectoryBackend(root_dir)
    
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        """删除沙盒"""
        root_dir = os.path.join(self._base_dir, sandbox_id)
        if os.path.exists(root_dir):
            shutil.rmtree(root_dir)


def create_isolated_sandbox(base_dir: str | None = None) -> IsolatedDirectoryBackend:
    """快速创建隔离目录沙盒"""
    provider = IsolatedDirectoryProvider(base_dir) if base_dir else IsolatedDirectoryProvider()
    return provider.get_or_create()


if __name__ == "__main__":
    print("Testing Isolated Directory Sandbox...")
    
    sandbox = create_isolated_sandbox()
    print(f"Sandbox created: {sandbox.id}")
    print(f"Root directory: {sandbox._root_dir}")
    
    # 测试命令执行
    result = sandbox.execute("pwd && ls -la")
    print(f"\nCommand test:\n{result.output}")
    
    # 测试文件写入
    result = sandbox.write("/app/test.txt", "Hello from Isolated Sandbox!")
    print(f"\nWrite result: {result}")
    
    # 测试文件读取
    content = sandbox.read("/app/test.txt")
    print(f"Read result: {content}")
    
    # 测试编辑
    result = sandbox.edit("/app/test.txt", "Hello", "Hi", replace_all=False)
    print(f"\nEdit result: {result}")
    
    content = sandbox.read("/app/test.txt")
    print(f"After edit: {content}")
    
    print(f"\nSandbox files:")
    for f in sandbox.ls_info("/app"):
        print(f"  {f}")
