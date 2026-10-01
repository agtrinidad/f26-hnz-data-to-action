"""Command-line entry point: `tobacco-inspect <command>` or `python -m tobacco_inspect`."""

from __future__ import annotations

import argparse
import sys

from tobacco_inspect import __version__
from tobacco_inspect.config import ConfigError, load_config

COMMANDS = {
    "refresh": "download and clean source data",
    "fit": "fit the risk model",
    "solve": "solve the inspection schedule",
    "report": "write route sheets and audit tables",
    "run-all": "refresh -> fit -> solve -> report",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tobacco-inspect", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="path to a YAML config (default: config/default.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, helptext in COMMANDS.items():
        sub.add_parser(name, help=helptext)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    if args.command == "refresh":
        from tobacco_inspect.data import ingest

        ingest.refresh(config)
        print("refresh complete: see data/interim and data/processed")
        return 0
    print(f"'{args.command}' is not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
