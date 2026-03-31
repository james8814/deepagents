"""Tests for TextualTokenTracker."""

from types import SimpleNamespace

from deepagents_cli.app import DeepAgentsApp
from deepagents_cli.token_state import TokenStateMiddleware, TokenTrackingState


class TestTextualTokenTracker:
    def test_add_updates_context_and_calls_callback(self):
        """Token add() should update current_context with total tokens."""
        called_with = []
        tracker = TextualTokenTracker(lambda x: called_with.append(x))

        tracker.add(1700)  # total_tokens from usage_metadata

        assert tracker.current_context == 1700
        assert called_with == [1700]

    def test_reset_clears_context_and_calls_callback_with_zero(self):
        """Token reset() should set context to 0 and call callback with 0."""
        called_with = []
        tracker = TextualTokenTracker(lambda x: called_with.append(x))
        tracker.add(1500, 200)
        called_with.clear()

        tracker.reset()

        assert tracker.current_context == 0
        assert called_with == [0]

    def test_hide_calls_hide_callback(self):
        """Token hide() should call the hide callback."""
        hide_called = []
        tracker = TextualTokenTracker(
            lambda _: None, hide_callback=lambda: hide_called.append(True)
        )

        tracker.hide()

        assert hide_called == [True]

    def test_hide_without_callback_is_noop(self):
        """Token hide() should be safe when no hide callback provided."""
        tracker = TextualTokenTracker(lambda _: None)
        tracker.hide()  # Should not raise

    def test_show_restores_current_value(self):
        """Token show() should restore display with current value."""
        called_with = []
        tracker = TextualTokenTracker(lambda x: called_with.append(x))
        tracker.add(1500)
        called_with.clear()

        tracker.show()

            def _update_tokens(self, count: int) -> None:
                display_calls.append(count)

            def _show_tokens(self) -> None:
                self._update_tokens(self._context_tokens)

        app = FakeApp()
        app._show_tokens()

        assert display_calls == [1500]

    def test_show_tokens_preserves_approximate_marker_without_fresh_usage(self):
        """Turns without usage metadata should not clear a stale-token marker."""
        display_calls: list[tuple[int, bool]] = []

        def update_tokens(count: int, *, approximate: bool = False) -> None:
            display_calls.append((count, approximate))

        app = SimpleNamespace(
            _context_tokens=1500,
            _tokens_approximate=True,
            _update_tokens=update_tokens,
        )

        DeepAgentsApp._show_tokens(app, approximate=False)  # type: ignore[arg-type]

        assert app._tokens_approximate is True
        assert display_calls == [(1500, True)]

    def test_reset_clears_cache(self):
        """Resetting (e.g. /clear) should zero the cache and display."""
        display_calls: list[int] = []

        class FakeApp:
            _context_tokens: int = 3000

            def _update_tokens(self, count: int) -> None:
                display_calls.append(count)

        app = FakeApp()
        app._context_tokens = 0
        app._update_tokens(0)

        assert app._context_tokens == 0
        assert display_calls == [0]


class TestPersistContextTokens:
    """Tests for the `_persist_context_tokens` helper."""

    async def test_calls_aupdate_state_with_token_count(self):
        """Happy path: persists the count via `aupdate_state`."""
        from unittest.mock import AsyncMock

        from deepagents_cli.textual_adapter import _persist_context_tokens

        agent = AsyncMock()
        config = {"configurable": {"thread_id": "t-1"}}

        await _persist_context_tokens(agent, config, 4200)  # type: ignore[arg-type]

        agent.aupdate_state.assert_awaited_once_with(config, {"_context_tokens": 4200})

    async def test_suppresses_exceptions(self):
        """Failures should be swallowed (non-critical persistence)."""
        from unittest.mock import AsyncMock

        from deepagents_cli.textual_adapter import _persist_context_tokens

        agent = AsyncMock()
        agent.aupdate_state.side_effect = RuntimeError("checkpointer down")
        config = {"configurable": {"thread_id": "t-1"}}

        # Should not raise
        await _persist_context_tokens(agent, config, 1000)  # type: ignore[arg-type]
