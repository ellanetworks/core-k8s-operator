# Ella Core Operator (K8s)

[Ella Core](https://github.com/ellanetworks/core) is a 5G mobile core network designed for private deployments. It consolidates the complexity of traditional 5G networks into a single application, offering simplicity, reliability, and security.

The Ella Core operator for Kubernetes is a Juju charm allowing for day-1 and day-2 operations of Ella Core on Kubernetes.

## Getting Started

Install Canonical K8s and Multus

```bash
sudo snap install k8s --classic --channel=1.32-classic/stable
sudo k8s bootstrap
sudo k8s kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset-thick.yml
```

Install Juju and bootstrap a Juju controller

```bash
sudo snap install juju --channel=3/stable
juju add-k8s k8s-localhost
juju bootstrap k8s-localhost
```

Create a Juju model

```bash
juju add-model dev
```

Deploy Ella Core

```bash
juju deploy ella-core-k8s --trust --channel=edge
```
