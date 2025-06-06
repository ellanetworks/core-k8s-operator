package charm

import (
	"crypto/rand"
	"fmt"
	"strings"

	pebbleClient "github.com/canonical/pebble/client"
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

func setPorts() error {
	err := goops.SetPorts([]*goops.Port{
		{
			Port:     APIPort,
			Protocol: "tcp",
		},
	})
	if err != nil {
		return fmt.Errorf("could not set ports: %w", err)
	}

	return nil
}

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

func createAdminAccount() error {
	coreClientConfig := &coreClient.Config{
		BaseURL: "http://127.0.0.1:" + fmt.Sprint(APIPort),
	}

	client, err := coreClient.New(coreClientConfig)
	if err != nil {
		return fmt.Errorf("could not create core client: %w", err)
	}

	status, err := client.GetStatus()
	if err != nil {
		return fmt.Errorf("could not get status: %w", err)
	}

	if status.Initialized {
		return nil
	}

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

	createUserOpts := &coreClient.CreateUserOptions{
		Email:    CharmUserEmail,
		Password: password,
		Role:     "admin",
	}

	err = client.CreateUser(createUserOpts)
	if err != nil {
		return fmt.Errorf("could not create user: %w", err)
	}

	return nil
}

func HandleDefaultHook() {
	isLeader, err := goops.IsLeader()
	if err != nil {
		goops.LogErrorf("Could not check if unit is leader: %v", err)
		return
	}

	if !isLeader {
		goops.LogWarningf("Unit is not leader")
		return
	}

	err = setPorts()
	if err != nil {
		goops.LogErrorf("Could not set ports: %v", err)
		return
	}

	goops.LogInfof("Ports set")

	env := goops.ReadEnv()

	k8s, err := NewK8s(env.ModelName)
	if err != nil {
		goops.LogErrorf("Could not create k8s client: %v", err)
		return
	}

	n2IPAddress, err := goops.GetConfigString("n2-ip")
	if err != nil {
		goops.LogErrorf("Could not get n2-ip config: %v", err)
		return
	}

	n3IPAddress, err := goops.GetConfigString("n3-ip")
	if err != nil {
		goops.LogErrorf("Could not get n3-ip config: %v", err)
		return
	}

	n6IPAddress, err := goops.GetConfigString("n6-ip")
	if err != nil {
		goops.LogErrorf("Could not get n6-ip config: %v", err)
		return
	}

	appName := getAppName()
	patchK8sResourcesOpts := &PatchK8sResourcesOptions{
		N2IPAddress:     n2IPAddress,
		N3IPAddress:     n3IPAddress,
		N6IPAddress:     n6IPAddress,
		StatefulsetName: appName,
		ContainerName:   ContainerName,
		AppName:         appName,
		UnitName:        env.UnitName,
		PodName:         getPodName(),
		N2ServiceName:   fmt.Sprintf("%s-external", appName),
	}

	err = k8s.patchK8sResources(patchK8sResourcesOpts)
	if err != nil {
		goops.LogErrorf("Could not patch k8s resources: %v", err)
		return
	}

	goops.LogInfof("K8s resources patched")

	pebble, err := pebbleClient.New(&pebbleClient.Config{Socket: socketPath})
	if err != nil {
		goops.LogErrorf("Could not connect to pebble: %v", err)
		return
	}

	expectedConfig, err := getExpectedConfig()
	if err != nil {
		goops.LogErrorf("Could not get expected config: %v", err)
		return
	}

	err = pushConfigFile(pebble, expectedConfig, ConfigPath)
	if err != nil {
		goops.LogErrorf("Could not push config file: %v", err)
		return
	}

	goops.LogInfof("Config file pushed")

	err = addPebbleLayer(pebble)
	if err != nil {
		goops.LogErrorf("Could not add pebble layer: %v", err)
		return
	}

	goops.LogInfof("Pebble layer added")

	err = startPebbleService(pebble)
	if err != nil {
		goops.LogErrorf("Could not start pebble service: %v", err)
		return
	}

	goops.LogInfof("Pebble service started")

	err = createAdminAccount()
	if err != nil {
		goops.LogErrorf("Could not create admin account: %v", err)
		return
	}

	goops.LogInfof("Admin account created")
}

func SetStatus() {
	status := goops.StatusActive

	message := ""

	err := goops.SetUnitStatus(status, message)
	if err != nil {
		goops.LogErrorf("Could not set status: %v", err)
		return
	}

	goops.LogInfof("Status set to %s", status)
}
