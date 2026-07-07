from __future__ import annotations

import argparse
import shlex
import sys


def split_shell_words(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"invalid shell-style argument string: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split a shell-style argument string.")
    parser.add_argument("value")
    parser.add_argument("--nul", action="store_true", help="Write NUL-delimited output.")
    args = parser.parse_args(argv)

    parts = split_shell_words(args.value)
    separator = "\0" if args.nul else "\n"
    if parts:
        sys.stdout.write(separator.join(parts))
        if not args.nul:
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
