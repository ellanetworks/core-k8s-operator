package juju

import (
	"bytes"
	"fmt"
	"os/exec"
)

const (
	baseCommand = "juju"
)

type JujuCommand struct{}

// CommandRunner is an interface for running commands.
// It allows for mocking in tests.
type CommandRunner interface {
	Run(args ...string) ([]byte, error)
}

type Juju struct {
	Runner CommandRunner
}

func New() *Juju {
	return &Juju{
		Runner: &JujuCommand{},
	}
}

func (j *JujuCommand) Run(args ...string) ([]byte, error) {
	cmd := exec.Command(baseCommand, args...)

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("command %s %s failed: %s: %w", baseCommand, args, stderr.String(), err)
	}

	return output, nil
}
