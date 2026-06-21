package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"
)

type config struct {
	nodeName                string
	hostRoot                string
	checkInterval           time.Duration
	cleanupCooldown         time.Duration
	triggerPercent          float64
	targetPercent           float64
	deleteTerminatedPods    bool
	terminatedPodGrace      time.Duration
	hostCleanupShellCommand string
	clusterCleanupCooldown  time.Duration
	deleteFinishedJobs      bool
	finishedJobGrace        time.Duration
	deleteEmptyNamespaces   bool
	emptyNamespaceGrace     time.Duration
	protectedNamespaces     []string
	tailscaleSelfHeal       bool
	selfHealCooldown        time.Duration
	tailscalePingTimeout    time.Duration
	tailscalePeer           string
	restartK3SOnHeal        bool
}

func loadConfig() (config, error) {
	nodeName := strings.TrimSpace(os.Getenv("NODE_NAME"))
	if nodeName == "" {
		return config{}, errors.New("NODE_NAME is required")
	}

	cfg := config{
		nodeName:                nodeName,
		hostRoot:                getenvDefault("HOST_ROOT", "/host"),
		checkInterval:           mustDurationEnv("CHECK_INTERVAL_SECONDS", 120*time.Second),
		cleanupCooldown:         mustDurationEnv("CLEANUP_COOLDOWN_SECONDS", 300*time.Second),
		triggerPercent:          mustPercentEnv("DISK_USAGE_TRIGGER_PERCENT", 85),
		targetPercent:           mustPercentEnv("DISK_USAGE_TARGET_PERCENT", 75),
		deleteTerminatedPods:    mustBoolEnv("DELETE_TERMINATED_PODS", true),
		terminatedPodGrace:      mustDurationEnv("TERMINATED_POD_GRACE_SECONDS", 120*time.Second),
		hostCleanupShellCommand: strings.TrimSpace(os.Getenv("HOST_CLEANUP_COMMAND")),
		clusterCleanupCooldown:  mustDurationEnv("CLUSTER_CLEANUP_COOLDOWN_SECONDS", 300*time.Second),
		deleteFinishedJobs:      mustBoolEnv("DELETE_FINISHED_JOBS", true),
		finishedJobGrace:        mustDurationEnv("FINISHED_JOB_GRACE_SECONDS", 900*time.Second),
		deleteEmptyNamespaces:   mustBoolEnv("DELETE_EMPTY_NAMESPACES", true),
		emptyNamespaceGrace:     mustDurationEnv("EMPTY_NAMESPACE_GRACE_SECONDS", 1800*time.Second),
		protectedNamespaces:     parseCSVEnv("EMPTY_NAMESPACE_PROTECTED_NAMESPACES", defaultProtectedNamespaces()),
		tailscaleSelfHeal:       mustBoolEnv("TAILSCALE_SELF_HEAL_ENABLED", true),
		selfHealCooldown:        mustDurationEnv("SELF_HEAL_COOLDOWN_SECONDS", 120*time.Second),
		tailscalePingTimeout:    mustDurationEnv("TAILSCALE_PING_TIMEOUT_SECONDS", 5*time.Second),
		tailscalePeer:           strings.TrimSpace(os.Getenv("TAILSCALE_PING_PEER")),
		restartK3SOnHeal:        mustBoolEnv("RESTART_K3S_ON_TAILSCALE_HEAL", true),
	}

	if cfg.targetPercent >= cfg.triggerPercent {
		return config{}, fmt.Errorf(
			"DISK_USAGE_TARGET_PERCENT must be lower than DISK_USAGE_TRIGGER_PERCENT, got %.1f >= %.1f",
			cfg.targetPercent,
			cfg.triggerPercent,
		)
	}

	if cfg.hostCleanupShellCommand == "" {
		cfg.hostCleanupShellCommand = defaultHostCleanupCommand()
	}

	return cfg, nil
}
