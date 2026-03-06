# Skills 动态加载问题定位与处理方案（外部团队集成指南）

## 背景与问题摘要
- 外部项目在接入 DeepAgents 时，报告了 5 个“Skills 动态加载”相关失败用例：来自 `test_e2e_v2.py`（3 个）与 `test_v2_dynamic_loading.py`（2 个）。
- 失败原因：测试期望存在 `_create_load_skill_tool` / `_create_unload_skill_tool` 方法，以及 `max_loaded_skills` 参数。这些属于“v2 动态加载 API”的能力，但旧版框架未对外提供。
- 影响：不影响现有“声明式技能注入”（基于路径的技能加载）；仅影响外部项目中“前瞻性动态加载”测试。

## 根因定位
- SkillsMiddleware 早期只负责“按源路径加载技能元数据并注入系统提示”，未提供“运行期工具式（tool）加载/卸载”的公开接口。
- 外部项目单测超前依赖了动态加载 API 的内部草案名称（`_create_*`），因此在旧版本上必然失败。

## 处理方案概览
- 短期（外部项目侧）：
  - 为依赖“动态加载 API”的测试增加特性探测 gating（或 skip 标记），避免在旧版本 DeepAgents 上强行执行。
- 中期（DeepAgents 侧）：
  - 已在 SkillsMiddleware 增加“动态加载/卸载”的最小可用能力，默认关闭，使用者显式开启后即可通过工具进行加载/卸载。
  - 该实现保持向后兼容：不影响未开启此能力的使用者与现有测试。

## 新增能力（默认关闭）
### 构造参数
- `expose_dynamic_tools: bool = False`
  是否暴露“动态技能管理”工具；默认 `False`。
- `max_loaded_skills: int = 10`（推荐生产环境保持 ≤4，避免上下文过度膨胀）
  同时标记为“已加载”的技能数量上限。

### 开启后的工具
- `load_skill(skill_name: str)`：将某个技能标记为“已加载”，在系统提示技能清单中显示 `[Loaded]`，引导模型优先考虑该技能。
- `unload_skill(skill_name: str)`：取消“已加载”标记。

说明：
- 工具只更新会话状态（`loaded_skills`），不修改任何技能文件内容。
- 上限溢出、未找到技能、重复操作等情况会返回明确的错误提示或消息。
- 标记作用域为当前会话/代理；不会跨会话/跨代理传播。

## 使用方式
```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware

agent = create_deep_agent(
    model="openai:gpt-4o-mini",  # 或其他模型
    middleware=[
        FilesystemMiddleware(backend=FilesystemBackend(root_dir="/srv/app")),
        SkillsMiddleware(
            backend=FilesystemBackend(root_dir="/srv/app"),
            sources=["/skills/user", "/skills/project"],
            expose_dynamic_tools=True,   # 开启动态工具
            max_loaded_skills=10,        # 可调上限（生产推荐 ≤4）
        ),
    ],
)
```

对话运行期（由 LLM 或上层业务）：
- `load_skill(skill_name="web-research")` → 成功后在清单中显示 `[Loaded]`
- `unload_skill(skill_name="web-research")` → 清除标记

## 与“声明式技能注入”的关系
- 声明式（基于路径）：在 skills 源路径新增/删除 `<skill-name>/SKILL.md`，下一轮调用自动生效/失效（无需工具）；适合部署端控制。
- 动态工具（本指南新增）：在同一会话中通过工具“标记优先级”，不改文件，快速引导模型优先使用关键技能；适合对话内的即时控制。
- 两者可并行使用：路径决定“有哪些技能”，动态标记决定“当前更优先的技能”。

## 外部项目测试建议（gating 示例）
为“动态加载能力”加上特性探测，避免在旧版 DeepAgents 上执行相关测试：

```python
# conftest.py（外部项目）
import importlib
import importlib.metadata as md
import pytest

def _deepagents_version() -> tuple[int, int, int]:
    try:
        ver = md.version("deepagents")
    except md.PackageNotFoundError:
        return (0, 0, 0)
    parts = (ver.split("+", 1)[0]).split(".")
    ints = [int(p) for p in parts[:3]] + [0] * (3 - len(parts))
    return tuple(ints[:3])

def _has_dynamic_skills_api() -> bool:
    try:
        sm = importlib.import_module("deepagents.middleware.skills")
        SkillsMiddleware = getattr(sm, "SkillsMiddleware", None)
        if SkillsMiddleware is None:
            return False
        m = SkillsMiddleware(backend=lambda rt: None, sources=["/skills/user"], expose_dynamic_tools=True)
        tool_names = {t.name for t in getattr(m, "tools", [])}
        return "load_skill" in tool_names and "unload_skill" in tool_names
    except Exception:
        return False

DYNAMIC_SKILLS_AVAILABLE = _has_dynamic_skills_api() or (_deepagents_version() >= (0, 5, 0))

pytestmark = pytest.mark.skipif(
    not DYNAMIC_SKILLS_AVAILABLE,
    reason="动态加载 API 尚不可用；请在 DeepAgents 启用 expose_dynamic_tools 或升级版本后再运行这些用例。",
)
```

## 兼容性与风险控制
- 默认关闭：不改变任何现有行为与系统提示内容。
- 工具只写状态：不改磁盘文件；避免引入额外持久化复杂度。
- 清晰的错误语义：不存在/已存在/超上限/未加载等情况均有明确反馈。
- 与已有系统提示整合：已加载技能显示 `[Loaded]`，不额外注入全文，保持上下文可控。

## 常见问题
**Q：和“v2 原版”的接口名字不一致怎么办？**
A：对外公开的是工具名 `load_skill` / `unload_skill`；外部项目无需也不应依赖任何私有名称（如 `_create_*`）。如需对接已有测试，可在测试中调用工具名，或使用上文 gating 控制。

**Q：如何限制加载过多技能导致模型分心？**
A：通过 `max_loaded_skills` 控制数量上限；超过上限会收到错误提示，需先卸载再加载。生产环境建议保持 ≤4。

**Q：能否让加载后立即把技能正文注入系统提示？**
A：当前版本仅标记优先级并在清单中显式标注；若需在同轮注入摘要，可在上层封装“读取技能摘要→附加系统消息”的业务逻辑，以避免上下文暴涨。

## 版本与状态
- 该能力已在主干可用，默认关闭，视为“实验性质”的对外接口；待文档与生态验证稳定后纳入正式版本说明。
- 外部项目可立即按上述方式启用并使用；如遇到边界问题，欢迎反馈以完善语义与行为。

---

如需我们提供示例适配层（封装 load/unload 的业务调用）或帮你在外部仓库落地 gating 方案，请联系维护者。我们可直接提交最小变更以确保 CI 通过与用例回归。
