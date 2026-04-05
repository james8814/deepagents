# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deep Agents is a batteries-included AI agent harness built on LangGraph. It provides planning, filesystem access, shell execution, and sub-agent spawning capabilities out of the box.

**Documentation**: https://docs.langchain.com/oss/python/deepagents/overview

## Monorepo Structure

```
deepagents/
├── libs/
│   ├── deepagents/      # Core SDK (published as `deepagents`)
│   ├── cli/             # Terminal UI (published as `deepagents-cli`)
│   ├── acp/             # Agent Context Protocol (published as `deepagents-acp`)
│   ├── harbor/          # Evaluation/benchmark framework
│   └── partners/daytona/ # Daytona sandbox integration
├── examples/            # Working agent examples
└── docs/                # Technical documentation
```

**Package Dependencies**:
```
deepagents-cli ──> deepagents
deepagents-acp ──> deepagents
deepagents-harbor ──> deepagents, deepagents-cli
langchain-daytona ──> deepagents
```

When modifying `libs/deepagents`, you must also run CLI tests since the CLI depends on the SDK.

## Build & Test Commands

Navigate to the package directory (`cd libs/deepagents` or `cd libs/cli`) then:

```bash
# Unit tests (no network)
make test
uv run --group test pytest -vvv --disable-socket --allow-unix-socket tests/unit_tests/

# Integration tests (network allowed, 30s timeout, parallel)
make integration_test
uv run --group test pytest -n auto -vvv --timeout 30 tests/integration_tests/

# Run specific test file
make test TEST_FILE=tests/unit_tests/middleware/test_skills.py

# Run tests in watch mode
make test_watch

# Run benchmark tests
make benchmark

# Lint and format
make lint
make format

# Type checking (CLI only - SDK does not use type checking)
make type

# Coverage
make coverage
```

**Pre-commit hooks**: Run `pre-commit install` to install. Hooks run format/lint on commit.

## Architecture

### Core SDK (`libs/deepagents/deepagents/`)

**Main entry point**: `create_deep_agent()` in `graph.py`

**SDK version**: 0.5.0 / **CLI version**: 0.0.34

**Default model**: `claude-sonnet-4-6`

**Middleware Stack** (execution order in `create_deep_agent`):
1. `TodoListMiddleware` - `write_todos` / `read_todos`
2. `SkillsMiddleware` (optional) - Loads `SKILL.md` metadata (progressive disclosure)
3. `FilesystemMiddleware` - File ops: `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`
4. `SubAgentMiddleware` - `task` tool for spawning sub-agents
5. `SummarizationMiddleware` - Auto-summarization at 85% context or 100k tokens
6. `PatchToolCallsMiddleware` - Fixes dangling tool calls
7. `AsyncSubAgentMiddleware` (optional) - Remote LangGraph server async sub-agents
8. User-provided middleware (appended)
9. `AnthropicPromptCachingMiddleware` - Prompt caching (after user middleware to preserve cache prefix)
10. `MemoryMiddleware` (optional) - Loads `AGENTS.md` into system prompt (last to avoid cache invalidation)
11. `HumanInTheLoopMiddleware` (optional) - Tool approval before execution

**File Uploads**: Files uploaded via CLI `/upload <path>` command are stored in `/uploads/`. The upload system includes:
- **Security validation**: File type detection using magic bytes (via `puremagic`), 100MB size limit, unauthorized type blocking
- **Type-specific guidance**: After upload, CLI shows guidance based on file type:
  - Text files: Use `ls /uploads` and `read_file` to access
  - Binary documents (PDF/DOCX/XLSX/PPTX): Use `read_file` directly — auto-converts to Markdown (requires `pip install deepagents[converters]`)
  - Images (.png/.jpg/.gif/.webp): `read_file` returns multimodal ImageBlock
  - Archives: Use `execute` with `unzip`, `tar`, etc.
  - Audio/Video: Use `execute` with external tools
- **Large file handling**: Tool results >20k tokens are written to `/large_tool_results/{tool_call_id}`

**Binary Document Conversion** (2026-03-13): `read_file` auto-converts binary documents via built-in Converters:
- Formats: PDF (pdfplumber), DOCX (python-docx), XLSX (openpyxl), PPTX (python-pptx)
- Flow: `download_files()` → tempfile → `detect_mime_type()` → `registry.get()` → `converter.convert()` → Markdown
- Pagination: `offset=N` (N>0) maps to `convert_page(page=N)` for PDF/PPTX (1-indexed)
- Install: `pip install deepagents[converters]`
- Implementation: `_convert_document_sync/async` in `filesystem.py` lines 414-570
- Tests: `tests/unit_tests/middleware/converters/test_converter_integration.py` (23 tests)

**Backends** (pluggable storage/execution):
- `BackendProtocol` - Base protocol: `ls`, `read`, `write`, `edit`, `grep`, `glob` (renamed from `ls_info`/`grep_raw`/`glob_info` in v0.5.0)
  - Return types: `LsResult`, `ReadResult`, `WriteResult`, `EditResult`, `GrepResult`, `GlobResult` (dataclasses with `error` field + result field)
  - Old method names (`ls_info`, `grep_raw`, `glob_info`) still work via deprecation shim
- `SandboxBackendProtocol` - Extends with `execute()` and `id` property
- `StateBackend` - In-memory via LangGraph state (default, ephemeral)
- `FilesystemBackend` - Local disk storage
- `StoreBackend` - LangGraph store persistence (cross-session)
- `LocalShellBackend` - Local shell execution
- `CompositeBackend` - Routes by path prefix (longest-match wins)

**Backend Instantiation** (v0.5.0+, factory pattern deprecated):
```python
# Direct instance — no runtime parameter needed
backend = StateBackend()
# Or for filesystem
backend = FilesystemBackend(root_dir="/workspace")
```

**CompositeBackend Routing**:
```python
composite = CompositeBackend(
    default=StateBackend(),
    routes={
        "/memories/": StoreBackend(),
        "/conversation_history/": fs_backend,
    }
)
```

### Sub-Agent Mechanism (`subagents.py`)

**State Isolation**: When invoking sub-agents, these keys are excluded from parent state:
```python
_EXCLUDED_STATE_KEYS = {
    "messages", "todos", "structured_response",
    "skills_metadata", "memory_contents", "subagent_logs",
    "skills_loaded", "skill_resources", "_summarization_event",
}
```

Note: All `PrivateStateAttr` fields must be in this set. `astream(stream_mode="values")` uses
`stream_channels` which does NOT respect `PrivateStateAttr` output filtering (unlike `invoke()`),
so explicit exclusion is required to prevent `InvalidUpdateError` with parallel sub-agents.

**General-Purpose Subagent**: Always created by default with its own middleware stack (TodoList, Filesystem, Summarization, AnthropicCache, PatchToolCalls).

**Task Tool Flow**:
1. Main agent calls `task(description, subagent_type)`
2. `SubAgentMiddleware` filters state, injects `HumanMessage(description)`
3. Sub-agent runs independently with its own middleware
4. Final message extracted as `ToolMessage` returned to parent

### Async Sub-Agent Mechanism (`async_subagents.py`) — v0.5.0

**Purpose**: Connect to remote LangGraph servers for asynchronous sub-agent execution.

**Tools provided** (5):
- `start_async_task` — Create remote thread + run, returns task_id immediately
- `check_async_task` — Query task status and result
- `update_async_task` — Send follow-up instructions
- `cancel_async_task` — Terminate running task
- `list_async_tasks` — List all tasks and their status

**State field**: `async_subagent_tasks` — persists across context compaction. Each task tracks `task_id`, `agent_name`, `status`, `created_at`, `updated_at`.

**Usage**: Pass async subagent specs in the unified `subagents` parameter (identified by `graph_id` field):
```python
create_deep_agent(subagents=[
    {"name": "sync-agent", "description": "...", "system_prompt": "..."},       # SubAgent
    {"name": "remote-agent", "description": "...", "graph_id": "my-graph"},     # AsyncSubAgent
])
```

**Export**: `from deepagents import AsyncSubAgent, AsyncSubAgentMiddleware`

### Skills System (`skills.py`)

**Structure**:
```
/skills/user/web-research/
├── SKILL.md          # YAML frontmatter + instructions
└── helper.py         # Optional supporting files
```

**SKILL.md Format**:
```yaml
---
name: web-research
description: Structured approach to web research
license: MIT
---
```

**V2 Features** (SkillsMiddleware V2 - 2026-02-18):
- **`load_skill` tool**: Load full skill instructions and discover resources
- **`unload_skill` tool**: Unload skill to free up context space
- **`[Loaded]` marker**: System prompt shows which skills are loaded
- **Context budget**: `max_loaded_skills=10` limits simultaneously loaded skills
- **Resource discovery**: Auto-scans `scripts/`, `references/`, `assets/` directories
- **`expose_dynamic_tools`**: `bool = False` — controls whether `load_skill`/`unload_skill` tools are exposed
- **`allowed_skills`**: `list[str] | None = None` — optional allowlist to filter visible skills by name

**Per-SubAgent Skill Filtering** (2026-03-07):
- `SubAgent` TypedDict has `skills_allowlist: NotRequired[list[str]]` field
- `create_deep_agent` wires `skills_allowlist` into `SkillsMiddleware(allowed_skills=...)`
- Enables per-SubAgent skill visibility: e.g., research_agent sees 4 skills, analysis_agent sees 6
- Default `None` preserves directory-level scan behavior (backward compatible)

**Progressive Disclosure**: Only metadata (name + description) injected at startup. Agent reads full `SKILL.md` via `load_skill()` when needed.

**Source Priority**: Later sources override earlier for same skill name (last one wins).

**V2 State Fields**:
- `skills_loaded`: List of loaded skill names
- `skill_resources`: Cached resource metadata per skill

### CLI (`libs/cli/deepagents_cli/`)

**Entry Point**: `create_cli_agent()` in `agent.py`

Textual-based terminal UI with:
- `app.py` - Main Textual application
- `widgets/` - UI components (messages, chat_input, approval, tool_widgets)
- `integrations/` - Third-party (daytona, modal, runloop, langsmith)
- `skills/` - Skills system
- `backends.py` - `CLIShellBackend` with per-command timeout support

**HITL Tool Approval** (when `auto_approve=False`):
- `execute`, `write_file`, `edit_file`, `web_search`, `fetch_url`, `task`
- Custom description formatters for each tool

**HITL Approval Flow**: When `interrupt_on` includes a tool, the UI shows an approval dialog before execution. User can approve, deny, or edit the tool call.

**Local vs Remote Mode**:
- **Local**: `CLIShellBackend` + `FilesystemBackend` + `LocalContextMiddleware`
- **Remote**: Sandbox backend (Modal/Daytona/Runloop) handles file ops + execute

**CLI Environment Variables** (2026-03-29):

- `DEEPAGENTS_CLI_` prefix: `DEEPAGENTS_CLI_{NAME}` takes priority over `{NAME}`. Resolved via `resolve_env_var()` in `model_config.py`.
- Priority: `DEEPAGENTS_CLI_X` > shell export `X` > project `.env` > `~/.deepagents/.env`
- Empty prefix var (`DEEPAGENTS_CLI_X=""`) shields the canonical var — `resolve_env_var` returns `None`.
- Registry: All `DEEPAGENTS_CLI_*` constants defined in `deepagents_cli/_env_vars.py` with drift-detection test.

**Global Dotenv** (2026-03-29): `~/.deepagents/.env` loaded as fallback after project `.env`. Both use `override=False` — shell exports always win.

**Agent Management** (2026-03-29): `list` and `reset` commands moved under `agents` subcommand:

- `deepagents agents list [--json]`
- `deepagents agents reset --agent NAME [--target SRC] [--dry-run]`

**Agent-Friendly UX** (2026-03-29): `--stdin` for explicit pipe detection, `--dry-run` for destructive commands, `SystemExit(1)` for error exits in scripted mode.

**ShellAllowListMiddleware** (2026-03-29): Validates shell commands inline for non-interactive mode, returns error `ToolMessage` for rejected commands instead of pausing the graph. Eliminates trace fragmentation.

**Qwen/DashScope Support** (content-builder-agent):
```bash
export DASHSCOPE_API_KEY="your-key"
export MODEL_PROVIDER="dashscope"
export DASHSCOPE_MODEL="qwen-plus"
./run_test_env.sh "Your task"
```

### Summarization (`summarization.py`)

**Storage**: `/conversation_history/{thread_id}.md` (appended on each summarization event)

**Environment Variables**:
- `DEEPAGENTS_FALLBACK_TRIGGER_TOKENS` (default: 100,000)
- `DEEPAGENTS_FALLBACK_KEEP_MESSAGES` (default: 6)

**Argument Truncation**: Configurable via `truncate_args_settings` - truncates `write_file`/`edit_file` args in old messages before summarization.

## Code Style

- **Type hints required** on all functions (avoid `Any`)
- **Google-style docstrings** with Args section
- **Line length**: 150 (deepagents), 100 (cli/acp/harbor)
- **American English** spelling
- **Single backticks** for inline code in docstrings

```python
def send_email(to: str, msg: str, *, priority: str = "normal") -> bool:
    """Send an email to a recipient with specified priority.

    Args:
        to: The email address of the recipient.
        msg: The message body to send.
        priority: Email priority level.

    Returns:
        `True` if email was sent successfully, `False` otherwise.
    """
```

### Exception Handling Pattern

Follow these rules for exception handling:

1. **Always define error messages as variables before raising** (EM101/EM102 compliance)
2. **Always preserve exception chains with `raise ... from err`**
3. **Prefer specific exception types over broad `Exception` catches**

```python
# Good: Message variable, specific exception, chain preserved
try:
    with file_path.open("rb"):
        pass
except FileNotFoundError as err:
    msg = f"File not found: {path}"
    raise ValidationError(msg) from err
except IsADirectoryError as err:
    msg = f"Not a file: {path}"
    raise ValidationError(msg) from err
except OSError as err:
    msg = f"File access error: {path}"
    raise ValidationError(msg) from err

# Bad: Inline message, no exception chain
raise ValidationError(f"File not found: {path}")
```

**Rationale**:
- Variables make messages reusable (e.g., for logging)
- Exception chains preserve debugging context
- Specific exceptions improve error handling granularity

## Testing Guidelines

**Test structure**:
- `tests/unit_tests/` - No network calls (enforced by `pytest-socket`)
- `tests/integration_tests/` - Network allowed, 30s timeout, parallel execution

**Test patterns**:
- Use fixtures/mocks for external dependencies
- Tests must be deterministic (no flaky tests)
- Avoid mocks when possible; test actual implementation
- Mark with appropriate pytest markers if needed

## CI/CD

**PR title format** (Conventional Commits):
```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
Scopes: `deepagents`, `sdk`, `deepagents-cli`, `cli`, `harbor`, `acp`, `examples`, `deps`, `daytona`

## Public API Stability

**CRITICAL**: Preserve function signatures, argument positions, and names for exported APIs.

- Check `__init__.py` exports before making changes
- Use keyword-only arguments for new parameters: `*, new_param: str = "default"`
- Mark experimental features with `!!! warning` in docstrings

## Security

**"Trust the LLM" Model**: Deep Agents follows a trust-the-LLM model. Enforce boundaries at the tool/sandbox level, not by expecting the model to self-police.

**Path Traversal Protection** (`FilesystemBackend.virtual_mode`):
- Prohibits `..` and `~` traversal
- All paths must resolve within `root_dir`
- Uses `os.O_NOFOLLOW` to prevent symlink attacks

**Sandbox Isolation**:
- **Remote** (Daytona/Modal/Runloop): Strong isolation in containers
- **Local** (`CLIShellBackend`): No isolation - use with HITL approval

**HITL Approval**: Configure `interrupt_on` in `create_deep_agent()` for destructive tools (`execute`, `write_file`, `edit_file`).

**Standardized Error Codes**: `file_not_found`, `permission_denied`, `is_directory`, `invalid_path` - LLM-actionable error reporting.

## Key Implementation Details

**File Result Eviction** (`FilesystemMiddleware`): Tool results >20k tokens are written to `/large_tool_results/{tool_call_id}` with preview + file reference.

**HumanMessage Eviction** (2026-03-28, `FilesystemMiddleware`): HumanMessages exceeding `human_message_token_limit_before_evict` (default 50k tokens) are written to `/conversation_history/{uuid}` and replaced with a truncated preview. Tagged via `lc_evicted_to` in `additional_kwargs`. Controlled by `human_message_token_limit_before_evict` parameter on `FilesystemMiddleware`.

**FileData NotRequired** (2026-03-28): `FileData.created_at` and `FileData.modified_at` are now `NotRequired[str]`. External code constructing `FileData` no longer needs to supply these fields. `create_file_data()` still works but internal code prefers direct `FileData()` construction.

**CRLF Normalization** (2026-03-28): `FilesystemBackend.edit()` normalizes `\r\n` and `\r` to `\n` in both `old_string` and `new_string` before matching.

**Backend Factory Deprecation** (2026-04-02): `StateBackend(runtime)` factory pattern is deprecated. Use `StateBackend()` directly — runtime is now injected internally by middleware. The `backend` parameter on `create_deep_agent` accepts instances only, not callables.

**OpenAI-Compatible Model Resolution** (2026-04-02): `resolve_model()` in `_models.py` auto-disables Responses API when `OPENAI_BASE_URL` points to non-OpenAI endpoints (DeepSeek, Qwen, etc.).

**Token Persistence** (2026-04-02): CLI persists token count in graph state across sessions via `token_state.py`. Token display shows "+" suffix for approximate/interrupted counts.

**http_request Tool Removed** (2026-04-02): The `http_request` tool has been removed from the CLI agent.

**Legacy SubAgent API Removed** (2026-04-05): `_get_subagents_legacy()` and related deprecated kwargs (`SubAgentKwargs`, `CompiledSubAgent` TypedDict with `Unpack`) removed from upstream. Local backward-compat shim retained: `SubAgentMiddleware` still accepts `default_model`/`default_tools` with `DeprecationWarning`, but new code should use the new API (`backend=..., subagents=[...]`).

**SubAgent interrupt_on Inheritance** (2026-04-05): Declarative `SubAgent` specs now inherit the parent agent's `interrupt_on` config by default. Opt-out: set `interrupt_on: {}` on the SubAgent spec. `CompiledSubAgent` and `AsyncSubAgent` do not inherit.

**SubAgent Config Forwarding** (2026-04-05): Parent `RunnableConfig` (including `configurable`, `callbacks`, `metadata`) is now forwarded to SubAgent invocations via `_forward_parent_config()`. This ensures LangSmith trace continuity and checkpointer access in subagents.

**PrivateStateAttr Exclusion** (2026-04-05): `_EXCLUDED_STATE_KEYS` in `subagents.py` expanded to include `subagent_logs`, `skills_loaded`, `skill_resources`, `_summarization_event`. All `PrivateStateAttr` fields must be in this set to prevent `InvalidUpdateError` with parallel sub-agents.

**Message ID Requirement**: All messages must have IDs for proper state management (see `_ensure_message_ids` in summarization).

**Backend Download vs Read**: Use `download_files()` for raw content (editing), `read()` returns line-numbered format (for LLM consumption).

**StateBackend Uploads**: Use `upload_files()` from `deepagents.upload_adapter` for universal file upload support.

**Thread ID Extraction**: Summarization extracts `thread_id` from LangGraph config, falls back to generated session ID.

**SkillsMiddleware V2** (2026-02-18, enhanced 2026-03-07):
- Full implementation: `docs/skillsmiddleware_docs/SkillsMiddleware_V2_核查报告.md`
- Design document: `docs/skillsmiddleware_docs/DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md`
- Key changes: `libs/deepagents/deepagents/middleware/skills.py` (+442 lines)
- CLI compatibility: Fully backward compatible, no changes required
- External team guide: `docs/api/EXTERNAL_TEAM_API_GUIDE.md`
- Review report: `docs/integrations/skills/v2_review_report.md`
- Dynamic loading guide: `docs/integrations/skills/dynamic_loading_guide.md`

**Upload Adapter V5.0** (2026-02-27):
- Location: `libs/deepagents/deepagents/upload_adapter.py`
- Purpose: Universal file upload for any backend
- Features: Auto strategy selection, overwrite detection, WeakKeyDictionary locks
- Export: `from deepagents import upload_files, UploadResult`
- Guide: `docs/UPLOAD_ADAPTER_GUIDE.md`

## Key Links

- **LangGraph docs**: https://docs.langchain.com/oss/python/langgraph/overview
- **API Reference**: https://reference.langchain.com/python/deepagents/
- **Textual docs** (for CLI): https://textual.textualize.io/
- **UV docs**: https://docs.astral.sh/uv/

**V2 Documentation**:
- **SkillsMiddleware V2 Design**: `docs/skillsmiddleware_docs/DeepAgents_SkillsMiddleware_V2_升级设计方案_final.md`
- **V2 Verification Report**: `docs/skillsmiddleware_docs/SkillsMiddleware_V2_核查报告.md`
- **Phase 3 Code Review**: `docs/skillsmiddleware_docs/Phase3_CodeReview_Report.md`
- **SDK Upgrade Guide**: `docs/api/SDK_UPGRADE_GUIDE.md`

**V5.0 Upload Adapter Documentation**:
- **User Guide**: `docs/UPLOAD_ADAPTER_GUIDE.md`
- **Implementation**: `docs/attachment_function_docs/UNIVERSAL_UPLOAD_ADAPTER_V5.md`
- **Final Report**: `docs/attachment_function_docs/FINAL_DELIVERY_REPORT.md`

**Converter Integration Documentation** (2026-03-13):
- **Changelog**: `CHANGELOG_CONVERTER_INTEGRATION.md`
- **API Reference (Converter 章节)**: `docs/api/API_REFERENCE.md`
- **Design Document**: `docs/unified_file_reader/UNIFIED_FILE_READER_DESIGN.md`
- **Migration Plan V3.1**: `docs/tmp/converter-migration-plan-v3.md`
