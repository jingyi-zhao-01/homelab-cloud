#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time

FLASHSALE_APP_DIR = "application/flashsale"


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be a non-empty string")
    return value


def _parse_lanes(payload: str) -> list[dict[str, object]]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--lanes-json must be valid JSON: {exc}") from exc
    if not isinstance(decoded, list):
        raise SystemExit("--lanes-json must decode to a JSON array")
    return decoded


def _run_invocation(invocation_type: str, invocation_value: str) -> None:
    if invocation_type == "make":
        command = ["make", "-C", FLASHSALE_APP_DIR, invocation_value]
    elif invocation_type == "python":
        command = ["python3", invocation_value]
    else:
        raise SystemExit(f"Unsupported invocation type: {invocation_type}")

    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ordered flashsale perf cadence declared by the app quality contract."
    )
    parser.add_argument(
        "--lanes-json",
        required=True,
        help="JSON array exported from the flashsale quality contract.",
    )
    args = parser.parse_args()

    lanes = _parse_lanes(args.lanes_json)
    for index, lane in enumerate(lanes, start=1):
        if not isinstance(lane, dict):
            raise SystemExit(f"Lane #{index} must be an object")

        lane_id = _require_str(lane.get("id"), f"lane #{index}.id")
        display_name = _require_str(lane.get("displayName"), f"lane #{index}.displayName")
        pause_before_seconds = lane.get("pauseBeforeSeconds", 0)
        if not isinstance(pause_before_seconds, int) or pause_before_seconds < 0:
            raise SystemExit(f"lane #{index}.pauseBeforeSeconds must be a non-negative integer")

        invocation = lane.get("invocation")
        if not isinstance(invocation, dict):
            raise SystemExit(f"lane #{index}.invocation must be an object")
        invocation_type = _require_str(invocation.get("type"), f"lane #{index}.invocation.type")
        invocation_value = _require_str(
            invocation.get("value"), f"lane #{index}.invocation.value"
        )

        print(f"[flashsale-perf-cadence] lane {index}/{len(lanes)}: {lane_id} - {display_name}")
        if pause_before_seconds:
            print(
                f"[flashsale-perf-cadence] pausing {pause_before_seconds}s before {lane_id}"
            )
            time.sleep(pause_before_seconds)

        _run_invocation(invocation_type, invocation_value)


if __name__ == "__main__":
    main()
