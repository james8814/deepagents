"""
Docker Sandbox Provider for Deep Agents
直接使用 Docker SDK 管理容器沙盒
"""

import os
import time
import uuid
from typing import Any

import docker
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


class DockerBackend(BaseSandbox):
    """Docker 容器沙盒后端实现
    
    使用 Docker SDK 在本地创建隔离的容器环境
    """
    
    def __init__(
        self,
        container: docker.models.containers.Container,
        client: docker.DockerClient,
        workdir: str = "/app"
    ) -> None:
        """初始化 Docker 沙盒后端
        
        Args:
            container: Docker 容器实例
            client: Docker 客户端
            workdir: 容器内工作目录
        """
        self._container = container
        self._client = client
        self._workdir = workdir
        self._timeout = 30 * 60  # 30 分钟超时
    
    @property
    def id(self) -> str:
        """沙盒唯一标识"""
        return self._container.id[:12]
    
    def execute(self, command: str) -> ExecuteResponse:
        """在容器中执行命令
        
        Args:
            command: 要执行的 shell 命令
            
        Returns:
            ExecuteResponse 包含输出和退出码
        """
        try:
            # 在容器中执行命令
            result = self._container.exec_run(
                cmd=["sh", "-c", command],
                workdir=self._workdir,
                timeout=self._timeout,
                environment={
                    "HOME": "/root",
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                }
            )
            
            # 解码输出
            output = result.output.decode('utf-8', errors='replace') if result.output else ""
            
            return ExecuteResponse(
                output=output,
                exit_code=result.exit_code,
                truncated=False
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=1,
                truncated=False
            )
    
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传文件到容器
        
        Args:
            files: (路径, 内容) 元组列表
            
        Returns:
            FileUploadResponse 列表
        """
        responses = []
        for path, content in files:
            try:
                # 确保目录存在
                dir_path = os.path.dirname(path)
                if dir_path:
                    self.execute(f"mkdir -p {dir_path}")
                
                # 使用 tar 流上传文件
                import tarfile
                import io
                
                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                    file_data = io.BytesIO(content)
                    tarinfo = tarfile.TarInfo(name=os.path.basename(path))
                    tarinfo.size = len(content)
                    tar.addfile(tarinfo, file_data)
                
                tar_stream.seek(0)
                self._container.put_archive(os.path.dirname(path) or self._workdir, tar_stream.read())
                
                responses.append(FileUploadResponse(path=path, error=None))
            except Exception as e:
                responses.append(FileUploadResponse(path=path, error="file_not_found"))
        
        return responses
    
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从容器下载文件
        
        Args:
            paths: 文件路径列表
            
        Returns:
            FileDownloadResponse 列表
        """
        responses = []
        for path in paths:
            try:
                # 从容器获取文件
                bits, stat = self._container.get_archive(path)
                
                # 读取 tar 流
                import tarfile
                import io
                
                file_obj = io.BytesIO(b''.join(bits))
                with tarfile.open(fileobj=file_obj, mode='r:*') as tar:
                    member = tar.getmembers()[0]
                    content = tar.extractfile(member).read()
                
                responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
        
        return responses


class DockerProvider(SandboxProvider[dict[str, Any]]):
    """Docker 沙盒提供商
    
    管理 Docker 容器的生命周期
    """
    
    def __init__(self, image: str = "python:3.11-slim") -> None:
        """初始化 Docker 提供商
        
        Args:
            image: Docker 镜像名称，默认 python:3.11-slim
        """
        self._client = docker.from_env()
        # 使用阿里云镜像加速
        self._image = f"registry.cn-hangzhou.aliyuncs.com/library/{image}"
        
        # 确保镜像存在
        try:
            self._client.images.get(self._image)
        except docker.errors.ImageNotFound:
            print(f"Pulling Docker image: {self._image}...")
            try:
                self._client.images.pull(self._image)
                print(f"Image {self._image} pulled successfully")
            except Exception as e:
                print(f"Warning: Failed to pull image: {e}")
                print(f"Trying original image: {image}")
                self._image = image
                self._client.images.pull(image)
    
    def list(
        self,
        *,
        cursor: str | None = None,
        **kwargs: Any,
    ) -> SandboxListResponse[dict[str, Any]]:
        """列出所有 Deep Agents 相关的容器"""
        containers = self._client.containers.list(
            filters={"label": "deepagents.sandbox=true"},
            all=True
        )
        
        items = []
        for container in containers:
            items.append({
                "sandbox_id": container.id[:12],
                "metadata": {
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else "unknown",
                    "created": container.attrs["Created"],
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
        """获取或创建 Docker 沙盒
        
        Args:
            sandbox_id: 现有容器 ID（可选）
            timeout: 启动超时时间
            
        Returns:
            DockerBackend 实例
        """
        if sandbox_id:
            # 连接到现有容器
            try:
                container = self._client.containers.get(sandbox_id)
                return DockerBackend(container, self._client)
            except docker.errors.NotFound:
                raise ValueError(f"Container {sandbox_id} not found")
        
        # 创建新容器
        container_name = f"deepagents-sandbox-{uuid.uuid4().hex[:8]}"
        
        try:
            container = self._client.containers.run(
                image=self._image,
                name=container_name,
                command="sleep infinity",  # 保持容器运行
                detach=True,
                labels={"deepagents.sandbox": "true"},
                environment={
                    "HOME": "/root",
                    "PYTHONUNBUFFERED": "1"
                },
                working_dir="/app",
                # 安全限制
                cpu_quota=100000,  # 限制 CPU
                mem_limit="512m",  # 限制内存
                network_mode="bridge",
                # 不挂载任何主机目录，完全隔离
            )
            
            # 等待容器就绪
            for _ in range(timeout // 2):
                container.reload()
                if container.status == "running":
                    # 测试执行
                    result = container.exec_run("echo ready", timeout=5)
                    if result.exit_code == 0:
                        break
                time.sleep(2)
            else:
                container.stop()
                container.remove()
                raise RuntimeError(f"Container failed to start within {timeout} seconds")
            
            # 安装常用工具
            container.exec_run(
                "apt-get update && apt-get install -y curl wget git grep findutils",
                timeout=120
            )
            
            return DockerBackend(container, self._client)
            
        except Exception as e:
            raise RuntimeError(f"Failed to create Docker sandbox: {e}")
    
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        """删除 Docker 沙盒
        
        Args:
            sandbox_id: 容器 ID
        """
        try:
            container = self._client.containers.get(sandbox_id)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass  # 容器已不存在


def create_docker_sandbox(image: str = "python:3.11-slim") -> DockerBackend:
    """快速创建 Docker 沙盒的便捷函数
    
    Args:
        image: Docker 镜像
        
    Returns:
        DockerBackend 实例
    """
    provider = DockerProvider(image=image)
    return provider.get_or_create()


# 测试代码
if __name__ == "__main__":
    print("Testing Docker Sandbox...")
    
    # 创建沙盒
    provider = DockerProvider()
    sandbox = provider.get_or_create()
    
    print(f"Sandbox created: {sandbox.id}")
    
    # 测试命令执行
    result = sandbox.execute("python --version")
    print(f"Python version: {result.output}")
    
    # 测试文件写入
    sandbox.write("/app/test.txt", "Hello from Docker Sandbox!")
    
    # 测试文件读取
    content = sandbox.read("/app/test.txt")
    print(f"File content: {content}")
    
    # 清理
    provider.delete(sandbox_id=sandbox.id)
    print(f"Sandbox {sandbox.id} deleted")
