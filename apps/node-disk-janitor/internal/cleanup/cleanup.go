package cleanup

import (
	"context"
	"log"
	"time"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
	"k8s.io/client-go/kubernetes"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
)

func DeleteTerminatedPodsOnNode(ctx context.Context, clientset kubernetes.Interface, nodeName string, cutoff time.Time) (int, error) {
	selector := fields.OneTermEqualSelector("spec.nodeName", nodeName).String()
	pods, err := clientset.CoreV1().Pods("").List(ctx, metav1.ListOptions{FieldSelector: selector})
	if err != nil {
		return 0, err
	}

	deleted := 0
	for _, pod := range pods.Items {
		if !IsTerminatedPod(pod, cutoff) {
			continue
		}
		err := clientset.CoreV1().Pods(pod.Namespace).Delete(ctx, pod.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete pod %s/%s failed: %v", pod.Namespace, pod.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func DeleteFinishedJobsClusterWide(ctx context.Context, clientset kubernetes.Interface, cutoff time.Time) (int, error) {
	jobs, err := clientset.BatchV1().Jobs("").List(ctx, metav1.ListOptions{})
	if err != nil {
		return 0, err
	}

	deleted := 0
	for _, job := range jobs.Items {
		if !IsFinishedJob(job, cutoff) {
			continue
		}
		err := clientset.BatchV1().Jobs(job.Namespace).Delete(ctx, job.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete job %s/%s failed: %v", job.Namespace, job.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func DeleteEmptyNamespacesClusterWide(
	ctx context.Context,
	clientset kubernetes.Interface,
	cutoff time.Time,
	protected []string,
) (int, error) {
	namespaces, err := clientset.CoreV1().Namespaces().List(ctx, metav1.ListOptions{})
	if err != nil {
		return 0, err
	}

	deleted := 0
	for _, namespace := range namespaces.Items {
		if !IsNamespaceCleanupCandidate(namespace, cutoff, protected) {
			continue
		}

		empty, err := NamespaceHasNoWorkloads(ctx, clientset, namespace.Name)
		if err != nil {
			log.Printf("inspect namespace %s failed: %v", namespace.Name, err)
			continue
		}
		if !empty {
			continue
		}

		err = clientset.CoreV1().Namespaces().Delete(ctx, namespace.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete namespace %s failed: %v", namespace.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func NamespaceHasNoWorkloads(ctx context.Context, clientset kubernetes.Interface, namespace string) (bool, error) {
	pods, err := clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(pods.Items) > 0 {
		return false, nil
	}

	services, err := clientset.CoreV1().Services(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(services.Items) > 0 {
		return false, nil
	}

	pvcs, err := clientset.CoreV1().PersistentVolumeClaims(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(pvcs.Items) > 0 {
		return false, nil
	}

	deployments, err := clientset.AppsV1().Deployments(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(deployments.Items) > 0 {
		return false, nil
	}

	statefulSets, err := clientset.AppsV1().StatefulSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(statefulSets.Items) > 0 {
		return false, nil
	}

	daemonSets, err := clientset.AppsV1().DaemonSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(daemonSets.Items) > 0 {
		return false, nil
	}

	replicaSets, err := clientset.AppsV1().ReplicaSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(replicaSets.Items) > 0 {
		return false, nil
	}

	jobs, err := clientset.BatchV1().Jobs(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(jobs.Items) > 0 {
		return false, nil
	}

	cronJobs, err := clientset.BatchV1().CronJobs(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	return len(cronJobs.Items) == 0, nil
}

func IsTerminatedPod(pod corev1.Pod, cutoff time.Time) bool {
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

func IsFinishedJob(job batchv1.Job, cutoff time.Time) bool {
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

func IsNamespaceCleanupCandidate(namespace corev1.Namespace, cutoff time.Time, protected []string) bool {
	if namespace.DeletionTimestamp != nil || namespace.Status.Phase != corev1.NamespaceActive {
		return false
	}
	if namespace.CreationTimestamp.After(cutoff) {
		return false
	}
	return !contains(protected, namespace.Name)
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
