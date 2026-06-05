#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = (
    REPO_ROOT / "application/flashsale/release/schemas/flashsale-quality-contract.schema.json"
)

def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be a non-empty string")
    return value


def _write_output(handle, key: str, value: str) -> None:
    handle.write(f"{key}<<__EOF__\n{value}\n__EOF__\n")


def _validate_document(document: object, schema_path: Path) -> None:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            path = ".".join(str(part) for part in error.absolute_path) or "<root>"
            print(f"{path}: {error.message}")
        raise SystemExit(1)


def _extract_invocation_value(invocation: dict[str, object], label: str) -> tuple[str, str]:
    invocation_type = _require_str(invocation.get("type"), f"{label}.type")
    if invocation_type == "make":
        return invocation_type, _require_str(invocation.get("target"), f"{label}.target")
    if invocation_type == "python":
        return invocation_type, _require_str(invocation.get("script"), f"{label}.script")
    raise SystemExit(f"{label}.type must be one of: make, python")


def _extract_perf_cadence(perf: dict[str, object]) -> list[dict[str, object]]:
    cadence = perf.get("cadence")
    if not isinstance(cadence, list):
        raise SystemExit("manifest spec.perf.cadence must be a YAML sequence")

    normalized: list[dict[str, object]] = []
    for index, lane in enumerate(cadence):
        label = f"manifest spec.perf.cadence[{index}]"
        if not isinstance(lane, dict):
            raise SystemExit(f"{label} must be a YAML mapping")

        lane_id = _require_str(lane.get("id"), f"{label}.id")
        display_name = _require_str(lane.get("displayName"), f"{label}.displayName")
        invocation = lane.get("invocation")
        if not isinstance(invocation, dict):
            raise SystemExit(f"{label}.invocation must be a YAML mapping")
        invocation_type, invocation_value = _extract_invocation_value(
            invocation, f"{label}.invocation"
        )

        pause_before_seconds = lane.get("pauseBeforeSeconds", 0)
        if not isinstance(pause_before_seconds, int) or pause_before_seconds < 0:
            raise SystemExit(f"{label}.pauseBeforeSeconds must be a non-negative integer")

        normalized.append(
            {
                "id": lane_id,
                "displayName": display_name,
                "pauseBeforeSeconds": pause_before_seconds,
                "invocation": {
                    "type": invocation_type,
                    "value": invocation_value,
                },
            }
        )

    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export flashsale quality contract fields into GitHub Actions outputs."
    )
    parser.add_argument("manifest", type=Path, help="Path to flashsale-quality-contract.yaml")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to the flashsale quality contract schema.",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Path to the GitHub Actions output file (for example $GITHUB_OUTPUT)",
    )
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    _validate_document(document, args.schema)
    if not isinstance(document, dict):
        raise SystemExit("flashsale quality contract must be a YAML mapping")

    spec = document.get("spec")
    if not isinstance(spec, dict):
        raise SystemExit("manifest spec must be a YAML mapping")

    perf = spec.get("perf")
    if not isinstance(perf, dict):
        raise SystemExit("manifest spec.perf must be a YAML mapping")

    perf_cadence = _extract_perf_cadence(perf)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as handle:
        _write_output(handle, "perf_cadence_json", json.dumps(perf_cadence))


if __name__ == "__main__":
    main()
