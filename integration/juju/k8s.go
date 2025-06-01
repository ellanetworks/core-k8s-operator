package juju

import (
	"fmt"
)

const (
	addK8sCommand = "add-k8s"
)

type AddK8sOptions struct {
	Name   string
	Client bool
}

func (j Juju) AddK8s(opts *AddK8sOptions) error {
	if opts.Name == "" {
		return fmt.Errorf("k8s name is required")
	}

	args := []string{addK8sCommand, opts.Name}

	if opts.Client {
		args = append(args, "--client")
	}

	_, err := j.Runner.Run(args...)
	if err != nil {
		return fmt.Errorf("failed to add k8s: %w", err)
	}

	return nil
}
