package integration_test

import (
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/gruyaume/go-juju/juju"
)

const (
	JujuModelName   = "test-model"
	ApplicationName = "ella-core"
	EllaCoreImage   = "ghcr.io/ellanetworks/ella-core:v0.0.18"
)

func getCharmPath() string {
	charmPath := os.Getenv("CHARM_PATH")
	if charmPath == "" {
		return "./ella-core-k8s_amd64.charm"
	}

	return charmPath
}

func waitForActiveStatus(t *testing.T, appName string, client *juju.Juju, timeout time.Duration) error {
	start := time.Now()

	for {
		if time.Since(start) > timeout {
			return fmt.Errorf("timed out waiting for active status")
		}

		status, err := client.Status()
		if err != nil {
			return err
		}

		if status.Applications[appName].ApplicationStatus.Current == "active" {
			return nil
		} else {
			t.Log("Waiting for active status, current status:", status)
		}

		time.Sleep(1 * time.Second)
	}
}

func TestIntegration(t *testing.T) {
	if os.Getenv("INTEGRATION") == "" {
		t.Skip("skipping integration tests, set environment variable INTEGRATION")
	}

	jujuClient := juju.New()

	err := jujuClient.AddModel(&juju.AddModelOptions{
		Name: JujuModelName,
	})
	if err != nil {
		t.Fatalf("Failed to add model: %v", err)
	}

	t.Log("Model is added")

	err = jujuClient.Deploy(&juju.DeployOptions{
		Charm:           getCharmPath(),
		ApplicationName: ApplicationName,
		Resources: map[string]string{
			"core-image": EllaCoreImage,
		},
		Trust: true,
	})
	if err != nil {
		t.Fatalf("Failed to deploy: %v", err)
	}

	t.Log("Charm is deployed")

	err = waitForActiveStatus(t, ApplicationName, jujuClient, 10*time.Minute)
	if err != nil {
		printDebugLogs(t, jujuClient)
		PrintKubectlLogs(t, JujuModelName, ApplicationName+"-0", "core")
		t.Fatalf("Failed to get active status: %v", err)
	}

	printDebugLogs(t, jujuClient)
	PrintKubectlLogs(t, JujuModelName, ApplicationName+"-0", "core")

	t.Log("Charm is active")
}

func printDebugLogs(t *testing.T, jujuClient *juju.Juju) {
	os.Stdout.Write([]byte("----Juju Debug Logs----\n"))

	err := jujuClient.PrintDebugLog(&juju.PrintDebugLogOptions{
		Replay: true,
	})
	if err != nil {
		t.Logf("Failed to capture logs: %v", err)
		return
	}

	os.Stdout.Write([]byte("\n----End of Debug Logs----\n"))
}
