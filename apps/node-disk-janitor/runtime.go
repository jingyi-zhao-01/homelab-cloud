package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"
)

func (j *janitor) tick(ctx context.Context) error {
	if j.cfg.tailscaleSelfHeal {
		if err := j.ensureNodeConnectivity(ctx); err != nil {
			log.Printf("node=%s connectivity self-heal failed: %v", j.cfg.nodeName, err)
		}
	}

	if err := j.runClusterCleanup(ctx); err != nil {
		log.Printf("node=%s cluster cleanup failed: %v", j.cfg.nodeName, err)
	}

	usage, err := diskUsagePercent(j.cfg.hostRoot)
	if err != nil {
		return fmt.Errorf("measure disk usage: %w", err)
	}

	log.Printf(
		"node=%s disk usage %.2f%% trigger=%.1f%% target=%.1f%%",
		j.cfg.nodeName,
		usage,
		j.cfg.triggerPercent,
		j.cfg.targetPercent,
	)

	if usage < j.cfg.triggerPercent {
		return nil
	}
	if time.Since(j.lastCleanupTime) < j.cfg.cleanupCooldown {
		log.Printf(
			"node=%s cleanup suppressed by cooldown remaining=%s",
			j.cfg.nodeName,
			j.cfg.cleanupCooldown-time.Since(j.lastCleanupTime),
		)
		return nil
	}

	before := usage
	j.lastCleanupTime = time.Now()

	if j.cfg.deleteTerminatedPods {
		deleted, err := j.deleteTerminatedPodsOnNode(ctx)
		if err != nil {
			log.Printf("node=%s delete terminated pods failed: %v", j.cfg.nodeName, err)
		} else {
			log.Printf("node=%s deleted %d terminated pod object(s)", j.cfg.nodeName, deleted)
		}
	}

	output, err := j.runHostCleanup(ctx)
	if err != nil {
		log.Printf("node=%s host cleanup command failed: %v", j.cfg.nodeName, err)
	}
	if strings.TrimSpace(output) != "" {
		log.Printf("node=%s host cleanup output:\n%s", j.cfg.nodeName, output)
	}

	after, afterErr := diskUsagePercent(j.cfg.hostRoot)
	if afterErr != nil {
		return fmt.Errorf("measure post-cleanup disk usage: %w", afterErr)
	}

	log.Printf(
		"node=%s cleanup completed before=%.2f%% after=%.2f%% reclaimed=%.2f%%",
		j.cfg.nodeName,
		before,
		after,
		before-after,
	)

	if after > j.cfg.targetPercent {
		log.Printf(
			"node=%s disk usage still above target after cleanup current=%.2f%% target=%.1f%%",
			j.cfg.nodeName,
			after,
			j.cfg.targetPercent,
		)
	}

	return nil
}
