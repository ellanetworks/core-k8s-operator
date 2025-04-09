package charm

import (
	"fmt"
	"strings"

	"github.com/canonical/pebble/client"
	"github.com/gruyaume/goops"
	"github.com/gruyaume/goops/commands"
	"gopkg.in/yaml.v3"
)

const (
	KeyPath    = "/etc/core/config/key.pem"
	CertPath   = "/etc/core/config/cert.pem"
	DBPath     = "/var/lib/core/database/core.db"
	ConfigPath = "/etc/core/config/core.yaml"
	Port       = 2111
)

type CoreConfig struct {
	KeyPath  string `yaml:"key_path"`
	CertPath string `yaml:"cert_path"`
	DBPath   string `yaml:"db_path"`
	Port     int    `yaml:"port"`
}

func pushConfigFile(containerName string, path string) error {
	socketPath := "/charm/containers/" + containerName + "/pebble.socket"

	pebble, err := client.New(&client.Config{Socket: socketPath})
	if err != nil {
		return fmt.Errorf("could not create pebble client: %w", err)
	}

	_, err = pebble.SysInfo()
	if err != nil {
		return fmt.Errorf("could not connect to pebble: %w", err)
	}

	coreConfig := CoreConfig{
		KeyPath:  KeyPath,
		CertPath: CertPath,
		DBPath:   DBPath,
		Port:     2111,
	}

	d, err := yaml.Marshal(coreConfig)
	if err != nil {
		return fmt.Errorf("could not marshal config to YAML: %w", err)
	}

	source := strings.NewReader(string(d))
	pushOptions := &client.PushOptions{
		Source: source,
		Path:   path,
	}

	err = pebble.Push(pushOptions)
	if err != nil {
		return fmt.Errorf("could not push config file: %w", err)
	}

	return nil
}

func setPorts(hookContext *goops.HookContext) error {
	setPortOpts := &commands.SetPortsOptions{
		Ports: []*commands.Port{
			{
				Port:     Port,
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

	err = pushConfigFile("core", "/etc/core/config/core.yaml")
	if err != nil {
		hookContext.Commands.JujuLog(commands.Error, "Could not push config file:", err.Error())
		return
	}

	hookContext.Commands.JujuLog(commands.Info, "Config file pushed")
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
