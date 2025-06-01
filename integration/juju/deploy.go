package juju

import (
	"fmt"
)

const (
	deployCommand = "deploy"
)

type DeployOptions struct {
	Charm           string
	ApplicationName string
	Resources       map[string]string // Optional resources for the charm
}

func (j Juju) Deploy(opts *DeployOptions) error {
	if opts.Charm == "" {
		return fmt.Errorf("charm is required")
	}

	args := []string{deployCommand, opts.Charm}
	if opts.ApplicationName != "" {
		args = append(args, opts.ApplicationName)
	}

	for resource, value := range opts.Resources {
		args = append(args, "--resource", fmt.Sprintf("%s=%s", resource, value))
	}

	_, err := j.Runner.Run(args...)
	if err != nil {
		return fmt.Errorf("failed to set status: %w", err)
	}

	return nil
}
