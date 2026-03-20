# DeepAgents 真实 LLM 端到端测试会话记录

**日期**: 2026-03-20
**LLM**: DeepSeek-V3-0324 (deepseek-chat)
**API**: https://api.deepseek.com (OpenAI 兼容接口)
**SDK**: 0.5.0

---

## 场景 1: 基本对话

```
用户: What is 2+2? Reply in one sentence.
Agent: 2+2 equals 4.
消息数: 2
状态: PASS
```

---

## 场景 2: 文件读写 (write_file + read_file)

```
用户: Write a file at /hello.txt with content 'Hello DeepAgents'. Then read it back and tell me what it says.

[0] Human: Write a file at /hello.txt with content 'Hello DeepAgents'...
[1] AI: [tool_calls: ['write_file']]
[2] Tool(write_file): Updated file /hello.txt
[3] AI: [tool_calls: ['read_file']]
[4] Tool(read_file):      1	Hello DeepAgents
[5] AI: The file `/hello.txt` contains: "Hello DeepAgents"

Tool 调用数: 2
文件数: 1
/hello.txt 存在: True
状态: PASS
```

---

## 场景 3: ls + grep (目录浏览和搜索)

```
预置文件: /readme.txt, /config.json, /notes.md
用户: List all files in / directory, then search for the word 'important' across all files.

[0] Human: List all files in / directory, then search for 'important'...
[1] AI: [tool_calls: ['ls']]
[2] Tool(ls): ['/config.json', '/notes.md', '/readme.txt']
[3] AI: [tool_calls: ['grep']]
[4] Tool(grep): /notes.md:
  1: Some important notes here
/readme.txt:
  1: This is an important readme file
[5] AI: **Results:**
**Files in / directory:** 1. /config.json 2. /notes.md 3. /readme.txt
**Files containing 'important':** /notes.md, /readme.txt

ls 被调用: True
grep 被调用: True
状态: PASS
```

---

## 场景 4: edit_file (编辑现有文件)

```
预置文件: /app.py (内容: print('Hello World')\nprint('Hello Again'))
用户: Edit the file /app.py: replace 'Hello' with 'Goodbye'. Show me the result.

[0] Human: Edit the file /app.py: replace 'Hello' with 'Goodbye'...
[1] AI: [tool_calls: ['read_file']]  -- 先读取文件
[2] Tool(read_file):      1	print('Hello World')
     2	print('Hello Again')
[3] AI: [tool_calls: ['edit_file']]  -- 执行替换
     args: {file_path: /app.py, old_string: Hello, new_string: Goodbye, replace_all: True}
[4] Tool(edit_file): Successfully replaced 2 instance(s) of the string in '/app.py'
[5] AI: [tool_calls: ['read_file']]  -- 再次读取确认
[6] Tool(read_file):      1	print('Goodbye World')
     2	print('Goodbye Again')
[7] AI: The file has been successfully edited. Both occurrences of 'Hello' have been replaced with 'Goodbye'

edit_file 被调用: True
状态: PASS
```

---

## 场景 5: 自定义工具

```
自定义工具: calculate(expression) -> 计算数学表达式
用户: Use the calculate tool to compute 123 * 456. Tell me the result.

[0] Human: Use the calculate tool to compute 123 * 456...
[1] AI: [tool_calls: ['calculate']]
[2] Tool(calculate): Result: 56088
[3] AI: 123 × 456 = 56,088

calculate 被调用: True
结果正确 (56088): True
状态: PASS
```

---

## 场景 6: write_todos (任务规划)

```
用户: Create a todo list with 3 tasks: 1) Review code 2) Write tests 3) Deploy. Use the write_todos tool.

[0] Human: Create a todo list with 3 tasks...
[1] AI: [tool_calls: ['write_todos']]
[2] Tool(write_todos): Updated todo list to [
     {content: 'Review code', status: 'in_progress'},
     {content: 'Write tests', status: 'pending'},
     {content: 'Deploy', status: 'pending'}
   ]
[3] AI: Todo list created with three tasks:
1. Review code (in progress)
2. Write tests (pending)
3. Deploy (pending)

write_todos 被调用: True
状态: PASS
```

---

## 场景 7: glob (文件模式搜索)

```
预置文件: /src/main.py, /src/utils.py, /readme.md, /tests/test_main.py
用户: Find all .py files using glob pattern '**/*.py'

[0] Human: Find all .py files using glob pattern '**/*.py'
[1] AI: [tool_calls: ['glob']]
[2] Tool(glob): ['/src/main.py', '/src/utils.py', '/tests/test_main.py']
[3] AI: Found 3 Python files:
1. /src/main.py
2. /src/utils.py
3. /tests/test_main.py

glob 被调用: True
状态: PASS
```

---

## 场景 8: 多轮对话 (context retention)

```
使用 MemorySaver checkpointer, thread_id="test-thread-1"

Turn 1:
  用户: My name is James. Remember it.
  Agent: I'll remember your name is James.

Turn 2:
  用户: What is my name?
  Agent: Your name is James.

名字被记住: True
状态: PASS
```

---

## 场景 9: SubAgent (子代理调用)

```
配置子代理: summarizer (system_prompt: "You are a text summarizer. Summarize in one sentence.")
用户: Use the 'summarizer' subagent to summarize: 'Machine learning is a subset of AI...'

[0] Human: Use the 'summarizer' subagent...
[1] AI: [tool_calls: ['task']]  -- 调用 task 工具派发到 summarizer 子代理
[2] Tool(task): Machine learning is a subset of artificial intelligence where systems learn and improve from experience...
[3] AI: The summarizer agent has provided this concise summary...

task (子代理) 被调用: True
状态: PASS
```

---

## 场景 10: FilesystemBackend (真实磁盘操作)

```
使用 FilesystemBackend + tmpdir, 预创建 /data.csv:
  name,age
  Alice,30
  Bob,25
  Charlie,35

用户: List the files in /, then read /data.csv and tell me who is the oldest person.

[0] Human: List the files in /, then read /data.csv...
[1] AI: [tool_calls: ['ls']]
[2] Tool(ls): ['/data.csv']
[3] AI: [tool_calls: ['read_file']]
[4] Tool(read_file):      1	name,age
     2	Alice,30
     3	Bob,25
     4	Charlie,35
[5] AI: Based on the CSV data:
- Alice: 30 years old
- Bob: 25 years old
- Charlie: 35 years old
The oldest person is **Charlie** at 35 years old.

ls 被调用: True
read_file 被调用: True
正确识别 Charlie (35岁): True
状态: PASS
```

---

## 测试总结

| # | 场景 | 工具/功能 | 状态 |
|---|------|----------|------|
| 1 | 基本对话 | 直接响应 | PASS |
| 2 | 文件读写 | write_file + read_file | PASS |
| 3 | 目录+搜索 | ls + grep | PASS |
| 4 | 文件编辑 | read_file + edit_file(replace_all) + read_file | PASS |
| 5 | 自定义工具 | calculate (用户定义) | PASS |
| 6 | 任务规划 | write_todos | PASS |
| 7 | 文件模式搜索 | glob | PASS |
| 8 | 多轮对话 | MemorySaver checkpointer | PASS |
| 9 | 子代理 | task (SubAgent) | PASS |
| 10 | 磁盘操作 | FilesystemBackend + ls + read_file | PASS |

**10/10 场景全部 PASS。**
**DeepAgents SDK 0.5.0 在真实 LLM (DeepSeek-V3) 下工作正常。**
