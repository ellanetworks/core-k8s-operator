package integration_test

import (
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/ellanetworks/core-k8s/integration/juju"
)

const (
	CharmPath       = "../ella-core-k8s_amd64.charm"
	JujuModelName   = "test-model"
	CloudName       = "test-cloud"
	ApplicationName = "ella-core"
	EllaCoreImage   = "ghcr.io/ellanetworks/ella-core:v0.0.15"
)

func waitForActiveStatus(appName string, client *juju.Juju, timeout time.Duration) error {
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
		}

		time.Sleep(1 * time.Second)
	}
}

func TestIntegration(t *testing.T) {
	if os.Getenv("INTEGRATION") == "" {
		t.Skip("skipping integration tests, set environment variable INTEGRATION")
	}

	jujuClient := juju.New()

	err := jujuClient.AddK8s(&juju.AddK8sOptions{
		Name:   CloudName,
		Client: true,
	})
	if err != nil {
		t.Fatalf("Failed to add k8s: %v", err)
	}

	t.Log("K8s cloud is added")

	err = jujuClient.Bootstrap(&juju.BootstrapOptions{
		CloudName: CloudName,
	})
	if err != nil {
		t.Fatalf("Failed to bootstrap: %v", err)
	}

	err = jujuClient.AddModel(&juju.AddModelOptions{
		Name: JujuModelName,
	})
	if err != nil {
		t.Fatalf("Failed to add model: %v", err)
	}

	t.Log("Model is added")

	err = jujuClient.Deploy(&juju.DeployOptions{
		Charm:           CharmPath,
		ApplicationName: ApplicationName,
		Resources: map[string]string{
			"core-image": EllaCoreImage,
		},
	})
	if err != nil {
		t.Fatalf("Failed to deploy: %v", err)
	}

	t.Log("Charm is deployed")

	err = waitForActiveStatus(ApplicationName, jujuClient, 5*time.Minute)
	if err != nil {
		t.Fatalf("Failed to wait for active status: %v", err)
	}

	t.Log("Charm is active")
}
