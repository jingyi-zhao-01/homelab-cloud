package main

import (
	"os"
	"path/filepath"

	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

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
