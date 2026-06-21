package main

import (
	"context"
	"errors"
	"math"
	"os/exec"
	"syscall"
)

func (j *janitor) runHostCleanup(ctx context.Context) (string, error) {
	return j.runHostScript(ctx, j.cfg.hostCleanupShellCommand)
}

func (j *janitor) runHostScript(ctx context.Context, script string) (string, error) {
	cmd := exec.CommandContext(
		ctx,
		"nsenter",
		"-t", "1",
		"-m", "-u", "-i", "-n", "-p",
		"--",
		"chroot", j.cfg.hostRoot,
		"/bin/sh", "-lc", script,
	)
	output, err := cmd.CombinedOutput()
	return string(output), err
}

func diskUsagePercent(path string) (float64, error) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, err
	}

	if stat.Blocks == 0 {
		return 0, errors.New("filesystem reports zero blocks")
	}

	total := float64(stat.Blocks) * float64(stat.Bsize)
	available := float64(stat.Bavail) * float64(stat.Bsize)
	used := total - available
	return roundToTwo(used / total * 100), nil
}

func roundToTwo(value float64) float64 {
	return math.Round(value*100) / 100
}

func defaultHostCleanupCommand() string {
	return `
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

run_if_present() {
  if command -v "$1" >/dev/null 2>&1; then
    "$@"
    return 0
  fi
  return 1
}

echo "[janitor] vacuuming journals"
run_if_present journalctl --vacuum-time=2d || true

echo "[janitor] removing exited containers"
if command -v crictl >/dev/null 2>&1; then
  crictl ps -a --state Exited -q | xargs -r crictl rm || true
  crictl pods --state NotReady -q | xargs -r crictl rmp || true
  crictl rmi --prune || true
fi

echo "[janitor] pruning containerd images"
if command -v ctr >/dev/null 2>&1; then
  ctr -n k8s.io images prune || true
fi

echo "[janitor] cleaning apt cache when present"
if command -v apt-get >/dev/null 2>&1; then
  apt-get clean || true
fi
`
}
