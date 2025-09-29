package charm

import (
	"context"
	"crypto/rand"
	"fmt"
	"net"
	"os"
	"strings"

	"github.com/ellanetworks/core-k8s/internal/k8s"
	coreClient "github.com/ellanetworks/core/client"
	"github.com/gruyaume/goops"
)

const (
	ContainerName        = "core"
	DBPath               = "/var/lib/core/core.db"
	ConfigPath           = "/etc/core/core.yaml"
	APIPort              = 2111
	N2Port               = 38412
	CharmUserEmail       = "charm@ellanetworks.com"
	CoreLoginSecretLabel = "ELLA_CORE_LOGIN"
)

func getAppName() string {
	env := goops.ReadEnv()

	parts := strings.Split(env.UnitName, "/")
	appName := parts[0]

	return appName
}

func getPodName() string {
	env := goops.ReadEnv()

	parts := strings.Split(env.UnitName, "/")
	podName := strings.Join(parts, "-")

	return podName
}

func generateRandomPassword() (string, error) {
	const passwordLength = 16

	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

	b := make([]byte, passwordLength)

	_, err := rand.Read(b)
	if err != nil {
		return "", err
	}

	for i := range b {
		b[i] = charset[b[i]%byte(len(charset))]
	}

	return string(b), nil
}

func createAdminAccount(ctx context.Context, core *coreClient.Client) error {
	password, err := generateRandomPassword()
	if err != nil {
		return fmt.Errorf("could not generate random password: %w", err)
	}

	_, err = goops.AddSecret(&goops.AddSecretOptions{
		Label: CoreLoginSecretLabel,
		Content: map[string]string{
			"password": password,
			"email":    CharmUserEmail,
		},
	})
	if err != nil {
		return fmt.Errorf("could not add secret: %w", err)
	}

	err = core.CreateUser(ctx, &coreClient.CreateUserOptions{
		Email:    CharmUserEmail,
		Password: password,
		RoleID:   coreClient.RoleAdmin,
	})
	if err != nil {
		return fmt.Errorf("could not create user: %w", err)
	}

	return nil
}

type ConfigOptions struct {
	LoggingLevel string `json:"logging-level"`
	N2IPAddress  string `json:"n2-ip"`
	N3IPAddress  string `json:"n3-ip"`
	N6IPAddress  string `json:"n6-ip"`
}

func (c *ConfigOptions) Validate() error {
	if c.LoggingLevel == "" {
		return fmt.Errorf("logging-level is required")
	}

	if c.N2IPAddress == "" {
		return fmt.Errorf("n2-ip is required")
	}

	if c.N3IPAddress == "" {
		return fmt.Errorf("n3-ip is required")
	}

	if c.N6IPAddress == "" {
		return fmt.Errorf("n6-ip is required")
	}

	return nil
}

func getFQDN() (string, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return "", err
	}

	addrs, err := net.LookupHost(hostname)
	if err != nil || len(addrs) == 0 {
		return hostname, nil
	}

	names, err := net.LookupAddr(addrs[0])
	if err != nil || len(names) == 0 {
		return hostname, nil
	}

	return names[0], nil
}

func Configure(ctx context.Context, k8sClient k8s.Client) error {
	isLeader, err := goops.IsLeader()
	if err != nil {
		return fmt.Errorf("could not check if unit is leader: %w", err)
	}

	if !isLeader {
		_ = goops.SetUnitStatus(goops.StatusBlocked, "Unit is not leader")
		return nil
	}

	err = goops.SetPorts([]*goops.Port{
		{
			Port:     APIPort,
			Protocol: "tcp",
		},
	})
	if err != nil {
		return fmt.Errorf("could not set ports: %w", err)
	}

	goops.LogInfof("Ports set")

	configOpts := ConfigOptions{}

	err = goops.GetConfig(&configOpts)
	if err != nil {
		return fmt.Errorf("could not get config: %w", err)
	}

	err = configOpts.Validate()
	if err != nil {
		_ = goops.SetUnitStatus(goops.StatusBlocked, "Invalid config: "+err.Error())
		return nil
	}

	appName := getAppName()

	env := goops.ReadEnv()

	err = k8sClient.PatchResources(&k8s.PatchResourcesOptions{
		N2IPAddress:     configOpts.N2IPAddress,
		N3IPAddress:     configOpts.N3IPAddress,
		N6IPAddress:     configOpts.N6IPAddress,
		StatefulsetName: appName,
		ContainerName:   ContainerName,
		AppName:         appName,
		UnitName:        env.UnitName,
		PodName:         getPodName(),
		N2ServiceName:   fmt.Sprintf("%s-external", appName),
		N2Port:          N2Port,
	})
	if err != nil {
		return fmt.Errorf("could not patch k8s resources: %w", err)
	}

	goops.LogInfof("K8s resources patched")

	pebble := goops.Pebble("core")

	_, err = pebble.SysInfo()
	if err != nil {
		_ = goops.SetUnitStatus(goops.StatusWaiting, "Waiting for pebble to be ready")
		return nil
	}

	expectedConfig, err := getExpectedConfig(&configOpts)
	if err != nil {
		return fmt.Errorf("could not get expected config: %w", err)
	}

	err = pushConfigFile(pebble, expectedConfig, ConfigPath)
	if err != nil {
		return fmt.Errorf("could not push config file: %w", err)
	}

	goops.LogInfof("Config file pushed")

	err = addPebbleLayer(pebble)
	if err != nil {
		return fmt.Errorf("could not add pebble layer: %w", err)
	}

	goops.LogInfof("Pebble layer added")

	err = startPebbleService(pebble)
	if err != nil {
		return fmt.Errorf("could not start pebble service: %w", err)
	}

	goops.LogInfof("Pebble service started")

	fqdn, err := getFQDN()
	if err != nil {
		return fmt.Errorf("failed to resolve FQDN: %w", err)
	}

	fqdn = strings.TrimSuffix(fqdn, ".")

	coreClient, err := coreClient.New(&coreClient.Config{
		BaseURL: fmt.Sprintf("http://%s:%d", fqdn, APIPort),
	})
	if err != nil {
		return fmt.Errorf("could not create core client: %w", err)
	}

	status, err := coreClient.GetStatus(ctx)
	if err != nil {
		_ = goops.SetUnitStatus(goops.StatusWaiting, "Waiting to be able to access core API")

		goops.LogDebugf("Could not get core status: %v", err)

		return nil
	}

	if !status.Initialized {
		goops.LogInfof("Core is not initialized, initializing now")

		err = createAdminAccount(ctx, coreClient)
		if err != nil {
			return fmt.Errorf("could not create admin account: %w", err)
		}

		goops.LogInfof("Admin account created")
	}

	_ = goops.SetUnitStatus(goops.StatusActive, "Charm is ready")

	return nil
}
