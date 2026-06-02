#!/usr/bin/env python3
from __future__ import annotations

import atexit
import shutil
import subprocess
import sys
from pathlib import Path

from integration_test_support import (
    BASE_ORDER_URL,
    BASE_PRODUCT_URL,
    BASE_USER_URL,
    COMPOSE_FILE,
    wait_for_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def log(message: str) -> None:
    print(f"[flashsale-compose] {message}")


def require_cmd(command: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"Missing required command: {command}")


def cleanup() -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "down",
            "-v",
            "--remove-orphans",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def run_tests(start_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(start_dir),
            "-p",
            "*_integration.py",
        ],
        check=True,
    )


def main() -> int:
    require_cmd("docker")
    require_cmd("python3")

    atexit.register(cleanup)

    log("Starting flashsale integration stack")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"],
        check=True,
    )

    wait_for_stack()
    log(f"Services ready: {BASE_USER_URL}, {BASE_PRODUCT_URL}, {BASE_ORDER_URL}")

    log("Running product-service integration tests")
    run_tests(REPO_ROOT / "flashsale" / "product-service" / "tests" / "interagtion")

    log("Running order-service integration tests")
    run_tests(REPO_ROOT / "flashsale" / "order-service" / "tests" / "interagtion")

    log("Integration PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
