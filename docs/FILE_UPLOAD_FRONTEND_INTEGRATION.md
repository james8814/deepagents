# 前端聊天界面文件上传集成方案

## 概述

本文档描述如何在带有前端 UI 的聊天界面中实现文件上传功能，使用户能够在消息输入框选择文件，并与文本消息一起提交给 Deep Agents 处理。

## 架构设计

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   前端 UI       │────▶│   后端 API      │────▶│   Deep Agents   │
│  (React/Vue)    │     │  (FastAPI/Flask)│     │   (Upload V5)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
       │                        │                        │
       │ 1. 选择文件            │ 2. 上传文件            │ 3. 存储到后端
       │ 3. 发送消息+路径       │ 4. 调用 agent          │ 5. LLM 读取文件
```

## 数据流

```
用户选择文件 → 前端上传 → 后端存储 → 返回文件路径 → 用户输入消息
                                                    ↓
LLM 分析文件 ← Agent 调用工具 ← 用户点击发送(路径+消息) ← 合并提交
```

---

## 1. 前端实现

### 1.1 组件结构

```typescript
// components/ChatInput.tsx
import React, { useState, useRef } from 'react';

interface FileUpload {
  id: string;
  file: File;
  name: string;
  status: 'uploading' | 'success' | 'error';
  path?: string;  // 上传成功后返回的路径
  error?: string;
}

interface ChatInputProps {
  onSend: (message: string, filePaths: string[]) => void;
  uploadUrl: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, uploadUrl }) => {
  const [message, setMessage] = useState('');
  const [uploads, setUploads] = useState<FileUpload[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 选择文件
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);

    for (const file of files) {
      const upload: FileUpload = {
        id: generateId(),
        file,
        name: file.name,
        status: 'uploading',
      };
      setUploads(prev => [...prev, upload]);

      try {
        // 上传文件到后端
        const path = await uploadFile(file, uploadUrl);
        setUploads(prev =>
          prev.map(u => u.id === upload.id ? { ...u, status: 'success', path } : u)
        );
      } catch (error) {
        setUploads(prev =>
          prev.map(u => u.id === upload.id ? { ...u, status: 'error', error: String(error) } : u)
        );
      }
    }
  };

  // 发送消息
  const handleSend = () => {
    if (!message.trim() && uploads.length === 0) return;

    const successfulPaths = uploads
      .filter(u => u.status === 'success' && u.path)
      .map(u => u.path!);

    onSend(message, successfulPaths);

    // 清空状态
    setMessage('');
    setUploads([]);
  };

  return (
    <div className="chat-input-container">
      {/* 已上传文件列表 */}
      {uploads.length > 0 && (
        <div className="uploaded-files">
          {uploads.map(upload => (
            <FileBadge key={upload.id} upload={upload} />
          ))}
        </div>
      )}

      {/* 输入框 */}
      <div className="input-row">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          multiple
          style={{ display: 'none' }}
        />
        <button onClick={() => fileInputRef.current?.click()}>
          📎 附件
        </button>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="输入消息..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <button onClick={handleSend} disabled={uploads.some(u => u.status === 'uploading')}>
          发送
        </button>
      </div>
    </div>
  );
};

// 文件上传函数
async function uploadFile(file: File, uploadUrl: string): Promise<string> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(uploadUrl, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.path;  // 返回如 "/uploads/document.pdf"
}

// 文件徽章组件
const FileBadge: React.FC<{ upload: FileUpload }> = ({ upload }) => (
  <div className={`file-badge ${upload.status}`}>
    <span className="file-name">{upload.name}</span>
    {upload.status === 'uploading' && <span className="spinner">⏳</span>}
    {upload.status === 'success' && <span>✓</span>}
    {upload.status === 'error' && <span title={upload.error}>✗</span>}
  </div>
);
```

### 1.2 样式参考

```css
/* styles/chat-input.css */
.chat-input-container {
  border-top: 1px solid #e0e0e0;
  padding: 12px;
  background: #fff;
}

.uploaded-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.file-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 16px;
  background: #f0f0f0;
  font-size: 14px;
}

.file-badge.success { background: #e8f5e9; }
.file-badge.error { background: #ffebee; }
.file-badge.uploading { background: #fff3e0; }

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-row textarea {
  flex: 1;
  min-height: 40px;
  max-height: 120px;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: vertical;
}
```

---

## 2. 后端 API 实现

### 2.1 FastAPI 示例

```python
# backend/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import uuid

from deepagents import create_deep_agent, upload_files
from deepagents.backends import FilesystemBackend

app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化后端和 agent
UPLOAD_DIR = "/workspace/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

backend = FilesystemBackend(root_dir="/workspace")
agent = create_deep_agent(backend=backend)

# ============ 文件上传接口 ============

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    接收前端上传的文件，存储到上传目录，返回文件路径。

    Returns:
        {
            "success": true,
            "path": "/uploads/document.pdf",
            "filename": "document.pdf",
            "size": 12345
        }
    """
    try:
        # 生成唯一文件名避免冲突
        file_ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 返回虚拟路径（Deep Agents 使用的路径）
        virtual_path = f"/uploads/{unique_name}"

        return {
            "success": True,
            "path": virtual_path,
            "filename": file.filename,
            "size": len(content)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 聊天接口 ============

class ChatRequest(BaseModel):
    message: str
    file_paths: List[str] = []  # 已上传文件的路径列表
    thread_id: str | None = None  # 可选，用于保持会话


class ChatResponse(BaseModel):
    response: str
    thread_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    处理用户消息，包含文件路径引用。

    如果有文件路径，构造提示词告知 LLM 文件位置。
    """
    try:
        # 构造包含文件引用的消息
        user_content = construct_message(request.message, request.file_paths)

        # 调用 Deep Agent
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_content}]},
            config={"configurable": {"thread_id": request.thread_id}} if request.thread_id else {}
        )

        # 提取 LLM 回复
        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        response_text = last_message.content if last_message else "无响应"

        return ChatResponse(
            response=response_text,
            thread_id=request.thread_id or generate_thread_id()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def construct_message(message: str, file_paths: List[str]) -> str:
    """
    构造发送给 LLM 的消息，包含文件引用说明。

    模式选择：
    - 简单模式：直接在消息中列出路径
    - 详细模式：为每个文件类型提供使用建议
    """
    if not file_paths:
        return message

    # 构建文件引用部分
    file_references = []
    for path in file_paths:
        file_type = get_file_type(path)
        hint = get_file_type_hint(file_type)
        file_references.append(f"- {path} ({file_type}){hint}")

    # 组合消息
    full_message = f"""{message}

[已上传文件]
{chr(10).join(file_references)}

请根据需要读取这些文件。"""

    return full_message


def get_file_type(path: str) -> str:
    """根据扩展名判断文件类型"""
    ext = os.path.splitext(path)[1].lower()
    type_map = {
        '.pdf': 'PDF文档',
        '.txt': '文本文件',
        '.py': 'Python代码',
        '.js': 'JavaScript代码',
        '.ts': 'TypeScript代码',
        '.json': 'JSON文件',
        '.md': 'Markdown文档',
        '.png': '图片',
        '.jpg': '图片',
        '.jpeg': '图片',
        '.csv': 'CSV数据',
        '.xlsx': 'Excel表格',
        '.zip': '压缩包',
    }
    return type_map.get(ext, '文件')


def get_file_type_hint(file_type: str) -> str:
    """根据文件类型提供使用提示"""
    hints = {
        'PDF文档': ' - 使用 read_file 提取文本',
        '文本文件': ' - 使用 read_file 直接读取',
        '图片': ' - 使用 execute + tesseract OCR 识别文字',
        '压缩包': ' - 使用 execute + unzip/tar 解压后查看',
        'Excel表格': ' - 使用 execute + pandas 读取数据',
    }
    return hints.get(file_type, '')


def generate_thread_id() -> str:
    """生成会话 ID"""
    return uuid.uuid4().hex


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2.2 使用 Upload Adapter V5 的替代方案

如果希望使用 Deep Agents 原生的上传功能：

```python
# backend/upload_adapter.py
from deepagents import upload_files, UploadResult
from deepagents.backends import FilesystemBackend

backend = FilesystemBackend(root_dir="/workspace")

async def upload_with_adapter(files: list[str]) -> list[UploadResult]:
    """使用 Upload Adapter V5 上传文件"""
    results = upload_files(
        backend=backend,
        files=files,
        destination_prefix="/uploads/",
        max_size_mb=100,
    )
    return results
```

---

## 3. 前端-后端消息格式

### 3.1 上传文件请求

```http
POST /api/upload
Content-Type: multipart/form-data

file: (binary file content)
```

响应：
```json
{
  "success": true,
  "path": "/uploads/a3f5d2e1.pdf",
  "filename": "report.pdf",
  "size": 45678
}
```

### 3.2 聊天请求

```http
POST /api/chat
Content-Type: application/json

{
  "message": "请分析这份报告的关键发现",
  "file_paths": ["/uploads/a3f5d2e1.pdf", "/uploads/data.csv"],
  "thread_id": "optional-thread-id"
}
```

响应：
```json
{
  "response": "根据报告内容，我发现了以下几点...",
  "thread_id": "abc123def456"
}
```

---

## 4. 完整使用示例

### 4.1 场景：用户上传 PDF 并提问

**步骤 1: 用户选择文件**
```
用户点击 "📎 附件" 按钮
选择文件: Q4财务报告.pdf
```

**步骤 2: 前端自动上传**
```typescript
// 显示上传进度
⏳ Q4财务报告.pdf (上传中...)

// 上传完成
✓ Q4财务报告.pdf
```

**步骤 3: 用户输入消息并发送**
```
用户输入: "这份报告的主要收入构成是什么？"
点击发送按钮
```

**步骤 4: 前端构造请求**
```typescript
onSend("这份报告的主要收入构成是什么？", ["/uploads/a3f5d2e1.pdf"])
```

**步骤 5: 后端处理**
```python
# 构造的消息内容
"""这份报告的主要收入构成是什么？

[已上传文件]
- /uploads/a3f5d2e1.pdf (PDF文档) - 使用 read_file 提取文本

请根据需要读取这些文件。"""
```

**步骤 6: Deep Agent 执行**
```
1. LLM 收到消息，发现需要读取 /uploads/a3f5d2e1.pdf
2. 调用 read_file 工具
3. 获取 PDF 内容
4. 分析问题并回答
```

**步骤 7: 返回结果给用户**
```
根据这份 Q4 财务报告，主要收入构成如下：
1. 产品销售收入: 65%
2. 服务收入: 25%
3. 其他收入: 10%
```

---

## 5. 高级功能

### 5.1 多文件上传

```typescript
// 支持一次选择多个文件
<input type="file" multiple onChange={handleFileSelect} />

// 上传多个文件
const files = [
  "/uploads/report.pdf",
  "/uploads/data.csv",
  "/uploads/chart.png"
];
```

### 5.2 文件类型限制

```typescript
// 限制可上传的文件类型
<input
  type="file"
  accept=".pdf,.txt,.csv,.json,.md,.py,.js,.ts,.png,.jpg,.jpeg"
/>
```

### 5.3 拖拽上传

```typescript
const handleDrop = (e: DragEvent) => {
  e.preventDefault();
  const files = Array.from(e.dataTransfer?.files || []);
  handleFileUpload(files);
};

<div
  onDrop={handleDrop}
  onDragOver={(e) => e.preventDefault()}
  className="drop-zone"
>
  拖拽文件到此处上传
</div>
```

### 5.4 图片预览

```typescript
// 图片文件显示预览
{uploads.map(upload => (
  upload.file.type.startsWith('image/') ? (
    <img
      src={URL.createObjectURL(upload.file)}
      alt={upload.name}
      className="image-preview"
    />
  ) : (
    <FileBadge upload={upload} />
  )
))}
```

---

## 6. 安全考虑

### 6.1 文件大小限制

```python
# 后端限制
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过100MB限制")
```

### 6.2 文件类型白名单

```python
ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.csv', '.json', '.md',
    '.py', '.js', '.ts', '.html', '.css',
    '.png', '.jpg', '.jpeg', '.gif',
    '.zip', '.tar', '.gz'
}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")
```

### 6.3 路径安全

```python
# 使用 uuid 重命名文件，避免路径遍历
safe_filename = f"{uuid.uuid4().hex[:8]}{file_ext}"
# 禁止使用用户提供的文件名直接存储
```

---

## 7. 错误处理

### 7.1 前端错误处理

```typescript
const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
  for (const file of files) {
    try {
      const path = await uploadFile(file, uploadUrl);
      // 成功处理
    } catch (error) {
      // 显示错误提示
      toast.error(`上传失败: ${file.name} - ${error.message}`);
    }
  }
};
```

### 7.2 后端错误响应

```python
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # 处理上传
        return {"success": True, "path": path}
    except FileTooLargeError:
        raise HTTPException(status_code=413, detail="文件过大")
    except InvalidFileTypeError:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")
```

---

## 8. 部署配置

### 8.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./uploads:/workspace/uploads
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

### 8.2 环境变量

```bash
# .env
ANTHROPIC_API_KEY=sk-xxx
UPLOAD_DIR=/workspace/uploads
MAX_FILE_SIZE=104857600  # 100MB
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 9. 相关文档

- **Upload Adapter V5 指南**: `./UPLOAD_ADAPTER_GUIDE.md`
- **Deep Agents API 参考**: `./api/API_REFERENCE.md`
- **部署指南**: `./deployment/DEPLOYMENT_GUIDE.md`

---

## 10. 快速开始检查清单

- [ ] 前端实现文件选择组件
- [ ] 前端实现上传进度显示
- [ ] 后端实现 `/api/upload` 接口
- [ ] 后端实现 `/api/chat` 接口
- [ ] 配置 CORS 允许前端访问
- [ ] 设置文件大小限制
- [ ] 配置允许的文件类型
- [ ] 测试单文件上传流程
- [ ] 测试多文件上传流程
- [ ] 测试错误处理
- [ ] 配置生产环境存储卷
