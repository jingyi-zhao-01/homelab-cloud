package main

import (
	"slices"
	"time"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
)

func isTerminatedPod(pod corev1.Pod, cutoff time.Time) bool {
	switch pod.Status.Phase {
	case corev1.PodFailed, corev1.PodSucceeded:
	default:
		return false
	}

	if pod.DeletionTimestamp != nil {
		return false
	}

	if pod.Status.StartTime != nil && pod.Status.StartTime.After(cutoff) {
		return false
	}

	for _, status := range pod.Status.ContainerStatuses {
		if status.State.Terminated == nil && status.LastTerminationState.Terminated == nil {
			return false
		}
	}

	return true
}

func isFinishedJob(job batchv1.Job, cutoff time.Time) bool {
	if job.DeletionTimestamp != nil || job.Status.Active > 0 {
		return false
	}

	finishedAt := jobFinishedTime(job)
	if finishedAt == nil || finishedAt.After(cutoff) {
		return false
	}

	return true
}

func jobFinishedTime(job batchv1.Job) *time.Time {
	for _, condition := range job.Status.Conditions {
		if (condition.Type == batchv1.JobComplete || condition.Type == batchv1.JobFailed) && condition.Status == corev1.ConditionTrue {
			finished := condition.LastTransitionTime.Time
			return &finished
		}
	}

	if job.Status.CompletionTime != nil {
		finished := job.Status.CompletionTime.Time
		return &finished
	}

	return nil
}

func isNamespaceCleanupCandidate(namespace corev1.Namespace, cutoff time.Time, protected []string) bool {
	if namespace.DeletionTimestamp != nil || namespace.Status.Phase != corev1.NamespaceActive {
		return false
	}
	if namespace.CreationTimestamp.After(cutoff) {
		return false
	}
	return !slices.Contains(protected, namespace.Name)
}
