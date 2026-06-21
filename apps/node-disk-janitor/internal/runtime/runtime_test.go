package runtime

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jingyi-zhao-01/homelab-cloud/apps/node-disk-janitor/internal/config"
	"k8s.io/client-go/kubernetes"
)

func TestDiskCleanupCooldownRemainingReturnsZeroWhenNeverRun(t *testing.T) {
	j := Janitor{
		cfg: config.JanitorConfig{
			CleanupCooldown: 5 * time.Minute,
		},
	}

	if remaining := j.diskCleanupCooldownRemaining(time.Now()); remaining != 0 {
		t.Fatalf("expected zero cooldown for a janitor that never cleaned up, got %s", remaining)
	}
}

func TestDiskCleanupCooldownRemainingReturnsRemainingDuration(t *testing.T) {
	now := time.Now()
	j := Janitor{
		cfg: config.JanitorConfig{
			CleanupCooldown: 5 * time.Minute,
		},
		lastCleanupTime: now.Add(-2 * time.Minute),
	}

	remaining := j.diskCleanupCooldownRemaining(now)
	if remaining < 2*time.Minute || remaining > 3*time.Minute {
		t.Fatalf("expected remaining cooldown to stay between 2m and 3m, got %s", remaining)
	}
}

func TestClusterCleanupDueReturnsFalseInsideCooldown(t *testing.T) {
	now := time.Now()
	j := Janitor{
		cfg: config.JanitorConfig{
			ClusterCleanupCooldown: 10 * time.Minute,
		},
		lastClusterSweep: now.Add(-2 * time.Minute),
	}

	if j.clusterCleanupDue(now) {
		t.Fatalf("expected cluster cleanup to stay suppressed inside cooldown")
	}
}

func TestClusterCleanupDueReturnsTrueAfterCooldown(t *testing.T) {
	now := time.Now()
	j := Janitor{
		cfg: config.JanitorConfig{
			ClusterCleanupCooldown: 10 * time.Minute,
		},
		lastClusterSweep: now.Add(-11 * time.Minute),
	}

	if !j.clusterCleanupDue(now) {
		t.Fatalf("expected cluster cleanup to run after cooldown expires")
	}
}

func TestRunClusterCleanupIfDueDoesNotConsumeCooldownOnFailure(t *testing.T) {
	now := time.Now()
	j := Janitor{
		cfg: config.JanitorConfig{
			ClusterCleanupCooldown: 10 * time.Minute,
			DeleteFinishedJobs:     true,
			FinishedJobGrace:       time.Minute,
		},
	}

	originalDeleteFinishedJobsClusterWide := deleteFinishedJobsClusterWide
	deleteFinishedJobsClusterWide = func(context.Context, kubernetes.Interface, time.Time) (int, error) {
		return 0, errors.New("boom")
	}
	defer func() {
		deleteFinishedJobsClusterWide = originalDeleteFinishedJobsClusterWide
	}()

	err := j.runClusterCleanupIfDue(context.Background(), now)
	if err == nil {
		t.Fatalf("expected cleanup failure to be returned")
	}
	if !j.lastClusterSweep.IsZero() {
		t.Fatalf("expected failed cleanup to leave cooldown untouched")
	}
}
