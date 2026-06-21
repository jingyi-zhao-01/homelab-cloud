package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
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
	tailscaleSelfHeal       bool
	selfHealCooldown        time.Duration
	tailscalePingTimeout    time.Duration
	tailscalePeer           string
	restartK3SOnHeal        bool
}

type janitor struct {
	cfg              config
	clientset        kubernetes.Interface
	lastCleanupTime  time.Time
	lastSelfHealTime time.Time
}

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

func newClientset() (kubernetes.Interface, error) {
	inCluster, err := rest.InClusterConfig()
	if err == nil {
		return kubernetes.NewForConfig(inCluster)
	}

	kubeconfig := os.Getenv("KUBECONFIG")
	if kubeconfig == "" {
		home, homeErr := os.UserHomeDir()
		if homeErr == nil {
			kubeconfig = filepath.Join(home, ".kube", "config")
		}
	}
	if kubeconfig == "" {
		return nil, err
	}

	outOfCluster, buildErr := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if buildErr != nil {
		return nil, buildErr
	}
	return kubernetes.NewForConfig(outOfCluster)
}

func (j *janitor) tick(ctx context.Context) error {
	if j.cfg.tailscaleSelfHeal {
		if err := j.ensureNodeConnectivity(ctx); err != nil {
			log.Printf("node=%s connectivity self-heal failed: %v", j.cfg.nodeName, err)
		}
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

func (j *janitor) ensureNodeConnectivity(ctx context.Context) error {
	status, err := j.inspectConnectivity(ctx)
	if err != nil {
		return err
	}

	if !status.tailscaledPresent {
		log.Printf("node=%s tailscale self-heal skipped: tailscaled service not present", j.cfg.nodeName)
		return nil
	}

	if status.tailscaledActive && status.hasTailscaleIPv4 && (status.peerCheckSkipped || status.peerReachable) && (status.k3sService == "" || status.k3sActive) {
		return nil
	}

	if time.Since(j.lastSelfHealTime) < j.cfg.selfHealCooldown {
		log.Printf(
			"node=%s self-heal suppressed by cooldown remaining=%s tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
			j.cfg.nodeName,
			j.cfg.selfHealCooldown-time.Since(j.lastSelfHealTime),
			status.tailscaledActive,
			status.hasTailscaleIPv4,
			status.peer,
			status.peerReachable,
			status.k3sService,
			status.k3sActive,
		)
		return nil
	}

	j.lastSelfHealTime = time.Now()

	log.Printf(
		"node=%s starting self-heal tailscaled_active=%t tailscale_ip=%t peer=%q peer_reachable=%t k3s_service=%q k3s_active=%t",
		j.cfg.nodeName,
		status.tailscaledActive,
		status.hasTailscaleIPv4,
		status.peer,
		status.peerReachable,
		status.k3sService,
		status.k3sActive,
	)

	needsTailscaleRestart := !status.tailscaledActive || !status.hasTailscaleIPv4 || (!status.peerCheckSkipped && !status.peerReachable)
	needsK3SRestart := (status.k3sService != "" && !status.k3sActive) || (needsTailscaleRestart && j.cfg.restartK3SOnHeal && status.k3sService != "")

	output, err := j.runHostScript(ctx, buildSelfHealScript(needsTailscaleRestart, needsK3SRestart, status.k3sService))
	if strings.TrimSpace(output) != "" {
		log.Printf("node=%s self-heal output:\n%s", j.cfg.nodeName, output)
	}
	if err != nil {
		return err
	}

	return nil
}

func (j *janitor) inspectConnectivity(ctx context.Context) (connectivityStatus, error) {
	output, err := j.runHostScript(ctx, j.inspectConnectivityScript())
	if err != nil {
		return connectivityStatus{}, fmt.Errorf("inspect connectivity: %w", err)
	}

	values := map[string]string{}
	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		values[parts[0]] = parts[1]
	}

	status := connectivityStatus{
		tailscaledPresent: values["TAILSCALED_PRESENT"] == "true",
		tailscaledActive:  values["TAILSCALED_ACTIVE"] == "true",
		hasTailscaleIPv4:  values["TAILSCALE_HAS_IPV4"] == "true",
		k3sService:        values["K3S_SERVICE"],
		k3sActive:         values["K3S_ACTIVE"] == "true",
		peer:              values["PEER"],
		peerReachable:     values["PEER_REACHABLE"] == "true",
		peerCheckSkipped:  values["PEER_REACHABLE"] == "skip",
	}

	return status, nil
}

func (j *janitor) inspectConnectivityScript() string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

override_peer=%q
ping_timeout=%d

tailscaled_present=false
tailscaled_active=false
tailscale_has_ipv4=false
k3s_service=""
k3s_active=false
peer=""
peer_reachable=skip

if [ "$(systemctl show -p LoadState --value tailscaled 2>/dev/null || true)" = "loaded" ]; then
  tailscaled_present=true
  if systemctl is-active --quiet tailscaled; then
    tailscaled_active=true
  fi
  if tailscale ip -4 >/dev/null 2>&1; then
    tailscale_has_ipv4=true
  fi
fi

if [ -n "$override_peer" ]; then
  peer="$override_peer"
elif [ -f /etc/systemd/system/k3s-agent.service.env ]; then
  # shellcheck disable=SC1091
  . /etc/systemd/system/k3s-agent.service.env
  peer="${K3S_URL:-}"
  peer="${peer#https://}"
  peer="${peer#http://}"
  peer="${peer%%%%:*}"
fi

if [ "$(systemctl show -p LoadState --value k3s-agent 2>/dev/null || true)" = "loaded" ]; then
  k3s_service="k3s-agent"
elif [ "$(systemctl show -p LoadState --value k3s 2>/dev/null || true)" = "loaded" ]; then
  k3s_service="k3s"
fi

if [ -n "$k3s_service" ] && systemctl is-active --quiet "$k3s_service"; then
  k3s_active=true
fi

if [ -n "$peer" ] && [ "$tailscaled_present" = true ] && [ "$tailscaled_active" = true ]; then
  if timeout "$ping_timeout" tailscale ping --timeout=5s --c=1 "$peer" >/dev/null 2>&1; then
    peer_reachable=true
  else
    peer_reachable=false
  fi
fi

printf 'TAILSCALED_PRESENT=%%s\n' "$tailscaled_present"
printf 'TAILSCALED_ACTIVE=%%s\n' "$tailscaled_active"
printf 'TAILSCALE_HAS_IPV4=%%s\n' "$tailscale_has_ipv4"
printf 'K3S_SERVICE=%%s\n' "$k3s_service"
printf 'K3S_ACTIVE=%%s\n' "$k3s_active"
printf 'PEER=%%s\n' "$peer"
printf 'PEER_REACHABLE=%%s\n' "$peer_reachable"
`, j.cfg.tailscalePeer, int(j.cfg.tailscalePingTimeout.Seconds()))
}

func buildSelfHealScript(restartTailscale, restartK3S bool, k3sService string) string {
	return fmt.Sprintf(`
set -eu

export PATH="/var/lib/rancher/k3s/data/current/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

restart_tailscale=%q
restart_k3s=%q
k3s_service=%q

if [ "$restart_tailscale" = "true" ]; then
  echo "[janitor] restarting tailscaled"
  systemctl restart tailscaled
  sleep 5
fi

if [ "$restart_k3s" = "true" ] && [ -n "$k3s_service" ]; then
  echo "[janitor] restarting $k3s_service"
  systemctl restart "$k3s_service"
fi
`, strconv.FormatBool(restartTailscale), strconv.FormatBool(restartK3S), k3sService)
}

func (j *janitor) deleteTerminatedPodsOnNode(ctx context.Context) (int, error) {
	selector := fields.OneTermEqualSelector("spec.nodeName", j.cfg.nodeName).String()
	pods, err := j.clientset.CoreV1().Pods("").List(ctx, metav1.ListOptions{FieldSelector: selector})
	if err != nil {
		return 0, err
	}

	deleted := 0
	cutoff := time.Now().Add(-j.cfg.terminatedPodGrace)
	for _, pod := range pods.Items {
		if !isTerminatedPod(pod, cutoff) {
			continue
		}
		err := j.clientset.CoreV1().Pods(pod.Namespace).Delete(ctx, pod.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete pod %s/%s failed: %v", pod.Namespace, pod.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func isTerminatedPod(pod corev1.Pod, cutoff time.Time) bool {
	switch pod.Status.Phase {
	case corev1.PodFailed, corev1.PodSucceeded:
	default:
		return false
	}

	if pod.DeletionTimestamp != nil {
		return false
	}

	if pod.Status.StartTime != nil && pod.Status.StartTime.Time.After(cutoff) {
		return false
	}

	for _, status := range pod.Status.ContainerStatuses {
		if status.State.Terminated == nil && status.LastTerminationState.Terminated == nil {
			return false
		}
	}

	return true
}

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
		"sh", "-lc", script,
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
