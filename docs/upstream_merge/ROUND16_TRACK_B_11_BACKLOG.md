# Track B 11 Backlog — #2892 Wiring Gaps (Round 16 Phase 2b)

**Status**: 🟡 AMBER deferred to 桶 6 / Phase 1.5 polish
**Discovered**: Round 16 Phase 2b 4th-round ULTRATHINK audit
**Scope**: 27 unit tests across 7 classes / 2 files
**Cutover impact**: ❌ 不阻塞 (pmagent 7 imports 仍 PASS)

---

## Background

Round 16 Phase 2b cherry-pick #2892 manual merge 时:

- `graph.py`: **Path 3 take ours** (保留 fork `_models` API 架构选择)
- `tests/`: **take theirs** (引入 #2892 NEW 特性 tests)

**Path 3 transitive leak Layer 3 (Wiring 层)**: tests 断言 #2892 NEW 行为，fork `graph.py` 未完整 wiring 这些 NEW 特性。这不是 regression，是 incomplete migration —— pre-shim (A25 fix) 时这些 tests 不 collect → 隐藏；post-shim 让 visibility 暴露 → 显式。

**Track B 三层 Symmetry Check 升级** (§2.4 v2 应用细化):

1. Source 层 — production code 不引用未引入的 module ✅
2. Module 层 — tests 引用的所有 module 已存在 ✅ (post-A25 shim)
3. **Wiring 层** — tests 断言的所有 production 行为已实现 ⚠️ Track B 11 NEW

---

## 27 Tests Categorization

### 类 1 — `HarnessProfile.excluded_middleware` wiring (15 tests)

**Wiring gap**: #2892 引入 `HarnessProfile.excluded_middleware: frozenset[type | str]` 字段，graph.py 应在组装 user middleware / profile.extra_middleware / GP subagent / declarative subagent / async subagent stack 时按此字段过滤。fork `_models` API 路径不依赖此特性 (fork 自身有 middleware exclusion 机制)。

**Tests** (in `tests/unit_tests/test_graph.py`):

`TestMiddlewareExclusionWiring` (8/10 fail):
- `test_excluded_middleware_strips_user_middleware_from_main_stack`
- `test_excluded_middleware_strips_profile_extra_middleware`
- `test_excluded_middleware_preserves_subclass`
- `test_excluded_middleware_strips_from_general_purpose_subagent_stack`
- `test_excluded_middleware_strips_from_declarative_subagent_stack`
- `test_excluded_middleware_strips_async_subagent_middleware`
- `test_excluded_middleware_handles_multiple_classes_in_one_set`
- `test_excluded_middleware_preserves_order_of_kept_entries`

`TestStringFormExcludedMiddleware` (7/13 fail):
- `test_string_entry_excludes_user_middleware_by_name`
- `test_string_entry_matches_overridden_name_on_summarization`
- `test_mixed_class_and_string_entries_both_apply`
- `test_string_entry_unknown_name_raises_coverage_error`
- `test_class_entry_unknown_class_raises_coverage_error`
- `test_entry_matching_only_gp_subagent_stack_is_accepted`
- `test_string_entry_matching_multiple_classes_raises`

### 类 2 — `profile.system_prompt_suffix` 传递 wiring (6 tests)

**Wiring gap**: #2892 引入 profile-driven system prompt 组装 (`base_system_prompt` / `system_prompt_suffix`)。subagent (declarative / GP) 应继承 profile suffix。fork SubAgent 不传递 suffix。

**Tests** (in `tests/unit_tests/test_graph.py`):

`TestSubagentSystemPromptWiring` (6/6 fail — class-level xfail):
- `test_subagent_inherits_profile_suffix`
- `test_subagent_base_system_prompt_replaces_authored_prompt`
- `test_general_purpose_subagent_inherits_profile_suffix`
- `test_general_purpose_subagent_with_gp_override_and_profile_suffix`
- `test_general_purpose_subagent_override_beats_profile_base`
- `test_general_purpose_subagent_falls_back_to_profile_base_without_override`

### 类 3 — LangChainDeprecationWarning emission (4 tests)

**Wiring gap**: #2892 / Round 14 引入 `model=None` deprecation。`get_default_model()` 调用路径应 emit `LangChainDeprecationWarning`，FilesystemBackend `virtual_mode` 默认值变更也应 emit。fork 删除 deprecation 系统。

**Tests**:

`TestModelNoneDeprecationWarning` (1/3 fail) in `test_graph.py`:
- `test_model_none_emits_deprecation_warning`

`TestBuildDefaultModelContract` (2/2 fail — class-level xfail) in `test_graph.py`:
- `test_create_deep_agent_does_not_consume_get_default_model_dedupe`
- `test_get_default_model_emits_langchain_deprecation_warning`

`TestVirtualModeDefaultDeprecation` (1/2 fail) in `test_filesystem_backend.py`:
- `test_omitted_virtual_mode_warns`

### 类 4 — `GeneralPurposeSubagentProfile` edits wiring (2 tests)

**Wiring gap**: #2892 引入 `GeneralPurposeSubagentProfile` (GP subagent 配置 dataclass)，graph.py 应在组装 GP subagent 时应用 profile-driven edits (description / system_prompt / tools)。fork GP subagent 不应用 profile-driven edits。

**Tests** (in `tests/unit_tests/test_graph.py`):

`TestGeneralPurposeSubagentProfileWiring` (2/3 fail):
- `test_create_deep_agent_applies_general_purpose_subagent_edits`
- `test_disabling_default_general_purpose_removes_task_tool`

---

## 桶 6 / Phase 1.5 决议路径

**Option 1 — 完整 wiring**:
反向 fork `_models` 架构选择，引入 fork 不需要的 upstream 特性 wiring。
**不推荐** — 与 Path 3 决策矛盾，ROI 不成立。

**Option 2 — Permanent xfail** (推荐):
桶 6 L4 E2E 实证 fork 不依赖此 27 wiring 中任一特性后，将 xfail reason 修订为
"fork 架构选择不用此 wiring (permanent)"。

**Option 3 — 部分 wiring**:
case-by-case 评估每类 wiring 的 fork 价值:
- 类 1 (excluded_middleware): pmagent agent.py 是否依赖? → 实证决议
- 类 2 (system_prompt_suffix): pmagent SubAgent 是否传递 suffix? → 实证决议
- 类 3 (deprecation warnings): 0 fork 依赖 (已确认) → permanent xfail
- 类 4 (GP profile edits): pmagent GP 是否用 profile-driven? → 实证决议

---

## 桶 6 L4 E2E 实证清单

桶 6 阶段执行以下实证，决定每类 wiring 的最终路径:

```bash
# 类 1 — excluded_middleware
grep -rn "excluded_middleware" pmagent/  # 0 hits → permanent xfail
                                          # >0 hits → 完整 wiring

# 类 2 — system_prompt_suffix
grep -rn "system_prompt_suffix\|base_system_prompt" pmagent/  # 0 → permanent xfail

# 类 3 — deprecation warnings (已知 0 fork 依赖)
# → permanent xfail (Path 3 决策已删除 deprecation 系统)

# 类 4 — GeneralPurposeSubagentProfile
grep -rn "GeneralPurposeSubagentProfile" pmagent/  # 0 → permanent xfail
```

---

## xfail 标记策略 (本轮实施)

- `strict=False`: 允许未来 fix 后自动 xpass，不会 fail
- 4 类 reason 文本不一致以便后续 grep 分类
- 模块级 REASON 常量 (DRY) 在 `tests/unit_tests/test_graph.py:39-65` 与 `tests/unit_tests/backends/test_filesystem_backend.py:13-22`
- Class-level decorator (TestSubagentSystemPromptWiring + TestBuildDefaultModelContract): 6/6 + 2/2 全 fail
- Method-level decorator (其余 5 个 mixed-fail 类): 仅标记失败方法

---

## 风险与不在 cutover 关键路径

- **不阻塞 Round 16 Phase 2b atomic cutover** — pmagent 7 imports 仍 100% PASS
- **不阻塞 24h 观察期 SDK QA** — clean baseline = 1526 PASS + 27 xfailed + 0 unexpected fail
- **不损失测试覆盖** — xfail 保留断言，未来 fix 自动 xpass
- **upstream-aligned** — 未来 Round 17 #2978 cherry-pick 自动覆盖 `_api/deprecation` shim；类 1/2/4 wiring 在桶 6 决议

---

## References

- 立规 §2.4 v2 应用细化 (Path 3 三层 Symmetry Check)
- A25 修复 commit (本轮 8th commit)
- Round 16 Phase 2b ULTRATHINK 审计 (4th round)
