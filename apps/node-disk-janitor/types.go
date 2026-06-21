package main

import (
	"time"

	"k8s.io/client-go/kubernetes"
)

type janitor struct {
	cfg              config
	clientset        kubernetes.Interface
	lastCleanupTime  time.Time
	lastClusterSweep time.Time
	lastSelfHealTime time.Time
}

type connectivityStatus struct {
	tailscaledPresent bool
	tailscaledActive  bool
	hasTailscaleIPv4  bool
	k3sService        string
	k3sActive         bool
	peer              string
	peerReachable     bool
	peerCheckSkipped  bool
}
