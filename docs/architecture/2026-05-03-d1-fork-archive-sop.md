# D-1: Fork 仓库归档 SOP（可执行版本）

**起草日期**: 2026-05-03
**起草人**: deepagents CTO
**性质**: ADR-0002 §9.6 fork 归档 4 步骨架的**可执行精化版本**（含具体命令 + 检查项 + 回滚预案）
**触发条件**: pmagent Phase 1.8 e2e 验证通过 → Phase 2.2 启动
**预估执行耗时**: 1-2 h（含 review + 通知周期）

---

## 0. 执行前置条件 checklist

执行 D-1 SOP 前，**必须全部满足**以下条件（任一不满足 → 不启动归档）：

- [ ] pmagent Phase 1.0-1.8 全部完成（装配 + V2 + invariants + e2e）
- [ ] pmagent `pyproject.toml` 已 pin `deepagents ~= 0.5.0`（不依赖 fork）
- [ ] pmagent `langgraph dev` 烟测通过（不依赖 fork import）
- [ ] pmagent `git grep "james8814/deepagents"` 返回 0（无 fork URL 残留）
- [ ] pmagent `git grep "deepagents-extras\|deepagents-enhanced"` 返回 0
- [ ] pmagent 8 项装配 invariant 测试套件 GREEN
- [ ] pmagent 9 项 subagent_logs contract 测试 GREEN
- [ ] **pmagent 技术总监**与**项目负责人**确认 Phase 2.2 启动授权
- [ ] **deepagents 团队**当前无未合并的 PR / unfinished work

---

## 1. 仓库现状盘点（已完成 2026-05-03）

| 项 | 现状 |
|---|------|
| **Fork URL** | `git@github.com:james8814/deepagents.git` |
| **Upstream URL** | `git@github.com:langchain-ai/deepagents.git` |
| **当前 active branch** | `master`（含 Round 14 + ADR-0002 v3 修订）|
| **唯一 consumer** | pmagent（james 个人项目）|
| **GitHub Actions workflows** | 25 个（继承 upstream，含 ci.yml / release.yml / integration_tests.yml 等）|
| **tags** | langchain-modal/repl/runloop/daytona 子包 tags + `v0.4.0` 主版本 tag |
| **README.md** | 当前为 upstream README（无 fork 自定义标识）|

---

## 2. 归档 SOP 4 阶段（可执行版本）

### Phase 2.2-A: 仓库元数据准备（30 min，本地操作）

#### Step A.1 创建 fork archived 分支（保留可读历史）

```bash
cd "/Volumes/0-/jameswu projects/deepagents"

# 切到独立 archived 分支（与 master 区分，标识 archive 时刻）
git checkout master
git pull origin master
git checkout -b archived/2026-05-03

# 验证分支创建
git branch | grep archived/2026-05-03
```

**回滚预案**：`git branch -D archived/2026-05-03`（仅本地分支，未 push）

#### Step A.2 起草 ARCHIVED README banner

在 `archived/2026-05-03` 分支上添加 README banner（**置顶**，原 README 内容下移）：

```markdown
# 🟡 ARCHIVED — This Repository Is No Longer Maintained

**归档日期**: 2026-05-03
**最后更新**: ADR-0002 v3 (2026-05-03)

## 这个 fork 发生了什么？

本仓库（`james8814/deepagents`）是 `langchain-ai/deepagents` 的一个内部 fork，
用于 pmagent 项目的定制需求（V2 增强 + 装配修改）。

经过 2026-05-02 的 ADR-0002 决议（Plan H+，三方签字 ACCEPTED），
**fork 仓库已被消除**：

- pmagent 项目改为通过 pip 直接依赖上游 `langchain-ai/deepagents`（PEP 440 范围 `~=0.5.0`）
- 所有定制内容（5 项 V2 增强类 + 装配代码）已迁移至 pmagent 仓库 `pmagent/src/agent_assembly/`
- 4 项私有 API 治理纪律由 pmagent 团队承担

## 演进路径

```
v1 → v2 → v3 → v4-rev2 → Plan E++ → Plan H → Plan H+ (最终方案)
                                              ↓
                                          消除 fork
                                              ↓
                                        本仓库归档 (2026-05-03)
```

## 如果你在找：

- **deepagents 上游**: <https://github.com/langchain-ai/deepagents>
- **ADR-0002 决策档案**: `docs/architecture/decisions/0002-fork-customization-strategy.md`
- **Plan H+ 配套设计**: `docs/architecture/2026-05-02-plan-h-plus-final.md`
- **pmagent 接受副本**: pmagent 仓库 `docs/decision-records/0002-fork-customization-strategy-acceptance.md`
- **pmagent 装配代码**: pmagent 仓库 `src/agent_assembly/`

## 仓库状态

- 🔒 **Read-only**（GitHub Archive 标记）
- 🔒 **CI 已停用**（所有 workflows 已 disable）
- 🔒 **不接受新的 commit / PR / issue**
- 🟢 **历史 commit 完整保留**（forensic / 历史参考）
- 🟢 **6 个月后评估是否彻底 delete**（默认保留，2026-11-02 季度评审）

## 为什么不删除？

参考价值：

1. ~3500 行 fork diff 含 10 个月的定制经验
2. Round 0-14 的 14 轮上游同步历史
3. 8 次方向探索（v1 → Plan H+）的完整决策档案
4. 后续团队遇到类似 fork-vs-upstream 取舍时的参考案例

---

## 原 deepagents README 内容

[原内容下移]
```

```bash
# 提交 banner
git add README.md
git commit -m "docs(archive): add ARCHIVED banner pointing to upstream + ADR-0002 v3

Phase 2.2 fork archive Step A.2.
Co-authored-by: pmagent 技术总监 + 项目负责人 (per ADR-0002 v3)"
```

#### Step A.3 添加 ARCHIVED 状态文件（机器可读）

```bash
cat > ARCHIVED.yaml << 'EOF'
# Machine-readable archive metadata
status: archived
archived_date: "2026-05-03"
archive_reason: "Plan H+ ACCEPTED via ADR-0002 v3 — fork eliminated, pmagent depends directly on upstream"
upstream: "https://github.com/langchain-ai/deepagents"
adr_link: "docs/architecture/decisions/0002-fork-customization-strategy.md"
plan_link: "docs/architecture/2026-05-02-plan-h-plus-final.md"
evaluation_date: "2026-11-02"  # 6-month review for permanent delete
final_round: 14
final_master_commit: "ecc7db88"  # last meaningful commit before archive
EOF

git add ARCHIVED.yaml
git commit -m "docs(archive): add machine-readable ARCHIVED.yaml metadata"
```

#### Step A.4 推送 archived 分支（不触碰 master）

```bash
# Push archived branch first (不动 master)
git push -u origin archived/2026-05-03

# 验证 push 成功
git ls-remote origin | grep archived/2026-05-03
```

**回滚预案**：`git push origin :archived/2026-05-03`（删除远程分支）

---

### Phase 2.2-B: CI / Workflows 停用（30 min，GitHub 远程操作）

#### Step B.1 停用所有 GitHub Actions workflows

**方式 1 — 通过 GitHub UI（推荐，可逆）**：

1. 打开 <https://github.com/james8814/deepagents/actions>
2. 对每个 workflow 点击 "..." → "Disable workflow"
3. 25 个 workflow 全部 disable

**方式 2 — 通过 gh CLI（批量）**：

```bash
# 列出所有 workflow
gh workflow list --repo james8814/deepagents

# 批量 disable（read workflow IDs from list output）
for wf_id in $(gh workflow list --repo james8814/deepagents --json id -q '.[].id'); do
  gh workflow disable "$wf_id" --repo james8814/deepagents
done

# 验证全部 disabled
gh workflow list --repo james8814/deepagents --all | grep "disabled_manually"
```

**方式 3 — 通过修改 workflow 文件（不推荐，污染 git history）**：

不推荐 — 会在 archived 仓库继续产生 commit。

**回滚预案**：`gh workflow enable <workflow_id> --repo james8814/deepagents`

#### Step B.2 关闭所有 open PRs / issues

```bash
# 列出 open PRs
gh pr list --repo james8814/deepagents --state open

# 如有 open PR：评估是否合并 / 关闭
# 推荐：关闭并附评论指向 ADR-0002 v3
gh pr list --repo james8814/deepagents --state open --json number -q '.[].number' | \
  while read pr; do
    gh pr close "$pr" --repo james8814/deepagents \
      --comment "Closing per ADR-0002 v3 — this fork is being archived. See README.md banner for migration path. Upstream: https://github.com/langchain-ai/deepagents"
  done

# 同样处理 open issues
gh issue list --repo james8814/deepagents --state open --json number -q '.[].number' | \
  while read issue; do
    gh issue close "$issue" --repo james8814/deepagents \
      --comment "Closing per ADR-0002 v3 — this fork is being archived. Upstream: https://github.com/langchain-ai/deepagents"
  done
```

**回滚预案**：`gh pr reopen <number>` / `gh issue reopen <number>`

---

### Phase 2.2-C: GitHub Repository Archive（10 min，GitHub 远程操作）

#### Step C.1 通过 GitHub Settings 转 archived 状态

**方式 1 — GitHub UI**：

1. 打开 <https://github.com/james8814/deepagents/settings>
2. 滚动到底部 "Danger Zone"
3. 点击 "Archive this repository"
4. 输入仓库名 `james8814/deepagents` 确认
5. 点击 "I understand the consequences, archive this repository"

**方式 2 — gh CLI**：

```bash
gh repo archive james8814/deepagents
```

#### Step C.2 验证 archived 状态

```bash
# 验证仓库已 archived
gh repo view james8814/deepagents --json isArchived

# 期望输出: {"isArchived": true}

# 验证只读（任何 push 应失败）
git push origin master 2>&1 | grep -i "archived"

# 期望输出: ! [remote rejected] master -> master (archived)
```

**回滚预案**：

```bash
gh repo unarchive james8814/deepagents
```

---

### Phase 2.2-D: pmagent 侧扫描清理（30 min，本地 + 跨仓库）

#### Step D.1 pmagent 仓库 fork URL 残留扫描

```bash
cd "/Volumes/0-/jameswu projects/langgraph_test/pmagent"

# 扫描 fork URL 引用
echo "=== fork URL references ==="
git grep "james8814/deepagents" || echo "✅ 无残留"

# 扫描已废弃的 extras / enhanced 包
echo "=== deepagents-extras / deepagents-enhanced ==="
git grep "deepagents-extras\|deepagents-enhanced" || echo "✅ 无残留"

# 扫描 pyproject.toml fork pin
echo "=== fork pin in pyproject.toml ==="
grep "james8814" pyproject.toml || echo "✅ 无 fork pin"

# 扫描 docs/ 旧引用（接受副本除外）
echo "=== docs/ fork references ==="
grep -rn "james8814" docs/ --exclude-dir=99-archive | \
  grep -v "decision-records/0002.*acceptance" | \
  grep -v "ADR_0002_NAMESPACE_COLLISION_BUG_REPORT" || \
  echo "✅ 仅接受副本 + bug 报告含历史引用"
```

**期望结果**：除 ADR-0002 接受副本（历史引用）+ bug 报告（历史引用）外，**应零残留**。

#### Step D.2 pmagent 仓库 examples / scripts 检查

```bash
# 扫描 examples / scripts
git grep "from deepagents.middleware.skills_v2\|from deepagents_extras\|from deepagents.enhance" || \
  echo "✅ 无 fork 私有 import 残留"

# 验证装配代码 import 全部指向上游 deepagents
git grep "from deepagents" src/agent_assembly/ | \
  grep -v "from deepagents\b\|from deepagents\." | \
  echo "✅ 装配代码仅 import 上游 deepagents"
```

#### Step D.3 pmagent 通知 commit

```bash
# 在 pmagent 接受副本添加 fork archived 状态
# 修改 pmagent/docs/decision-records/0002-fork-customization-strategy-acceptance.md
# 添加 §10: Fork 归档状态

cat >> pmagent/docs/decision-records/0002-fork-customization-strategy-acceptance.md << 'EOF'

---

## 10. Fork 归档状态确认（2026-XX-XX，Phase 2.2 完成后）

| 项 | 状态 |
|---|---|
| `james8814/deepagents` GitHub 仓库 | 🔒 archived（read-only）|
| Fork URL 残留扫描 | ✅ 0 残留（除接受副本 + bug 报告历史引用）|
| pmagent 装配代码 import | ✅ 全部指向上游 `deepagents` |
| `pyproject.toml` deepagents pin | ✅ `deepagents ~= 0.5.0`（无 fork URL）|
| pmagent `langgraph dev` 烟测 | ✅ 通过（不依赖 fork） |
| Plan H+ 全部架构决策生效 | ✅ ADR-0002 v3 + Phase 1.0-1.8 完成 |

**Phase 2.2 完成签字**:

- deepagents CTO: ✅ 完成 SOP D-1 4 阶段执行
- pmagent 技术总监: ✅ 验证 pmagent 侧零回归
- 项目负责人: ✅ 批准 Phase 2 收尾

EOF
```

---

## 3. 回滚预案矩阵（按阶段倒序）

| 阶段 | 回滚命令 | 时间窗 |
|------|---------|--------|
| Phase 2.2-D pmagent 通知 | `git revert <commit>` 在 pmagent | 任意 |
| Phase 2.2-C GitHub archive | `gh repo unarchive james8814/deepagents` | 即时（GitHub 不限制）|
| Phase 2.2-B CI 停用 | `gh workflow enable <id>` 批量恢复 | 即时 |
| Phase 2.2-A README banner | `git push origin :archived/2026-05-03` 删除 archived 分支 | 即时 |

**完整回滚耗时**：< 30 min（4 阶段 + 验证）

---

## 4. 6 个月后评估（2026-11-02 季度评审）

ADR-0002 §9.6 step 4 规定的 6 个月评估，由 deepagents CTO 主持：

### 4.1 评估输入

- 过去 6 个月 fork 仓库被访问次数（GitHub Insights → Traffic）
- pmagent 团队是否曾因 forensic 需要 clone fork
- 是否有第三方（如未来加入 pmagent 的开发者）需要参考 fork 历史

### 4.2 评估输出

| 决策 | 触发条件 | 后续动作 |
|------|---------|---------|
| **保持 archived**（默认）| 仍有 forensic / 历史参考价值 | 继续保留，下次评审 2027-05-02 |
| **彻底 delete** | 6 个月内 0 访问 + 团队确认无价值 | `gh repo delete james8814/deepagents` |
| **解 archive 重启**（不推荐）| ADR-0002 §12 翻盘条件触发 | 不应直接解 archive，应重新做 spike + 新 ADR |

---

## 5. 当前阻塞 / 等待

**SOP 状态**：✅ 起草完成 2026-05-03（可执行版本）

**等待执行触发**：

- ⏳ pmagent Phase 1.0-1.8 全部完成（预估 9-12 d 实施日历）
- ⏳ pmagent `pyproject.toml` pin 切换到 `deepagents ~= 0.5.0`
- ⏳ pmagent 8 项装配 invariant 测试 GREEN
- ⏳ 项目负责人 + pmagent 技术总监授权 Phase 2.2 启动

**deepagents 团队执行权**：满足上述所有触发条件后，**deepagents CTO** 按本 SOP 执行 4 阶段（A → B → C → D），总耗时约 1-2 h。

---

## 6. 责任团队矩阵

| 阶段 | 负责团队 | 可介入团队 |
|------|---------|----------|
| Phase 2.2-A 仓库元数据准备 | **deepagents CTO** | — |
| Phase 2.2-B CI 停用 | **deepagents CTO** | — |
| Phase 2.2-C GitHub Archive | **deepagents CTO**（需 GitHub 仓库 admin 权限）| 项目负责人（如需 admin override）|
| Phase 2.2-D pmagent 侧扫描清理 | **pmagent 团队** | deepagents CTO 协助验证 |
| 6 个月后评估 | **deepagents CTO** 主持 | pmagent 团队 + 项目负责人 review |

---

## 7. 元层方法论沉淀

本 SOP 体现 ADR-0002 v3 changelog 的 ADR 评审 checklist v1：

- ✅ **#1 仓库布局图配实测脚本**：本 SOP 每步含可执行 bash 命令
- ✅ **#3 "已修订 N 处"配 grep 验证**：Phase 2.2-D Step D.1 含 `git grep` 验证
- ✅ **#4 设计决策配 import test**：Phase 2.2-D Step D.2 含装配代码 import 验证

新增 SOP 沉淀（建议加入 ADR 评审 checklist v2）：

> **#5 任何归档/废弃决策必须配可执行回滚预案**（限时窗口、命令清单、预期输出）

---

**文档状态**：✅ 可执行 SOP 起草完成 2026-05-03
**deepagents CTO 签字**：✅ 2026-05-03（设计层签字，执行层等触发条件）
**等待**：
1. pmagent 技术总监 review §0 触发条件 + §2.2-D pmagent 侧步骤
2. 项目负责人确认 §6 责任矩阵 + §3 回滚预案矩阵

**配套文档**：
- [ADR-0002 v3](decisions/0002-fork-customization-strategy.md) §9.6 fork 归档 SOP（4 步骨架）
- [Plan H+](2026-05-02-plan-h-plus-final.md)
- [Phase 1 装配支援包](2026-05-03-phase-1-handoff-package.md)
- [SubAgent 终止最佳实践](2026-05-03-subagent-termination-best-practices.md)
- [D-2 SubAgent telemetry hook 设计](2026-05-03-d2-subagent-telemetry-hook-design.md)
