package main

import (
	"context"
	"log"
	"time"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
)

func (j *janitor) runClusterCleanup(ctx context.Context) error {
	if time.Since(j.lastClusterSweep) < j.cfg.clusterCleanupCooldown {
		return nil
	}

	j.lastClusterSweep = time.Now()

	if j.cfg.deleteFinishedJobs {
		deleted, err := j.deleteFinishedJobsClusterWide(ctx)
		if err != nil {
			log.Printf("node=%s delete finished jobs failed: %v", j.cfg.nodeName, err)
		} else if deleted > 0 {
			log.Printf("node=%s deleted %d finished job(s)", j.cfg.nodeName, deleted)
		}
	}

	if j.cfg.deleteEmptyNamespaces {
		deleted, err := j.deleteEmptyNamespacesClusterWide(ctx)
		if err != nil {
			log.Printf("node=%s delete empty namespaces failed: %v", j.cfg.nodeName, err)
		} else if deleted > 0 {
			log.Printf("node=%s deleted %d empty namespace(s)", j.cfg.nodeName, deleted)
		}
	}

	return nil
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

func (j *janitor) deleteFinishedJobsClusterWide(ctx context.Context) (int, error) {
	jobs, err := j.clientset.BatchV1().Jobs("").List(ctx, metav1.ListOptions{})
	if err != nil {
		return 0, err
	}

	deleted := 0
	cutoff := time.Now().Add(-j.cfg.finishedJobGrace)
	for _, job := range jobs.Items {
		if !isFinishedJob(job, cutoff) {
			continue
		}
		err := j.clientset.BatchV1().Jobs(job.Namespace).Delete(ctx, job.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete job %s/%s failed: %v", job.Namespace, job.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func (j *janitor) deleteEmptyNamespacesClusterWide(ctx context.Context) (int, error) {
	namespaces, err := j.clientset.CoreV1().Namespaces().List(ctx, metav1.ListOptions{})
	if err != nil {
		return 0, err
	}

	deleted := 0
	cutoff := time.Now().Add(-j.cfg.emptyNamespaceGrace)
	for _, namespace := range namespaces.Items {
		if !isNamespaceCleanupCandidate(namespace, cutoff, j.cfg.protectedNamespaces) {
			continue
		}

		empty, err := j.namespaceHasNoWorkloads(ctx, namespace.Name)
		if err != nil {
			log.Printf("inspect namespace %s failed: %v", namespace.Name, err)
			continue
		}
		if !empty {
			continue
		}

		err = j.clientset.CoreV1().Namespaces().Delete(ctx, namespace.Name, metav1.DeleteOptions{})
		if err != nil && !apierrors.IsNotFound(err) {
			log.Printf("delete namespace %s failed: %v", namespace.Name, err)
			continue
		}
		deleted++
	}

	return deleted, nil
}

func (j *janitor) namespaceHasNoWorkloads(ctx context.Context, namespace string) (bool, error) {
	pods, err := j.clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(pods.Items) > 0 {
		return false, nil
	}

	services, err := j.clientset.CoreV1().Services(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(services.Items) > 0 {
		return false, nil
	}

	pvcs, err := j.clientset.CoreV1().PersistentVolumeClaims(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(pvcs.Items) > 0 {
		return false, nil
	}

	deployments, err := j.clientset.AppsV1().Deployments(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(deployments.Items) > 0 {
		return false, nil
	}

	statefulSets, err := j.clientset.AppsV1().StatefulSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(statefulSets.Items) > 0 {
		return false, nil
	}

	daemonSets, err := j.clientset.AppsV1().DaemonSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(daemonSets.Items) > 0 {
		return false, nil
	}

	replicaSets, err := j.clientset.AppsV1().ReplicaSets(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(replicaSets.Items) > 0 {
		return false, nil
	}

	jobs, err := j.clientset.BatchV1().Jobs(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	if len(jobs.Items) > 0 {
		return false, nil
	}

	cronJobs, err := j.clientset.BatchV1().CronJobs(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return false, err
	}
	return len(cronJobs.Items) == 0, nil
}
