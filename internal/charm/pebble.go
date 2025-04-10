package charm

import (
	"fmt"
	"strings"

	"github.com/canonical/pebble/client"
	"gopkg.in/yaml.v3"
)

const (
	socketPath = "/charm/containers/core/pebble.socket"
)

type PebbleLayer struct {
	Summary     string                   `yaml:"summary"`
	Description string                   `yaml:"description"`
	Services    map[string]ServiceConfig `yaml:"services"`
}

func pushConfigFile(pebbleClient *client.Client, config []byte, path string) error {
	_, err := pebbleClient.SysInfo()
	if err != nil {
		return fmt.Errorf("could not connect to pebble: %w", err)
	}

	source := strings.NewReader(string(config))
	pushOptions := &client.PushOptions{
		Source: source,
		Path:   path,
	}

	err = pebbleClient.Push(pushOptions)
	if err != nil {
		return fmt.Errorf("could not push config file: %w", err)
	}

	return nil
}

func addPebbleLayer(pebbleClient *client.Client) error {
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

	err = pebbleClient.AddLayer(addLayerOpts)
	if err != nil {
		return fmt.Errorf("could not add pebble layer: %w", err)
	}

	return nil
}

func startPebbleService(pebbleClient *client.Client) error {
	serviceOpts := &client.ServiceOptions{
		Names: []string{"core"},
	}

	_, err := pebbleClient.Start(serviceOpts)
	if err != nil {
		return fmt.Errorf("could not start pebble service: %w", err)
	}

	return nil
}
