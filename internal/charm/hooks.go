package charm

import (
	"fmt"
	"strings"

	"github.com/canonical/pebble/client"
	"github.com/gruyaume/goops"
	"github.com/gruyaume/goops/commands"
)

const (
	ContainerName = "core"
	DBPath        = "/var/lib/core/core.db"
	ConfigPath    = "/etc/core/core.yaml"
	APIPort       = 2111
	N2Port        = 38412
)

func setPorts(hookContext *goops.HookContext) error {
	setPortOpts := &commands.SetPortsOptions{
		Ports: []*commands.Port{
			{
				Port:     APIPort,
				Protocol: "tcp",
			},
		},
	}

	err := hookContext.Commands.SetPorts(setPortOpts)
	if err != nil {
		return fmt.Errorf("could not set ports: %w", err)
	}

	return nil
}

func getAppName(hookContext *goops.HookContext) string {
	unitName := hookContext.Environment.JujuUnitName()
	parts := strings.Split(unitName, "/")
	appName := parts[0]

	return appName
}

func getPodName(hookContext *goops.HookContext) string {
	unitName := hookContext.Environment.JujuUnitName()
	parts := strings.Split(unitName, "/")
	podName := strings.Join(parts, "-")

	return podName
}

func HandleDefaultHook(hookContext *goops.HookContext) {
	isLeader, err := hookContext.Commands.IsLeader()
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not check if unit is leader:", err.Error())
		return
	}

	if !isLeader {
		hookContext.Commands.JujuLog(commands.Warning, "Unit is not leader")
		return
	}

	err = setPorts(hookContext)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not set ports:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Ports set")

	modelName := hookContext.Environment.JujuModelName()

	k8s, err := NewK8s(modelName)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not create k8s client:", err.Error())
		return
	}

	configGetOpts := &commands.ConfigGetOptions{
		Key: "n2-ip",
	}

	n2IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not get n2-ip config:", err.Error())
		return
	}

	configGetOpts = &commands.ConfigGetOptions{
		Key: "n3-ip",
	}

	n3IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not get n3-ip config:", err.Error())
		return
	}

	configGetOpts = &commands.ConfigGetOptions{
		Key: "n6-ip",
	}

	n6IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not get n6-ip config:", err.Error())
		return
	}

	appName := getAppName(hookContext)
	patchK8sResourcesOpts := &PatchK8sResourcesOptions{
		N2IPAddress:     n2IPAddress,
		N3IPAddress:     n3IPAddress,
		N6IPAddress:     n6IPAddress,
		StatefulsetName: appName,
		ContainerName:   ContainerName,
		AppName:         appName,
		UnitName:        hookContext.Environment.JujuUnitName(),
		PodName:         getPodName(hookContext),
		N2ServiceName:   fmt.Sprintf("%s-external", appName),
	}

	err = k8s.patchK8sResources(patchK8sResourcesOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not patch k8s resources:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "K8s resources patched")

	pebble, err := client.New(&client.Config{Socket: socketPath})
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not connect to pebble:", err.Error())
		return
	}

	expectedConfig, err := getExpectedConfig()
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not get expected config:", err.Error())
		return
	}

	err = pushConfigFile(pebble, expectedConfig, ConfigPath)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not push config file:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Config file pushed")

	err = addPebbleLayer(pebble)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not add pebble layer:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Pebble layer added")

	err = startPebbleService(pebble)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not start pebble service:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Pebble service started")
}

func SetStatus(hookContext *goops.HookContext) {
	status := commands.StatusActive

	message := ""

	statusSetOpts := &commands.StatusSetOptions{
		Name:    status,
		Message: message,
	}

	err := hookContext.Commands.StatusSet(statusSetOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not set status:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Status set to active")
}
