package juju

import (
	"fmt"
)

const (
	bootstrapCommand = "bootstrap"
)

type BootstrapOptions struct {
	CloudName string
}

func (j Juju) Bootstrap(opts *BootstrapOptions) error {
	if opts.CloudName == "" {
		return fmt.Errorf("cloud name is required")
	}

	args := []string{bootstrapCommand, opts.CloudName}

	_, err := j.Runner.Run(args...)
	if err != nil {
		return fmt.Errorf("failed to bootstrap: %w", err)
	}

	return nil
}
