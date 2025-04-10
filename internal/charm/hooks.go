package charm

import (
	"fmt"

	"github.com/canonical/pebble/client"
	"github.com/gruyaume/goops"
	"github.com/gruyaume/goops/commands"
)

const (
	DBPath                            = "/var/lib/core/core.db"
	ConfigPath                        = "/etc/core/core.yaml"
	N2Port                            = 38412
	APIPort                           = 2111
	N3InterfaceBridgeName             = "n3-br"
	N3NetworkAttachmentDefinitionName = "core-n3"
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
		Key: "n3-ip",
	}

	n3IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not get n3-ip config:", err.Error())
		return
	}

	createNADOpts := &CreateNADOptions{
		Name: N3NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						n3IPAddress,
					},
				},
			},
			Capabilities: Capabilities{
				Mac: true,
			},
			Type:   "bridge",
			Bridge: N3InterfaceBridgeName,
		},
	}

	err = k8s.createNad(createNADOpts)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not create random NAD:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Random NAD created")

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
