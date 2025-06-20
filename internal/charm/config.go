package charm

import (
	"fmt"

	"gopkg.in/yaml.v3"
)

type SystemLoggingConfig struct {
	Level  string `yaml:"level"`
	Output string `yaml:"output"`
}

type AuditLoggingConfig struct {
	Output string `yaml:"output"`
	Path   string `yaml:"path,omitempty"`
}

type LoggingConfig struct {
	System SystemLoggingConfig `yaml:"system"`
	Audit  AuditLoggingConfig  `yaml:"audit"`
}

type DBConfig struct {
	Path string `yaml:"path"`
}

type InterfaceConfig struct {
	Name string `yaml:"name"`
	Port int    `yaml:"port,omitempty"`
}

type InterfacesConfig struct {
	N2  InterfaceConfig `yaml:"n2"`
	N3  InterfaceConfig `yaml:"n3"`
	N6  InterfaceConfig `yaml:"n6"`
	API InterfaceConfig `yaml:"api"`
}

type XDPConfig struct {
	AttachMode string `yaml:"attach-mode"`
}

type CoreConfig struct {
	Logging    LoggingConfig    `yaml:"logging"`
	DB         DBConfig         `yaml:"db"`
	Interfaces InterfacesConfig `yaml:"interfaces"`
	XDPConfig  XDPConfig        `yaml:"xdp"`
}

type ServiceConfig struct {
	Override string `yaml:"override"`
	Summary  string `yaml:"summary"`
	Command  string `yaml:"command"`
	Startup  string `yaml:"startup"`
}

func getExpectedConfig(config *ConfigOptions) ([]byte, error) {
	coreConfig := CoreConfig{
		Logging: LoggingConfig{
			System: SystemLoggingConfig{
				Level:  config.LoggingLevel,
				Output: "stdout",
			},
			Audit: AuditLoggingConfig{
				Output: "stdout",
			},
		},
		DB: DBConfig{
			Path: DBPath,
		},
		Interfaces: InterfacesConfig{
			N2: InterfaceConfig{
				Name: "n2",
				Port: N2Port,
			},
			N3: InterfaceConfig{
				Name: "n3",
			},
			N6: InterfaceConfig{
				Name: "n6",
			},
			API: InterfaceConfig{
				Name: "lo",
				Port: APIPort,
			},
		},
		XDPConfig: XDPConfig{
			AttachMode: "generic",
		},
	}

	b, err := yaml.Marshal(coreConfig)
	if err != nil {
		return nil, fmt.Errorf("could not marshal config to YAML: %w", err)
	}

	return b, nil
}
