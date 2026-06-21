package main

import (
	"context"
	"log"
	"time"

	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/config"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/host"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/kubeclient"
	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/runtime"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	clientset, err := kubeclient.New()
	if err != nil {
		log.Fatalf("build kubernetes client: %v", err)
	}

	j := runtime.New(cfg, clientset, host.RunScript)

	log.Printf(
		"node-disk-janitor started node=%s host_root=%s trigger=%.1f%% target=%.1f%% interval=%s cooldown=%s",
		cfg.NodeName,
		cfg.HostRoot,
		cfg.TriggerPercent,
		cfg.TargetPercent,
		cfg.CheckInterval,
		cfg.CleanupCooldown,
	)

	ctx := context.Background()
	ticker := time.NewTicker(cfg.CheckInterval)
	defer ticker.Stop()

	if err := j.RunMaintenanceCycle(ctx); err != nil {
		log.Printf("initial maintenance cycle failed: %v", err)
	}

	for range ticker.C {
		if err := j.RunMaintenanceCycle(ctx); err != nil {
			log.Printf("maintenance cycle failed: %v", err)
		}
	}
}
