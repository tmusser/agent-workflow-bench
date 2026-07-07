from __future__ import annotations

from benchmark_harness import shell_words
from benchmark_harness.shell_words import split_shell_words


def test_split_shell_words_handles_empty_strings():
    assert split_shell_words("") == []
    assert split_shell_words("   ") == []


def test_split_shell_words_preserves_quoted_values():
    assert split_shell_words('--json --config foo="bar baz"') == [
        "--json",
        "--config",
        "foo=bar baz",
    ]


def test_split_shell_words_rejects_invalid_shell_syntax():
    try:
        split_shell_words('"unterminated')
    except ValueError as exc:
        assert "No closing quotation" in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError("expected invalid shell syntax to raise")


def test_shell_words_cli_accepts_values_that_start_with_flags(capsys):
    assert shell_words.main(["--", "--json --ephemeral"]) == 0
    assert capsys.readouterr().out == "--json\n--ephemeral\n"
