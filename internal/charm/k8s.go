package charm

import (
	"context"
	"encoding/json"
	"fmt"

	netattachv1 "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/apis/k8s.cni.cncf.io/v1"
	netattachclient "github.com/k8snetworkplumbingwg/network-attachment-definition-client/pkg/client/clientset/versioned"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
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

type K8s struct {
	Namespace string
	Client    *netattachclient.Clientset
}

func NewK8s(namespace string) (*K8s, error) {
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, fmt.Errorf("error getting in-cluster config: %w", err)
	}

	client, err := netattachclient.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("error creating network attachment definition client: %w", err)
	}

	return &K8s{
		Namespace: namespace,
		Client:    client,
	}, nil
}

// createNad creates the NetworkAttachmentDefinition in the specified namespace.
// If the NAD already exists, it does not attempt to create it again.
func (k *K8s) createNad(opts *CreateNADOptions) error {
	// Check if the NAD already exists.
	_, err := k.Client.
		K8sCniCncfIoV1().
		NetworkAttachmentDefinitions(k.Namespace).
		Get(context.TODO(), opts.Name, metav1.GetOptions{})
	if err == nil {
		// The NAD exists already.
		fmt.Printf("NetworkAttachmentDefinition %q already exists in namespace %q.\n", opts.Name, k.Namespace)
		return nil
	}
	// If the error is not a NotFound error, return the error.
	if !apierrors.IsNotFound(err) {
		return fmt.Errorf("error checking for existing NetworkAttachmentDefinition: %w", err)
	}

	// Marshal the NAD configuration.
	nadConfig, err := json.Marshal(opts.NAD)
	if err != nil {
		return fmt.Errorf("error marshalling NetworkAttachmentDefinition: %w", err)
	}

	// Define the new NAD object.
	newNad := &netattachv1.NetworkAttachmentDefinition{
		ObjectMeta: metav1.ObjectMeta{
			Name:      opts.Name,
			Namespace: k.Namespace,
		},
		Spec: netattachv1.NetworkAttachmentDefinitionSpec{
			Config: string(nadConfig),
		},
	}

	// Create the NAD using the clientset.
	_, err = k.Client.
		K8sCniCncfIoV1().
		NetworkAttachmentDefinitions(k.Namespace).
		Create(context.TODO(), newNad, metav1.CreateOptions{})
	if err != nil {
		return fmt.Errorf("error creating NetworkAttachmentDefinition: %w", err)
	}

	fmt.Printf("Successfully created NetworkAttachmentDefinition %q in namespace %q.\n", opts.Name, k.Namespace)
	return nil
}
