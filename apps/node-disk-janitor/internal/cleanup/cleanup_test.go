package cleanup

import (
	"testing"
	"time"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func TestIsTerminatedPodRejectsFreshSucceededPod(t *testing.T) {
	now := time.Now()
	pod := corev1.Pod{
		Status: corev1.PodStatus{
			Phase: corev1.PodSucceeded,
			ContainerStatuses: []corev1.ContainerStatus{
				{
					State: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{
							FinishedAt: metav1.Time{Time: now},
						},
					},
				},
			},
		},
	}

	if IsTerminatedPod(pod, now.Add(-time.Minute)) {
		t.Fatalf("expected fresh succeeded pod to be skipped")
	}
}

func TestIsTerminatedPodAcceptsOldFailedPod(t *testing.T) {
	finished := time.Now().Add(-10 * time.Minute)
	pod := corev1.Pod{
		Status: corev1.PodStatus{
			Phase: corev1.PodFailed,
			ContainerStatuses: []corev1.ContainerStatus{
				{
					State: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{
							FinishedAt: metav1.Time{Time: finished},
						},
					},
				},
			},
		},
	}

	if !IsTerminatedPod(pod, time.Now().Add(-time.Minute)) {
		t.Fatalf("expected old failed pod to qualify for deletion")
	}
}

func TestIsTerminatedPodRejectsRecentlyFinishedLongRunningPod(t *testing.T) {
	finished := time.Now()
	pod := corev1.Pod{
		Status: corev1.PodStatus{
			Phase:     corev1.PodSucceeded,
			StartTime: &metav1.Time{Time: finished.Add(-time.Hour)},
			ContainerStatuses: []corev1.ContainerStatus{
				{
					State: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{
							FinishedAt: metav1.Time{Time: finished},
						},
					},
				},
			},
		},
	}

	if IsTerminatedPod(pod, finished.Add(-time.Minute)) {
		t.Fatalf("expected recently finished long-running pod to be preserved")
	}
}

func TestIsFinishedJobAcceptsOldCompletedJob(t *testing.T) {
	finished := time.Now().Add(-20 * time.Minute)
	job := batchv1.Job{
		Status: batchv1.JobStatus{
			Conditions: []batchv1.JobCondition{
				{
					Type:               batchv1.JobComplete,
					Status:             corev1.ConditionTrue,
					LastTransitionTime: metav1.Time{Time: finished},
				},
			},
		},
	}

	if !IsFinishedJob(job, time.Now().Add(-10*time.Minute)) {
		t.Fatalf("expected old completed job to be deletable")
	}
}

func TestIsFinishedJobRejectsFreshFailedJob(t *testing.T) {
	finished := time.Now().Add(-2 * time.Minute)
	job := batchv1.Job{
		Status: batchv1.JobStatus{
			Conditions: []batchv1.JobCondition{
				{
					Type:               batchv1.JobFailed,
					Status:             corev1.ConditionTrue,
					LastTransitionTime: metav1.Time{Time: finished},
				},
			},
		},
	}

	if IsFinishedJob(job, time.Now().Add(-10*time.Minute)) {
		t.Fatalf("expected fresh failed job to be preserved")
	}
}

func TestNamespaceCleanupCandidateProtectsSystemNamespaces(t *testing.T) {
	namespace := corev1.Namespace{
		ObjectMeta: metav1.ObjectMeta{
			Name:              "kube-system",
			CreationTimestamp: metav1.Time{Time: time.Now().Add(-time.Hour)},
		},
		Status: corev1.NamespaceStatus{Phase: corev1.NamespaceActive},
	}

	protected := []string{"kube-system", "default"}

	if IsNamespaceCleanupCandidate(namespace, time.Now().Add(-10*time.Minute), protected) {
		t.Fatalf("expected kube-system to be protected")
	}
}
