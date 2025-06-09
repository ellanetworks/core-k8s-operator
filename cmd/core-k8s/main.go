package main

import (
	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/gruyaume/goops"
)

func main() {
	err := charm.Configure()
	if err != nil {
		goops.LogErrorf("could not configure charm: %v", err)
		return
	}
}
