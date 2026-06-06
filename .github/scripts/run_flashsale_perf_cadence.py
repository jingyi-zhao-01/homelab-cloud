#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

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


def _run_invocation(
    invocation_type: str,
    invocation_value: str,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
) -> None:
    if invocation_type == "make":
        command = ["make", "-C", FLASHSALE_APP_DIR, invocation_value]
    elif invocation_type == "python":
        command = ["python3", invocation_value]
    else:
        raise SystemExit(f"Unsupported invocation type: {invocation_type}")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    if log_path is None:
        subprocess.run(command, check=True, env=merged_env)
        return

    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=merged_env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ordered flashsale perf cadence declared by the app quality contract."
    )
    parser.add_argument(
        "--lanes-json",
        required=True,
        help="JSON array exported from the flashsale quality contract.",
    )
    parser.add_argument(
        "--results-root",
        default="",
        help="Optional directory where each perf lane should persist machine-readable outputs.",
    )
    args = parser.parse_args()

    lanes = _parse_lanes(args.lanes_json)
    results_root = Path(args.results_root).resolve() if args.results_root else None
    manifest: list[dict[str, object]] = []
    if results_root is not None:
        results_root.mkdir(parents=True, exist_ok=True)

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

        lane_manifest: dict[str, object] = {
            "index": index,
            "id": lane_id,
            "display_name": display_name,
            "invocation_type": invocation_type,
            "invocation_value": invocation_value,
            "pause_before_seconds": pause_before_seconds,
        }

        invocation_env: dict[str, str] | None = None
        log_path: Path | None = None
        if results_root is not None:
            lane_dir = results_root / f"{index:02d}-{lane_id}"
            lane_dir.mkdir(parents=True, exist_ok=True)
            invocation_env = {
                "PERF_RESULTS_DIR": str(lane_dir),
                "PERF_LANE_ID": lane_id,
                "PERF_LANE_DISPLAY_NAME": display_name,
            }
            log_path = lane_dir / "lane.log"
            lane_manifest["results_dir"] = lane_dir.name

        started_at = datetime.now(timezone.utc)
        lane_manifest["started_at_utc"] = started_at.isoformat()
        try:
            _run_invocation(
                invocation_type,
                invocation_value,
                env=invocation_env,
                log_path=log_path,
            )
        except subprocess.CalledProcessError as exc:
            lane_manifest["status"] = "failed"
            lane_manifest["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
            lane_manifest["exit_code"] = exc.returncode
            manifest.append(lane_manifest)
            if results_root is not None:
                (results_root / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n",
                    encoding="utf-8",
                )
            raise
        else:
            lane_manifest["status"] = "passed"
            lane_manifest["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
            manifest.append(lane_manifest)

    if results_root is not None:
        (results_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
