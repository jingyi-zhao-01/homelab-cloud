package main

import (
	"context"
	"log"
	"time"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	clientset, err := newClientset()
	if err != nil {
		log.Fatalf("build kubernetes client: %v", err)
	}

	j := &janitor{
		cfg:       cfg,
		clientset: clientset,
	}

	log.Printf(
		"node-disk-janitor started node=%s host_root=%s trigger=%.1f%% target=%.1f%% interval=%s cooldown=%s",
		cfg.nodeName,
		cfg.hostRoot,
		cfg.triggerPercent,
		cfg.targetPercent,
		cfg.checkInterval,
		cfg.cleanupCooldown,
	)

	ctx := context.Background()
	ticker := time.NewTicker(cfg.checkInterval)
	defer ticker.Stop()

	if err := j.tick(ctx); err != nil {
		log.Printf("initial tick failed: %v", err)
	}

	for range ticker.C {
		if err := j.tick(ctx); err != nil {
			log.Printf("tick failed: %v", err)
		}
	}
}
