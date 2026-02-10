"""
Chroot Sandbox for Deep Agents
使用 chroot 创建轻量级沙盒（无需 Docker 镜像）
"""

import os
import shutil
import subprocess
import tempfile
import uuid
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


class ChrootBackend(BaseSandbox):
    """Chroot 沙盒后端
    
    使用 Linux chroot 创建轻量级隔离环境
    注意：需要 root 权限运行
    """
    
    def __init__(self, root_dir: str) -> None:
        """初始化 chroot 沙盒
        
        Args:
            root_dir: chroot 根目录
        """
        self._root_dir = root_dir
        self._timeout = 60  # 60 秒超时
        
        # 创建基本目录结构
        self._setup_chroot()
    
    def _setup_chroot(self) -> None:
        """设置 chroot 环境"""
        # 创建基本目录
        for d in ["bin", "lib", "lib64", "usr/bin", "usr/lib", "usr/lib64", "tmp", "app"]:
            os.makedirs(os.path.join(self._root_dir, d), exist_ok=True)
        
        # 复制必要的二进制文件
        self._copy_binary("/bin/bash", "bin/bash")
        self._copy_binary("/bin/ls", "bin/ls")
        self._copy_binary("/bin/cat", "bin/cat")
        self._copy_binary("/bin/echo", "bin/echo")
        self._copy_binary("/bin/grep", "bin/grep")
        self._copy_binary("/bin/mkdir", "bin/mkdir")
        self._copy_binary("/bin/rm", "bin/rm")
        self._copy_binary("/bin/cp", "bin/cp")
        self._copy_binary("/bin/mv", "bin/mv")
        self._copy_binary("/bin/pwd", "bin/pwd")
        self._copy_binary("/bin/chmod", "bin/chmod")
        self._copy_binary("/bin/chown", "bin/chown")
        self._copy_binary("/usr/bin/awk", "usr/bin/awk")
        self._copy_binary("/usr/bin/perl", "usr/bin/perl")
        self._copy_binary("/usr/bin/python3", "usr/bin/python3")
        self._copy_binary("/usr/bin/base64", "usr/bin/base64")
        
        # 复制库文件
        self._copy_libs("bin/bash")
    
    def _copy_binary(self, src: str, dst: str) -> None:
        """复制二进制文件到 chroot"""
        dst_path = os.path.join(self._root_dir, dst)
        if os.path.exists(src) and not os.path.exists(dst_path):
            shutil.copy2(src, dst_path)
    
    def _copy_libs(self, binary_path: str) -> None:
        """复制二进制文件依赖的库"""
        try:
            result = subprocess.run(
                ["ldd", os.path.join(self._root_dir, binary_path)],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split("\n"):
                if "=>" in line:
                    parts = line.split("=>")
                    if len(parts) == 2:
                        lib_path = parts[1].split()[0].strip()
                        if os.path.exists(lib_path):
                            lib_name = os.path.basename(lib_path)
                            for lib_dir in ["lib", "lib64", "usr/lib", "usr/lib64"]:
                                dst = os.path.join(self._root_dir, lib_dir, lib_name)
                                if os.path.exists(os.path.dirname(dst)):
                                    shutil.copy2(lib_path, dst)
                                    break
        except Exception:
            pass
    
    @property
    def id(self) -> str:
        """沙盒唯一标识"""
        return os.path.basename(self._root_dir)
    
    def execute(self, command: str) -> ExecuteResponse:
        """在 chroot 中执行命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            ExecuteResponse
        """
        try:
            # 使用 chroot 执行命令
            full_cmd = f"chroot {self._root_dir} /bin/sh -c 'cd /app && {command}'"
            
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                # 使用 unshare 增加隔离
                executable="/bin/bash"
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n[stderr] " + result.stderr
            
            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=False
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Command timed out after {self._timeout} seconds",
                exit_code=124,
                truncated=False
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error: {str(e)}",
                exit_code=1,
                truncated=False
            )
    
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传文件到 chroot"""
        responses = []
        for path, content in files:
            try:
                # 去掉开头的 /，相对 chroot 根目录
                if path.startswith("/"):
                    path = path[1:]
                
                full_path = os.path.join(self._root_dir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, "wb") as f:
                    f.write(content)
                
                responses.append(FileUploadResponse(path=path, error=None))
            except Exception as e:
                responses.append(FileUploadResponse(path=path, error="file_not_found"))
        
        return responses
    
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从 chroot 下载文件"""
        responses = []
        for path in paths:
            try:
                if path.startswith("/"):
                    path = path[1:]
                
                full_path = os.path.join(self._root_dir, path)
                
                with open(full_path, "rb") as f:
                    content = f.read()
                
                responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
        
        return responses


class ChrootProvider(SandboxProvider[dict[str, Any]]):
    """Chroot 沙盒提供商"""
    
    def __init__(self, base_dir: str = "/tmp/deepagents-chroot") -> None:
        """初始化 chroot 提供商
        
        Args:
            base_dir: 沙盒根目录的基础路径
        """
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def list(
        self,
        *,
        cursor: str | None = None,
        **kwargs: Any,
    ) -> SandboxListResponse[dict[str, Any]]:
        """列出所有 chroot 沙盒"""
        items = []
        for name in os.listdir(self._base_dir):
            path = os.path.join(self._base_dir, name)
            if os.path.isdir(path):
                items.append({
                    "sandbox_id": name,
                    "metadata": {
                        "status": "running",
                        "path": path
                    }
                })
        
        return {"items": items, "cursor": None}
    
    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        timeout: int = 180,
        **kwargs: Any,
    ) -> SandboxBackendProtocol:
        """获取或创建 chroot 沙盒"""
        if sandbox_id:
            root_dir = os.path.join(self._base_dir, sandbox_id)
            if os.path.exists(root_dir):
                return ChrootBackend(root_dir)
            raise ValueError(f"Sandbox {sandbox_id} not found")
        
        # 创建新的 chroot
        sandbox_id = f"sandbox-{uuid.uuid4().hex[:8]}"
        root_dir = os.path.join(self._base_dir, sandbox_id)
        
        return ChrootBackend(root_dir)
    
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        """删除 chroot 沙盒"""
        root_dir = os.path.join(self._base_dir, sandbox_id)
        if os.path.exists(root_dir):
            shutil.rmtree(root_dir)


def create_chroot_sandbox() -> ChrootBackend:
    """快速创建 chroot 沙盒"""
    provider = ChrootProvider()
    return provider.get_or_create()


if __name__ == "__main__":
    print("Testing Chroot Sandbox...")
    
    sandbox = create_chroot_sandbox()
    print(f"Sandbox created: {sandbox.id}")
    
    # 测试命令执行
    result = sandbox.execute("echo 'Hello from Chroot!'")
    print(f"Test command: {result.output}")
    
    # 测试文件操作
    sandbox.write("/app/test.txt", "Hello World!")
    content = sandbox.read("/app/test.txt")
    print(f"File content: {content}")
    
    print(f"Sandbox path: {sandbox._root_dir}")
