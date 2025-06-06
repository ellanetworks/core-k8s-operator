package main

import (
	"os"

	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/gruyaume/goops"
)

func main() {
	env := goops.ReadEnv()

	if env.HookName != "" {
		charm.HandleDefaultHook()
		charm.SetStatus()
		os.Exit(0)
	}
}
