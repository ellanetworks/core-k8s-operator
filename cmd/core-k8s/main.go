package main

import (
	"context"
	"os"

	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/ellanetworks/core-k8s/internal/k8s"
	"github.com/gruyaume/goops"
)

func main() {
	env := goops.ReadEnv()

	k8sClient, err := k8s.New(env.ModelName)
	if err != nil {
		goops.LogErrorf("could not create k8s client: %v", err)
		os.Exit(1)
	}

	ctx := context.Background()

	err = charm.Configure(ctx, k8sClient)
	if err != nil {
		goops.LogErrorf("could not configure charm: %v", err)
		os.Exit(1)
	}
}
