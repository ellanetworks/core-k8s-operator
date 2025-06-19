package charm_test

import (
	"reflect"
	"testing"

	"github.com/ellanetworks/core-k8s/internal/charm"
	"github.com/ellanetworks/core-k8s/internal/k8s"
	"github.com/gruyaume/goops/goopstest"
)

type FakeK8s struct{}

func (f FakeK8s) PatchK8sResources(*k8s.PatchK8sResourcesOptions) error {
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
	ctx := goopstest.Context{
		Charm: ConfigureWithFakeK8s,
	}

	stateIn := &goopstest.State{
		Leader: false,
	}

	stateOut, err := ctx.Run("install", stateIn)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	if stateOut.UnitStatus != "blocked" {
		t.Errorf("expected status 'blocked', got '%s'", stateOut.UnitStatus)
	}
}

func TestGivenLeaderWhenConfigureThenPortsSet(t *testing.T) {
	ctx := goopstest.Context{
		Charm: ConfigureWithFakeK8s,
	}

	stateIn := &goopstest.State{
		Leader: true,
	}

	stateOut, err := ctx.Run("install", stateIn)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	expectedPorts := &goopstest.Port{
		Port:     2111,
		Protocol: "tcp",
	}
	if !reflect.DeepEqual(stateOut.Ports, []*goopstest.Port{expectedPorts}) {
		t.Errorf("expected ports %v, got %v", []goopstest.Port{*expectedPorts}, stateOut.Ports)
	}
}

func TestGivenInvalidConfigWhenConfigureThenStatusBlocked(t *testing.T) {
	ctx := goopstest.Context{
		Charm: ConfigureWithFakeK8s,
	}

	stateIn := &goopstest.State{
		Leader: true,
		Config: map[string]string{
			"logging-level": "",
			"n2-ip":         "2.2.2.2",
			"n3-ip":         "3.3.3.3",
			"n6-ip":         "6.6.6.6",
		},
	}

	stateOut, err := ctx.Run("install", stateIn)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	if stateOut.UnitStatus != "blocked" {
		t.Errorf("expected status 'blocked', got '%s'", stateOut.UnitStatus)
	}
}

func TestGivenCantConnectToPebbleWhenConfigureThenStatusIsWaiting(t *testing.T) {
	ctx := goopstest.Context{
		Charm: ConfigureWithFakeK8s,
	}

	stateIn := &goopstest.State{
		Leader: true,
		Config: map[string]string{
			"logging-level": "debug",
			"n2-ip":         "2.2.2.2",
			"n3-ip":         "3.3.3.3",
			"n6-ip":         "6.6.6.6",
		},
		Containers: []*goopstest.Container{
			{
				Name: "core",
			},
		},
	}

	stateOut, err := ctx.Run("install", stateIn)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.CharmErr != nil {
		t.Fatalf("unexpected charm error: %v", ctx.CharmErr)
	}

	if stateOut.UnitStatus != "waiting" {
		t.Errorf("expected status 'waiting', got '%s'", stateOut.UnitStatus)
	}
}
