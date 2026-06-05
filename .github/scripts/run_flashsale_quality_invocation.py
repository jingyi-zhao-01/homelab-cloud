#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a declarative flashsale quality lane invocation."
    )
    parser.add_argument(
        "--type",
        dest="invocation_type",
        choices=["make", "python"],
        required=True,
        help="Invocation type exported from the flashsale quality contract.",
    )
    parser.add_argument(
        "--value",
        required=True,
        help="Invocation payload. For make this is the target, for python this is the script path.",
    )
    args = parser.parse_args()

    if args.invocation_type == "make":
        command = ["make", "-C", "flashsale", args.value]
    else:
        command = ["python3", args.value]

    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
