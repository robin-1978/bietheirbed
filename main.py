from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pc-assistant",
        description="PC Assistant - A Python computer assistant agent",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to configuration YAML file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Print version and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from pc_assistant import __version__

        print(f"pc_assistant {__version__}")
        return 0

    config_path = args.config
    if config_path is not None:
        config_path = str(Path(config_path).resolve())

    from pc_assistant import async_main

    try:
        return asyncio.run(async_main(config_path, args.verbose))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
