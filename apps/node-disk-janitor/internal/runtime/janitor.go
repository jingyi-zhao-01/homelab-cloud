package runtime

import (
	"context"
	"log"
	"strings"
	"time"

	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/cleanup"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/config"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/connectivity"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/host"
	"k8s.io/client-go/kubernetes"
)

var deleteFinishedJobsClusterWide = cleanup.DeleteFinishedJobsClusterWide
var deleteEmptyNamespacesClusterWide = cleanup.DeleteEmptyNamespacesClusterWide

type Janitor struct {
	cfg              config.JanitorConfig
	clientset        kubernetes.Interface
	lastCleanupTime  time.Time
	lastClusterSweep time.Time
	lastSelfHealTime time.Time
	runScript        func(context.Context, string) (string, error)
}

func New(cfg config.JanitorConfig, clientset kubernetes.Interface, runScript func(context.Context, string) (string, error)) *Janitor {
	return &Janitor{
		cfg:       cfg,
		clientset: clientset,
		runScript: runScript,
	}
}

func (j *Janitor) RunMaintenanceCycle(ctx context.Context) error {
	j.runConnectivitySelfHealCycle(ctx)
	j.runClusterCleanupCycle(ctx)

	usage, err := j.measureNodeDiskUsage()
	if err != nil {
		return err
	}

	j.logNodeDiskUsage(usage)

	if err := j.runDiskCleanupIfNeeded(ctx, usage, time.Now()); err != nil {
		return err
	}

	return nil
}

func (j *Janitor) runConnectivitySelfHealCycle(ctx context.Context) {
	if !j.cfg.TailscaleSelfHeal {
		return
	}

	status, err := connectivity.Inspect(ctx, j.runScript, j.cfg)
	if err != nil {
		log.Printf("node=%s connectivity self-heal failed: %v", j.cfg.NodeName, err)
		return
	}

	if status.TailscaledPresent && status.TailscaledActive && status.HasTailscaleIPv4 &&
		(status.PeerCheckSkipped || status.PeerReachable) && (status.K3SService == "" || status.K3SActive) {
		return
	}

	if time.Since(j.lastSelfHealTime) < j.cfg.SelfHealCooldown {
		log.Printf(
			"node=%s self-heal suppressed by cooldown remaining=%s tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
			j.cfg.NodeName,
			j.cfg.SelfHealCooldown-time.Since(j.lastSelfHealTime),
			status.TailscaledActive,
			status.HasTailscaleIPv4,
			status.Peer,
			status.PeerReachable,
			status.K3SService,
			status.K3SActive,
		)
		return
	}

	j.lastSelfHealTime = time.Now()

	log.Printf(
		"node=%s starting self-heal tailscaled_service=%q tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
		j.cfg.NodeName,
		status.TailscaledService,
		status.TailscaledActive,
		status.HasTailscaleIPv4,
		status.Peer,
		status.PeerReachable,
		status.K3SService,
		status.K3SActive,
	)

	needsTailscaleRestart := !status.TailscaledActive || !status.HasTailscaleIPv4 || (!status.PeerCheckSkipped && !status.PeerReachable)
	needsK3SRestart := (status.K3SService != "" && !status.K3SActive) || (needsTailscaleRestart && j.cfg.RestartK3SOnHeal && status.K3SService != "")

	output, err := j.runScript(ctx, connectivity.BuildSelfHealScript(
		needsTailscaleRestart,
		status.TailscaledService,
		needsK3SRestart,
		status.K3SService,
	))
	if strings.TrimSpace(output) != "" {
		log.Printf("node=%s self-heal output:\n%s", j.cfg.NodeName, output)
	}
	if err != nil {
		log.Printf("node=%s connectivity self-heal failed: %v", j.cfg.NodeName, err)
	}
}

func (j *Janitor) runClusterCleanupCycle(ctx context.Context) {
	if err := j.runClusterCleanupIfDue(ctx, time.Now()); err != nil {
		log.Printf("node=%s cluster cleanup failed: %v", j.cfg.NodeName, err)
	}
}

func (j *Janitor) runClusterCleanupIfDue(ctx context.Context, now time.Time) error {
	if !j.clusterCleanupDue(now) {
		return nil
	}

	if err := j.runFinishedJobCleanup(ctx); err != nil {
		return err
	}
	if err := j.runEmptyNamespaceCleanup(ctx); err != nil {
		return err
	}

	j.lastClusterSweep = now

	return nil
}

func (j *Janitor) clusterCleanupDue(now time.Time) bool {
	if j.lastClusterSweep.IsZero() {
		return true
	}

	return now.Sub(j.lastClusterSweep) >= j.cfg.ClusterCleanupCooldown
}

func (j *Janitor) runFinishedJobCleanup(ctx context.Context) error {
	if !j.cfg.DeleteFinishedJobs {
		return nil
	}

	cutoff := time.Now().Add(-j.cfg.FinishedJobGrace)
	deletedCount, err := deleteFinishedJobsClusterWide(ctx, j.clientset, cutoff)
	if err != nil {
		return err
	}

	if deletedCount > 0 {
		log.Printf("node=%s deleted %d finished job(s)", j.cfg.NodeName, deletedCount)
	}

	return nil
}

func (j *Janitor) runEmptyNamespaceCleanup(ctx context.Context) error {
	if !j.cfg.DeleteEmptyNamespaces {
		return nil
	}

	cutoff := time.Now().Add(-j.cfg.EmptyNamespaceGrace)
	deletedCount, err := deleteEmptyNamespacesClusterWide(
		ctx,
		j.clientset,
		cutoff,
		j.cfg.ProtectedNamespaces,
	)
	if err != nil {
		return err
	}

	if deletedCount > 0 {
		log.Printf("node=%s deleted %d empty namespace(s)", j.cfg.NodeName, deletedCount)
	}

	return nil
}

func (j *Janitor) measureNodeDiskUsage() (float64, error) {
	usage, err := host.DiskUsagePercent(j.cfg.HostRoot)
	if err != nil {
		return 0, err
	}

	return usage, nil
}

func (j *Janitor) logNodeDiskUsage(usage float64) {
	log.Printf(
		"node=%s disk usage %.2f%% trigger=%.1f%% target=%.1f%%",
		j.cfg.NodeName,
		usage,
		j.cfg.TriggerPercent,
		j.cfg.TargetPercent,
	)
}

func (j *Janitor) runDiskCleanupIfNeeded(ctx context.Context, usage float64, now time.Time) error {
	if usage < j.cfg.TriggerPercent {
		return nil
	}

	if j.diskCleanupCooldownRemaining(now) > 0 {
		log.Printf(
			"node=%s cleanup suppressed by cooldown remaining=%s",
			j.cfg.NodeName,
			j.diskCleanupCooldownRemaining(now),
		)
		return nil
	}

	return j.runDiskCleanup(ctx, usage, now)
}

func (j *Janitor) diskCleanupCooldownRemaining(now time.Time) time.Duration {
	if j.lastCleanupTime.IsZero() {
		return 0
	}

	elapsed := now.Sub(j.lastCleanupTime)
	if elapsed >= j.cfg.CleanupCooldown {
		return 0
	}

	return j.cfg.CleanupCooldown - elapsed
}

func (j *Janitor) runDiskCleanup(ctx context.Context, usageBefore float64, now time.Time) error {
	j.lastCleanupTime = now

	j.deleteTerminatedPodsIfEnabled(ctx)
	j.runHostCleanupCommand(ctx)

	usageAfter, err := j.measureNodeDiskUsage()
	if err != nil {
		return err
	}

	log.Printf(
		"node=%s cleanup completed before=%.2f%% after=%.2f%% reclaimed=%.2f%%",
		j.cfg.NodeName,
		usageBefore,
		usageAfter,
		usageBefore-usageAfter,
	)

	if usageAfter > j.cfg.TargetPercent {
		log.Printf(
			"node=%s disk usage still above target after cleanup current=%.2f%% target=%.1f%%",
			j.cfg.NodeName,
			usageAfter,
			j.cfg.TargetPercent,
		)
	}

	return nil
}

func (j *Janitor) deleteTerminatedPodsIfEnabled(ctx context.Context) {
	if !j.cfg.DeleteTerminatedPods {
		return
	}

	cutoff := time.Now().Add(-j.cfg.TerminatedPodGrace)
	deletedCount, err := cleanup.DeleteTerminatedPodsOnNode(ctx, j.clientset, j.cfg.NodeName, cutoff)
	if err != nil {
		log.Printf("node=%s delete terminated pods failed: %v", j.cfg.NodeName, err)
		return
	}

	log.Printf("node=%s deleted %d terminated pod object(s)", j.cfg.NodeName, deletedCount)
}

func (j *Janitor) runHostCleanupCommand(ctx context.Context) {
	output, err := j.runScript(ctx, j.cfg.HostCleanupShellCommand)
	if err != nil {
		log.Printf("node=%s host cleanup command failed: %v", j.cfg.NodeName, err)
	}
	if strings.TrimSpace(output) != "" {
		log.Printf("node=%s host cleanup output:\n%s", j.cfg.NodeName, output)
	}
}
