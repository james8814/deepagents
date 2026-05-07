"""Re-export LangChainDeprecationWarning for #2892 test compatibility.

Round 16 Phase 2b A25 mitigation. See _api/__init__.py for context.
"""

from langchain_core._api.deprecation import LangChainDeprecationWarning

__all__ = ["LangChainDeprecationWarning"]
