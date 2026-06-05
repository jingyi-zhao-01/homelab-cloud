#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _stringify_env(env: dict[str, Any] | None) -> dict[str, str]:
    if not env:
        return {}
    return {key: str(value) for key, value in env.items()}


def _copy_autoscaling(service_spec: dict[str, Any]) -> dict[str, Any]:
    autoscaling = service_spec.get("autoscaling")
    if not autoscaling:
        return {}
    return {"autoscaling": autoscaling}


def build_overlay(spec: dict[str, Any]) -> dict[str, Any]:
    services = spec.get("services", {})
    overlay: dict[str, Any] = {}

    service_mapping = {
        "userService": "userService",
        "productService": "productService",
        "orderService": "orderService",
    }

    for manifest_name, chart_name in service_mapping.items():
        service_spec = services.get(manifest_name)
        if not service_spec:
            continue

        chart_service: dict[str, Any] = {}

        replicas = service_spec.get("replicas")
        if replicas is not None:
            chart_service["replicaCount"] = replicas

        chart_service.update(_copy_autoscaling(service_spec))

        env = _stringify_env(service_spec.get("env"))
        if env:
            chart_service["env"] = env

        if manifest_name == "orderService":
            worker_replicas = service_spec.get("workerReplicas")
            if worker_replicas is not None:
                chart_service["workerReplicaCount"] = worker_replicas

            worker_spec = service_spec.get("worker", {})
            worker_env = _stringify_env(worker_spec.get("env"))
            if worker_env:
                chart_service.setdefault("worker", {})
                chart_service["worker"]["env"] = worker_env

        overlay[chart_name] = chart_service

    return overlay


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate flashsale release manifest into Helm values overlay."
    )
    parser.add_argument("manifest", type=Path, help="Path to flashsale-release.yaml")
    parser.add_argument("output", type=Path, help="Path to generated Helm values YAML")
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise SystemExit("flashsale release manifest must be a YAML mapping")

    if document.get("kind") != "FlashsaleRelease":
        raise SystemExit("manifest kind must be FlashsaleRelease")

    spec = document.get("spec")
    if not isinstance(spec, dict):
        raise SystemExit("manifest spec must be a YAML mapping")

    overlay = build_overlay(spec)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(overlay, handle, sort_keys=False)


if __name__ == "__main__":
    main()
