package charm

import (
	"context"
	"encoding/json"
	"fmt"

	netattachv1 "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/apis/k8s.cni.cncf.io/v1"
	netattachclient "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/client/clientset/versioned"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
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

type PatchStatefulSetOptions struct {
	Name               string
	ContainerName      string
	PodName            string
	CapNetAdmin        bool
	Privileged         bool
	NetworkAnnotations []*NetworkAnnotation
}

type K8s struct {
	Namespace       string
	NetAttachClient *netattachclient.Clientset
	Client          *kubernetes.Clientset
}

func NewK8s(namespace string) (*K8s, error) {
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

	return &K8s{
		Namespace:       namespace,
		NetAttachClient: netAttachClient,
		Client:          client,
	}, nil
}

// createNad creates the NetworkAttachmentDefinition in the specified namespace.
// If the NAD already exists, it does not attempt to create it again.
func (k *K8s) createNad(opts *CreateNADOptions) error {
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

// Patch a statefulset with Multus annotation and NET_ADMIN capability
// patchStatefulSet patches a statefulset to update the Multus network annotations
// and to add NET_ADMIN capability to a container's security context if required.
func (k *K8s) patchStatefulSet(opts *PatchStatefulSetOptions) error {
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
