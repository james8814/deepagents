# SubAgent 工作日志提取功能 - 详细实施计划

**启动日期**: 2026-03-11
**预计周期**: 2-3 周（4-5 工程日）
**优先级**: P1（高优先）
**状态**: 🚀 **即将启动**

---

## 📋 概述

基于架构师和内部研发团队的一致评审意见，启动 **SubAgent 工作日志提取功能** 的开发。该功能将填补 DeepAgents 框架在可观测性方面的空白，为用户提供完整的 SubAgent 执行链路追踪能力。

**评审共识**:
- ✅ 框架契合度: 4.8/5.0（优秀）
- ✅ 零风险实现: 100% 向后兼容
- ✅ 实现成本: 4-5 工程日，~250 行代码
- ✅ 战略价值: 竞争优势，提升框架完整度

---

## 🎯 项目目标

### 核心目标
实现 SubAgent 执行过程的完整日志记录，使开发者能够：
- 理解 SubAgent 如何解决问题
- 快速定位和调试失败的子任务
- 验证工具调用的正确性和参数
- 提高对系统的可信度

### 成功标准
- ✅ 日志完整记录所有工具调用/结果配对
- ✅ 敏感数据自动脱敏（token, secret, password, api_key）
- ✅ 大输出自动截断（>500 字符）
- ✅ 100% 向后兼容，现有应用无需改动
- ✅ 全部单元测试通过
- ✅ 集成测试验证真实 SubAgent 场景
- ✅ 文档完整，包含最佳实践示例

---

## 🏗️ 架构设计

### 核心组件

#### 1. **State Definition** (`libs/deepagents/deepagents/graph.py`)
```python
# 在 AgentState TypedDict 中添加
subagent_logs: Annotated[
    NotRequired[dict[str, list[dict]]],
    _subagent_logs_reducer,
]

# Reducer 函数
def _subagent_logs_reducer(
    left: dict[str, list[dict]] | None,
    right: dict[str, list[dict]] | None,
) -> dict[str, list[dict]]:
    """
    SubAgent 工作日志合并 reducer
    
    支持 per task_id 隔离，多个 SubAgent 并发执行时各自维护日志
    """
    if left is None:
        return right or {}
    if right is None:
        return left
    # 合并两个日志字典，保持 task_id 隔离
    result = left.copy()
    for task_id, entries in right.items():
        if task_id in result:
            result[task_id].extend(entries)
        else:
            result[task_id] = entries
    return result
```

#### 2. **SubAgentLoggingMiddleware** (新文件: `libs/deepagents/deepagents/middleware/subagent_logging.py`)

```python
from typing import Any
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage
from .base import BaseMiddleware

class SubAgentLoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging SubAgent tool execution.
    
    Features:
    - Records tool calls with parameters
    - Captures tool results
    - Auto-redacts sensitive data
    - Truncates large outputs
    - Per-SubAgent isolation via task_id
    """
    
    def __init__(
        self,
        enabled: bool = True,
        sensitive_keys: set[str] | None = None,
        max_output_length: int = 500,
    ):
        """
        Initialize SubAgentLoggingMiddleware.
        
        Args:
            enabled: Whether logging is active
            sensitive_keys: Fields to redact (token, secret, password, etc.)
            max_output_length: Max length for truncation
        """
        self.enabled = enabled
        self.sensitive_keys = sensitive_keys or {
            "token", "secret", "password", "api_key",
            "authorization", "private_key", "credentials",
            "access_token", "refresh_token", "jwt"
        }
        self.max_output_length = max_output_length
    
    def before_agent_starts(self, state: dict[str, Any]) -> dict[str, Any]:
        """Initialize subagent_logs if not present."""
        if "subagent_logs" not in state:
            state["subagent_logs"] = {}
        return state
    
    def after_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_result: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Record tool call and result.
        
        Logic:
        1. Extract current task_id from state context
        2. Create tool_call entry with redaction
        3. Create tool_result entry with truncation
        4. Append to state.subagent_logs[task_id]
        """
        if not self.enabled:
            return state
        
        task_id = state.get("_current_task_id")  # Set by SubAgentMiddleware
        if not task_id:
            return state
        
        # Initialize task_id logs if needed
        if "subagent_logs" not in state:
            state["subagent_logs"] = {}
        if task_id not in state["subagent_logs"]:
            state["subagent_logs"][task_id] = []
        
        # Create tool_call entry
        tool_call_entry = {
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_input": self._redact(tool_input),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Create tool_result entry
        tool_result_entry = {
            "type": "tool_result",
            "content": self._truncate(tool_result),
            "status": "success",  # Can be "error" if tool raised
            "timestamp": datetime.now().isoformat(),
        }
        
        # Append to logs
        state["subagent_logs"][task_id].append(tool_call_entry)
        state["subagent_logs"][task_id].append(tool_result_entry)
        
        return state
    
    def _redact(self, obj: Any) -> Any:
        """Recursively redact sensitive fields."""
        if isinstance(obj, dict):
            return {
                k: "***" if k.lower() in self.sensitive_keys else self._redact(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._redact(item) for item in obj]
        return obj
    
    def _truncate(self, text: str, length: int | None = None) -> str:
        """Truncate text if longer than max_output_length."""
        max_len = length or self.max_output_length
        if len(text) > max_len:
            return text[:max_len] + "... (truncated)"
        return text


def create_subagent_logging_middleware(
    enabled: bool = True,
    sensitive_keys: set[str] | None = None,
    max_output_length: int = 500,
) -> SubAgentLoggingMiddleware:
    """Factory function for creating SubAgentLoggingMiddleware."""
    return SubAgentLoggingMiddleware(
        enabled=enabled,
        sensitive_keys=sensitive_keys,
        max_output_length=max_output_length,
    )
```

#### 3. **Integration Point** (`libs/deepagents/deepagents/graph.py`)

在 `create_deep_agent()` 中添加参数和集成逻辑：

```python
def create_deep_agent(
    model: str | BaseChatModel,
    ...,
    subagent_logging: bool = True,  # ← 新参数
    subagent_logging_config: dict[str, Any] | None = None,
    ...
) -> CompiledGraph:
    """
    Create a deep agent with optional SubAgent logging.
    
    Args:
        subagent_logging: Enable SubAgent execution logging
        subagent_logging_config: Config dict with keys:
            - sensitive_keys: set[str] - fields to redact
            - max_output_length: int - output truncation length
    """
    # ... existing code ...
    
    middleware: list[BaseMiddleware] = [
        TodoListMiddleware(),
        # ... other middleware ...
    ]
    
    # Add SubAgentLoggingMiddleware if enabled
    if subagent_logging:
        config = subagent_logging_config or {}
        logging_mw = create_subagent_logging_middleware(
            enabled=True,
            sensitive_keys=config.get("sensitive_keys"),
            max_output_length=config.get("max_output_length", 500),
        )
        middleware.append(logging_mw)
    
    # ... rest of middleware setup ...
    
    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        ...
    )
```

#### 4. **State Isolation** (`libs/deepagents/deepagents/subagents.py`)

扩展现有的隔离机制：

```python
# Update _EXCLUDED_STATE_KEYS
_EXCLUDED_STATE_KEYS = {
    "messages",
    "todos",
    "structured_response",
    "skills_metadata",
    "memory_contents",
    "subagent_logs",  # ← 新增：防止父 SubAgent 日志泄露到子 SubAgent
}
```

---

## 🔄 实施阶段

### **第一阶段：技术分享与设计验证（1 天）**

**目标**: 获得详细的参考实现知识，完成架构设计确认

**任务**:
- [ ] 邀请 PMAgent 团队进行内部技术分享会
  - 分享 EventLoggingMiddleware 的实现细节
  - 讨论与 DeepAgents 框架的适配差异
  - 回答实现中的技术问题
  
- [ ] 审查 PMAgent 参考实现代码
  - 了解 redact_and_truncate() 的完整实现
  - 学习状态管理的最佳实践
  - 参考他们的测试用例设计
  
- [ ] 完成 DeepAgents 版本的详细设计
  - 确认文件路径和模块结构
  - 设计 API 接口（参数、返回值）
  - 列出需要修改的所有文件
  
- [ ] 架构设计评审
  - 与 PMAgent 团队确认适配方案
  - 与内部团队走通集成点
  - 获得 go/no-go 信号

**输出**:
- ✅ 技术分享会议纪要
- ✅ 修改文件清单（含行数估算）
- ✅ API 设计文档
- ✅ 架构评审通过记录

**预计时间**: 1 天

---

### **第二阶段：核心代码实现（2 天）**

**目标**: 完成 State、Reducer 和 Middleware 的实现

**Task 1: State + Reducer 实现** (1 天)

```
目标文件: libs/deepagents/deepagents/graph.py
预计代码: ~50 行

步骤:
  1. 在 AgentState 中添加 subagent_logs 字段定义
  2. 实现 _subagent_logs_reducer() 函数
  3. 在 DEFAULT_STATE 中初始化为 {}
  4. 更新 _EXCLUDED_STATE_KEYS 加入 "subagent_logs"
  5. 编写 reducer 单元测试（3 个测试用例）
  
验证标准:
  ✅ 无语法错误
  ✅ 类型检查通过
  ✅ Reducer 单元测试 3/3 pass
```

**Task 2: SubAgentLoggingMiddleware 实现** (1 天)

```
目标文件: libs/deepagents/deepagents/middleware/subagent_logging.py (新文件)
预计代码: ~100 行

步骤:
  1. 创建 SubAgentLoggingMiddleware 类
  2. 实现 __init__() 和参数验证
  3. 实现 before_agent_starts() 初始化逻辑
  4. 实现 after_tool_call() 日志记录逻辑
  5. 实现 _redact() 敏感数据脱敏
  6. 实现 _truncate() 大输出截断
  7. 实现 create_subagent_logging_middleware() 工厂函数
  8. 编写单元测试（5 个测试用例）

验证标准:
  ✅ 无语法/类型错误
  ✅ Middleware 单元测试 5/5 pass
  ✅ 敏感字段正确脱敏为 "***"
  ✅ 长输出正确截断
```

**Task 3: create_deep_agent() 集成** (0.5 天)

```
目标文件: libs/deepagents/deepagents/graph.py (修改)
预计代码: ~20 行

步骤:
  1. 添加 subagent_logging 参数到 create_deep_agent()
  2. 添加 subagent_logging_config 参数
  3. 在中间件初始化时根据参数加载 Middleware
  4. 添加日志输出（middleware enabled/disabled）
  5. 编写集成单元测试（2 个测试用例）

验证标准:
  ✅ 参数解析正确
  ✅ Middleware 正确注入到栈中
  ✅ 集成测试 2/2 pass
```

**输出**:
- ✅ 代码实现完整（~170 行核心代码）
- ✅ 单元测试全部通过（10 个测试）
- ✅ 代码审查通过
- ✅ 类型检查通过

**预计时间**: 2 天

---

### **第三阶段：集成测试与文档（1 天）**

**目标**: 验证真实 SubAgent 场景，编写文档和示例

**Task 1: 集成测试** (0.5 天)

```
目标文件: libs/deepagents/tests/unit_tests/middleware/test_subagent_logging_integration.py (新文件)
预计代码: ~80 行测试代码

测试场景:
  1. 单 SubAgent 执行（verify logs populated correctly）
  2. 多 SubAgent 并发执行（verify per-task_id isolation）
  3. SubAgent 失败场景（verify error status recorded）
  4. 敏感数据在真实 SubAgent 中被正确脱敏
  5. 与其他中间件的兼容性（Summarization + Logging）

验证标准:
  ✅ 所有集成测试 5/5 pass
  ✅ logs 结构符合设计（type, tool_name, content 等字段）
  ✅ 敏感数据确实被脱敏
  ✅ 并发 SubAgent 的日志不互相干扰
```

**Task 2: 文档编写** (0.5 天)

```
生成文件:
  1. API Reference (docs/api/subagent_logging.md)
     - SubAgentLoggingMiddleware 类文档
     - create_subagent_logging_middleware() 函数文档
     - 配置参数说明
     - 返回值结构说明
     
  2. Best Practices Guide (docs/guides/subagent_logging_best_practices.md)
     - 何时启用/禁用日志
     - 敏感字段配置建议
     - 性能考虑（输出长度限制）
     - 常见问题解答
     
  3. Example Code (examples/subagent_logging_example.py)
     - 基础使用示例
     - 自定义敏感字段示例
     - 从状态中读取日志的示例
     - 前端集成示例（如何在 UI 中展示）
     
  4. CHANGELOG 条目
     - 新功能简描
     - 破坏性变更：无
     - 迁移指南：无需迁移

内容要点:
  ✅ 清晰的 API 文档
  ✅ 实际可用的代码示例
  ✅ 最佳实践建议
  ✅ 常见问题回答
```

**输出**:
- ✅ 集成测试全部通过（5 个测试）
- ✅ 完整的 API 文档
- ✅ 最佳实践指南
- ✅ 可复制的示例代码
- ✅ CHANGELOG 条目

**预计时间**: 1 天

---

### **第四阶段：最终验证与发布准备（0.5-1 天）**

**目标**: 代码审查、性能基准、发布准备

**Task 1: 代码审查** (0.5 天)

```
审查清单:
  代码质量:
    [ ] 没有 pylint/flake8 错误
    [ ] 所有类型注解完整
    [ ] 代码风格符合项目规范
    [ ] 注释清晰（特别是复杂逻辑）
  
  功能正确性:
    [ ] 敏感字段脱敏完整
    [ ] 大输出截断正确
    [ ] 并发隔离有效
    [ ] 错误处理充分
  
  向后兼容性:
    [ ] 现有 API 未改变
    [ ] 现有测试仍通过
    [ ] 没有破坏性变更
  
  文档完整性:
    [ ] API 文档准确
    [ ] 示例代码可运行
    [ ] CHANGELOG 更新
```

**Task 2: 性能基准** (0.25 天)

```
测试场景:
  1. 无日志情况（baseline）
     - Agent 执行时间
     - 状态序列化大小
  
  2. 启用日志情况
     - Agent 执行时间（overhead 应 < 5%）
     - 状态序列化大小（logs 应 < 10% of total）
  
  3. 日志截断效果
     - 验证 500 字符限制有效
     - 验证并发 SubAgent 日志数量合理

通过标准:
  ✅ 执行时间 overhead < 5%
  ✅ 状态大小增长 < 10%
  ✅ 无内存泄漏
```

**Task 3: 发布准备** (0.25 天)

```
准备项:
  [ ] 更新 CHANGELOG.md
  [ ] 更新 README.md (添加 subagent_logging 特性)
  [ ] 更新 API Reference 文档
  [ ] 创建发布说明 (release notes)
  [ ] 版本号规划 (建议 0.4.7 或 0.5.0)
  
PR 准备:
  [ ] 从 feature/subagent-logging 创建 PR 到 master
  [ ] PR 描述中包含：
      - 功能概述
      - 测试覆盖（单元+集成）
      - Breaking changes: None
      - 迁移指南: 不需要
  [ ] 至少 2 人代码审查通过
```

**输出**:
- ✅ 代码审查通过
- ✅ 性能基准通过
- ✅ PR 创建并通过审查
- ✅ 版本发布准备完成

**预计时间**: 0.5-1 天

---

## 📊 详细时间表

| 阶段 | 任务 | 负责人 | 时间 | 交付物 |
|------|------|--------|------|--------|
| **第一阶段** | 技术分享 + 设计验证 | 架构师 + 2 名工程师 | 1 天 | 设计文档、修改清单 |
| **第二阶段** | 核心代码实现 | 2-3 名工程师 | 2 天 | ~170 行代码，10 个测试通过 |
| **第三阶段** | 集成测试 + 文档 | 1-2 名工程师 | 1 天 | 集成测试通过，文档完整 |
| **第四阶段** | 代码审查 + 发布 | 架构师 + 工程师 | 0.5-1 天 | PR 通过，版本就绪 |
| **总计** | | | **4-5 天** | **生产就绪版本** |

---

## 🔗 依赖关系

```
第一阶段 (1 天)
    ↓ (go/no-go)
    
第二阶段 (2 天，可并行)
  ├─ Task 1: State + Reducer (1 day)
  ├─ Task 2: Middleware (1 day)
  └─ Task 3: 集成点 (0.5 day)
    ↓ (代码完成)
    
第三阶段 (1 天，可并行)
  ├─ 集成测试 (0.5 day)
  └─ 文档编写 (0.5 day)
    ↓ (测试通过)
    
第四阶段 (0.5-1 天)
  ├─ 代码审查
  ├─ 性能基准
  └─ 发布准备
    ↓
    
发布 (版本 0.4.7 或 0.5.0)
```

---

## 📁 文件修改清单

### **新建文件** (2 个)
```
libs/deepagents/deepagents/middleware/subagent_logging.py
  - SubAgentLoggingMiddleware 类 (~100 行)
  - 工厂函数 (~20 行)
  - 辅助函数 (_redact, _truncate) (~30 行)

libs/deepagents/tests/unit_tests/middleware/test_subagent_logging_integration.py
  - 集成测试用例 (~80 行)
```

### **修改文件** (3 个)
```
libs/deepagents/deepagents/graph.py
  - 添加 subagent_logs 字段定义 (~15 行)
  - 添加 _subagent_logs_reducer() 函数 (~20 行)
  - 修改 create_deep_agent() 添加参数 (~20 行)
  - 修改 _EXCLUDED_STATE_KEYS 添加 "subagent_logs" (~1 行)

libs/deepagents/deepagents/subagents.py
  - 修改 _EXCLUDED_STATE_KEYS (~1 行)

libs/deepagents/tests/unit_tests/test_graph.py
  - 添加 subagent_logging 参数测试 (~30 行)
```

### **文档文件** (4 个)
```
docs/api/subagent_logging.md (新文件)
  - API 文档 (~150 行)

docs/guides/subagent_logging_best_practices.md (新文件)
  - 最佳实践指南 (~150 行)

examples/subagent_logging_example.py (新文件)
  - 示例代码 (~80 行)

CHANGELOG.md (修改)
  - 添加版本条目 (~10 行)
```

**总计**: 2 个新建文件 + 3 个修改文件 + 4 个文档文件 ≈ **600-700 行代码+文档**

---

## ✅ 验收标准

### **代码质量**
- [ ] 所有代码通过 lint（ruff check）
- [ ] 所有代码通过类型检查（mypy 或 pyright）
- [ ] 代码覆盖率 >= 85%
- [ ] 无新的 deprecation 警告

### **功能完整性**
- [ ] 所有工具调用都被记录
- [ ] 敏感字段被正确脱敏
- [ ] 大输出被正确截断
- [ ] 并发 SubAgent 的日志正确隔离
- [ ] 与所有现有中间件兼容

### **测试覆盖**
- [ ] 单元测试：10+ 个，全部通过
- [ ] 集成测试：5+ 个，全部通过
- [ ] 性能测试：overhead < 5%
- [ ] 兼容性测试：现有测试全部通过

### **文档完整性**
- [ ] API 文档准确完整
- [ ] 至少 3 个实际代码示例
- [ ] 最佳实践指南
- [ ] CHANGELOG 更新
- [ ] 无格式错误

### **向后兼容性**
- [ ] 现有 API 完全不变
- [ ] 现有应用无需修改
- [ ] 默认行为清晰
- [ ] 降级策略完善

---

## 🚀 快速启动清单

### **立即行动** (今天)
- [ ] 分享此计划给团队
- [ ] 与 PMAgent 团队协调技术分享时间
- [ ] 准备技术分享会议室和议程
- [ ] 分配工程师名单

### **第一阶段准备** (本周)
- [ ] 完成技术分享会议
- [ ] 梳理参考实现代码
- [ ] 完成详细设计文档
- [ ] 架构评审通过

### **第二阶段启动** (下周)
- [ ] 创建 feature 分支：`feature/subagent-logging`
- [ ] 分配任务给 2-3 名工程师
- [ ] 建立代码审查 checklist
- [ ] 开始代码实现

---

## 📞 沟通计划

### **团队定期同步**
- **频率**: 每日 15:00（快速站会，5 分钟）
- **内容**: 进展、阻止因素、当日计划
- **工具**: Slack + 可选录制

### **架构师审查**
- **频率**: 每日/隔日（设计审查 + 代码审查）
- **checkpoint**: 
  - 第一阶段结束：架构设计通过
  - 第二阶段结束：代码审查通过
  - 第三阶段结束：集成测试通过
  - 第四阶段结束：发布审查通过

### **与 PMAgent 团队协作**
- **技术分享会**: 第一阶段
- **Q&A 会**: 第二阶段中期（如有技术卡点）
- **集成验证**: 第三阶段（共同测试）

---

## 📋 关键决策记录

**决策 1**: 实现位置
- ✅ **决议**: 在 `libs/deepagents/deepagents/middleware/subagent_logging.py`
- **理由**: 保持模块化，便于维护和测试

**决策 2**: 默认启用？
- ✅ **决议**: YES（`subagent_logging=True`）
- **理由**: 提升默认体验，用户可选择关闭

**决策 3**: 与数据库集成？
- ✅ **决议**: NO（先实现基础版本）
- **理由**: 日志只存状态中，用户自主决定持久化

**决策 4**: 版本号？
- ✅ **建议**: v0.4.7 (incremental) 或 v0.5.0 (next minor)
- **理由**: 取决于其他 0.5.0 计划功能

---

## 📝 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| PMAgent 实现细节难以迁移 | 低 | 中 | 邀请他们协作，必要时 pair programming |
| 性能开销超预期 | 低 | 中 | 提前做性能基准，优化 append 逻辑 |
| 与第三方中间件冲突 | 低 | 低 | 充分的兼容性测试 |
| 时间估算不准 | 中 | 低 | 保留 1 天 buffer，及时调整 |

---

## 🎯 成功定义

**项目成功 = 以下全部满足**:

1. ✅ **功能完整**: 所有需求实现，测试覆盖 >= 85%
2. ✅ **质量优秀**: 无新 lint 错误，所有审查通过
3. ✅ **兼容友好**: 100% 向后兼容，现有应用零影响
4. ✅ **文档充分**: API 文档、指南、示例全覆盖
5. ✅ **性能达标**: 执行时间 overhead < 5%
6. ✅ **按时交付**: 在 2-3 周内完成
7. ✅ **生产就绪**: 可直接发布到 PyPI

---

## 📞 项目负责人

**项目经理**: [待指派]
**架构师**: Claude Code 架构师
**核心工程师**: [2-3 名，待指派]
**技术顾问**: PMAgent 团队

---

## 🔗 相关链接

- [DEEPAGENTS_FEATURE_PROPOSAL.md](./docs/tmp/DEEPAGENTS_FEATURE_PROPOSAL.md) - 原始提案
- [EXTERNAL_PROPOSAL_ANALYSIS.md](./EXTERNAL_PROPOSAL_ANALYSIS.md) - 架构分析报告
- [ARCHITECTURE_RECOMMENDATION.txt](./ARCHITECTURE_RECOMMENDATION.txt) - 架构师推荐
- [PMAgent 参考实现](./docs/tmp/SUBAGENT_LOGGING_VERIFICATION_REPORT.md) - 验证报告

---

*计划制定日期: 2026-03-11*
*状态: 🚀 **准备启动**，等待最终批准*

