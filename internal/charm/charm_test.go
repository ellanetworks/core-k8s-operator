package charm_test

import (
	"reflect"
	"testing"

	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/ellanetworks/core-k8s/internal/k8s"
	"github.com/gruyaume/goops/goopstest"
)

type FakeK8s struct{}

func (f FakeK8s) PatchResources(*k8s.PatchResourcesOptions) error {
	return nil
}

func ConfigureWithFakeK8s() error {
	fakeK8s := &FakeK8s{}

	err := charm.Configure(fakeK8s)
	if err != nil {
		return err
	}

	return nil
}

func TestGivenNotLeaderWhenConfigureThenStatusBlocked(t *testing.T) {
	ctx := goopstest.NewContext(
		ConfigureWithFakeK8s,
	)

	stateIn := goopstest.State{
		Leader: false,
	}

	stateOut := ctx.Run("install", stateIn)

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	expectedStatus := goopstest.Status{
		Name:    "blocked",
		Message: "Unit is not leader",
	}
	if stateOut.UnitStatus != expectedStatus {
		t.Errorf("expected status %v, got %v", expectedStatus, stateOut.UnitStatus)
	}
}

func TestGivenLeaderWhenConfigureThenPortsSet(t *testing.T) {
	ctx := goopstest.NewContext(
		ConfigureWithFakeK8s,
	)

	stateIn := goopstest.State{
		Leader: true,
	}

	stateOut := ctx.Run("install", stateIn)

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	expectedPorts := goopstest.Port{
		Port:     2111,
		Protocol: "tcp",
	}
	if !reflect.DeepEqual(stateOut.Ports, []goopstest.Port{expectedPorts}) {
		t.Errorf("expected ports %v, got %v", []goopstest.Port{expectedPorts}, stateOut.Ports)
	}
}

func TestGivenInvalidConfigWhenConfigureThenStatusBlocked(t *testing.T) {
	ctx := goopstest.NewContext(
		ConfigureWithFakeK8s,
	)

	stateIn := goopstest.State{
		Leader: true,
		Config: map[string]any{
			"logging-level": "",
			"n2-ip":         "2.2.2.2",
			"n3-ip":         "3.3.3.3",
			"n6-ip":         "6.6.6.6",
		},
	}

	stateOut := ctx.Run("install", stateIn)

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	expectedStatus := goopstest.Status{
		Name:    "blocked",
		Message: "Invalid config: logging-level is required",
	}
	if stateOut.UnitStatus != expectedStatus {
		t.Errorf("expected status %v, got %v", expectedStatus, stateOut.UnitStatus)
	}
}

func TestGivenCantConnectToPebbleWhenConfigureThenStatusIsWaiting(t *testing.T) {
	ctx := goopstest.NewContext(
		ConfigureWithFakeK8s,
	)

	stateIn := goopstest.State{
		Leader: true,
		Config: map[string]any{
			"logging-level": "debug",
			"n2-ip":         "2.2.2.2",
			"n3-ip":         "3.3.3.3",
			"n6-ip":         "6.6.6.6",
		},
		Containers: []goopstest.Container{
			{
				Name: "core",
			},
		},
	}

	stateOut := ctx.Run("install", stateIn)

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	expectedStatus := goopstest.Status{
		Name:    "waiting",
		Message: "Waiting for pebble to be ready",
	}
	if stateOut.UnitStatus != expectedStatus {
		t.Errorf("expected status %v, got %v", expectedStatus, stateOut.UnitStatus)
	}
}
