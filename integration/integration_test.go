package integration_test

import (
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/ellanetworks/core-k8s/integration/juju"
)

const (
	JujuModelName   = "test-model"
	CloudName       = "test-cloud"
	ApplicationName = "ella-core"
	EllaCoreImage   = "ghcr.io/ellanetworks/ella-core:v0.0.15"
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
			t.Log("Waiting for active status, current status:", status.Applications[appName].ApplicationStatus.Current)
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
	})
	if err != nil {
		t.Fatalf("Failed to deploy: %v", err)
	}

	t.Log("Charm is deployed")

	err = waitForActiveStatus(t, ApplicationName, jujuClient, 10*time.Minute)
	if err != nil {
		t.Fatalf("Failed to wait for active status: %v", err)
	}

	t.Log("Charm is active")
}
