package charm

import (
	"fmt"
	"strings"

	"github.com/canonical/pebble/client"
	"github.com/gruyaume/goops"
	"github.com/gruyaume/goops/commands"
)

const (
	ContainerName                     = "core"
	DBPath                            = "/var/lib/core/core.db"
	ConfigPath                        = "/etc/core/core.yaml"
	N2Port                            = 38412
	APIPort                           = 2111
	N2InterfaceBridgeName             = "n2-br"
	N2NetworkAttachmentDefinitionName = "core-n2"
	N2InterfaceName                   = "n2"
	N3InterfaceBridgeName             = "n3-br"
	N3NetworkAttachmentDefinitionName = "core-n3"
	N3InterfaceName                   = "n3"
	N6InterfaceBridgeName             = "n6-br"
	N6NetworkAttachmentDefinitionName = "core-n6"
	N6InterfaceName                   = "n6"
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

func createAdditionalInterfaces(hookContext *goops.HookContext, k8s *K8s) error {
	configGetOpts := &commands.ConfigGetOptions{
		Key: "n2-ip",
	}

	n2IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		return fmt.Errorf("could not get n2-ip config: %w", err)
	}

	createN2NADOpts := &CreateNADOptions{
		Name: N2NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						n2IPAddress,
					},
				},
			},
			Capabilities: Capabilities{
				Mac: true,
			},
			Type:   "bridge",
			Bridge: N2InterfaceBridgeName,
		},
	}

	err = k8s.createNad(createN2NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n2 nad: %w", err)
	}

	configGetOpts = &commands.ConfigGetOptions{
		Key: "n3-ip",
	}

	n3IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		return fmt.Errorf("could not get n3-ip config: %w", err)
	}

	createN3NADOpts := &CreateNADOptions{
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

	err = k8s.createNad(createN3NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n3 nad: %w", err)
	}

	configGetOpts = &commands.ConfigGetOptions{
		Key: "n6-ip",
	}

	n6IPAddress, err := hookContext.Commands.ConfigGetString(configGetOpts)
	if err != nil {
		return fmt.Errorf("could not get n3-ip config: %w", err)
	}

	createN6NADOpts := &CreateNADOptions{
		Name: N6NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						n6IPAddress,
					},
				},
			},
			Capabilities: Capabilities{
				Mac: true,
			},
			Type:   "bridge",
			Bridge: N6InterfaceBridgeName,
		},
	}

	err = k8s.createNad(createN6NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n6 nad: %w", err)
	}

	patchStatefulSetOpts := &PatchStatefulSetOptions{
		Name:          getAppName(hookContext),
		ContainerName: ContainerName,
		PodName:       getPodName(hookContext),
		CapNetAdmin:   true,
		Privileged:    true,
		NetworkAnnotations: []*NetworkAnnotation{
			{
				Name:      N2NetworkAttachmentDefinitionName,
				Interface: N2InterfaceName,
			},
			{
				Name:      N3NetworkAttachmentDefinitionName,
				Interface: N3InterfaceName,
			},
			{
				Name:      N6NetworkAttachmentDefinitionName,
				Interface: N6InterfaceName,
			},
		},
	}

	err = k8s.patchStatefulSet(patchStatefulSetOpts)
	if err != nil {
		return fmt.Errorf("could not patch statefulset: %w", err)
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

	err = createAdditionalInterfaces(hookContext, k8s)
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not create additional interfaces:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Additional interfaces created")

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
