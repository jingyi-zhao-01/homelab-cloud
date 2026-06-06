#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _read_manifest(results_dir: Path) -> list[dict[str, object]]:
    manifest_path = results_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"results manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text())


def _copy_results(results_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for entry in results_dir.iterdir():
        if entry.name == "manifest.json":
            continue
        target = destination_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy flashsale perf outputs into the flashsale repo results tree."
    )
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--flashsale-dir", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--image-tag", default="")
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    flashsale_dir = Path(args.flashsale_dir).resolve()
    if not results_dir.exists():
        raise SystemExit(f"results directory not found: {results_dir}")
    if not flashsale_dir.exists():
        raise SystemExit(f"flashsale directory not found: {flashsale_dir}")

    manifest = _read_manifest(results_dir)
    created_at = datetime.now(timezone.utc)
    run_slug = f"run-{args.run_id}-attempt-{args.run_attempt}"
    relative_results_dir = (
        Path("perf")
        / "results"
        / created_at.strftime("%Y")
        / created_at.strftime("%m")
        / created_at.strftime("%d")
        / run_slug
    )
    destination_dir = flashsale_dir / relative_results_dir

    _copy_results(results_dir, destination_dir)

    metadata = {
        "workflow_name": args.workflow_name,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "created_at_utc": created_at.isoformat(),
        "source_ref": args.source_ref,
        "source_sha": args.source_sha,
        "image_tag": args.image_tag,
        "lane_count": len(manifest),
        "lanes": manifest,
    }
    (destination_dir / "run-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )

    print(relative_results_dir.as_posix())


if __name__ == "__main__":
    main()
