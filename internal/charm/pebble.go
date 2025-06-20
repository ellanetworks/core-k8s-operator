package charm

import (
	"fmt"
	"strings"

	"github.com/canonical/pebble/client"
	"github.com/gruyaume/goops"
	"gopkg.in/yaml.v3"
)

type PebbleLayer struct {
	Summary     string                   `yaml:"summary"`
	Description string                   `yaml:"description"`
	Services    map[string]ServiceConfig `yaml:"services"`
}

func pushConfigFile(pebble goops.PebbleClient, config []byte, path string) error {
	source := strings.NewReader(string(config))
	pushOptions := &client.PushOptions{
		Source: source,
		Path:   path,
	}

	err := pebble.Push(pushOptions)
	if err != nil {
		return fmt.Errorf("could not push config file: %w", err)
	}

	return nil
}

func addPebbleLayer(pebble goops.PebbleClient) error {
	layerData, err := yaml.Marshal(PebbleLayer{
		Summary:     "Ella Core layer",
		Description: "pebble config layer for Ella Core",
		Services: map[string]ServiceConfig{
			"core": {
				Override: "replace",
				Summary:  "Ella Core Service",
				Command:  "core --config " + ConfigPath,
				Startup:  "enabled",
			},
		},
	})
	if err != nil {
		return fmt.Errorf("could not marshal layer data to YAML: %w", err)
	}

	addLayerOpts := &client.AddLayerOptions{
		Combine:   true,
		Label:     "core",
		LayerData: layerData,
	}

	err = pebble.AddLayer(addLayerOpts)
	if err != nil {
		return fmt.Errorf("could not add pebble layer: %w", err)
	}

	return nil
}

func startPebbleService(pebble goops.PebbleClient) error {
	serviceOpts := &client.ServiceOptions{
		Names: []string{"core"},
	}

	_, err := pebble.Start(serviceOpts)
	if err != nil {
		return fmt.Errorf("could not start pebble service: %w", err)
	}

	return nil
}
