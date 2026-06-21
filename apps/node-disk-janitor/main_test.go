package main

import (
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func TestIsTerminatedPodRejectsFreshSucceededPod(t *testing.T) {
	now := time.Now()
	pod := corev1.Pod{
		Status: corev1.PodStatus{
			Phase:     corev1.PodSucceeded,
			StartTime: &metav1.Time{Time: now},
			ContainerStatuses: []corev1.ContainerStatus{
				{
					State: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{},
					},
				},
			},
		},
	}

	if isTerminatedPod(pod, now.Add(-time.Minute)) {
		t.Fatalf("expected fresh succeeded pod to be skipped")
	}
}

func TestIsTerminatedPodAcceptsOldFailedPod(t *testing.T) {
	start := time.Now().Add(-10 * time.Minute)
	pod := corev1.Pod{
		Status: corev1.PodStatus{
			Phase:     corev1.PodFailed,
			StartTime: &metav1.Time{Time: start},
			ContainerStatuses: []corev1.ContainerStatus{
				{
					State: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{},
					},
				},
			},
		},
	}

	if !isTerminatedPod(pod, time.Now().Add(-time.Minute)) {
		t.Fatalf("expected old failed pod to qualify for deletion")
	}
}
