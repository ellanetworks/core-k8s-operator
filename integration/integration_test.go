package integration_test

import (
	"os"
	"testing"

	"github.com/ellanetworks/core-k8s/integration/juju"
)

const (
	CharmPath     = "./ella-core-k8s_amd64.charm"
	JujuModelName = "test-model"
	CloudName     = "test-cloud"
)

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

	t.Log("K8s added successfully")

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

	t.Log("Model added successfully")

	err = jujuClient.Deploy(&juju.DeployOptions{
		Charm: CharmPath,
	})
	if err != nil {
		t.Fatalf("Failed to deploy: %v", err)
	}

	t.Log("Deployment successful")
}
