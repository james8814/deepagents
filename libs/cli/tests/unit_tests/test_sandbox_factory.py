"""Tests for sandbox factory optional dependency handling."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from deepagents_cli.integrations.sandbox_factory import (
    _get_provider,
    verify_sandbox_deps,
)


@pytest.mark.parametrize(
    ("provider", "package"),
    [
        ("daytona", "langchain-daytona"),
        ("modal", "langchain-modal"),
        ("runloop", "langchain-runloop"),
    ],
)
def test_get_provider_raises_helpful_error_for_missing_optional_dependency(
    provider: str,
    package: str,
) -> None:
    """Provider construction should explain which CLI extra to install."""
    error = (
        rf"The '{provider}' sandbox provider requires the "
        rf"'{package}' package"
    )
    with (
        patch(
            "deepagents_cli.integrations.sandbox_factory.importlib.import_module",
            side_effect=ImportError("missing dependency"),
        ),
        pytest.raises(ImportError, match=error),
    ):
        _get_provider(provider)


class TestVerifySandboxDeps:
    """Tests for the early sandbox dependency check."""

    @pytest.mark.parametrize(
        ("provider", "expected_module"),
        [
            ("daytona", "langchain_daytona"),
            ("modal", "langchain_modal"),
            ("runloop", "langchain_runloop"),
        ],
    )
    def test_raises_import_error_when_backend_missing(
        self, provider: str, expected_module: str
    ) -> None:
        """Should raise ImportError with install instructions."""
        mock_find_spec = patch(
            "deepagents_cli.integrations.sandbox_factory.importlib.util.find_spec",
            return_value=None,
        )
        with (
            mock_find_spec as find_spec,
            pytest.raises(
                ImportError,
                match=rf"Missing dependencies for '{provider}' sandbox.*"
                rf"pip install 'deepagents-cli\[{provider}\]'",
            ),
        ):
            verify_sandbox_deps(provider)

        find_spec.assert_called_once_with(expected_module)

    @pytest.mark.parametrize(
        "provider",
        ["daytona", "modal", "runloop"],
    )
    def test_passes_when_backend_installed(self, provider: str) -> None:
        """Should not raise when the backend module is found."""
        spec_sentinel = object()
        with patch(
            "deepagents_cli.integrations.sandbox_factory.importlib.util.find_spec",
            return_value=spec_sentinel,
        ):
            verify_sandbox_deps(provider)  # should not raise

    @pytest.mark.parametrize(
        "exc_cls",
        [ImportError, ValueError],
    )
    def test_raises_when_find_spec_throws(self, exc_cls: type) -> None:
        """find_spec can raise ImportError/ValueError in corrupted envs."""
        with (
            patch(
                "deepagents_cli.integrations.sandbox_factory.importlib.util.find_spec",
                side_effect=exc_cls("broken"),
            ),
            pytest.raises(ImportError, match="Missing dependencies"),
        ):
            verify_sandbox_deps("daytona")

    @pytest.mark.parametrize("provider", ["none", "langsmith", "", None])
    def test_skips_builtin_and_empty_providers(self, provider: str | None) -> None:
        """Built-in and empty providers should be silently accepted."""
        verify_sandbox_deps(provider)  # type: ignore[arg-type]

    def test_skips_unknown_provider(self) -> None:
        """Unknown providers are passed through for downstream handling."""
        verify_sandbox_deps("unknown_provider")  # should not raise


class TestLangSmithSnapshotResolution:
    """Env-var-driven snapshot resolution in `_LangSmithProvider.get_or_create`."""

    @staticmethod
    def _make_ready_sandbox() -> MagicMock:
        """Mock Sandbox whose readiness poll succeeds immediately."""
        sandbox = MagicMock()
        sandbox.run.return_value = MagicMock(exit_code=0)
        return sandbox

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock SandboxClient that yields a ready sandbox from create_sandbox."""
        client = MagicMock()
        client.create_sandbox.return_value = self._make_ready_sandbox()
        return client

    @pytest.fixture
    def provider(self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch):
        """Build `_LangSmithProvider` with its SandboxClient patched."""
        monkeypatch.setenv("LANGSMITH_API_KEY", "fake")
        with patch("langsmith.sandbox.SandboxClient", return_value=mock_client):
            from deepagents_cli.integrations.sandbox_factory import (
                _LangSmithProvider,
            )

            return _LangSmithProvider()

    def test_snapshot_id_env_var_boots_directly_without_listing(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`LANGSMITH_SANDBOX_SNAPSHOT_ID` skips name lookup and auto-build."""
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", "snap-abc123")
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", raising=False)

        provider.get_or_create()

        mock_client.list_snapshots.assert_not_called()
        mock_client.create_snapshot.assert_not_called()
        mock_client.create_sandbox.assert_called_once()
        kwargs = mock_client.create_sandbox.call_args.kwargs
        assert kwargs["snapshot_id"] == "snap-abc123"

    def test_snapshot_name_env_var_overrides_default(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`LANGSMITH_SANDBOX_SNAPSHOT_NAME` is used as the lookup name."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", "custom-snap")

        # `MagicMock(name=...)` sets the mock's repr, not `.name` — the
        # explicit assignment below is load-bearing for the filter to match.
        existing = MagicMock(id="snap-xyz", status="ready")
        existing.name = "custom-snap"
        mock_client.list_snapshots.return_value = [existing]

        provider.get_or_create()

        mock_client.list_snapshots.assert_called_once()
        mock_client.create_snapshot.assert_not_called()
        assert mock_client.create_sandbox.call_args.kwargs["snapshot_id"] == "snap-xyz"

    def test_snapshot_name_env_var_triggers_build_when_missing(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unknown snapshot name triggers `create_snapshot` with that name."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", "built-snap")
        mock_client.list_snapshots.return_value = []
        built = MagicMock(id="snap-built")
        mock_client.create_snapshot.return_value = built

        provider.get_or_create()

        mock_client.create_snapshot.assert_called_once()
        assert mock_client.create_snapshot.call_args.kwargs["name"] == "built-snap"
        kwargs = mock_client.create_sandbox.call_args.kwargs
        assert kwargs["snapshot_id"] == "snap-built"

    def test_snapshot_id_wins_over_name(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`_ID` takes precedence — `_NAME` is ignored when both are set."""
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", "snap-id-wins")
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", "ignored-name")

        provider.get_or_create()

        mock_client.list_snapshots.assert_not_called()
        kwargs = mock_client.create_sandbox.call_args.kwargs
        assert kwargs["snapshot_id"] == "snap-id-wins"

    def test_defaults_when_no_env_vars(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With no env vars, falls back to `deepagents-cli` + 16 GiB."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", raising=False)
        mock_client.list_snapshots.return_value = []
        mock_client.create_snapshot.return_value = MagicMock(id="snap-default")

        provider.get_or_create()

        kwargs = mock_client.create_snapshot.call_args.kwargs
        assert kwargs["name"] == "deepagents-cli"
        assert kwargs["docker_image"] == "python:3"
        assert kwargs["fs_capacity_bytes"] == 16 * 1024**3

    def test_list_snapshots_failure_raises_runtime_error(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SDK failure during `list_snapshots` is wrapped in `RuntimeError`."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", raising=False)
        mock_client.list_snapshots.side_effect = Exception("network down")

        with pytest.raises(RuntimeError, match="Failed to list snapshots"):
            provider.get_or_create()

        mock_client.create_snapshot.assert_not_called()
        mock_client.create_sandbox.assert_not_called()

    def test_create_snapshot_failure_raises_runtime_error(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SDK failure during `create_snapshot` is wrapped with name context."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", "broken-snap")
        mock_client.list_snapshots.return_value = []
        mock_client.create_snapshot.side_effect = Exception("quota exceeded")

        with pytest.raises(
            RuntimeError,
            match=r"Failed to build snapshot 'broken-snap'",
        ):
            provider.get_or_create()

        mock_client.create_sandbox.assert_not_called()

    def test_non_ready_matching_snapshot_raises_instead_of_rebuilding(
        self,
        provider,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Matching-name snapshot in non-ready state must not silently rebuild."""
        monkeypatch.delenv("LANGSMITH_SANDBOX_SNAPSHOT_ID", raising=False)
        monkeypatch.setenv("LANGSMITH_SANDBOX_SNAPSHOT_NAME", "in-flight")

        building = MagicMock(id="snap-build-1", status="building")
        building.name = "in-flight"
        mock_client.list_snapshots.return_value = [building]

        with pytest.raises(
            RuntimeError,
            match=r"Snapshot 'in-flight' exists but is in state 'building'",
        ):
            provider.get_or_create()

        mock_client.create_snapshot.assert_not_called()
        mock_client.create_sandbox.assert_not_called()
