"""Internal API helpers — Round 16 Phase 2b A25 mitigation shim.

Background: #2892 test files reference deepagents._api.deprecation, but #2978
(introduces this module) was DEFERRED Group A SKIP. This shim re-exports
LangChainDeprecationWarning from langchain_core to restore test collectability
without cherry-picking #2978's 130+ line backend refactor.

Future: Round 17 cherry-pick #2978 will overwrite this shim cleanly.
"""
