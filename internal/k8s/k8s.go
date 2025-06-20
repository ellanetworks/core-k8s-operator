package k8s

import (
	"context"
	"encoding/json"
	"fmt"

	netattachv1 "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/apis/k8s.cni.cncf.io/v1"
	netattachclient "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/client/clientset/versioned"
	v1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

const (
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

type Address struct {
	Address string `json:"address"`
}

type IPAM struct {
	Type      string    `json:"type"`
	Addresses []Address `json:"addresses"`
}

type Capabilities struct {
	Mac bool `json:"mac"`
}

type NetworkAttachmentDefinition struct {
	CNIVersion   string       `json:"cniVersion"`
	IPAM         IPAM         `json:"ipam"`
	Type         string       `json:"type"`
	Bridge       string       `json:"bridge"`
	Capabilities Capabilities `json:"capabilities"`
}

type CreateNADOptions struct {
	Name string
	NAD  *NetworkAttachmentDefinition
}

type NetworkAnnotation struct {
	Name      string `json:"name"`
	Interface string `json:"interface"`
}

// RealK8s implements the K8sProvider interface using a real Kubernetes client.
type RealK8s struct {
	Namespace       string
	NetAttachClient *netattachclient.Clientset
	Client          *kubernetes.Clientset
}

// K8sProvider defines the interface for Kubernetes operations.
type Client interface {
	PatchResources(opts *PatchResourcesOptions) error
}

// New creates a new instance of RealK8s using in-cluster configuration.
func New(namespace string) (Client, error) {
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, fmt.Errorf("error getting in-cluster config: %w", err)
	}

	netAttachClient, err := netattachclient.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("error creating network attachment definition client: %w", err)
	}

	client, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("error creating Kubernetes client: %w", err)
	}

	return RealK8s{
		Namespace:       namespace,
		NetAttachClient: netAttachClient,
		Client:          client,
	}, nil
}

// createNad creates the NetworkAttachmentDefinition in the specified namespace.
// If the NAD already exists, it does not attempt to create it again.
func (k RealK8s) createNad(opts *CreateNADOptions) error {
	_, err := k.NetAttachClient.
		K8sCniCncfIoV1().
		NetworkAttachmentDefinitions(k.Namespace).
		Get(context.TODO(), opts.Name, metav1.GetOptions{})
	if err == nil {
		fmt.Printf("NetworkAttachmentDefinition %q already exists in namespace %q.\n", opts.Name, k.Namespace)
		return nil
	}

	if !apierrors.IsNotFound(err) {
		return fmt.Errorf("error checking for existing NetworkAttachmentDefinition: %w", err)
	}

	nadConfig, err := json.Marshal(opts.NAD)
	if err != nil {
		return fmt.Errorf("error marshalling NetworkAttachmentDefinition: %w", err)
	}

	newNad := &netattachv1.NetworkAttachmentDefinition{
		ObjectMeta: metav1.ObjectMeta{
			Name:      opts.Name,
			Namespace: k.Namespace,
		},
		Spec: netattachv1.NetworkAttachmentDefinitionSpec{
			Config: string(nadConfig),
		},
	}

	_, err = k.NetAttachClient.
		K8sCniCncfIoV1().
		NetworkAttachmentDefinitions(k.Namespace).
		Create(context.TODO(), newNad, metav1.CreateOptions{})
	if err != nil {
		return fmt.Errorf("error creating NetworkAttachmentDefinition: %w", err)
	}

	return nil
}

type PatchStatefulSetOptions struct {
	Name               string
	ContainerName      string
	PodName            string
	CapNetAdmin        bool
	Privileged         bool
	NetworkAnnotations []*NetworkAnnotation
}

// Patch a statefulset with Multus annotation and NET_ADMIN capability
// patchStatefulSetNetwork patches a statefulset to update the Multus network annotations
// and to add NET_ADMIN capability to a container's security context if required.
func (k RealK8s) patchStatefulSetNetwork(opts *PatchStatefulSetOptions) error {
	// Marshal the network annotations into a JSON string.
	annotationsBytes, err := json.Marshal(opts.NetworkAnnotations)
	if err != nil {
		return fmt.Errorf("error marshalling network annotations: %w", err)
	}

	const NetworkAnnotationResourceKey = "k8s.v1.cni.cncf.io/networks"

	// Build the patch document.
	// We always patch the pod template metadata annotations.
	patchMap := map[string]interface{}{
		"spec": map[string]interface{}{
			"template": map[string]interface{}{
				"metadata": map[string]interface{}{
					"annotations": map[string]interface{}{
						NetworkAnnotationResourceKey: string(annotationsBytes),
					},
				},
			},
		},
	}

	// If NET_ADMIN capability is required, add a patch to update the container's securityContext.
	if opts.CapNetAdmin {
		// Build the container patch which targets the container with the given name.
		containerPatch := map[string]interface{}{
			"name": opts.ContainerName,
			"securityContext": map[string]interface{}{
				"capabilities": map[string]interface{}{
					"add": []string{"NET_ADMIN"},
				},
			},
		}
		// Add the container patch under spec.template.spec.
		patchMap["spec"].(map[string]interface{})["template"].(map[string]interface{})["spec"] = map[string]interface{}{
			"containers": []interface{}{containerPatch},
		}
	}

	// If privileged is required, add a patch to update the container's securityContext.
	if opts.Privileged {
		// Build the container patch which targets the container with the given name.
		containerPatch := map[string]interface{}{
			"name": opts.ContainerName,
			"securityContext": map[string]interface{}{
				"privileged": true,
			},
		}
		// Add the container patch under spec.template.spec.
		patchMap["spec"].(map[string]interface{})["template"].(map[string]interface{})["spec"] = map[string]interface{}{
			"containers": []interface{}{containerPatch},
		}
	}

	// Marshal the patch document to JSON.
	patchBytes, err := json.Marshal(patchMap)
	if err != nil {
		return fmt.Errorf("error marshalling patch: %w", err)
	}

	// Patch the statefulset using a strategic merge patch.
	_, err = k.Client.AppsV1().StatefulSets(k.Namespace).Patch(
		context.TODO(),
		opts.Name,
		types.StrategicMergePatchType,
		patchBytes,
		metav1.PatchOptions{
			FieldManager: "charm",
		},
	)
	if err != nil {
		return fmt.Errorf("error patching statefulset %q: %w", opts.Name, err)
	}

	return nil
}

type PatchStatefulSetVolumeOptions struct {
	Name                 string
	ContainerName        string
	PodName              string
	RequestedVolume      v1.Volume
	RequestedVolumeMount v1.VolumeMount
}

// patchStatefulSetWithEbpfVolume retrieves the statefulset by name and patches it by adding the requested eBPF volume and volume mount only if they are not already present.
func (k RealK8s) patchStatefulSetWithEbpfVolume(opts *PatchStatefulSetVolumeOptions) error {
	statefulset, err := k.Client.AppsV1().StatefulSets(k.Namespace).Get(context.TODO(), opts.Name, metav1.GetOptions{})
	if err != nil {
		if apierrors.IsNotFound(err) {
			return fmt.Errorf("statefulset %q not found in namespace %q", opts.Name, k.Namespace)
		}

		return fmt.Errorf("error getting statefulset %q: %w", opts.Name, err)
	}

	var container *v1.Container

	for i := range statefulset.Spec.Template.Spec.Containers {
		if statefulset.Spec.Template.Spec.Containers[i].Name == opts.ContainerName {
			container = &statefulset.Spec.Template.Spec.Containers[i]
			break
		}
	}

	if container == nil {
		return fmt.Errorf("could not find container %q in statefulset %q", opts.ContainerName, opts.Name)
	}

	modified := false

	foundVolumeMount := false

	for _, vm := range container.VolumeMounts {
		if vm.Name == opts.RequestedVolumeMount.Name {
			foundVolumeMount = true
			break
		}
	}

	if !foundVolumeMount {
		container.VolumeMounts = append(container.VolumeMounts, opts.RequestedVolumeMount)
		modified = true
	}

	foundVolume := false

	for _, vol := range statefulset.Spec.Template.Spec.Volumes {
		if vol.Name == opts.RequestedVolume.Name {
			foundVolume = true
			break
		}
	}

	if !foundVolume {
		statefulset.Spec.Template.Spec.Volumes = append(statefulset.Spec.Template.Spec.Volumes, opts.RequestedVolume)
		modified = true
	}

	if !modified {
		return nil
	}

	// Update the StatefulSet with the new volume and volume mount.
	_, err = k.Client.AppsV1().StatefulSets(k.Namespace).Update(context.TODO(), statefulset, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("error replacing StatefulSet %q: %w", opts.Name, err)
	}

	return nil
}

type PatchResourcesOptions struct {
	N2IPAddress     string
	N3IPAddress     string
	N6IPAddress     string
	StatefulsetName string
	AppName         string
	ContainerName   string
	UnitName        string
	PodName         string
	N2ServiceName   string
	N2Port          int32
}

func (k RealK8s) PatchResources(opts *PatchResourcesOptions) error {
	createN2NADOpts := &CreateNADOptions{
		Name: N2NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						opts.N2IPAddress,
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

	err := k.createNad(createN2NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n2 nad: %w", err)
	}

	createN3NADOpts := &CreateNADOptions{
		Name: N3NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						opts.N3IPAddress,
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

	err = k.createNad(createN3NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n3 nad: %w", err)
	}

	createN6NADOpts := &CreateNADOptions{
		Name: N6NetworkAttachmentDefinitionName,
		NAD: &NetworkAttachmentDefinition{
			CNIVersion: "0.3.1",
			IPAM: IPAM{
				Type: "static",
				Addresses: []Address{
					{
						opts.N6IPAddress,
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

	err = k.createNad(createN6NADOpts)
	if err != nil {
		return fmt.Errorf("could not create n6 nad: %w", err)
	}

	patchStatefulSetOpts := &PatchStatefulSetOptions{
		Name:          opts.StatefulsetName,
		ContainerName: opts.ContainerName,
		PodName:       opts.PodName,
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

	err = k.patchStatefulSetNetwork(patchStatefulSetOpts)
	if err != nil {
		return fmt.Errorf("could not patch statefulset: %w", err)
	}

	patchStatefulsetVolOpts := &PatchStatefulSetVolumeOptions{
		Name:          opts.StatefulsetName,
		ContainerName: opts.ContainerName,
		PodName:       opts.PodName,
		RequestedVolume: v1.Volume{
			Name: "ebpf",
			VolumeSource: v1.VolumeSource{
				HostPath: &v1.HostPathVolumeSource{
					Path: "/sys/fs/bpf",
				},
			},
		},
		RequestedVolumeMount: v1.VolumeMount{
			Name:      "ebpf",
			MountPath: "/sys/fs/bpf",
		},
	}

	err = k.patchStatefulSetWithEbpfVolume(patchStatefulsetVolOpts)
	if err != nil {
		return fmt.Errorf("could not patch statefulset with eBPF volume: %w", err)
	}

	createN2ServiceOpts := &CreateN2ServiceOptions{
		Name:    opts.N2ServiceName,
		AppName: opts.AppName,
		N2Port:  opts.N2Port,
	}

	err = k.createN2Service(createN2ServiceOpts)
	if err != nil {
		return fmt.Errorf("could not create n2 service: %w", err)
	}

	return nil
}

type CreateN2ServiceOptions struct {
	Name    string
	AppName string
	N2Port  int32
}

func (k RealK8s) createN2Service(opts *CreateN2ServiceOptions) error {
	_, err := k.Client.CoreV1().Services(k.Namespace).Get(context.TODO(), opts.Name, metav1.GetOptions{})
	if err == nil {
		return nil
	}

	if !apierrors.IsNotFound(err) {
		return fmt.Errorf("error checking for existing Service: %w", err)
	}

	service := &v1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      opts.Name,
			Namespace: k.Namespace,
		},
		Spec: v1.ServiceSpec{
			Selector: map[string]string{
				"app.kubernetes.io/name": opts.AppName,
			},
			Ports: []v1.ServicePort{
				{
					Name:     "ngapp",
					Port:     opts.N2Port,
					Protocol: "SCTP",
				},
			},
			Type: "LoadBalancer",
		},
	}

	_, err = k.Client.CoreV1().Services(k.Namespace).Create(context.TODO(), service, metav1.CreateOptions{})
	if err != nil {
		return fmt.Errorf("error creating Service: %w", err)
	}

	return nil
}
