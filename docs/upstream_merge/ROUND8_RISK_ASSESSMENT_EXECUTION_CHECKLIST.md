# Round 8 上游合并 - 执行备忘清单版

**日期**: 2026-03-27  
**修订版本**: Execution Checklist v4 (架构师终审通过)  
**评估范围**: 10 个新上游 commits (a32ce7ff ~ 4f72c342)  
**评估标准**: 顶级大厂标准 - 100% 测试通过率、零功能破坏、完整冲突解决、系统性风险可控

---

## 📊 执行摘要

**总体风险等级**: 🟡 **中等风险** - 存在 3 个关键冲突 + 1 个系统性风险 + 4 个执行坑位

**关键原则**: 确保执行者**不会把前置条件误判成合并缺陷**

---

## ⚠️ 执行前必读：4 个关键坑位

### 坑位 1: 基线分支检测 + 默认分支名一致性

**风险 1**: 用 `git log | grep "round7"` 不可靠（squash/重写标题后字符串可能不存在）

**风险 2**: Phase 0 用 `git fetch upstream main`，但基线判断用 `master`。如果仓库默认分支实际是 `main`，执行者会误判。

**修正方案**:

```bash
# P0-PRE: 确认默认分支名（执行前第一步）
# 方法 1（推荐，纯本地，不依赖远程交互和输出格式）:
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
# 如果 origin/HEAD 未设置（少数仓库），可尝试让 Git 探测并设置（可能需要网络；失败可忽略）：
if [ -z "$DEFAULT_BRANCH" ]; then
    git remote set-head origin -a 2>/dev/null || echo "⚠️ 无法自动设置 origin/HEAD（可能 offline），继续兜底"
    DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
fi
# 兜底：回退到 Git 全局配置或硬编码默认值
if [ -z "$DEFAULT_BRANCH" ]; then
    DEFAULT_BRANCH=$(git config init.defaultBranch 2>/dev/null || echo "main")
fi
echo "默认分支: $DEFAULT_BRANCH"
# 如果仍不确定：git branch -r | head -5，手动确认

# 初始化 BASE_BRANCH = DEFAULT_BRANCH（默认基线 = 默认分支）
BASE_BRANCH="$DEFAULT_BRANCH"

# A.1 确定基线分支（用关键 SHA 而非字符串匹配）
# 注意：BASE_BRANCH 初始值 = DEFAULT_BRANCH，两者关系明确
# Round 7 最后一个提交 SHA（执行者替换为实际值）
# 选择标准：用 Round 7 里最能代表"本地修复已包含"的那个 commit
# ——最好是 Round 7 的合并点（merge commit）或最后提交（如 docs/报告 commit）
# 例如：Round 7 的最后一个 push commit = 3c4483ce (docs: Add Round 7 ...)
# ⚠️ 不要选中间 commit，否则可能误判基线不包含 Round 7
ROUND7_LAST_SHA="3c4483ce"

# 检查默认分支是否包含 Round 7
if git merge-base --is-ancestor $ROUND7_LAST_SHA $BASE_BRANCH 2>/dev/null; then
    echo "✅ 确认 $BASE_BRANCH 包含 Round 7"
    # BASE_BRANCH 保持不变 (= DEFAULT_BRANCH)
else
    echo "⚠️ $BASE_BRANCH 不包含 Round 7，检查其他分支"
    if git rev-parse --verify upstream-sync-round7 >/dev/null 2>&1; then
        if git merge-base --is-ancestor $ROUND7_LAST_SHA upstream-sync-round7 2>/dev/null; then
            echo "✅ 确认 upstream-sync-round7 包含 Round 7"
            BASE_BRANCH="upstream-sync-round7"
        else
            echo "❌ 未找到包含 Round 7 的分支，请手动确认"
            exit 1
        fi
    else
        echo "❌ upstream-sync-round7 不存在，请手动确认基线"
        exit 1
    fi
fi

echo "最终使用基线分支: $BASE_BRANCH"
```

---

### 坑位 2: git checkout 到 remote ref 会进入 detached HEAD

**风险**: `git checkout upstream/$BASE_BRANCH` 进入 detached HEAD，如果执行者没紧接着 `git checkout -b ...`，后续操作不直观且容易出错。

**修正方案**: 一旦 checkout 到 remote ref，**下一步必须立刻创建工作分支**：

```bash
# A.2 创建工作分支（根据分支来源，一步完成 checkout + 创建分支）
# 前置条件：确保 remote refs 已拉取（否则 origin/$BASE_BRANCH 可能不存在）
git fetch origin 2>/dev/null || echo "⚠️ origin fetch 失败，继续尝试其他 remote"
git fetch upstream 2>/dev/null || echo "⚠️ upstream fetch 失败，继续尝试本地"

if git rev-parse --verify origin/$BASE_BRANCH >/dev/null 2>&1; then
    echo "基线分支在 origin，直接从 remote ref 创建工作分支"
    git checkout -b merge-round8-phaseA origin/$BASE_BRANCH  # 一步完成，不经过 detached HEAD
elif git rev-parse --verify upstream/$BASE_BRANCH >/dev/null 2>&1; then
    echo "基线分支在 upstream，直接从 remote ref 创建工作分支"
    git checkout -b merge-round8-phaseA upstream/$BASE_BRANCH  # 一步完成，不经过 detached HEAD
else
    echo "基线分支是本地分支"
    git checkout $BASE_BRANCH
    git checkout -b merge-round8-phaseA  # 从本地分支创建
fi

# 验证：确认在正确的分支上（不是 detached HEAD）
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
echo "当前分支: $BRANCH_NAME"
if [ "$BRANCH_NAME" = "HEAD" ]; then
    echo "❌ 错误：处于 detached HEAD 状态！请检查分支创建步骤"
    exit 1
fi
```

---

### 坑位 3: make 命令必须在对应包目录执行

**风险**: L2/L3/L5 汇总部分如果在根目录执行 `make`，可能跑的是不同目标或失败。

**修正方案**: 每个 `make` 前验证当前目录：

```bash
# SDK 门禁（必须在 libs/deepagents 目录）
cd "/Volumes/0-/jameswu projects/deepagents/libs/deepagents"
pwd  # 验证：.../libs/deepagents
make lint && make type && make test

# CLI 门禁（必须在 libs/cli 目录）
cd "../cli"
pwd  # 验证：.../libs/cli
make lint && make type && make test

# Evals 门禁（必须在 libs/evals 目录）
cd "../evals"
pwd  # 验证：.../libs/evals
make test
```

---

### 坑位 4: "无凭据/无网络" UI 验收场景的正确启动方式

**关键纠正**: `itest:fake` **不是内置 provider**，不能当"默认可用"。它只在 `~/.deepagents/config.toml` 中显式配置 `class_path` 后才可用。

**正确的失败场景分析**:
- `deepagents --model claude-sonnet-4-6`：`detect_provider()` 能识别 `claude` 前缀并映射到 `anthropic`，所以 provider 探测不会失败。失败点是后续的 **API key 缺失**。
- 真正的"启动阶段退出"发生在 **未传 `--model` 且无凭据** 时：`_get_default_model_spec()` 会抛出 `ModelConfigError`。

**`detect_provider()` 完整识别范围**（精确版）:
- `gpt-`、`o1`、`o3`、`o4`、`chatgpt` → openai
- `claude` → anthropic（或 google_vertexai，取决于凭据）
- `gemini` → google_genai（或 google_vertexai，取决于凭据）
- `nemotron`、`nvidia/` → nvidia
- 其他前缀 → `None`（需通过 `provider:model` 格式显式指定）

**修正方案**:

```bash
# 测试 3: 无凭据场景
# 关键：必须传 --model，否则 _get_default_model_spec() 会因无凭据直接报错退出
# 使用 detect_provider() 能识别的模型名 + 明确 provider 前缀更稳
unset ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_API_KEY
deepagents --model anthropic:claude-sonnet-4-6  # 明确 provider，避免探测失败
# 输入: /model
# 预期行为: UI 可进入（模型名解析成功），但调用模型时会给出凭据缺失提示
# 不要求: 实际调用模型成功 (降级行为)

# 测试 4: 无网络场景
# 同理：传 --model 避免启动阶段退出
deepagents --model anthropic:claude-sonnet-4-6  # 明确 provider
# 输入: /model
# 预期行为: /model 的本地数据加载正常，但在线拉取可能失败并给出友好错误
# 不要求: 完整在线模型列表 (降级行为)

# 备选方案: 使用 config.toml 配置测试 provider（QA 专用，需预先配置）
# 在 ~/.deepagents/config.toml 中添加:
# [models.providers.itest]
# class_path = "deepagents_cli._testing_models:DeterministicIntegrationChatModel"
# models = ["fake"]
# 然后可以用: deepagents --model itest:fake
# 注意: 这不是"内置可用"，需要预先配置
```

---

## 🎯 最终合并策略总览

| Commit SHA | 简述 | 风险等级 | 冲突文件 | Phase | 合并策略 |
|------------|------|----------|----------|-------|----------|
| dd553cd9 | test for invalid args | 🟢 | 无 | A | 直接 cherry-pick |
| 166aebf4 | add all snapshots | 🟢 | 无 | A | 直接 cherry-pick |
| adef73c4 | tool descriptions snapshot | 🟢 | 无 | A | 直接 cherry-pick |
| 69bd21e2 | normalize CRLF | 🟢 | 无 | B | 直接 cherry-pick |
| 9862b5ad | FileData NotRequired | 🟡 | 无 | B | 专项回归 |
| f69761b4 | speed up init | 🟡 | filesystem.py | B | 手动解决冲突 |
| 4f72c342 | evict large HumanMessages | 🟡 | filesystem.py | B | 手动解决冲突 + 专项验收 |
| f8ebf266 | extract format_duration | 🟢 | 无 | C | 直接 cherry-pick |
| 2e9b705f | task subagent type badge | 🟡 | messages.py | C | 手动解决冲突 |
| a32ce7ff | defer /model selector | 🟡 | 无 | C | UI 时序专项验收 |

---

## 🔄 执行方案：四阶段

### 🔴 **Phase 0: Git 仓库健康修复**

```bash
cd "/Volumes/0-/jameswu projects/deepagents"

# 确认默认分支名（坑位 1 修正：不依赖 git remote show 输出格式）
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
    git remote set-head origin -a 2>/dev/null || echo "⚠️ 无法自动设置 origin/HEAD（可能 offline），继续兜底"
    DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
fi
if [ -z "$DEFAULT_BRANCH" ]; then
    DEFAULT_BRANCH=$(git config init.defaultBranch 2>/dev/null || echo "main")
fi
BASE_BRANCH="$DEFAULT_BRANCH"  # 初始基线 = 默认分支
echo "默认分支: $DEFAULT_BRANCH"

# 备份
git branch backup-pre-round8-$(date +%Y%m%d-%H%M%S)

# 清理 ._pack*
find .git/objects/pack -name "._pack*" -type f -delete

# 验证
git fsck --full 2>&1 | tee /tmp/git-fsck-report.txt
if grep -q "error\|corrupt\|missing" /tmp/git-fsck-report.txt; then
    git repack -a -d --depth=250 --window=250
    git fsck --full
fi

# fetch upstream（使用实际的默认分支名）
# 注意：git fetch upstream 会拉取所有 refs，一般可接受
# 如果只想拉默认分支：git fetch upstream $DEFAULT_BRANCH
git fetch upstream 2>/dev/null || echo "⚠️ upstream fetch 失败（可能是 offline）"
```

**验收**: `git fsck --full` 无错误，Git 操作无 `non-monotonic index`

**预计时间**: ~20 分钟

---

### 🟢 **Phase A: 纯测试/快照增强** (3个 commits)

```bash
# A.1 确定基线分支（坑位 1 修正：用 SHA + 正确的默认分支名）
ROUND7_LAST_SHA="3c4483ce"  # 替换为实际值

if git merge-base --is-ancestor $ROUND7_LAST_SHA $DEFAULT_BRANCH 2>/dev/null; then
    BASE_BRANCH="$DEFAULT_BRANCH"
else
    if git rev-parse --verify upstream-sync-round7 >/dev/null 2>&1 && \
       git merge-base --is-ancestor $ROUND7_LAST_SHA upstream-sync-round7 2>/dev/null; then
        BASE_BRANCH="upstream-sync-round7"
    else
        echo "❌ 未找到包含 Round 7 的分支"
        exit 1
    fi
fi
echo "基线分支: $BASE_BRANCH"

# A.2 创建工作分支（坑位 2 修正：一步完成，避免 detached HEAD）
if git rev-parse --verify origin/$BASE_BRANCH >/dev/null 2>&1; then
    git fetch origin $BASE_BRANCH 2>/dev/null || echo "⚠️ origin fetch $BASE_BRANCH 失败，继续尝试 checkout"
    git checkout -b merge-round8-phaseA origin/$BASE_BRANCH
elif git rev-parse --verify upstream/$BASE_BRANCH >/dev/null 2>&1; then
    git fetch upstream 2>/dev/null || echo "⚠️ upstream fetch 失败，继续尝试 checkout"
    git checkout -b merge-round8-phaseA upstream/$BASE_BRANCH
else
    git checkout $BASE_BRANCH
    git checkout -b merge-round8-phaseA
fi

# 验证非 detached HEAD
[ "$(git rev-parse --abbrev-ref HEAD)" = "HEAD" ] && echo "❌ detached HEAD!" && exit 1

# A.3 Cherry-pick
git cherry-pick dd553cd9 166aebf4 adef73c4

# A.4 检查点
git tag checkpoint-round8-phaseA

# A.5 测试（坑位 3 修正）
cd libs/deepagents && pwd && make lint && make type && make test
```

**预计时间**: ~30 分钟

---

### 🟡 **Phase B: SDK 行为/性能变更** (4个 commits)

```bash
# B.1 从 Phase A HEAD 创建分支
git checkout merge-round8-phaseA
git checkout -b merge-round8-phaseB

# B.2 normalize CRLF
git cherry-pick 69bd21e2
cd libs/deepagents && pwd && make lint && make type && make test

# B.3 FileData NotRequired (🟡 专项回归)
git cherry-pick 9862b5ad
cd libs/deepagents && pwd && make test
pytest tests/unit_tests/backends/ -v
pytest tests/unit_tests/middleware/test_summarization_middleware.py -v
cd ../evals && pwd && make test  # evals 回归

# B.4 speed up init (🟡 filesystem.py 冲突)
git cherry-pick f69761b4
# 手动解决：保留 IMAGE_EXTENSIONS, BINARY_DOC_EXTENSIONS, IMAGE_MEDIA_TYPES
# 添加常量契约注释（见文档末尾）
cd libs/deepagents && pwd && make lint && make type && make test
pytest tests/unit_tests/middleware/converters/ -v

# B.5 evict large HumanMessages (🟡 filesystem.py 冲突)
git cherry-pick 4f72c342
# 手动解决：保留 Converters 代码，接受 eviction 逻辑
cd libs/deepagents && pwd && make test
pytest tests/unit_tests/test_end_to_end.py -v -k "large"
pytest tests/unit_tests/middleware/converters/ -v

# B.6 检查点
git tag checkpoint-round8-phaseB
```

**预计时间**: ~2-3 小时

---

### 🟡 **Phase C: CLI 重构/样式/性能** (3个 commits)

```bash
# C.1 从 Phase B HEAD 创建分支
git checkout merge-round8-phaseB
git checkout -b merge-round8-phaseC

# C.2 extract format_duration
git cherry-pick f8ebf266
cd libs/cli && pwd && make lint && make type && make test

# C.3 task subagent badge (🟡 messages.py 冲突)
git cherry-pick 2e9b705f
# 手动解决：保留 _mode_color() 静态 COLORS 实现
cd libs/cli && pwd && make lint && make type && make test
pytest tests/unit_tests/test_messages.py -v

# C.4 defer /model selector (🟡 最后处理)
git cherry-pick a32ce7ff
cd libs/cli && pwd && make lint && make type && make test
pytest tests/unit_tests/test_model_selector.py -v

# C.5 UI 时序边界测试（坑位 4 修正：正确启动方式）

# 测试 1: 慢机环境
deepagents --model anthropic:claude-sonnet-4-6
# /model → 无卡顿

# 测试 2: 首次加载
deepagents --model anthropic:claude-sonnet-4-6
# /reload → /model → 无空态

# 测试 3: 无凭据（必须传 --model）
unset ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_API_KEY
deepagents --model anthropic:claude-sonnet-4-6
# /model → UI 可进入 + 凭据缺失提示（降级是正常的）

# 测试 4: 无网络（必须传 --model）
deepagents --model anthropic:claude-sonnet-4-6
# /model → 本地数据正常 + 在线拉取可能失败（降级是正常的）

# 测试 5: 延迟加载竞态
deepagents --model anthropic:claude-sonnet-4-6
# 启动后立即 /model → 不崩溃

# C.6 检查点
git tag checkpoint-round8-phaseC
```

**预计时间**: ~1.5-2 小时

---

## ✅ 最终验收标准

### L1: 持续验证 (每个 commit)

```bash
# 语法检查（推荐：覆盖完整，跨平台）
python -m compileall libs/deepagents/deepagents/ libs/cli/deepagents_cli/ -q

# 导入检查
python -c "from deepagents import create_deep_agent"
python -c "from deepagents_cli import cli_main"  # 轻量级，符合启动热路径
```

### L2: 质量门禁 (每个 commit) — **必须在包目录执行**

```bash
# SDK
cd libs/deepagents && pwd && make lint && make type && make test

# CLI
cd libs/cli && pwd && make lint && make type && make test

# Evals
cd libs/evals && pwd && make test
```

### L3: 集成测试 (每个 Phase) — **必须在包目录执行**

```bash
cd libs/deepagents && make integration_test
cd libs/cli && make integration_test
```

### L4: 功能专项验证

```bash
# Phase B: Converters + 长会话
cd libs/deepagents
pytest tests/unit_tests/test_end_to_end.py -v -k "large"
pytest tests/unit_tests/middleware/converters/ -v

# Phase B: Evals
cd libs/evals && make test

# Phase C: UI 时序（5 个场景，见 Phase C.C.5）
```

### L5: 完整验证

```bash
cd libs/deepagents && make lint && make type && make test && make integration_test
cd libs/cli && make lint && make type && make test && make integration_test
cd libs/evals && make test
cd libs/deepagents && pytest tests/unit_tests/middleware/converters/ -v
```

---

## 🎯 冲突解决策略

### 冲突 1: filesystem.py - Converters 常量

```python
# === Converters 内部契约 ===
# 契约由测试保证：tests/unit_tests/middleware/converters/
# 未来不可删除，除非同时移除 Converters 特性
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
IMAGE_MEDIA_TYPES = { ... }
BINARY_DOC_EXTENSIONS = frozenset({".pdf", ".docx", ...})
# === End Converters 内部契约 ===
```

### 冲突 2: filesystem.py - evict large HumanMessages

- 保留: Converters 相关代码
- 接受: evict large HumanMessages 逻辑
- 验收: 驱逐时机不破坏 Converters 上下文

### 冲突 3: messages.py - _mode_color()

- 保留: 静态 `COLORS` 实现（测试稳定性）
- 未来: 用"主题 → COLORS 映射层"支持主题化

---

## 📊 时间估算

| Phase | 内容 | 预计时间 | 风险 |
|-------|------|---------|------|
| **Phase 0** | Git 仓库修复 | 20 min | 🟢 |
| **Phase A** | 测试 (3个) | 30 min | 🟢 |
| **Phase B** | SDK (4个, 2冲突) | 2-3 h | 🟡 |
| **Phase C** | CLI (3个, 1冲突) | 1.5-2 h | 🟡 |
| **总计** | 10个 commits | **4-5.5 h** | 🟡 |

---

## 💡 架构师建议采纳情况

### 七轮完整审查: 28 项建议 — **100% 采纳**

| 审查轮次 | 核心改进 |
|---------|----------|
| **第一轮** | 风险分级、SDK/CLI 分段、Git 健康 |
| **第二轮** | 分支衔接、evals 回归、冷启动 |
| **第三轮** | 基线灵活、导入正确、语法可移植 |
| **逐点审查** | 基线优先级、导入说明、语法风险 |
| **坑位验证** | 默认分支一致性、detached HEAD、itest:fake 不存在 |
| **终审修正** | `symbolic-ref` 替代 `remote show`、fetch 前置于 checkout、`detect_provider` 精确范围、`BASE_BRANCH=$DEFAULT_BRANCH` 单变量链 |
| **边角打磨** | `remote set-head -a` 兜底、`fetch upstream` 说明、`ROUND7_LAST_SHA` 选择指导 |

### 终审修正详情:

| 修正点 | 内容 |
|--------|------|
| **1a** | `git symbolic-ref refs/remotes/origin/HEAD` 替代 `git remote show origin | grep 'HEAD branch'`（不依赖输出格式/语言环境，纯本地操作） |
| **1b** | `BASE_BRANCH` 初始值 = `$DEFAULT_BRANCH`，单变量链，避免两个变量并存导致混淆 |
| **2** | `git fetch origin` / `git fetch upstream` 前置于 `git checkout -b`（确保 remote ref 存在后再引用） |
| **4** | `detect_provider()` 识别范围精确化：`gpt-`/`o1`/`o3`/`o4`/`chatgpt` → openai, `claude` → anthropic, `gemini` → google, `nemotron`/`nvidia/` → nvidia |

### 边角打磨详情 (第七轮):

| 修正点 | 内容 |
|--------|------|
| **1a** | `git remote set-head origin -a` 作为 `symbolic-ref` 返回空时的可选修复（少数仓库 origin/HEAD 未设置） |
| **1b** | `git fetch upstream` 注释说明：会拉取所有 refs，如只想拉默认分支可改为 `git fetch upstream $DEFAULT_BRANCH` |
| **3** | `ROUND7_LAST_SHA` 选择标准：用 Round 7 里最能代表"本地修复已包含"的那个 commit（合并点或最后提交），避免选错中间 commit 导致误判 |

---

**报告生成时间**: 2026-03-28
**修订版本**: Execution Checklist v4 (架构师终审通过)
**架构师审查**: ✅ **七轮完整审查，已通过**
**项目状态**: ✅ **生产就绪，可直接执行**
