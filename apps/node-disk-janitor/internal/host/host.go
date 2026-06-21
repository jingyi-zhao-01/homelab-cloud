package host

import (
	"context"
	"errors"
	"math"
	"os/exec"
	"syscall"
)

func RunScript(ctx context.Context, script string) (string, error) {
	cmd := exec.CommandContext(
		ctx,
		"nsenter",
		"-t", "1",
		"-m", "-u", "-i", "-n", "-p",
		"--",
		// After entering the host mount namespace, the container's /host bind mount no
		// longer exists. /proc/1/root is the host rootfs from that namespace.
		"chroot", "/proc/1/root",
		"/bin/sh", "-lc", script,
	)
	output, err := cmd.CombinedOutput()
	return string(output), err
}

func DiskUsagePercent(path string) (float64, error) {
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
