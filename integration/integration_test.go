package integration_test

import (
	"os"
	"testing"

	"github.com/ellanetworks/core-k8s/integration/juju"
)

const (
	CharmPath     = "./ella-core-k8s_amd64.charm"
	JujuModelName = "test-model"
)

func TestIntegration(t *testing.T) {
	if os.Getenv("INTEGRATION") == "" {
		t.Skip("skipping integration tests, set environment variable INTEGRATION")
	}

	jujuClient := juju.New()

	jujuModels, err := jujuClient.ListModels()
	if err != nil {
		t.Fatalf("Failed to list models: %v", err)
	}

	for _, model := range jujuModels {
		if model.ShortName == JujuModelName {
			t.Fatalf("Model %s already exists", JujuModelName)
		}
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
