# Global development guidelines for the Deep Agents monorepo

This document provides comprehensive context to understand the Deep Agents Python project and assist with development.

## Project overview

Deep Agents is a batteries-included agent harness for building AI agents with planning, filesystem access, shell execution, and sub-agent spawning capabilities. It is built on top of LangGraph and provides opinionated defaults while remaining fully customizable.

### Key features

- **Planning** — `write_todos` / `read_todos` for task breakdown and progress tracking
- **Filesystem** — `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep` for reading and writing context
- **Shell access** — `execute` for running commands (with sandboxing support)
- **Sub-agents** — `task` for delegating work with isolated context windows
- **Context management** — Auto-summarization when conversations get long, large outputs saved to files
- **Provider agnostic** — Works with Claude, OpenAI, Google, or any LangChain-compatible model

### Repository layout

```
deepagents/
├── libs/
│   ├── deepagents/      # Core SDK (published as `deepagents`)
│   ├── cli/             # Terminal UI (published as `deepagents-cli`)
│   ├── acp/             # Agent Context Protocol support (published as `deepagents-acp`)
│   ├── harbor/          # Evaluation/benchmark framework (published as `deepagents-harbor`)
│   └── partners/
│       └── daytona/     # Daytona sandbox integration (published as `langchain-daytona`)
├── examples/            # Working agent examples and patterns
│   ├── deep_research/   # Multi-step web research agent
│   ├── content-builder-agent/  # Content writing with memory and skills
│   ├── text-to-sql-agent/      # Natural language to SQL
│   ├── ralph_mode/      # Autonomous looping pattern
│   └── downloading_agents/     # Agent distribution pattern
├── .github/             # CI/CD workflows and templates
└── README.md            # Information about Deep Agents
```

## Monorepo structure

This is a Python monorepo with multiple independently versioned packages using `uv` for dependency management.

### Package dependencies

```
deepagents-cli ──> deepagents
deepagents-acp ──> deepagents
deepagents-harbor ──> deepagents, deepagents-cli
langchain-daytona ──> deepagents
```

When modifying the SDK (`libs/deepagents`), you must also run CLI tests since the CLI depends on the SDK.

### Package configuration

Each package in `libs/` has its own `pyproject.toml` and `uv.lock`:

| Package | Python Version | Build System | Entry Point |
|---------|---------------|--------------|-------------|
| deepagents | >=3.11,<4.0 | setuptools | `create_deep_agent()` |
| deepagents-cli | >=3.11,<4.0 | hatchling | `deepagents`, `deepagents-cli` |
| deepagents-acp | >=3.11 | hatchling | `deepagents-acp` |
| deepagents-harbor | >=3.12 | setuptools | N/A (library) |
| langchain-daytona | >=3.11,<4.0 | hatchling | N/A (library) |

## Technology stack

- **Python**: 3.11+ (3.12+ for harbor)
- **Package manager**: `uv` — Fast Python package installer and resolver
- **Build backends**: setuptools, hatchling
- **Task runner**: `make` — See `Makefile` in each package
- **Linter/Formatter**: `ruff` — Fast Python linter and formatter
- **Type checker**: `ty` — Static type checking (CLI only)
- **Testing**: `pytest` — Testing framework with pytest-asyncio, pytest-socket, pytest-timeout
- **UI Framework**: Textual (for CLI) — Terminal UI framework

## Build and test commands

### SDK (`libs/deepagents/`)

```bash
# Run unit tests (no network)
make test

# Run integration tests (network allowed)
make integration_test

# Run tests in watch mode
make test_watch

# Run with coverage
make coverage

# Lint and format
make lint
make format

# Run specific test file
uv run --group test pytest tests/unit_tests/test_specific.py
```

### CLI (`libs/cli/`)

```bash
# Run unit tests
make test

# Run integration tests
make integration_test

# Type checking (CLI only)
make type

# Run the CLI locally
make run
# or
uvx --no-cache --reinstall .
```

### General uv commands

```bash
# Sync dependencies
uv sync --group test --locked

# Run a command with dependencies
uv run --group test pytest

# Install a package in editable mode
uv pip install -e .
```

## Code organization

### Deep Agents SDK (`libs/deepagents/deepagents/`)

```
deepagents/
├── __init__.py           # Public API exports
├── _version.py           # Version string
├── graph.py              # Main `create_deep_agent()` function
├── backends/             # Pluggable storage backends
│   ├── protocol.py       # BackendProtocol and SandboxBackendProtocol
│   ├── state.py          # StateBackend (in-memory state storage)
│   ├── filesystem.py     # FilesystemBackend (disk storage)
│   ├── store.py          # StoreBackend (LangGraph store integration)
│   ├── composite.py      # CompositeBackend (combines multiple)
│   ├── sandbox.py        # Sandbox backend utilities
│   ├── local_shell.py    # Local shell execution
│   └── utils.py          # Backend utilities
└── middleware/           # Agent middleware
    ├── filesystem.py     # FilesystemMiddleware (file tools)
    ├── memory.py         # MemoryMiddleware (AGENTS.md loading)
    ├── skills.py         # SkillsMiddleware (skill loading)
    ├── subagents.py      # SubAgentMiddleware (sub-agent spawning)
    ├── summarization.py  # SummarizationMiddleware (context management)
    └── patch_tool_calls.py  # Tool call patching middleware
```

### Deep Agents CLI (`libs/cli/deepagents_cli/`)

```
deepagents_cli/
├── __init__.py           # Public API exports
├── __main__.py           # Entry point for `python -m deepagents_cli`
├── main.py               # Main CLI entry point
├── agent.py              # Agent configuration and setup
├── app.py                # Main Textual application
├── config.py             # Configuration management
├── tools.py              # Tool definitions for CLI
├── sessions.py           # Session management
├── backends.py           # Backend configuration
├── file_ops.py           # File operations
├── ui.py                 # UI rendering logic
├── skills/               # Skills system
│   ├── commands.py       # Skill CLI commands
│   └── load.py           # Skill loading logic
├── integrations/         # Third-party integrations
│   ├── daytona.py        # Daytona sandbox
│   ├── modal.py          # Modal sandbox
│   ├── runloop.py        # Runloop sandbox
│   ├── langsmith.py      # LangSmith integration
│   └── sandbox_factory.py # Sandbox factory
└── widgets/              # Textual widgets
    ├── messages.py       # Message display
    ├── chat_input.py     # Chat input
    ├── approval.py       # Human-in-the-loop approval
    ├── tool_widgets.py   # Tool execution display
    └── ...
```

## Key architectural concepts

### Backends

Backends provide pluggable file storage and execution capabilities:

- **`BackendProtocol`**: Base protocol for file operations (read, write, edit, ls, glob, grep)
- **`SandboxBackendProtocol`**: Extends `BackendProtocol` with `execute()` for shell commands
- **`StateBackend`**: Stores files in LangGraph state (default)
- **`FilesystemBackend`**: Stores files on local disk
- **`StoreBackend`**: Uses LangGraph store for persistence
- **`CompositeBackend`**: Combines multiple backends with priority ordering
- **`LocalShellBackend`**: Executes shell commands locally

### Middleware

Middleware wraps agent execution to add capabilities:

- **`TodoListMiddleware`**: Manages todo lists for planning
- **`FilesystemMiddleware`**: Adds file operation tools
- **`SubAgentMiddleware`**: Enables sub-agent spawning via `task` tool
- **`SummarizationMiddleware`**: Auto-summarizes long conversations
- **`MemoryMiddleware`**: Loads `AGENTS.md` files into context
- **`SkillsMiddleware`**: Loads and injects skill files

### Sub-agents

Sub-agents allow delegation to specialized agents:

```python
SubAgent = {
    "name": str,
    "description": str,
    "prompt": str,
    "tools": list[BaseTool],
    "model": BaseChatModel,
    "middleware": list[AgentMiddleware]
}
```

### Skills

Skills are reusable capabilities defined in `SKILL.md` files with YAML frontmatter:

```markdown
---
name: skill-name
description: What this skill does
---

# Skill instructions in markdown...
```

Skills are loaded from backend sources (paths) and injected into the system prompt.

## Code style guidelines

### General rules

- All Python code MUST include type hints and return types
- Use descriptive, self-explanatory variable names
- Follow existing patterns in the codebase
- Break up complex functions (>20 lines) into smaller, focused functions
- Avoid using the `any` type
- Prefer single word variable names where possible
- Use American English spelling (e.g., "behavior", not "behaviour")

### Imports

```python
# Standard library
from collections.abc import Callable
from typing import Any

# Third-party
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

# First-party
from deepagents.backends import StateBackend
```

### Docstrings

Use Google-style docstrings with Args section for all public functions:

```python
def send_email(to: str, msg: str, *, priority: str = "normal") -> bool:
    """Send an email to a recipient with specified priority.

    Any additional context about the function can go here.

    Args:
        to: The email address of the recipient.
        msg: The message body to send.
        priority: Email priority level.

    Returns:
        `True` if email was sent successfully, `False` otherwise.

    Raises:
        InvalidEmailError: If the email address format is invalid.
        SMTPConnectionError: If unable to connect to email server.
    """
```

Notes:
- Types go in function signatures, NOT in docstrings
- If a default is present, DO NOT repeat it in the docstring
- Use single backticks (`` `code` ``) for inline code references, NOT Sphinx-style double backticks
- Focus on "why" rather than "what" in descriptions

### Ruff configuration

Each package has its own ruff configuration in `pyproject.toml`:

- Line length: 150 (deepagents), 100 (acp, harbor)
- Google-style docstrings: `convention = "google"`
- First-party packages recognized for import sorting

## Testing instructions

### Test structure

```
tests/
├── unit_tests/           # No network calls allowed
│   ├── backends/         # Backend tests
│   └── middleware/       # Middleware tests
└── integration_tests/    # Network calls permitted
```

### Unit tests

- Run with: `make test` or `uv run --group test pytest -vvv --disable-socket --allow-unix-socket tests/unit_tests/`
- No network calls allowed (enforced by `pytest-socket`)
- Tests should be deterministic (no flaky tests)
- Avoid mocks as much as possible
- Test actual implementation, do not duplicate logic into tests

### Integration tests

- Run with: `make integration_test` or `uv run --group test pytest -n auto -vvv --timeout 30 tests/integration_tests/`
- Network calls permitted
- Uses pytest-xdist for parallel execution (`-n auto`)
- 30-second timeout per test

### Writing tests

```python
# Example test structure
def test_feature_happy_path() -> None:
    """Test the happy path of feature X."""
    # Arrange
    input_data = ...
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```

Checklist for new tests:
- [ ] Tests fail when your new logic is broken
- [ ] Happy path is covered
- [ ] Edge cases and error conditions are tested
- [ ] Use fixtures/mocks for external dependencies
- [ ] Tests are deterministic (no flaky tests)

## Development workflow

### Setup

1. Install `uv`: https://docs.astral.sh/uv/getting-started/installation/
2. Clone the repository
3. Navigate to a package directory: `cd libs/deepagents`
4. Sync dependencies: `uv sync --group test --locked`

### Making changes

1. Create a feature branch
2. Make your changes
3. Run tests: `make test`
4. Run linting: `make lint`
5. Run formatting: `make format`
6. Commit with a conventional commit message

### Pre-commit hooks

The repository uses pre-commit hooks for code quality:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## CI/CD

### GitHub Actions workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR, push to master | Run linting and tests on changed packages |
| `_lint.yml` | Called by ci.yml | Reusable linting workflow |
| `_test.yml` | Called by ci.yml | Reusable testing workflow |
| `pr_lint.yml` | PR edit/open | Validate PR title follows Conventional Commits |
| `release-please.yml` | Push to master | Automated releases |

### CI behavior

- Only packages with changes are tested
- SDK changes also trigger CLI tests
- Pushes to master run full CI
- Python version matrix: 3.11, 3.12, 3.13, 3.14

### PR title format (Conventional Commits)

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types**: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert, release, hotfix

**Scopes**: deepagents, sdk, deepagents-cli, cli, harbor, acp, examples, infra, deps, daytona

**Examples**:
- `feat(sdk): add multi-agent support`
- `fix(cli): resolve flag parsing error`
- `docs: update API usage examples`

**Rules**:
1. Type must start with lowercase
2. Breaking changes: append `!` after type/scope (e.g., `feat!: drop x support`)
3. Release commits: `release(scope): x.y.z`
4. PR titles should include a scope (with exceptions for docs-only changes)
5. All PR titles should be lowercase except for proper nouns

## Release process

The project uses `release-please` for automated releases:

1. Merging a PR with conventional commit triggers release-please
2. Release-please creates a release PR with changelog updates
3. Merging the release PR creates a GitHub release
4. The release workflow publishes to PyPI

### Version management

- Versions are stored in `pyproject.toml` and `_version.py`
- `release-please-config.json` configures the release behavior
- Tag format: `deepagents-cli==0.0.19` (component included)

## Security considerations

- **No `eval()`, `exec()`, or `pickle` on user-controlled input**
- Proper exception handling (no bare `except:`)
- Use a `msg` variable for error messages
- Remove unreachable/commented code before committing
- Check for race conditions or resource leaks
- Ensure proper resource cleanup (file handles, connections)
- Deep Agents follows a "trust the LLM" model — enforce boundaries at the tool/sandbox level

## Maintaining stable public interfaces

**CRITICAL**: Always attempt to preserve function signatures, argument positions, and names for exported/public methods. Do not make breaking changes.

**Before making ANY changes to public APIs:**
- Check if the function/class is exported in `__init__.py`
- Look for existing usage patterns in tests and examples
- Use keyword-only arguments for new parameters: `*, new_param: str = "default"`
- Mark experimental features clearly with docstring warnings (using MkDocs Material admonitions, like `!!! warning`)

**Ask**: "Would this change break someone's code if they used it last week?"

## Package-specific guidance

### Deep Agents CLI

`deepagents-cli` uses [Textual](https://textual.textualize.io/) for its terminal UI framework.

**Key Textual resources:**
- **Guide:** https://textual.textualize.io/guide/
- **Widget gallery:** https://textual.textualize.io/widget_gallery/
- **CSS reference:** https://textual.textualize.io/styles/
- **API reference:** https://textual.textualize.io/api/

**Textual patterns used:**
- **Workers** (`@work` decorator) for async operations
- **Message passing** for widget communication
- **Reactive attributes** for state management

**Testing Textual apps:**
- Use `textual.pilot` for async UI testing
- Snapshot testing available for visual regression

### Deep Agents ACP

The ACP (Agent Client Protocol) package provides integration with editors like Zed.

- Entry point: `run.sh` shell script
- Configuration: `.env` file for API keys
- Zed integration: Add to `settings.json` under `agent_servers`

### Deep Agents Harbor

Harbor is an evaluation framework for benchmarking agents.

- Uses `harbor` CLI for running benchmarks
- Integrates with LangSmith for tracing
- Supports multiple sandbox environments (Docker, Daytona, Modal, Runloop)
- Default benchmark: Terminal Bench 2.0

## Documentation

- **Documentation site**: https://docs.langchain.com/oss/python/deepagents/overview
- **API Reference**: https://reference.langchain.com/python/deepagents/
- **Contributing Guide**: https://docs.langchain.com/oss/python/contributing/overview
- **Local docs**: Check `../docs/` if available locally

## Contributing checklist

When submitting a PR:

- [ ] Add a disclaimer to the PR description mentioning AI agent involvement
- [ ] Describe the "why" of the changes
- [ ] Highlight areas requiring careful review
- [ ] Follow Conventional Commits format for PR title
- [ ] Ensure all tests pass
- [ ] Ensure linting passes
- [ ] Update documentation if needed
- [ ] Update AGENTS.md if changing development workflows or architecture

## Useful links

- **LangGraph docs**: https://docs.langchain.com/oss/python/langgraph/overview
- **LangChain docs**: https://python.langchain.com/
- **UV documentation**: https://docs.astral.sh/uv/
- **Textual documentation**: https://textual.textualize.io/
