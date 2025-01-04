# Ella K8s Operator

## Getting Started

### Install Kubernetes

Install MicroK8s

```bash
sudo snap install microk8s --channel=1.32-strict/stable
```

Add the community repository MicroK8s addon:
```shell
sudo microk8s addons repo add community https://github.com/canonical/microk8s-community-addons --reference feat/strict-fix-multus
```

Enable the following MicroK8s addons.

```shell
sudo microk8s enable hostpath-storage
sudo microk8s enable multus
```

### Install Juju

Install Juju
```shell
sudo snap install juju --channel=3.6/stable
```

Bootstrap a Juju controller
```shell
juju bootstrap microk8s
```

Create a Juju model
```shell
juju add-model demo
```

### Deploy Ella Core K8s

Deploy Ella K8s
```shell
juju deploy ella-core-k8s --trust --channel=edge
```

Deploy the 5G gNodeB simulator
```bash
juju deploy sdcore-router-k8s --trust --channel=1.5/edge
juju deploy sdcore-gnbsim-k8s --trust --channel=1.5/edge
juju integrate ella-k8s:fiveg_gnb_identity sdcore-gnbsim-k8s:fiveg_gnb_identity
juju integrate sdcore-gnbsim-k8s:fiveg-n2 ella-k8s:fiveg-n2
```

Retrieve the Ella Application address

```bash
guillaume@thinkpad:~/code/ella-k8s-operator$ juju status
Model  Controller          Cloud/Region        Version  SLA          Timestamp
dev    microk8s-localhost  microk8s/localhost  3.5.1    unsupported  21:00:50-04:00

App                Version  Status  Scale  Charm              Channel      Rev  Address         Exposed  Message
ella-k8s                    active      1  ella-k8s           latest/edge   21  10.152.183.124  no       
sdcore-gnbsim-k8s  1.4.3    active      1  sdcore-gnbsim-k8s  1.5/edge     437  10.152.183.57   no       

Unit                  Workload  Agent  Address      Ports  Message
ella-k8s/0*           active    idle   10.1.19.156         
sdcore-gnbsim-k8s/0*  active    idle   10.1.19.129  
```

Navigate to Ella's Application address in your browser `http://10.152.183.124:5000`

Creare a Network Slice

Click on the `Network Slices` tab and click on the `Create` button. Create a network slice with the following parameters:
- Name: `default`
- MCC: `001`
- MNC: `01`
- gNodeB: `dev-gnbsim-sdcore-gnbsim-k8s (tac: 1)`

Create a Subscriber

Click on the `Subscribers` tab and click on the `Create` button. Create a subscriber with the following parameters:
- IMSI: `001010100007487`
- OPC: `981d464c7c52eb6e5036234984ad0bcf`
- Key: `5122250214c33e723a5dd523fc145fc0`
- Sequence Number: `16f3b3f70fc2`
- Network Slice: `default`
- Device Group: `default-default`

Run the 5G Simulation:

```bash
juju run sdcore-gnbsim-k8s/0 start-simulation
```

## How-to Guides

### Integrate with COS

Create a model for observability:

```bash
juju add-model cos
```

Deploy cos lite and wait for all applications to be in active status:

```bash
juju deploy cos-lite --trust
```

Create offers for integrating with COS:

```bash
juju offer cos.prometheus:receive-remote-write
juju offer cos.loki:logging
juju offer cos.grafana:grafana-dashboard
```

Switch to the model in which Ella is deployed:

```bash
juju switch <ella model>
```

Deploy Grafana Agent:
```bash
juju deploy grafana-agent-k8s
```

Integrate Ella K8s with Grafana Agent:

```bash
juju integrate grafana-agent-k8s ella-k8s:metrics-endpoint
```

Consume the COS offers:

```bash
juju consume cos.prometheus
juju consume cos.loki
juju consume cos.grafana
```

Integrate Grafana Agent with COS:

```bash
juju integrate prometheus:receive-remote-write grafana-agent-k8s:send-remote-write
juju integrate loki:logging grafana-agent-k8s:logging-consumer
juju integrate grafana:grafana-dashboard grafana-agent-k8s:grafana-dashboards-provider
```

Switch to the cos model:

```bash
juju switch cos
```

Retrieve the Grafana admin password:

```bash
juju run grafana/leader get-admin-password
```

Log in Grafana, and search for Ella related metrics.
