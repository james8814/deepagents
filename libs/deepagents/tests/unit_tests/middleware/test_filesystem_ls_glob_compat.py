import pytest

from deepagents.backends.protocol import GlobResult, LsResult
from deepagents.middleware.filesystem import _normalize_glob_result, _normalize_ls_result


def test_normalize_ls_result_accepts_lsresult() -> None:
    result = LsResult(entries=[{"path": "/a.txt"}])
    assert _normalize_ls_result(result) is result


def test_normalize_ls_result_accepts_list_str() -> None:
    with pytest.warns(DeprecationWarning):
        result = _normalize_ls_result(["/a.txt", "/b.txt"])
    assert result.error is None
    assert result.entries == [{"path": "/a.txt"}, {"path": "/b.txt"}]


def test_normalize_glob_result_accepts_globresult() -> None:
    result = GlobResult(matches=[{"path": "/a.txt"}])
    assert _normalize_glob_result(result) is result


def test_normalize_glob_result_accepts_list_dict() -> None:
    with pytest.warns(DeprecationWarning):
        result = _normalize_glob_result([{"path": "/a.txt"}])
    assert result.error is None
    assert result.matches == [{"path": "/a.txt"}]


def test_normalize_glob_result_accepts_error_str() -> None:
    result = _normalize_glob_result("boom")
    assert result.error == "boom"
