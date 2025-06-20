package integration_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
)

func PrintKubectlLogs(t *testing.T, namespace, podName, containerName string) {
	kubeconfig := filepath.Join(homedir.HomeDir(), ".kube", "config")

	config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		t.Logf("Failed to load kubeconfig: %v", err)
		return
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		t.Logf("Failed to create Kubernetes client: %v", err)
		return
	}

	req := clientset.CoreV1().Pods(namespace).GetLogs(podName, &corev1.PodLogOptions{
		Container: containerName,
	})

	logs, err := req.Stream(context.Background())
	if err != nil {
		t.Logf("Failed to get logs for pod %s: %v", podName, err)
		return
	}
	defer logs.Close()

	os.Stdout.Write([]byte("---- Logs for pod " + podName + " ----\n"))

	buf := make([]byte, 4096)

	for {
		n, err := logs.Read(buf)
		if n > 0 {
			os.Stdout.Write(buf[:n])
		}

		if err != nil {
			break
		}
	}

	os.Stdout.Write([]byte("\n---- End of Logs ----\n"))
}
