package main

import (
	"os"

	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/gruyaume/goops"
)

func main() {
	hookContext := goops.NewHookContext()
	hookName := hookContext.Environment.JujuHookName()

	if hookName != "" {
		charm.HandleDefaultHook(hookContext)
		charm.SetStatus(hookContext)
		os.Exit(0)
	}
}
