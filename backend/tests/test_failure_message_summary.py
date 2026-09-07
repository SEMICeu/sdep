"""Cover the end-of-run failure message section defined in ``tests/conftest.py``.

The section exists because the quiet test targets pipe pytest through ``tail`` and pytest
drops the message from its own summary line when it does not fit the terminal width.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import pytest_terminal_summary


class _StubReport:
    """Stands in for a pytest ``TestReport``."""

    def __init__(self, nodeid: str, longrepr: Any, longreprtext: str = "") -> None:
        self.nodeid = nodeid
        self.longrepr = longrepr
        self.longreprtext = longreprtext


class _StubCrash:
    """Location of the crash, as pytest hangs it off a longrepr."""

    def __init__(self, message: str) -> None:
        self.message = message


class _StubLongrepr:
    def __init__(self, message: str) -> None:
        self.reprcrash = _StubCrash(message)


class _StubReporter:
    """Records what the hook writes, in place of pytest's terminal reporter."""

    def __init__(self, failed: list[Any]) -> None:
        self.stats: dict[str, list[Any]] = {"failed": failed}
        self.lines: list[str] = []

    def write_sep(self, sep: str, title: str, **markup: bool) -> None:
        self.lines.append(title)

    def write_line(self, line: str) -> None:
        self.lines.append(line)


def _summarize(failed: list[Any]) -> list[str]:
    reporter = _StubReporter(failed)
    pytest_terminal_summary(reporter)  # type: ignore[arg-type]

    return reporter.lines


def test_passing_run_writes_nothing() -> None:
    assert _summarize([]) == []


def test_failure_message_is_repeated_under_its_nodeid() -> None:
    report = _StubReport(
        "tests/api/test_openapi_version_diff.py::test_version_diff_is_current",
        _StubLongrepr(
            "Failed: docs/API_DIFF.md is out of date. Run `make api-diff-update`."
        ),
    )

    assert _summarize([report]) == [
        "failure messages",
        "tests/api/test_openapi_version_diff.py::test_version_diff_is_current",
        "    Failed: docs/API_DIFF.md is out of date. Run `make api-diff-update`.",
    ]


def test_only_the_first_message_line_is_repeated() -> None:
    report = _StubReport(
        "tests/test_x.py::test_x", _StubLongrepr("Run `make x`.\n\ndetail")
    )

    assert _summarize([report])[-1] == "    Run `make x`."


def test_longrepr_without_a_crash_falls_back_to_its_text() -> None:
    report = _StubReport(
        "tests/test_x.py::test_x", "no reprcrash here", "path:1: Failed: hint"
    )

    assert _summarize([report])[-1] == "    path:1: Failed: hint"


def test_failure_without_a_message_lists_the_nodeid_only() -> None:
    report = _StubReport("tests/test_x.py::test_x", None, "   ")

    assert _summarize([report]) == ["failure messages", "tests/test_x.py::test_x"]
