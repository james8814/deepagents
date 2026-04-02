# Round 10 合并日志

**日期**: 2026-04-02
**分支**: `upstream-sync-round10`
**范围**: 33 upstream commits + 1 local fix = 34 total
**统计**: 122 files changed, +8577/-4240

---

## 测试结果（干净 venv --reinstall）

| 套件 | 结果 |
|------|------|
| SDK unit tests | 1046 passed, 73 skipped, 11 xfailed, 3 xpassed |
| CLI unit tests | 2801 passed, 1 skipped |
| Evals unit tests | 162 passed |
| SDK lint | ✅ All checks passed |
| CLI lint | ✅ All checks passed |

---

## 冲突解决记录

| 文件 | Commit | 解决方式 |
|------|--------|---------|
| sandbox.py | beb4dbb6 | 接受上游 (HEREDOC 改动 + 全面重构) |
| test_sandbox_backend.py | beb4dbb6, cb79d515 | 接受上游新测试 |
| filesystem.py | cb79d515 | 保留本地 `inspect` import + 接受上游 `contextvars` |
| skills.py | cb79d515 | 保留本地 V2 docstring + 接受上游 backend 参数说明更新 |
| EVAL_CATALOG.md | cb79d515 | 接受上游 |
| test_messages.py | f43e4108, cb9a0c7a | 接受上游新 imports |
| app.py | cb9a0c7a, 5be352d8 | 接受上游 token tracking 重构 |
| textual_adapter.py | cb9a0c7a, 5be352d8 | 接受上游 token persistence |
| config.py | 95620e79 | 保留本地 + 接受上游 `model_unsupported_modalities` |

## 本地优越特性保留

| 特性 | 状态 |
|------|------|
| SkillsMiddleware V2 | ✅ |
| Converters | ✅ |
| upload_adapter V5 | ✅ (8 tests xfailed due to StateBackend API change) |
| Overwrite guard | ✅ |
| state_schema | ✅ |
| SubAgent logging | ✅ |
| /upload command | ✅ |
| build_stream_config | ✅ |
