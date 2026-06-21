package config

import (
	"errors"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

type JanitorConfig struct {
	NodeName                string
	HostRoot                string
	CheckInterval           time.Duration
	CleanupCooldown         time.Duration
	TriggerPercent          float64
	TargetPercent           float64
	DeleteTerminatedPods    bool
	TerminatedPodGrace      time.Duration
	HostCleanupShellCommand string
	ClusterCleanupCooldown  time.Duration
	DeleteFinishedJobs      bool
	FinishedJobGrace        time.Duration
	DeleteEmptyNamespaces   bool
	EmptyNamespaceGrace     time.Duration
	ProtectedNamespaces     []string
	TailscaleSelfHeal       bool
	SelfHealCooldown        time.Duration
	TailscalePingTimeout    time.Duration
	TailscalePeer           string
	RestartK3SOnHeal        bool
}

func Load() (JanitorConfig, error) {
	nodeName := strings.TrimSpace(os.Getenv("NODE_NAME"))
	if nodeName == "" {
		return JanitorConfig{}, errors.New("NODE_NAME is required")
	}

	cfg := JanitorConfig{
		NodeName:                nodeName,
		HostRoot:                getenvDefault("HOST_ROOT", "/host"),
		CheckInterval:           mustDurationEnv("CHECK_INTERVAL_SECONDS", 120*time.Second),
		CleanupCooldown:         mustDurationEnv("CLEANUP_COOLDOWN_SECONDS", 300*time.Second),
		TriggerPercent:          mustPercentEnv("DISK_USAGE_TRIGGER_PERCENT", 85),
		TargetPercent:           mustPercentEnv("DISK_USAGE_TARGET_PERCENT", 75),
		DeleteTerminatedPods:    mustBoolEnv("DELETE_TERMINATED_PODS", true),
		TerminatedPodGrace:      mustDurationEnv("TERMINATED_POD_GRACE_SECONDS", 120*time.Second),
		HostCleanupShellCommand: strings.TrimSpace(os.Getenv("HOST_CLEANUP_COMMAND")),
		ClusterCleanupCooldown:  mustDurationEnv("CLUSTER_CLEANUP_COOLDOWN_SECONDS", 300*time.Second),
		DeleteFinishedJobs:      mustBoolEnv("DELETE_FINISHED_JOBS", true),
		FinishedJobGrace:        mustDurationEnv("FINISHED_JOB_GRACE_SECONDS", 900*time.Second),
		DeleteEmptyNamespaces:   mustBoolEnv("DELETE_EMPTY_NAMESPACES", true),
		EmptyNamespaceGrace:     mustDurationEnv("EMPTY_NAMESPACE_GRACE_SECONDS", 1800*time.Second),
		ProtectedNamespaces:     parseCSVEnv("EMPTY_NAMESPACE_PROTECTED_NAMESPACES", defaultProtectedNamespaces()),
		TailscaleSelfHeal:       mustBoolEnv("TAILSCALE_SELF_HEAL_ENABLED", true),
		SelfHealCooldown:        mustDurationEnv("SELF_HEAL_COOLDOWN_SECONDS", 120*time.Second),
		TailscalePingTimeout:    mustDurationEnv("TAILSCALE_PING_TIMEOUT_SECONDS", 5*time.Second),
		TailscalePeer:           strings.TrimSpace(os.Getenv("TAILSCALE_PING_PEER")),
		RestartK3SOnHeal:        mustBoolEnv("RESTART_K3S_ON_TAILSCALE_HEAL", true),
	}

	if cfg.TargetPercent >= cfg.TriggerPercent {
		return JanitorConfig{}, fmt.Errorf(
			"DISK_USAGE_TARGET_PERCENT must be lower than DISK_USAGE_TRIGGER_PERCENT, got %.1f >= %.1f",
			cfg.TargetPercent,
			cfg.TriggerPercent,
		)
	}

	if cfg.HostCleanupShellCommand == "" {
		cfg.HostCleanupShellCommand = hostCleanupDefault()
	}

	return cfg, nil
}

func mustDurationEnv(name string, fallback time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}

	seconds, err := strconv.Atoi(raw)
	if err != nil || seconds <= 0 {
		log.Fatalf("%s must be a positive integer number of seconds, got %q", name, raw)
	}
	return time.Duration(seconds) * time.Second
}

func mustPercentEnv(name string, fallback float64) float64 {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}

	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || value <= 0 || value >= 100 {
		log.Fatalf("%s must be a percentage between 0 and 100, got %q", name, raw)
	}
	return value
}

func mustBoolEnv(name string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}

	switch strings.ToLower(raw) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		log.Fatalf("%s must be a boolean, got %q", name, raw)
		return false
	}
}

func getenvDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func parseCSVEnv(name string, fallback []string) []string {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}

	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed == "" {
			continue
		}
		values = append(values, trimmed)
	}
	if len(values) == 0 {
		return fallback
	}
	return values
}

func defaultProtectedNamespaces() []string {
	return []string{
		"default",
		"kube-node-lease",
		"kube-public",
		"kube-system",
		"control-plane-agents",
		"datadog",
		"monitoring",
	}
}

func hostCleanupDefault() string {
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
