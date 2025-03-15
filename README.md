# Ella Core Operator (K8s)

[Ella Core](https://github.com/ellanetworks/core) is a 5G mobile core network designed for private deployments. It consolidates the complexity of traditional 5G networks into a single application, offering simplicity, reliability, and security.

The Ella Core operator for Kubernetes is a Juju charm allowing lifecycle operations of Ella Core on Kubernetes.

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
juju deploy ella-core-k8s ella-core --channel=edge --trust
```

Wait for the application to be running. You can check the status with `juju status`.

```bash
guillaume@courge:~/code/core-k8s-operator$ juju status
Model  Controller     Cloud/Region   Version  SLA          Timestamp
dev1   k8s-localhost  k8s-localhost  3.6.4    unsupported  11:13:32-04:00

App            Version  Status  Scale  Charm          Channel  Rev  Address         Exposed  Message
ella-core-k8s           active      1  ella-core-k8s             0  10.152.183.149  no       

Unit              Workload  Agent  Address     Ports  Message
ella-core-k8s/0*  active    idle   10.1.0.117 
```

Fetch the username and password to access the Ella Core UI

```bash
juju show-secret ELLA_CORE_LOGIN --reveal
```

Deploy the gNodeB simulator and a router, and integrate the gNodeB simulator with Ella Core:

```bash
juju deploy sdcore-router-k8s router --channel=1.5/stable --trust
juju deploy sdcore-gnbsim-k8s gnbsim --channel=1.6/edge --trust
juju integrate ella-core:fiveg-n2 gnbsim:fiveg-n2
juju integrate ella-core:fiveg_core_gnb gnbsim:fiveg_core_gnb
```

Wait for the application to be running. You can check the status with `juju status`.
